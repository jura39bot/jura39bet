"""
Sofascore Scraper Module

Récupère les statistiques d'équipes, forme récente et H2H depuis Sofascore.
"""

import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from pathlib import Path

# Import des utilitaires anti-détection
import sys
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


class SofascoreScraper:
    """Scraper pour récupérer les données depuis l'API Sofascore."""
    
    def __init__(self, config_path: str = "config/sources.json"):
        """Initialise le scraper avec la configuration."""
        self.config = self._load_config(config_path)
        self.base_url = self.config['sofascore']['api_url']
        
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
            'Origin': 'https://www.sofascore.com',
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
    
    def _make_request(self, url: str, params: Optional[Dict] = None, attempt: int = 0) -> Optional[Dict]:
        """
        Effectue une requête HTTP avec gestion des erreurs et retry.
        
        Args:
            url: URL de la requête
            params: Paramètres de la requête
            attempt: Numéro de tentative actuel
            
        Returns:
            Données JSON ou None en cas d'échec
        """
        self._rate_limit()
        
        # Rotation des headers à chaque tentative
        if attempt > 0:
            self._rotate_headers(referer='https://www.sofascore.com/')
            simulate_human_delay(1.0, 3.0)
        
        try:
            # Ajout de cookies de session
            cookies = get_session_cookies('sofascore.com')
            
            response = self.session.get(
                url, 
                params=params, 
                timeout=self.timeout,
                cookies=cookies,
                allow_redirects=True
            )
            
            # Log des informations de réponse
            status_info = parse_response_status(response)
            logger.debug(f"Response status: {status_info['status_code']} for {url}")
            
            # Gestion des codes d'erreur
            if response.status_code == 403:
                logger.warning(f"403 Forbidden for {url} - attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    # Backoff exponentiel
                    delay = min(2 ** attempt, 30)
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    return self._make_request(url, params, attempt + 1)
                return None
            
            if response.status_code == 429:
                logger.warning(f"429 Rate Limited for {url}")
                if attempt < self.max_retries - 1:
                    delay = min(2 ** (attempt + 2), 60)
                    logger.info(f"Rate limited, waiting {delay}s...")
                    time.sleep(delay)
                    return self._make_request(url, params, attempt + 1)
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            if attempt < self.max_retries - 1:
                delay = min(2 ** attempt, 30)
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
                return self._make_request(url, params, attempt + 1)
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {url}: {e}")
            return None
    
    def get_matches_for_date(self, date: datetime) -> List[Dict]:
        """
        Récupère tous les matchs des 5 grands championats pour une date donnée.
        
        Args:
            date: Date pour laquelle récupérer les matchs
            
        Returns:
            Liste des matchs avec détails de base
        """
        matches = []
        date_str = date.strftime('%Y-%m-%d')
        
        for league_key, league_info in self.config['sofascore']['leagues'].items():
            logger.info(f"Fetching matches for {league_info['name']} on {date_str}")
            
            # Endpoint pour les matchs du jour par ligue
            url = f"{self.base_url}/sport/football/scheduled-events/{date_str}"
            
            data = self._make_request(url)
            if not data or 'events' not in data:
                logger.warning(f"No data returned for {league_info['name']}")
                continue
            
            # Filtrer les matchs de la ligue concernée
            for event in data.get('events', []):
                if event.get('tournament', {}).get('uniqueTournament', {}).get('id') == league_info['id']:
                    match_data = {
                        'id': event.get('id'),
                        'league': league_info['name'],
                        'league_id': league_info['id'],
                        'home_team': event.get('homeTeam', {}).get('name'),
                        'home_team_id': event.get('homeTeam', {}).get('id'),
                        'away_team': event.get('awayTeam', {}).get('name'),
                        'away_team_id': event.get('awayTeam', {}).get('id'),
                        'start_time': event.get('startTimestamp'),
                        'status': event.get('status', {}).get('type'),
                        'round': event.get('roundInfo', {}).get('round'),
                        'season': event.get('season', {}).get('year'),
                    }
                    matches.append(match_data)
            
            # Délai aléatoire entre les ligues
            simulate_human_delay(1.0, 2.0)
        
        logger.info(f"Found {len(matches)} matches for {date_str}")
        return matches
    
    def get_team_form(self, team_id: int, limit: int = 5) -> List[Dict]:
        """
        Récupère la forme récente d'une équipe (5 derniers matchs).
        
        Args:
            team_id: ID de l'équipe
            limit: Nombre de matchs à récupérer (défaut: 5)
            
        Returns:
            Liste des derniers matchs avec résultats
        """
        url = f"{self.base_url}/team/{team_id}/events/last/{limit}"
        data = self._make_request(url)
        
        if not data or 'events' not in data:
            logger.warning(f"No form data found for team {team_id}")
            return []
        
        form_matches = []
        for event in data.get('events', []):
            home_score = event.get('homeScore', {}).get('current')
            away_score = event.get('awayScore', {}).get('current')
            
            # Déterminer si l'équipe était à domicile ou à l'extérieur
            is_home = event.get('homeTeam', {}).get('id') == team_id
            
            # Calculer le résultat
            if home_score is None or away_score is None:
                result = 'N/A'
            elif home_score == away_score:
                result = 'D'
            elif (is_home and home_score > away_score) or (not is_home and away_score > home_score):
                result = 'V'
            else:
                result = 'D'
            
            form_matches.append({
                'match_id': event.get('id'),
                'date': event.get('startTimestamp'),
                'opponent': event.get('awayTeam' if is_home else 'homeTeam', {}).get('name'),
                'is_home': is_home,
                'score': f"{home_score}-{away_score}" if home_score is not None else "N/A",
                'result': result,
                'goals_for': home_score if is_home else away_score,
                'goals_against': away_score if is_home else home_score
            })
        
        return form_matches
    
    def get_h2h(self, match_id: int) -> Dict:
        """
        Récupère l'historique des confrontations directes (H2H).
        
        Args:
            match_id: ID du match
            
        Returns:
            Données H2H avec historique des rencontres
        """
        url = f"{self.base_url}/event/{match_id}/h2h"
        data = self._make_request(url)
        
        if not data:
            logger.warning(f"No H2H data found for match {match_id}")
            return {}
        
        h2h_data = {
            'match_id': match_id,
            'team1_wins': 0,
            'team2_wins': 0,
            'draws': 0,
            'matches': []
        }
        
        for match in data.get('events', []):
            home_score = match.get('homeScore', {}).get('current')
            away_score = match.get('awayScore', {}).get('current')
            
            if home_score is None or away_score is None:
                continue
            
            h2h_match = {
                'date': match.get('startTimestamp'),
                'home_team': match.get('homeTeam', {}).get('name'),
                'away_team': match.get('awayTeam', {}).get('name'),
                'home_score': home_score,
                'away_score': away_score,
                'result': 'D' if home_score == away_score else ('H' if home_score > away_score else 'A')
            }
            h2h_data['matches'].append(h2h_match)
            
            # Compter les victoires (simplifié)
            if home_score == away_score:
                h2h_data['draws'] += 1
            elif home_score > away_score:
                h2h_data['team1_wins'] += 1
            else:
                h2h_data['team2_wins'] += 1
        
        return h2h_data
    
    def get_team_stats(self, team_id: int, season_id: Optional[int] = None) -> Dict:
        """
        Récupère les statistiques de saison d'une équipe.
        
        Args:
            team_id: ID de l'équipe
            season_id: ID de la saison (optionnel)
            
        Returns:
            Statistiques de l'équipe
        """
        url = f"{self.base_url}/team/{team_id}/statistics/season"
        if season_id:
            url = f"{self.base_url}/team/{team_id}/statistics/season/{season_id}"
        
        data = self._make_request(url)
        
        if not data:
            logger.warning(f"No stats found for team {team_id}")
            return {}
        
        stats = data.get('statistics', {})
        return {
            'team_id': team_id,
            'matches_played': stats.get('matches'),
            'wins': stats.get('wins'),
            'draws': stats.get('draws'),
            'losses': stats.get('losses'),
            'goals_scored': stats.get('goalsScored'),
            'goals_conceded': stats.get('goalsConceded'),
            'clean_sheets': stats.get('cleanSheet'),
            'avg_goals_scored': stats.get('goalsScoredPerMatch'),
            'avg_goals_conceded': stats.get('goalsConcededPerMatch')
        }
    
    def enrich_match_data(self, match: Dict) -> Dict:
        """
        Enrichit les données d'un match avec forme, H2H et stats.
        
        Args:
            match: Données de base du match
            
        Returns:
            Match enrichi avec toutes les statistiques
        """
        logger.info(f"Enriching match: {match['home_team']} vs {match['away_team']}")
        
        enriched = match.copy()
        
        # Récupérer la forme des 2 équipes
        enriched['home_form'] = self.get_team_form(match['home_team_id'])
        enriched['away_form'] = self.get_team_form(match['away_team_id'])
        
        # Calculer les buts sur les 5 derniers matchs
        enriched['home_goals_scored_5'] = sum(m.get('goals_for', 0) or 0 for m in enriched['home_form'][:5])
        enriched['home_goals_conceded_5'] = sum(m.get('goals_against', 0) or 0 for m in enriched['home_form'][:5])
        enriched['away_goals_scored_5'] = sum(m.get('goals_for', 0) or 0 for m in enriched['away_form'][:5])
        enriched['away_goals_conceded_5'] = sum(m.get('goals_against', 0) or 0 for m in enriched['away_form'][:5])
        
        # Récupérer H2H
        enriched['h2h'] = self.get_h2h(match['id'])
        
        return enriched
    
    def scrape_matches(self, days: int = 2) -> Dict[str, List[Dict]]:
        """
        Scrape les matchs pour aujourd'hui et les jours suivants.
        
        Args:
            days: Nombre de jours à scraper (défaut: 2 pour aujourd'hui + demain)
            
        Returns:
            Dictionnaire avec les matchs par date
        """
        all_matches = {}
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            logger.info(f"=== Scraping matches for {date_str} ===")
            matches = self.get_matches_for_date(date)
            
            # Enrichir chaque match
            enriched_matches = []
            for match in matches:
                try:
                    enriched = self.enrich_match_data(match)
                    enriched_matches.append(enriched)
                    # Délai entre les enrichissements
                    simulate_human_delay(0.5, 1.5)
                except Exception as e:
                    logger.error(f"Error enriching match {match['id']}: {e}")
                    enriched_matches.append(match)  # Ajouter sans enrichissement
            
            all_matches[date_str] = enriched_matches
        
        return all_matches