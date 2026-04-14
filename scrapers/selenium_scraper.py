"""
Selenium Scraper Module - Contournement des blocages anti-bot

Utilise Chrome headless avec rotation d'User-Agent et gestion avancée
des cookies/localStorage pour contourner les protections anti-scraping.
"""

import json
import logging
import time
import random
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    WebDriverException, 
    NoSuchElementException,
    ElementNotInteractableException
)
from webdriver_manager.chrome import ChromeDriverManager

# Import des utilitaires
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.scraper_utils import get_random_user_agent, simulate_human_delay

logger = logging.getLogger(__name__)


class SeleniumScraper:
    """
    Scraper basé sur Selenium avec Chrome headless.
    
    Contourne les protections anti-bot par :
    - Rotation d'User-Agent via Chrome Options
    - Exécution JavaScript pour simuler un vrai navigateur
    - Gestion des cookies et localStorage
    - Screenshots pour debug
    - Timeouts et retry intégrés
    """
    
    def __init__(self, config_path: str = "config/selenium_config.json"):
        """
        Initialise le scraper Selenium.
        
        Args:
            config_path: Chemin vers le fichier de configuration Selenium
        """
        self.config = self._load_config(config_path)
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Configuration
        self.headless = self.config.get('headless', True)
        self.window_size = self.config.get('window_size', '1920,1080')
        self.implicit_wait = self.config.get('implicit_wait', 10)
        self.page_load_timeout = self.config.get('page_load_timeout', 30)
        self.script_timeout = self.config.get('script_timeout', 20)
        
        # Retry configuration
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 2.0)
        
        # Screenshots
        self.screenshot_dir = Path(self.config.get('screenshot_dir', 'logs/screenshots'))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("SeleniumScraper initialized")
    
    def _load_config(self, path: str) -> Dict:
        """Charge la configuration depuis le fichier JSON."""
        default_config = {
            'headless': True,
            'window_size': '1920,1080',
            'implicit_wait': 10,
            'page_load_timeout': 30,
            'script_timeout': 20,
            'max_retries': 3,
            'retry_delay': 2.0,
            'screenshot_dir': 'logs/screenshots',
            'chrome_options': [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',
                '--disable-javascript',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--allow-running-insecure-content'
            ]
        }
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Fusion avec les valeurs par défaut
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except FileNotFoundError:
            logger.warning(f"Config file not found: {path}, using defaults")
            return default_config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}, using defaults")
            return default_config
    
    def _get_chrome_options(self) -> Options:
        """
        Configure les options Chrome avec rotation d'User-Agent.
        
        Returns:
            Options Chrome configurées
        """
        options = Options()
        
        # Mode headless
        if self.headless:
            options.add_argument('--headless=new')
        
        # Taille de fenêtre
        options.add_argument(f'--window-size={self.window_size}')
        
        # User-Agent aléatoire
        user_agent = get_random_user_agent()
        options.add_argument(f'--user-agent={user_agent}')
        logger.debug(f"Using User-Agent: {user_agent[:60]}...")
        
        # Options anti-détection
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Options supplémentaires depuis la config
        for opt in self.config.get('chrome_options', []):
            if opt not in options.arguments:
                options.add_argument(opt)
        
        # Préférences pour réduire la détection
        prefs = {
            'profile.default_content_setting_values': {
                'images': 2,  # Désactiver les images pour accélérer
                'plugins': 2,
                'popups': 2,
                'geolocation': 2,
                'notifications': 2,
                'auto_select_certificate': 2,
                'fullscreen': 2,
                'mouselock': 2,
                'mixed_script': 2,
                'media_stream': 2,
                'media_stream_mic': 2,
                'media_stream_camera': 2,
                'protocol_handlers': 2,
                'ppapi_broker': 2,
                'automatic_downloads': 2,
                'midi_sysex': 2,
                'push_messaging': 2,
                'ssl_cert_decisions': 2,
                'metro_switch_to_desktop': 2,
                'protected_media_identifier': 2,
                'app_banner': 2,
                'site_engagement': 2,
                'durable_storage': 2
            },
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        }
        options.add_experimental_option('prefs', prefs)
        
        return options
    
    def start(self) -> 'SeleniumScraper':
        """
        Démarre le navigateur Chrome.
        
        Returns:
            Instance du scraper (pour chaînage)
        """
        if self.driver is not None:
            logger.warning("Driver already running, restarting...")
            self.quit()
        
        try:
            options = self._get_chrome_options()
            
            # Utiliser webdriver-manager pour gérer chromedriver
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Configuration des timeouts
            self.driver.implicitly_wait(self.implicit_wait)
            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.set_script_timeout(self.script_timeout)
            
            # WebDriverWait pour les attentes explicites
            self.wait = WebDriverWait(self.driver, self.implicit_wait)
            
            # Masquer la détection WebDriver
            self._hide_webdriver()
            
            logger.info("Chrome driver started successfully")
            
        except WebDriverException as e:
            logger.error(f"Failed to start Chrome driver: {e}")
            raise
        
        return self
    
    def _hide_webdriver(self):
        """Masque les signes de détection WebDriver."""
        try:
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'fr']
                });
                window.chrome = { runtime: {} };
            """)
        except Exception as e:
            logger.warning(f"Could not hide webdriver signs: {e}")
    
    def quit(self):
        """Ferme proprement le navigateur."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Chrome driver closed")
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    def __enter__(self):
        """Context manager entry."""
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.quit()
        return False
    
    def navigate(self, url: str, wait_for: Optional[str] = None, 
                 wait_by: By = By.TAG_NAME, timeout: Optional[int] = None) -> bool:
        """
        Navigue vers une URL avec attente optionnelle d'un élément.
        
        Args:
            url: URL à charger
            wait_for: Sélecteur CSS ou XPath de l'élément à attendre
            wait_by: Type de sélecteur (By.CSS_SELECTOR, By.XPATH, etc.)
            timeout: Timeout spécifique (sinon utilise self.implicit_wait)
            
        Returns:
            True si la navigation a réussi
        """
        if not self.driver:
            raise RuntimeError("Driver not started. Call start() first.")
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Navigating to {url} (attempt {attempt + 1}/{self.max_retries})")
                self.driver.get(url)
                
                # Attendre le chargement complet
                if wait_for:
                    wait_time = timeout or self.implicit_wait
                    custom_wait = WebDriverWait(self.driver, wait_time)
                    custom_wait.until(EC.presence_of_element_located((wait_by, wait_for)))
                    logger.debug(f"Element {wait_for} found")
                
                # Délai aléatoire pour simuler un humain
                simulate_human_delay(0.5, 1.5)
                
                return True
                
            except TimeoutException:
                logger.warning(f"Timeout waiting for {wait_for} on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except WebDriverException as e:
                logger.error(f"Navigation error: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        
        return False
    
    def get_page_source(self) -> str:
        """Retourne le source HTML de la page actuelle."""
        if not self.driver:
            raise RuntimeError("Driver not started")
        return self.driver.page_source
    
    def execute_script(self, script: str, *args) -> Any:
        """
        Exécute du JavaScript sur la page.
        
        Args:
            script: Script JavaScript à exécuter
            *args: Arguments à passer au script
            
        Returns:
            Résultat du script
        """
        if not self.driver:
            raise RuntimeError("Driver not started")
        return self.driver.execute_script(script, *args)
    
    def set_local_storage(self, key: str, value: str):
        """Définit une valeur dans le localStorage."""
        self.execute_script(f"localStorage.setItem('{key}', '{value}');")
    
    def get_local_storage(self, key: str) -> Optional[str]:
        """Récupère une valeur du localStorage."""
        result = self.execute_script(f"return localStorage.getItem('{key}');")
        return result
    
    def set_cookie(self, name: str, value: str, domain: Optional[str] = None):
        """Ajoute un cookie."""
        cookie = {'name': name, 'value': value}
        if domain:
            cookie['domain'] = domain
        self.driver.add_cookie(cookie)
    
    def get_cookies(self) -> List[Dict]:
        """Récupère tous les cookies."""
        return self.driver.get_cookies()
    
    def find_element(self, by: By, value: str, timeout: Optional[int] = None):
        """
        Trouve un élément avec attente explicite.
        
        Args:
            by: Type de sélecteur
            value: Valeur du sélecteur
            timeout: Timeout en secondes
            
        Returns:
            Élément WebElement ou None
        """
        if not self.driver:
            raise RuntimeError("Driver not started")
        
        try:
            wait_time = timeout or self.implicit_wait
            custom_wait = WebDriverWait(self.driver, wait_time)
            return custom_wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logger.debug(f"Element not found: {value}")
            return None
    
    def find_elements(self, by: By, value: str) -> List:
        """
        Trouve tous les éléments correspondants.
        
        Args:
            by: Type de sélecteur
            value: Valeur du sélecteur
            
        Returns:
            Liste des éléments
        """
        if not self.driver:
            raise RuntimeError("Driver not started")
        return self.driver.find_elements(by, value)
    
    def click_element(self, by: By, value: str, timeout: Optional[int] = None) -> bool:
        """
        Clique sur un élément.
        
        Args:
            by: Type de sélecteur
            value: Valeur du sélecteur
            timeout: Timeout en secondes
            
        Returns:
            True si le clic a réussi
        """
        try:
            element = self.find_element(by, value, timeout)
            if element:
                # Scroll vers l'élément
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                simulate_human_delay(0.3, 0.7)
                element.click()
                return True
        except (NoSuchElementException, ElementNotInteractableException) as e:
            logger.warning(f"Could not click element {value}: {e}")
        return False
    
    def scroll_to_bottom(self):
        """Scroll jusqu'en bas de la page."""
        self.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        simulate_human_delay(0.5, 1.0)
    
    def scroll_to_top(self):
        """Scroll jusqu'en haut de la page."""
        self.execute_script("window.scrollTo(0, 0);")
        simulate_human_delay(0.3, 0.7)
    
    def take_screenshot(self, name: Optional[str] = None) -> str:
        """
        Prend une capture d'écran pour debug.
        
        Args:
            name: Nom du fichier (sans extension)
            
        Returns:
            Chemin du fichier screenshot
        """
        if not self.driver:
            raise RuntimeError("Driver not started")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name or 'screenshot'}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        self.driver.save_screenshot(str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)
    
    def wait_for_ajax(self, timeout: int = 10) -> bool:
        """
        Attend que les requêtes AJAX soient terminées.
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            True si les requêtes sont terminées
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return jQuery.active == 0") if self.execute_script("return typeof jQuery != 'undefined'") else True
            )
            return True
        except TimeoutException:
            logger.warning("Timeout waiting for AJAX")
            return False
    
    def extract_data_via_js(self, extraction_script: str) -> Any:
        """
        Extrait des données via JavaScript personnalisé.
        
        Args:
            extraction_script: Script JS retournant les données
            
        Returns:
            Données extraites
        """
        return self.execute_script(extraction_script)
    
    def retry_with_selenium(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction avec retry et fallback sur Selenium.
        
        Args:
            func: Fonction à exécuter
            *args, **kwargs: Arguments de la fonction
            
        Returns:
            Résultat de la fonction
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if not self.driver:
                    self.start()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Rotation User-Agent et restart
                    self.quit()
                    time.sleep(self.retry_delay * (attempt + 1))
                    self.start()
        
        raise last_error


class SeleniumScraperPool:
    """Pool de scrapers Selenium pour parallélisation."""
    
    def __init__(self, size: int = 3):
        self.size = size
        self.scrapers: List[SeleniumScraper] = []
        self.active = [False] * size
    
    def initialize(self):
        """Initialise tous les scrapers du pool."""
        for i in range(self.size):
            scraper = SeleniumScraper()
            scraper.start()
            self.scrapers.append(scraper)
            self.active[i] = False
        logger.info(f"Selenium pool initialized with {self.size} scrapers")
    
    def get_available(self) -> Optional[tuple]:
        """Récupère un scraper disponible."""
        for i, is_active in enumerate(self.active):
            if not is_active:
                self.active[i] = True
                return i, self.scrapers[i]
        return None
    
    def release(self, index: int):
        """Libère un scraper."""
        if 0 <= index < len(self.active):
            self.active[index] = False
    
    def close_all(self):
        """Ferme tous les scrapers."""
        for scraper in self.scrapers:
            scraper.quit()
        self.scrapers = []
        self.active = []
        logger.info("Selenium pool closed")