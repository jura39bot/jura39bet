"""
OddsPortal Scraper Module

Récupère les cotes des bookmakers depuis OddsPortal.
Utilise Selenium pour charger les pages et attendre le chargement AJAX des cotes.
"""

import json
import logging
import time
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

# Import des utilitaires anti-détection
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.scraper_utils import (
    get_random_headers,
    simulate_human_delay,
    get_session_cookies
)

# Import Selenium
try:
    from scrapers.selenium_scraper import SeleniumScraper
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("SeleniumScraper not available")

logger = logging.getLogger(__name__)


class OddsPortalScraper:
    """
    Scraper pour récupérer les cotes depuis OddsPortal.
    Utilise Selenium pour contourner les protections anti-bot.
    """
    
    def __init__(self, config_path: str = "config/sources.json", use_selenium: bool = True):
        """
        Initialise le scraper avec la configuration.
        
        Args:
            config_path: Chemin vers le fichier de configuration
            use_selenium: Forcer l'utilisation de Selenium (recommandé pour OddsPortal)
        """
        self.config = self._load_config(config_path)
        self.base_url = self.config['oddsportal']['base_url']
        
        # Configuration retry
        self.retry_config = self.config.get('retry', {})
        self.max_retries = self.retry_config.get('max_retries', 3)
        self.timeout = self.retry_config.get('timeout', 30)
        
        # Selenium
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.selenium_scraper: Optional[SeleniumScraper] = None
        
        # Selectors depuis la config Selenium
        self.selectors = self._load_selectors()
        
        if self.use_selenium:
            logger.info("OddsPortal scraper will use Selenium (recommended)")
        else:
            logger.warning("OddsPortal scraper without Selenium - may encounter 404/anti-bot errors")
    
    def _load_config(self, path: str) -> Dict:
        """Charge la configuration depuis le fichier JSON."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
    
    def _load_selectors(self) -> Dict:
        """Charge les sélecteurs depuis la config Selenium."""
        try:
            selenium_config_path = Path(__file__).parent.parent / "config" / "selenium_config.json"
            with open(selenium_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('oddsportal_selectors', {})
        except (FileNotFoundError, json.JSONDecodeError):
            # Valeurs par défaut
            return {
                'match_row': 'div.eventRow',
                'match_link': 'a[href*="/soccer/"]',
                'home_team': '.table-participant__name span:first-child',
                'away_team': '.table-participant__name span:last-child',
                'odds_1': '[data-testid="odds"]',
                'odds_x': '[data-testid="odds"]',
                'odds_2': '[data-testid="odds"]',
                'match_time': '.table-time'
            }
    
    def _init_selenium(self):
        """Initialise le scraper Selenium si nécessaire."""
        if not self.selenium_scraper and self.use_selenium:
            try:
                self.selenium_scraper = SeleniumScraper()
                self.selenium_scraper.start()
                logger.info("Selenium scraper initialized for OddsPortal")
            except Exception as e:
                logger.error(f"Failed to initialize Selenium: {e}")
                self.use_selenium = False
    
    def _close_selenium(self):
        """Ferme le scraper Selenium."""
        if self.selenium_scraper:
            try:
                self.selenium_scraper.quit()
                logger.info("Selenium scraper closed")
            except Exception as e:
                logger.warning(f"Error closing Selenium: {e}")
            finally:
                self.selenium_scraper = None
    
    def _get_page_with_selenium(self, url: str, wait_for_odds: bool = True) -> Optional[str]:
        """
        Charge une page avec Selenium et attend le chargement AJAX.
        
        Args:
            url: URL à charger
            wait_for_odds: Attendre que les cotes soient chargées
            
        Returns:
            Contenu HTML de la page ou None
        """
        if not self.use_selenium:
            logger.error("Selenium not available")
            return None
        
        try:
            self._init_selenium()
            
            if not self.selenium_scraper:
                logger.error("Selenium scraper not initialized")
                return None
            
            logger.info(f"Selenium loading: {url}")
            
            # Naviguer vers la page
            success = self.selenium_scraper.navigate(
                url=url,
                wait_for="body",
                wait_by=By.TAG_NAME,
                timeout=30
            )
            
            if not success:
                logger.error("Failed to load page with Selenium")
                return None
            
            # Attendre le chargement AJAX des cotes
            if wait_for_odds:
                logger.info("Waiting for AJAX odds to load...")
                time.sleep(3)  # Délai initial pour le chargement
                
                # Attendre que les éléments de cotes soient présents
                try:
                    # Essayer différents sélecteurs pour les cotes
                    odds_selectors = [
                        '[data-testid="odds"]',
                        '.odds-nowrp',
                        '[class*="odds"]',
                        '.eventRow'
                    ]
                    
                    for selector in odds_selectors:
                        try:
                            element = self.selenium_scraper.find_element(
                                By.CSS_SELECTOR, 
                                selector, 
                                timeout=10
                            )
                            if element:
                                logger.debug(f"Odds element found with selector: {selector}")
                                break
                        except:
                            continue
                    
                    # Attendre un peu plus pour le chargement complet
                    time.sleep(2)
                    
                except Exception as e:
                    logger.warning(f"Could not wait for odds: {e}")
            
            # Prendre un screenshot pour debug
            self.selenium_scraper.take_screenshot("oddsportal_page")
            
            # Récupérer le HTML
            html = self.selenium_scraper.get_page_source()
            logger.info(f"Page loaded successfully, HTML size: {len(html)} bytes")
            
            return html
            
        except Exception as e:
            logger.error(f"Selenium error loading page: {e}")
            return None
    
    def _extract_json_data(self, html: str) -> Optional[Dict]:
        """Extrait les données JSON du script dans la page."""
        try:
            # Recherche du script contenant les données
            pattern = r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            # Alternative: chercher d'autres patterns de données
            pattern2 = r'"matches":(\[.*?\])'
            match2 = re.search(pattern2, html, re.DOTALL)
            if match2:
                return {'matches': json.loads(match2.group(1))}
            
            # Pattern pour OddsPortal spécifique
            pattern3 = r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});'
            match3 = re.search(pattern3, html, re.DOTALL)
            if match3:
                return json.loads(match3.group(1))
                
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error extracting JSON data: {e}")
        
        return None
    
    def _parse_match_odds_html(self, match_element) -> Optional[Dict]:
        """
        Parse les cotes d'un élément match avec BeautifulSoup.
        
        Args:
            match_element: Élément BeautifulSoup du match
            
        Returns:
            Données du match avec cotes ou None
        """
        try:
            # Extraction des équipes - essayer plusieurs sélecteurs
            teams_elem = match_element.select_one('.table-participant a, [class*="participant"] a')
            
            if not teams_elem:
                # Essayer de trouver dans les liens directs
                teams_elem = match_element.select_one('a[href*="/soccer/"]')
            
            if not teams_elem:
                return None
            
            teams_text = teams_elem.get_text(strip=True)
            
            # Parser les noms d'équipes
            home_team, away_team = self._parse_team_names(teams_text)
            if not home_team or not away_team:
                return None
            
            # Extraction des cotes - essayer plusieurs sélecteurs
            odds = self._extract_odds_from_element(match_element)
            
            if len(odds) < 3:
                logger.debug(f"Not enough odds found for {home_team} vs {away_team}")
                return None
            
            # Extraire l'heure du match
            time_elem = match_element.select_one('.table-time, [class*="time"]')
            match_time = time_elem.get_text(strip=True) if time_elem else None
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'match_time': match_time,
                'odds_1': odds[0],  # Victoire domicile
                'odds_X': odds[1],  # Match nul
                'odds_2': odds[2],  # Victoire extérieur
                'bookmaker': 'average'  # Cote moyenne
            }
            
        except Exception as e:
            logger.error(f"Error parsing match odds from HTML: {e}")
            return None
    
    def _parse_team_names(self, teams_text: str) -> tuple:
        """
        Parse les noms d'équipes depuis le texte.
        
        Args:
            teams_text: Texte contenant les noms des équipes
            
        Returns:
            Tuple (home_team, away_team) ou (None, None)
        """
        # Essayer différents séparateurs
        separators = [' - ', ' v ', ' vs ', ' – ', ' — ']
        
        for sep in separators:
            if sep in teams_text:
                parts = teams_text.split(sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        
        return None, None
    
    def _extract_odds_from_element(self, element) -> List[float]:
        """
        Extrait les cotes d'un élément HTML.
        
        Args:
            element: Élément BeautifulSoup
            
        Returns:
            Liste des cotes extraites
        """
        odds = []
        
        # Essayer plusieurs sélecteurs pour les cotes
        odds_selectors = [
            '.odds-nowrp',
            '[data-testid="odds"]',
            '[class*="odds"]',
            '.right',
            '.center',
            'td[class*="odds"]',
            'div[class*="odd"]'
        ]
        
        for selector in odds_selectors:
            odds_elements = element.select(selector)
            if odds_elements:
                for elem in odds_elements[:3]:  # 1X2 = 3 cotes max
                    try:
                        odd_text = elem.get_text(strip=True).replace(',', '.')
                        # Filtrer les valeurs qui ne sont pas des nombres
                        if odd_text and self._is_valid_odd(odd_text):
                            odds.append(float(odd_text))
                    except (ValueError, AttributeError):
                        continue
                
                if len(odds) >= 3:
                    break
        
        return odds
    
    def _is_valid_odd(self, text: str) -> bool:
        """Vérifie si le texte est une cote valide."""
        try:
            value = float(text.replace(',', '.'))
            # Les cotes sont généralement entre 1.01 et 100
            return 1.0 <= value <= 200.0
        except ValueError:
            return False
    
    def get_matches_for_league(self, league_key: str, date: Optional[datetime] = None) -> List[Dict]:
        """
        Récupère les matchs et cotes pour une ligue.
        
        Args:
            league_key: Clé de la ligue (premier_league, la_liga, etc.)
            date: Date optionnelle pour filtrer
            
        Returns:
            Liste des matchs avec leurs cotes
        """
        league_info = self.config['oddsportal']['leagues'].get(league_key)
        if not league_info:
            logger.error(f"League {league_key} not found in config")
            return []
        
        # Construire l'URL
        url = urljoin(self.base_url, league_info['path'])
        
        # Si une date est fournie, l'ajouter à l'URL
        if date:
            date_str = date.strftime('%Y-%m-%d')
            url = urljoin(url, date_str + '/')
            logger.info(f"Fetching odds for date {date_str} from {url}")
        else:
            logger.info(f"Fetching odds from: {url}")
        
        # Utiliser Selenium pour charger la page
        html = self._get_page_with_selenium(url, wait_for_odds=True)
        
        if not html:
            logger.error(f"Failed to fetch HTML from {url}")
            return []
        
        matches = []
        
        # Essayer d'extraire les données JSON d'abord
        json_data = self._extract_json_data(html)
        if json_data:
            logger.info("Extracting data from JSON...")
            matches = self._parse_matches_from_json(json_data)
        
        # Si pas de données JSON ou parsing échoué, parser le HTML
        if not matches:
            logger.info("Parsing matches from HTML...")
            matches = self._parse_matches_from_html(html)
        
        logger.info(f"Found {len(matches)} matches with odds for {league_info['name']}")
        
        # Délai aléatoire après chaque ligue
        simulate_human_delay(1.0, 2.0)
        
        return matches
    
    def _parse_matches_from_json(self, json_data: Dict) -> List[Dict]:
        """
        Parse les matchs depuis les données JSON.
        
        Args:
            json_data: Données JSON extraites
            
        Returns:
            Liste des matchs parsés
        """
        matches = []
        
        # Essayer différentes structures JSON
        events = json_data.get('matches', []) or json_data.get('events', [])
        
        for match_data in events:
            try:
                parsed = self._parse_match_from_json(match_data)
                if parsed:
                    matches.append(parsed)
            except Exception as e:
                logger.error(f"Error parsing match from JSON: {e}")
        
        return matches
    
    def _parse_matches_from_html(self, html: str) -> List[Dict]:
        """
        Parse les matchs depuis le HTML.
        
        Args:
            html: Contenu HTML
            
        Returns:
            Liste des matchs parsés
        """
        matches = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Essayer plusieurs sélecteurs pour trouver les lignes de match
            match_selectors = [
                'div.eventRow',
                '[class*="eventRow"]',
                'tr[class*="match"]',
                '[class*="match-row"]',
                '.table-main tr'
            ]
            
            match_rows = []
            for selector in match_selectors:
                match_rows = soup.select(selector)
                if match_rows:
                    logger.debug(f"Found {len(match_rows)} rows with selector: {selector}")
                    break
            
            if not match_rows:
                # Essayer des sélecteurs plus génériques
                match_rows = soup.find_all('tr')
                logger.debug(f"Fallback: found {len(match_rows)} table rows")
            
            for row in match_rows:
                try:
                    parsed = self._parse_match_odds_html(row)
                    if parsed:
                        matches.append(parsed)
                except Exception as e:
                    logger.debug(f"Error parsing match row: {e}")
        
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
        
        return matches
    
    def _parse_match_from_json(self, match_data: Dict) -> Optional[Dict]:
        """
        Parse les données d'un match depuis le JSON.
        
        Args:
            match_data: Données du match
            
        Returns:
            Données parsées ou None
        """
        try:
            home_team = match_data.get('home', {}).get('name') or match_data.get('homeName')
            away_team = match_data.get('away', {}).get('name') or match_data.get('awayName')
            
            if not home_team or not away_team:
                return None
            
            # Extraire les cotes
            odds_data = match_data.get('odds', {}) or match_data.get('averageOdds', {})
            
            # Format 1X2
            odd_1 = odds_data.get('1') or odds_data.get('home') or odds_data.get('odd1')
            odd_x = odds_data.get('X') or odds_data.get('draw') or odds_data.get('oddX')
            odd_2 = odds_data.get('2') or odds_data.get('away') or odds_data.get('odd2')
            
            if not all([odd_1, odd_x, odd_2]):
                return None
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'odds_1': float(odd_1),
                'odds_X': float(odd_x),
                'odds_2': float(odd_2),
                'bookmaker': 'average',
                'match_time': match_data.get('startTime') or match_data.get('time')
            }
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error parsing match JSON: {e}")
            return None
    
    def get_match_odds_detail(self, match_url: str) -> Dict:
        """
        Récupère les cotes détaillées d'un match spécifique.
        
        Args:
            match_url: URL du match sur OddsPortal
            
        Returns:
            Dictionnaire avec les cotes par bookmaker
        """
        url = urljoin(self.base_url, match_url)
        logger.info(f"Fetching detailed odds from {url}")
        
        html = self._get_page_with_selenium(url, wait_for_odds=True)
        if not html:
            return {}
        
        odds_by_bookmaker = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Recherche des lignes de cotes par bookmaker
            odds_rows = soup.select('table.table-main tr, .odds-table tr, [class*="bookmaker"]')
            
            for row in odds_rows:
                bookmaker_elem = row.select_one('.bookmaker a, [class*="bookmaker"]')
                if not bookmaker_elem:
                    continue
                
                bookmaker = bookmaker_elem.get_text(strip=True)
                odds_elems = row.select('.odds-nowrp, [class*="odds"]')
                
                if len(odds_elems) >= 3:
                    try:
                        odds_by_bookmaker[bookmaker] = {
                            '1': float(odds_elems[0].get_text(strip=True).replace(',', '.')),
                            'X': float(odds_elems[1].get_text(strip=True).replace(',', '.')),
                            '2': float(odds_elems[2].get_text(strip=True).replace(',', '.'))
                        }
                    except ValueError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error parsing detailed odds: {e}")
        
        return odds_by_bookmaker
    
    def scrape_all_leagues(self, date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """
        Scrape les cotes pour toutes les ligues configurées.
        
        Args:
            date: Date optionnelle pour filtrer les matchs
            
        Returns:
            Dictionnaire avec les matchs par ligue
        """
        all_odds = {}
        
        try:
            for league_key in self.config['oddsportal']['leagues'].keys():
                league_name = self.config['oddsportal']['leagues'][league_key]['name']
                logger.info(f"=== Scraping odds for {league_name} ===")
                
                try:
                    matches = self.get_matches_for_league(league_key, date)
                    all_odds[league_key] = matches
                except Exception as e:
                    logger.error(f"Error scraping {league_name}: {e}")
                    all_odds[league_key] = []
        
        finally:
            # Toujours fermer Selenium à la fin
            self._close_selenium()
        
        return all_odds
    
    def merge_with_sofascore_data(self, sofascore_matches: List[Dict], odds_data: List[Dict]) -> List[Dict]:
        """
        Fusionne les données Sofascore avec les cotes OddsPortal.
        
        Args:
            sofascore_matches: Liste des matchs depuis Sofascore
            odds_data: Liste des cotes depuis OddsPortal
            
        Returns:
            Liste des matchs enrichis avec les cotes
        """
        enriched_matches = []
        
        for match in sofascore_matches:
            home_team = match.get('home_team', '').lower()
            away_team = match.get('away_team', '').lower()
            
            # Rechercher les cotes correspondantes
            matching_odds = None
            for odds in odds_data:
                odds_home = odds.get('home_team', '').lower()
                odds_away = odds.get('away_team', '').lower()
                
                # Correspondance fuzzy simple
                if (home_team in odds_home or odds_home in home_team or 
                    self._teams_match(home_team, odds_home)) and \
                   (away_team in odds_away or odds_away in away_team or
                    self._teams_match(away_team, odds_away)):
                    matching_odds = odds
                    break
            
            enriched = match.copy()
            if matching_odds:
                enriched['odds'] = {
                    '1': matching_odds.get('odds_1'),
                    'X': matching_odds.get('odds_X'),
                    '2': matching_odds.get('odds_2'),
                    'bookmaker': matching_odds.get('bookmaker', 'average')
                }
            else:
                enriched['odds'] = None
            
            enriched_matches.append(enriched)
        
        return enriched_matches
    
    def _teams_match(self, team1: str, team2: str) -> bool:
        """
        Vérifie si deux noms d'équipe correspondent (fuzzy matching).
        
        Args:
            team1: Premier nom d'équipe
            team2: Deuxième nom d'équipe
            
        Returns:
            True si les équipes semblent correspondre
        """
        # Normaliser les noms
        t1 = team1.lower().replace('fc', '').replace('cf', '').strip()
        t2 = team2.lower().replace('fc', '').replace('cf', '').strip()
        
        # Vérifier la similarité
        if t1 == t2:
            return True
        
        # Vérifier si l'un contient l'autre
        if t1 in t2 or t2 in t1:
            return True
        
        # Vérifier les mots communs
        words1 = set(t1.split())
        words2 = set(t2.split())
        common = words1 & words2
        
        if len(common) >= min(len(words1), len(words2)) / 2:
            return True
        
        return False