"""
BetIntel Data Merger Module

Fusionne les données provenant de Sofascore et OddsPortal
pour créer une vue unifiée des matchs avec statistiques et cotes.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class DataMerger:
    """
    Fusionne les données de différentes sources (Sofascore, OddsPortal).
    """
    
    def __init__(self, data_dir: str = "data"):
        """Initialise le merger avec le répertoire de données."""
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.merged_dir = self.data_dir / "merged"
        
        # Créer le répertoire merged s'il n'existe pas
        self.merged_dir.mkdir(parents=True, exist_ok=True)
    
    def merge_daily_data(self, date_str: str) -> List[Dict]:
        """
        Fusionne les données Sofascore et OddsPortal pour une date donnée.
        
        Args:
            date_str: Date au format YYYY-MM-DD
            
        Returns:
            Liste des matchs fusionnés
        """
        logger.info(f"Merging data for {date_str}")
        
        # Charger les données Sofascore
        sofascore_data = self._load_sofascore_data(date_str)
        
        # Charger les données OddsPortal
        oddsportal_data = self._load_oddsportal_data(date_str)
        
        # Fusionner
        merged_matches = self._merge_matches(sofascore_data, oddsportal_data)
        
        # Sauvegarder
        self._save_merged_data(date_str, merged_matches)
        
        logger.info(f"Merged {len(merged_matches)} matches for {date_str}")
        return merged_matches
    
    def _load_sofascore_data(self, date_str: str) -> List[Dict]:
        """Charge les données Sofascore pour une date."""
        filepath = self.raw_dir / f"sofascore_{date_str}.json"
        
        if not filepath.exists():
            logger.warning(f"Sofascore data not found for {date_str}")
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('matches', data if isinstance(data, list) else [])
        except Exception as e:
            logger.error(f"Error loading Sofascore data: {e}")
            return []
    
    def _load_oddsportal_data(self, date_str: str) -> List[Dict]:
        """Charge les données OddsPortal pour une date."""
        filepath = self.raw_dir / f"oddsportal_{date_str}.json"
        
        if not filepath.exists():
            logger.warning(f"OddsPortal data not found for {date_str}")
            return []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Aplatir les données par ligue
                all_odds = []
                if isinstance(data, dict):
                    for league, matches in data.items():
                        if isinstance(matches, list):
                            for match in matches:
                                match['league_key'] = league
                            all_odds.extend(matches)
                elif isinstance(data, list):
                    all_odds = data
                return all_odds
        except Exception as e:
            logger.error(f"Error loading OddsPortal data: {e}")
            return []
    
    def _merge_matches(self, sofascore_matches: List[Dict], 
                       oddsportal_matches: List[Dict]) -> List[Dict]:
        """
        Fusionne les listes de matchs de différentes sources.
        
        Args:
            sofascore_matches: Matchs avec stats de Sofascore
            oddsportal_matches: Matchs avec cotes d'OddsPortal
            
        Returns:
            Liste fusionnée
        """
        merged = []
        
        for sofa_match in sofascore_matches:
            home_team = sofa_match.get('home_team', '')
            away_team = sofa_match.get('away_team', '')
            
            # Chercher les cotes correspondantes
            matching_odds = self._find_matching_odds(
                home_team, away_team, oddsportal_matches
            )
            
            # Créer le match fusionné
            merged_match = {
                'id': sofa_match.get('id'),
                'date': sofa_match.get('date'),
                'kickoff': sofa_match.get('start_time'),
                'league': sofa_match.get('league'),
                'league_id': sofa_match.get('league_id'),
                'home_team': home_team,
                'home_team_id': sofa_match.get('home_team_id'),
                'away_team': away_team,
                'away_team_id': sofa_match.get('away_team_id'),
                'round': sofa_match.get('round'),
                'season': sofa_match.get('season'),
                
                # Stats de Sofascore
                'home_form': sofa_match.get('home_form', []),
                'away_form': sofa_match.get('away_form', []),
                'home_goals_scored_5': sofa_match.get('home_goals_scored_5', 0),
                'home_goals_conceded_5': sofa_match.get('home_goals_conceded_5', 0),
                'away_goals_scored_5': sofa_match.get('away_goals_scored_5', 0),
                'away_goals_conceded_5': sofa_match.get('away_goals_conceded_5', 0),
                'h2h': sofa_match.get('h2h', {}),
                
                # Cotes d'OddsPortal
                'odds': matching_odds if matching_odds else None,
                
                # Métadonnées
                'merged_at': datetime.now().isoformat(),
                'sources': ['sofascore'] + (['oddsportal'] if matching_odds else [])
            }
            
            merged.append(merged_match)
        
        # Ajouter les matchs d'OddsPortal sans correspondance Sofascore
        for odds_match in oddsportal_matches:
            home_team = odds_match.get('home_team', '')
            away_team = odds_match.get('away_team', '')
            
            # Vérifier si déjà fusionné
            already_merged = any(
                self._teams_match(m['home_team'], m['away_team'], home_team, away_team)
                for m in merged
            )
            
            if not already_merged:
                merged_match = {
                    'date': odds_match.get('match_time'),
                    'league': odds_match.get('league_key', 'Unknown'),
                    'home_team': home_team,
                    'away_team': away_team,
                    'odds': {
                        '1': odds_match.get('odds_1'),
                        'X': odds_match.get('odds_X'),
                        '2': odds_match.get('odds_2'),
                        'bookmaker': odds_match.get('bookmaker', 'average')
                    },
                    'home_form': [],
                    'away_form': [],
                    'h2h': {'matches': []},
                    'merged_at': datetime.now().isoformat(),
                    'sources': ['oddsportal']
                }
                merged.append(merged_match)
        
        return merged
    
    def _find_matching_odds(self, home_team: str, away_team: str,
                            oddsportal_matches: List[Dict]) -> Optional[Dict]:
        """
        Trouve les cotes correspondantes pour un match.
        
        Args:
            home_team: Nom de l'équipe à domicile
            away_team: Nom de l'équipe à l'extérieur
            oddsportal_matches: Liste des matchs avec cotes
            
        Returns:
            Dictionnaire des cotes ou None
        """
        for odds_match in oddsportal_matches:
            odds_home = odds_match.get('home_team', '')
            odds_away = odds_match.get('away_team', '')
            
            if self._teams_match(home_team, away_team, odds_home, odds_away):
                return {
                    '1': odds_match.get('odds_1'),
                    'X': odds_match.get('odds_X'),
                    '2': odds_match.get('odds_2'),
                    'bookmaker': odds_match.get('bookmaker', 'average')
                }
        
        return None
    
    def _teams_match(self, home1: str, away1: str, home2: str, away2: str) -> bool:
        """
        Vérifie si deux paires d'équipes correspondent (matching fuzzy).
        
        Args:
            home1, away1: Première paire d'équipes
            home2, away2: Deuxième paire d'équipes
            
        Returns:
            True si les équipes correspondent
        """
        home1_lower = home1.lower()
        away1_lower = away1.lower()
        home2_lower = home2.lower()
        away2_lower = away2.lower()
        
        # Correspondance exacte
        if home1_lower == home2_lower and away1_lower == away2_lower:
            return True
        
        # Correspondance partielle
        home_match = (
            home1_lower in home2_lower or home2_lower in home1_lower or
            self._normalize_team_name(home1_lower) == self._normalize_team_name(home2_lower)
        )
        away_match = (
            away1_lower in away2_lower or away2_lower in away1_lower or
            self._normalize_team_name(away1_lower) == self._normalize_team_name(away2_lower)
        )
        
        return home_match and away_match
    
    def _normalize_team_name(self, name: str) -> str:
        """
        Normalise un nom d'équipe pour la comparaison.
        
        Args:
            name: Nom de l'équipe
            
        Returns:
            Nom normalisé
        """
        # Supprimer les mots communs et les caractères spéciaux
        common_words = ['fc', 'cf', 'sc', 'ac', 'as', 'rc', 'club', 'football']
        normalized = name.lower()
        
        for word in common_words:
            normalized = normalized.replace(word, '')
        
        # Supprimer les espaces et caractères spéciaux
        normalized = ''.join(c for c in normalized if c.isalnum())
        
        return normalized
    
    def _save_merged_data(self, date_str: str, matches: List[Dict]):
        """Sauvegarde les données fusionnées."""
        filepath = self.merged_dir / f"matches_{date_str}.json"
        
        output = {
            'date': date_str,
            'generated_at': datetime.now().isoformat(),
            'count': len(matches),
            'matches': matches
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Saved merged data to {filepath}")
    
    def get_merged_data(self, date_str: str) -> List[Dict]:
        """
        Récupère les données fusionnées pour une date.
        
        Args:
            date_str: Date au format YYYY-MM-DD
            
        Returns:
            Liste des matchs fusionnés
        """
        filepath = self.merged_dir / f"matches_{date_str}.json"
        
        if not filepath.exists():
            logger.warning(f"Merged data not found for {date_str}, attempting merge...")
            return self.merge_daily_data(date_str)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('matches', [])
        except Exception as e:
            logger.error(f"Error loading merged data: {e}")
            return []
    
    def get_match_by_teams(self, home_team: str, away_team: str,
                           date_str: Optional[str] = None) -> Optional[Dict]:
        """
        Recherche un match spécifique par noms d'équipes.
        
        Args:
            home_team: Nom de l'équipe à domicile
            away_team: Nom de l'équipe à l'extérieur
            date_str: Date optionnelle (aujourd'hui par défaut)
            
        Returns:
            Données du match ou None
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        matches = self.get_merged_data(date_str)
        
        for match in matches:
            if self._teams_match(
                match.get('home_team', ''),
                match.get('away_team', ''),
                home_team, away_team
            ):
                return match
        
        return None
    
    def get_all_matches(self, date_str: Optional[str] = None,
                        league: Optional[str] = None) -> List[Dict]:
        """
        Récupère tous les matchs pour une date, avec filtre optionnel par ligue.
        
        Args:
            date_str: Date (aujourd'hui par défaut)
            league: Filtre par ligue
            
        Returns:
            Liste des matchs
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        matches = self.get_merged_data(date_str)
        
        if league:
            matches = [
                m for m in matches
                if league.lower() in m.get('league', '').lower()
            ]
        
        return matches
    
