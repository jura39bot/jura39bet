#!/usr/bin/env python3
"""
BetIntel Scraper - Script principal d'orchestration

Ce script orchestre le scraping des données de matchs depuis Sofascore et OddsPortal.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Ajouter le répertoire courant au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.sofascore import SofascoreScraper
from scrapers.oddsportal import OddsPortalScraper


class BetIntelScraper:
    """Orchestrateur principal du scraping BetIntel."""
    
    def __init__(self, config_path: str = "config/sources.json"):
        """Initialise l'orchestrateur avec les scrapers."""
        self.config_path = config_path
        self.sofascore = SofascoreScraper(config_path)
        self.oddsportal = OddsPortalScraper(config_path)
        self.data_dir = Path("data/raw")
        
    def ensure_data_dir(self, date_str: str) -> Path:
        """Crée le répertoire de données pour une date donnée."""
        date_dir = self.data_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir
    
    def save_data(self, data: Dict, filename: str, date_str: str):
        """Sauvegarde les données dans un fichier JSON."""
        date_dir = self.ensure_data_dir(date_str)
        filepath = date_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Data saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving data to {filepath}: {e}")
            raise
    
    def scrape_day(self, date: datetime, include_odds: bool = True) -> Dict:
        """
        Scrape les données pour une journée spécifique.
        
        Args:
            date: Date à scraper
            include_odds: Inclure les cotes depuis OddsPortal
            
        Returns:
            Dictionnaire avec toutes les données scrapées
        """
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"\n{'='*60}")
        logger.info(f"SCRAPING DAY: {date_str}")
        logger.info(f"{'='*60}\n")
        
        result = {
            'date': date_str,
            'scraped_at': datetime.now().isoformat(),
            'matches': []
        }
        
        # 1. Récupérer les matchs depuis Sofascore
        logger.info("Step 1: Fetching matches from Sofascore...")
        try:
            sofascore_matches = self.sofascore.get_matches_for_date(date)
            logger.info(f"Found {len(sofascore_matches)} matches from Sofascore")
        except Exception as e:
            logger.error(f"Error fetching from Sofascore: {e}")
            sofascore_matches = []
        
        # 2. Enrichir avec les stats détaillées
        logger.info("Step 2: Enriching match data...")
        enriched_matches = []
        for match in sofascore_matches:
            try:
                enriched = self.sofascore.enrich_match_data(match)
                enriched_matches.append(enriched)
            except Exception as e:
                logger.error(f"Error enriching match {match.get('id')}: {e}")
                enriched_matches.append(match)
        
        # 3. Récupérer les cotes depuis OddsPortal
        if include_odds:
            logger.info("Step 3: Fetching odds from OddsPortal...")
            try:
                odds_data = self.oddsportal.scrape_all_leagues(date)
                
                # Fusionner les cotes avec les matchs
                for match in enriched_matches:
                    league_key = self._get_league_key(match.get('league', ''))
                    if league_key and league_key in odds_data:
                        match = self._merge_odds(match, odds_data[league_key])
                        
            except Exception as e:
                logger.error(f"Error fetching from OddsPortal: {e}")
        
        result['matches'] = enriched_matches
        result['total_matches'] = len(enriched_matches)
        
        # 4. Sauvegarder les données
        logger.info("Step 4: Saving data...")
        self.save_data(result, f"matches_{date_str}.json", date_str)
        
        # Sauvegarder aussi un résumé
        summary = self._create_summary(result)
        self.save_data(summary, f"summary_{date_str}.json", date_str)
        
        return result
    
    def _get_league_key(self, league_name: str) -> str:
        """Convertit le nom de ligue en clé de configuration."""
        league_map = {
            'Premier League': 'premier_league',
            'La Liga': 'la_liga',
            'Serie A': 'serie_a',
            'Ligue 1': 'ligue_1',
            'Bundesliga': 'bundesliga'
        }
        return league_map.get(league_name)
    
    def _merge_odds(self, match: Dict, odds_list: List[Dict]) -> Dict:
        """Fusionne les cotes avec un match."""
        home_team = match.get('home_team', '').lower()
        away_team = match.get('away_team', '').lower()
        
        for odds in odds_list:
            odds_home = odds.get('home_team', '').lower()
            odds_away = odds.get('away_team', '').lower()
            
            # Correspondance des noms d'équipes
            if self._teams_match(home_team, odds_home) and self._teams_match(away_team, odds_away):
                match['odds'] = {
                    '1': odds.get('odds_1'),
                    'X': odds.get('odds_X'),
                    '2': odds.get('odds_2'),
                    'source': 'OddsPortal'
                }
                break
        
        return match
    
    def _teams_match(self, team1: str, team2: str) -> bool:
        """Vérifie si deux noms d'équipes correspondent (fuzzy matching)."""
        team1 = team1.lower().replace('fc', '').replace('cf', '').strip()
        team2 = team2.lower().replace('fc', '').replace('cf', '').strip()
        
        # Correspondance exacte ou partielle
        return team1 in team2 or team2 in team1 or team1 == team2
    
    def _create_summary(self, data: Dict) -> Dict:
        """Crée un résumé des données scrapées."""
        matches = data.get('matches', [])
        
        summary = {
            'date': data.get('date'),
            'scraped_at': data.get('scraped_at'),
            'total_matches': len(matches),
            'by_league': {},
            'matches_with_odds': 0,
            'matches_without_odds': 0
        }
        
        for match in matches:
            league = match.get('league', 'Unknown')
            
            if league not in summary['by_league']:
                summary['by_league'][league] = {
                    'count': 0,
                    'with_odds': 0
                }
            
            summary['by_league'][league]['count'] += 1
            
            if match.get('odds'):
                summary['matches_with_odds'] += 1
                summary['by_league'][league]['with_odds'] += 1
            else:
                summary['matches_without_odds'] += 1
        
        return summary
    
    def run(self, days: int = 2, include_odds: bool = True) -> Dict:
        """
        Lance le scraping pour plusieurs jours.
        
        Args:
            days: Nombre de jours à scraper (aujourd'hui + jours suivants)
            include_odds: Inclure les cotes depuis OddsPortal
            
        Returns:
            Dictionnaire avec tous les résultats
        """
        logger.info(f"\n{'#'*60}")
        logger.info(f"BETINTEL SCRAPER - Starting run")
        logger.info(f"Days to scrape: {days}")
        logger.info(f"Include odds: {include_odds}")
        logger.info(f"{'#'*60}\n")
        
        all_results = {
            'run_started_at': datetime.now().isoformat(),
            'days': days,
            'include_odds': include_odds,
            'results': {}
        }
        
        for i in range(days):
            date = datetime.now() + timedelta(days=i)
            
            try:
                day_result = self.scrape_day(date, include_odds)
                all_results['results'][date.strftime('%Y-%m-%d')] = day_result
            except Exception as e:
                logger.error(f"Failed to scrape {date.strftime('%Y-%m-%d')}: {e}")
                all_results['results'][date.strftime('%Y-%m-%d')] = {
                    'error': str(e),
                    'matches': []
                }
        
        all_results['run_completed_at'] = datetime.now().isoformat()
        
        # Sauvegarder le rapport global
        self.save_data(all_results, 'full_report.json', datetime.now().strftime('%Y-%m-%d'))
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"SCRAPING COMPLETED")
        logger.info(f"{'#'*60}\n")
        
        return all_results


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='BetIntel Scraper')
    parser.add_argument('--days', type=int, default=2, help='Number of days to scrape (default: 2)')
    parser.add_argument('--no-odds', action='store_true', help='Skip OddsPortal scraping')
    parser.add_argument('--date', type=str, help='Specific date to scrape (YYYY-MM-DD format)')
    
    args = parser.parse_args()
    
    scraper = BetIntelScraper()
    
    if args.date:
        # Scraper une date spécifique
        date = datetime.strptime(args.date, '%Y-%m-%d')
        result = scraper.scrape_day(date, not args.no_odds)
        print(f"\nScraped {result['total_matches']} matches for {args.date}")
    else:
        # Scraper les jours configurés
        results = scraper.run(days=args.days, include_odds=not args.no_odds)
        
        # Afficher le résumé
        print("\n" + "="*60)
        print("SCRAPING SUMMARY")
        print("="*60)
        for date_str, data in results['results'].items():
            if 'error' in data:
                print(f"\n{date_str}: ERROR - {data['error']}")
            else:
                print(f"\n{date_str}: {data.get('total_matches', 0)} matches")


if __name__ == "__main__":
    main()