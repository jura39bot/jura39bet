"""
OddsPortal Scraper Module

Récupère les cotes des bookmakers depuis OddsPortal.
"""

import json
import logging
import time
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# Import des utilitaires anti-détection
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.scraper_utils import (
    get_random_headers,
    simulate_human_delay,
    retry_with_backoff,
    get_session_cookies,
    RequestThrottler,
    parse_response_status
)

logger = logging.getLogger(__name__)


class OddsPortalScraper:
    """Scraper pour récupérer les cotes depuis OddsPortal."""
    
    def __init__(self, config_path: str = "config/sources.json"):
        """Initialise le scraper avec la configuration."""
        self.config = self._load_config(config_path)
        self.base_url = self.config['oddsportal']['base_url']
        
        # Configuration retry
        self.retry_config = self.config.get('retry', {})
        self.max_retries = self.retry_config.get('max_retries', 3)
        self.timeout = self.retry_config.get('timeout', 30)
        
        # Session avec headers anti-détection
        self.session = requests.Session()
        self._rotate_headers()
        
        # Throttler pour les délais
        retry_delay_min = self.retry_config.get('min_delay', 1.0)
        retry_delay_max = self.retry_config.get('max_delay', 5.0)
        self.throttler = RequestThrottler(min_delay=retry_delay_min, max_delay=retry_delay_max)
        
        self.last_request_time = 0
        self.rate_limit_delay = self.config.get('rate_limit', {}).get('delay_between_requests', 1.0)
        
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
    
    def _rotate_headers(self, referer: Optional[str] = None):
        """Rotation des headers pour éviter la détection."""
        extra_headers = {
            'Origin': 'https://www.oddsportal.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
        headers = get_random_headers(referer=referer, extra_headers=extra_headers)
        self.session.headers.update(headers)
        logger.debug(f"Rotated headers with User-Agent: {headers['User-Agent'][:50]}...")
    
    def _rate_limit(self):
        """Gère le rate limiting avec délai aléatoire."""
        elapsed = time.time() - self.last_request_time
        min_delay = self.retry_config.get('min_delay', 1.0)
        max_delay = self.retry_config.get('max_delay', 5.0)
        
        if elapsed < self.rate_limit_delay:
            sleep_time = random.uniform(min_delay, max_delay)
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, attempt: int = 0) -> Optional[str]:
        """
        Effectue une requête HTTP avec gestion des erreurs et retry.
        
        Args:
            url: URL de la requête
            attempt: Numéro de tentative actuel
            
        Returns:
            Contenu HTML ou None en cas d'échec
        """
        self._rate_limit()
        
        # Rotation des headers à chaque tentative
        if attempt > 0:
            self._rotate_headers(referer='https://www.oddsportal.com/')
            simulate_human_delay(1.0, 3.0)
        
        try:
            # Ajout de cookies de session
            cookies = get_session_cookies('oddsportal.com')
            
            response = self.session.get(
                url, 
                timeout=self.timeout,
                cookies=cookies,
                allow_redirects=True
            )
            
            # Log des informations de réponse
            status_info = parse_response_status(response)
            logger.debug(f"Response status: {status_info['status_code']} for {url}")
            
            # Gestion des redirections
            if response.history:
                logger.info(f"Redirected: {' -> '.join([str(r.status_code) for r in response.history])} -> {response.status_code}")
            
            # Gestion des codes d'erreur
            if response.status_code == 404:
                logger.warning(f"404 Not Found for {url} - page may not exist")
                # Essayer l'URL sans la date
                if attempt == 0 and '/202' in url:
                    base_url = url.split('/202')[0] + '/'
                    logger.info(f"Trying base URL without date: {base_url}")
                    return self._make_request(base_url, attempt + 1)
                if attempt < self.max_retries - 1:
                    delay = min(2 ** attempt, 30)
                    time.sleep(delay)
                    return self._make_request(url, attempt + 1)
                return None
            
            if response.status_code == 403:
                logger.warning(f"403 Forbidden for {url} - attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    delay = min(2 ** attempt, 30)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    return self._make_request(url, attempt + 1)
                return None
            
            if response.status_code == 429:
                logger.warning(f"429 Rate Limited for {url}")
                if attempt < self.max_retries - 1:
                    delay = min(2 ** (attempt + 2), 60)
                    logger.info(f"Rate limited, waiting {delay}s...")
                    time.sleep(delay)
                    return self._make_request(url, attempt + 1)
                return None
            
            response.raise_for_status()
            return response.text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            if attempt < self.max_retries - 1:
                delay = min(2 ** attempt, 30)
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
                return self._make_request(url, attempt + 1)
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
                
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error extracting JSON data: {e}")
        
        return None
    
    def _parse_match_odds_html(self, match_element) -> Optional[Dict]:
        """Parse les cotes d'un élément match avec BeautifulSoup."""
        try:
            # Extraction des équipes - essayer plusieurs sélecteurs
            teams_elem = match_element.select('.table-participant a')
            if not teams_elem:
                teams_elem = match_element.select('[class*="participant"]')
            if not teams_elem:
                teams_elem = match_element.select('a[href*="/soccer/"]')
            
            if not teams_elem:
                return None
            
            teams_text = teams_elem[0].get_text(strip=True)
            if ' - ' in teams_text:
                home_team, away_team = teams_text.split(' - ', 1)
            elif ' v ' in teams_text:
                home_team, away_team = teams_text.split(' v ', 1)
            elif ' vs ' in teams_text:
                home_team, away_team = teams_text.split(' vs ', 1)
            else:
                return None
            
            # Extraction des cotes - essayer plusieurs sélecteurs
            odds_elements = match_element.select('.odds-nowrp, [class*="odds"], .right, .center')
            odds = []
            for elem in odds_elements[:3]:  # 1X2 = 3 cotes
                try:
                    odd_text = elem.get_text(strip=True).replace(',', '.')
                    # Filtrer les valeurs qui ne sont pas des nombres
                    if odd_text and odd_text.replace('.', '').isdigit():
                        odds.append(float(odd_text))
                except (ValueError, AttributeError):
                    continue
            
            if len(odds) < 3:
                return None
            
            return {
                'home_team': home_team.strip(),
                'away_team': away_team.strip(),
                'odds_1': odds[0],  # Victoire domicile
                'odds_X': odds[1],  # Match nul
                'odds_2': odds[2],  # Victoire extérieur
                'bookmaker': 'average'  # Cote moyenne
            }
            
        except Exception as e:
            logger.error(f"Error parsing match odds from HTML: {e}")
            return None
    
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
        
        # Construire l'URL - utiliser la page principale sans date par défaut
        url = urljoin(self.base_url, league_info['path'])
        
        # Si une date est fournie, l'ajouter à l'URL
        if date:
            # Format: /soccer/england/premier-league/2024-04-15/
            date_str = date.strftime('%Y-%m-%d')
            url = urljoin(url, date_str + '/')
            logger.info(f"Fetching odds for date {date_str} from {url}")
        else:
            logger.info(f"Fetching odds from main page: {url}")
        
        html = self._make_request(url)
        if not html:
            logger.error(f"Failed to fetch HTML from {url}")
            return []
        
        matches = []
        
        # Essayer d'extraire les données JSON d'abord
        json_data = self._extract_json_data(html)
        if json_data and 'matches' in json_data:
            logger.info("Extracting data from JSON...")
            for match in json_data['matches']:
                try:
                    parsed = self._parse_match_from_json(match)
                    if parsed:
                        matches.append(parsed)
                except Exception as e:
                    logger.error(f"Error parsing match from JSON: {e}")
        else:
            # Fallback: parsing HTML avec BeautifulSoup
            logger.info("JSON data not found, using HTML parsing...")
            soup = BeautifulSoup(html, 'html.parser')  # Utiliser html.parser au lieu de lxml
            
            # Essayer plusieurs sélecteurs pour trouver les lignes de match
            match_rows = soup.select('table.table-main tr, [class*="match"], [class*="event"], .table-row')
            
            if not match_rows:
                # Essayer des sélecteurs plus génériques
                match_rows = soup.find_all('tr')
            
            logger.info(f"Found {len(match_rows)} potential match rows")
            
            for row in match_rows:
                try:
                    parsed = self._parse_match_odds_html(row)
                    if parsed:
                        matches.append(parsed)
                except Exception as e:
                    logger.error(f"Error parsing match row: {e}")
        
        logger.info(f"Found {len(matches)} matches with odds for {league_info['name']}")
        
        # Délai aléatoire après chaque ligue
        simulate_human_delay(1.0, 2.0)
        
        return matches
    
    def _parse_match_from_json(self, match_data: Dict) -> Optional[Dict]:
        """Parse les données d'un match depuis le JSON."""
        try:
            home_team = match_data.get('home', {}).get('name') or match_data.get('homeName')
            away_team = match_data.get('away', {}).get('name') or match_data.get('awayName')
            
            if not home_team or not away_team:
                return None
            
            # Extraire les cotes
            odds_data = match_data.get('odds', {})
            if not odds_data:
                odds_data = match_data.get('averageOdds', {})
            
            # Format 1X2
            odd_1 = odds_data.get('1') or odds_data.get('home')
            odd_x = odds_data.get('X') or odds_data.get('draw')
            odd_2 = odds_data.get('2') or odds_data.get('away')
            
            if not all([odd_1, odd_x, odd_2]):
                return None
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'odds_1': float(odd_1),
                'odds_X': float(odd_x),
                'odds_2': float(odd_2),
                'bookmaker': 'average',
                'match_time': match_data.get('startTime')
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
        
        html = self._make_request(url)
        if not html:
            return {}
        
        odds_by_bookmaker = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Recherche des lignes de cotes par bookmaker
            odds_rows = soup.select('table.table-main tr, .odds-table tr')
            
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
        
        for league_key in self.config['oddsportal']['leagues'].keys():
            league_name = self.config['oddsportal']['leagues'][league_key]['name']
            logger.info(f"=== Scraping odds for {league_name} ===")
            
            try:
                matches = self.get_matches_for_league(league_key, date)
                all_odds[league_key] = matches
            except Exception as e:
                logger.error(f"Error scraping {league_name}: {e}")
                all_odds[league_key] = []
        
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
                if (home_team in odds_home or odds_home in home_team) and \
                   (away_team in odds_away or odds_away in away_team):
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