"""
BetIntel Predictor Module

Module de prédiction de matchs de football basé sur les données scrapées.
Utilise les statistiques de forme, H2H, et cotes pour calculer les probabilités.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from data.merge import DataMerger

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Résultat d'une prédiction de match."""
    home_team: str
    away_team: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    home_goals_expected: float
    away_goals_expected: float
    confidence: float  # 0-100
    recommendation: str
    ev_analysis: Dict[str, Dict[str, float]]
    key_factors: List[str]
    match_data: Dict[str, Any]


class MatchPredictor:
    """Prédicteur de matchs de football."""
    
    # Poids pour les différents facteurs de prédiction
    WEIGHTS = {
        'recent_form': 0.35,
        'h2h': 0.25,
        'goals_stats': 0.25,
        'home_advantage': 0.15,
    }
    
    def __init__(self, data_dir: str = "data"):
        """Initialise le prédicteur."""
        self.data_dir = Path(data_dir)
        self.merger = DataMerger()
        self._cache = {}
        
    def _load_cached_data(self, date_str: str) -> List[Dict]:
        """Charge les données en cache pour une date donnée."""
        if date_str not in self._cache:
            merged_file = self.data_dir / "merged" / f"matches_{date_str}.json"
            if merged_file.exists():
                with open(merged_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache[date_str] = data.get('matches', [])
            else:
                self._cache[date_str] = []
        return self._cache[date_str]
    
    def search_matches(self, team_name: str, date: str, league: Optional[str] = None) -> List[Dict]:
        """
        Recherche les matchs contenant une équipe spécifique.
        
        Args:
            team_name: Nom de l'équipe à rechercher
            date: Date des matchs (YYYY-MM-DD)
            league: Filtre optionnel par ligue
            
        Returns:
            Liste des matchs correspondants
        """
        matches = self._load_cached_data(date)
        team_lower = team_name.lower()
        
        results = []
        for match in matches:
            home = match.get('home_team', '').lower()
            away = match.get('away_team', '').lower()
            
            if team_lower in home or team_lower in away or home in team_lower or away in team_lower:
                if league is None or match.get('league', '').lower() == league.lower():
                    results.append(match)
        
        return results
    
    def get_match_data(self, home_team: str, away_team: str, 
                       date: Optional[str] = None) -> Optional[Dict]:
        """
        Récupère les données complètes d'un match spécifique.
        
        Args:
            home_team: Nom de l'équipe à domicile
            away_team: Nom de l'équipe à l'extérieur
            date: Date optionnelle du match
            
        Returns:
            Données du match ou None si non trouvé
        """
        if date:
            dates_to_check = [date]
        else:
            # Chercher sur plusieurs jours
            dates_to_check = [
                datetime.now().strftime('%Y-%m-%d'),
                (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            ]
        
        home_lower = home_team.lower()
        away_lower = away_team.lower()
        
        for date_str in dates_to_check:
            matches = self._load_cached_data(date_str)
            for match in matches:
                match_home = match.get('home_team', '').lower()
                match_away = match.get('away_team', '').lower()
                
                # Correspondance fuzzy
                if ((home_lower in match_home or match_home in home_lower) and
                    (away_lower in match_away or match_away in away_lower)):
                    return match
        
        # Si pas trouvé dans les données scrapées, créer une structure vide
        # pour permettre les requêtes futures
        return self._create_empty_match_data(home_team, away_team, date)
    
    def _create_empty_match_data(self, home_team: str, away_team: str,
                                  date: Optional[str] = None) -> Dict:
        """Crée une structure de données vide pour un match."""
        return {
            'home_team': home_team,
            'away_team': away_team,
            'date': date or datetime.now().strftime('%Y-%m-%d'),
            'home_form': [],
            'away_form': [],
            'h2h': {'matches': []},
            'odds': None,
        }
    
    def get_matches_for_date(self, date: str, league: Optional[str] = None,
                             limit: int = 20) -> List[Dict]:
        """
        Récupère tous les matchs pour une date donnée.
        
        Args:
            date: Date au format YYYY-MM-DD
            league: Filtre optionnel par ligue
            limit: Nombre maximum de matchs
            
        Returns:
            Liste des matchs
        """
        matches = self._load_cached_data(date)
        
        if league:
            matches = [m for m in matches if league.lower() in m.get('league', '').lower()]
        
        return matches[:limit]
    
    def get_live_matches(self, league: Optional[str] = None) -> List[Dict]:
        """
        Récupère les matchs en direct.
        
        Args:
            league: Filtre optionnel par ligue
            
        Returns:
            Liste des matchs en cours
        """
        # Pour l'instant, simuler des matchs live
        # Dans une implémentation réelle, cela viendrait d'une API live
        today = datetime.now().strftime('%Y-%m-%d')
        matches = self._load_cached_data(today)
        
        # Filtrer les matchs qui devraient être en cours
        live_matches = []
        for match in matches:
            kickoff = match.get('kickoff', '')
            if kickoff:
                try:
                    match_time = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
                    now = datetime.now(match_time.tzinfo)
                    # Considérer comme live si le match a commencé il y a moins de 2h
                    if now - match_time < timedelta(hours=2) and now >= match_time:
                        match['live'] = True
                        match['current_minute'] = min(90, int((now - match_time).total_seconds() / 60))
                        live_matches.append(match)
                except:
                    pass
        
        if league:
            live_matches = [m for m in live_matches if league.lower() in m.get('league', '').lower()]
        
        return live_matches
    
    def predict(self, match_data: Dict) -> PredictionResult:
        """
        Calcule la prédiction pour un match.
        
        Args:
            match_data: Données du match (forme, H2H, stats, cotes)
            
        Returns:
            Résultat de la prédiction
        """
        home_team = match_data.get('home_team', 'Home')
        away_team = match_data.get('away_team', 'Away')
        
        # Calculer les probabilités basées sur différents facteurs
        form_probs = self._calculate_form_probability(match_data)
        h2h_probs = self._calculate_h2h_probability(match_data)
        goals_probs = self._calculate_goals_probability(match_data)
        home_advantage = self.WEIGHTS['home_advantage']
        
        # Combiner les probabilités pondérées
        home_win_prob = (
            form_probs['home'] * self.WEIGHTS['recent_form'] +
            h2h_probs['home'] * self.WEIGHTS['h2h'] +
            goals_probs['home'] * self.WEIGHTS['goals_stats'] +
            home_advantage * 0.1  # Avantage domicile
        )
        
        away_win_prob = (
            form_probs['away'] * self.WEIGHTS['recent_form'] +
            h2h_probs['away'] * self.WEIGHTS['h2h'] +
            goals_probs['away'] * self.WEIGHTS['goals_stats']
        )
        
        draw_prob = (
            form_probs['draw'] * self.WEIGHTS['recent_form'] +
            h2h_probs['draw'] * self.WEIGHTS['h2h'] +
            goals_probs['draw'] * self.WEIGHTS['goals_stats']
        )
        
        # Normaliser pour que la somme = 1
        total = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total
        draw_prob /= total
        away_win_prob /= total
        
        # Calculer les buts attendus
        home_goals_exp, away_goals_exp = self._calculate_expected_goals(match_data)
        
        # Calculer la confiance
        confidence = self._calculate_confidence(match_data)
        
        # Analyse EV
        ev_analysis = self._calculate_ev_analysis(
            home_win_prob, draw_prob, away_win_prob,
            match_data.get('odds', {})
        )
        
        # Déterminer la recommandation
        recommendation = self._generate_recommendation(
            home_win_prob, draw_prob, away_win_prob,
            ev_analysis, match_data
        )
        
        # Facteurs clés
        key_factors = self._identify_key_factors(match_data, home_win_prob, away_win_prob)
        
        return PredictionResult(
            home_team=home_team,
            away_team=away_team,
            home_win_prob=home_win_prob * 100,
            draw_prob=draw_prob * 100,
            away_win_prob=away_win_prob * 100,
            home_goals_expected=home_goals_exp,
            away_goals_expected=away_goals_exp,
            confidence=confidence,
            recommendation=recommendation,
            ev_analysis=ev_analysis,
            key_factors=key_factors,
            match_data=match_data
        )
    
    def _calculate_form_probability(self, match_data: Dict) -> Dict[str, float]:
        """Calcule les probabilités basées sur la forme récente."""
        home_form = match_data.get('home_form', [])
        away_form = match_data.get('away_form', [])
        
        if not home_form or not away_form:
            return {'home': 0.33, 'draw': 0.34, 'away': 0.33}
        
        # Calculer les points de forme (V=3, D=1, D=0)
        def form_points(form):
            points = 0
            for match in form[:5]:  # 5 derniers matchs
                result = match.get('result', '')
                if result == 'V':
                    points += 3
                elif result == 'D':
                    points += 1
            return points / 15  # Normaliser sur 15 points max
        
        home_strength = form_points(home_form)
        away_strength = form_points(away_form)
        
        # Probabilités relatives
        total = home_strength + away_strength + 0.3  # 0.3 pour le match nul
        home_prob = home_strength / total
        away_prob = away_strength / total
        draw_prob = 0.3 / total
        
        return {'home': home_prob, 'draw': draw_prob, 'away': away_prob}
    
    def _calculate_h2h_probability(self, match_data: Dict) -> Dict[str, float]:
        """Calcule les probabilités basées sur l'historique H2H."""
        h2h = match_data.get('h2h', {})
        matches = h2h.get('matches', [])
        
        if not matches:
            return {'home': 0.33, 'draw': 0.34, 'away': 0.33}
        
        home_wins = h2h.get('team1_wins', 0)
        away_wins = h2h.get('team2_wins', 0)
        draws = h2h.get('draws', 0)
        total = home_wins + away_wins + draws
        
        if total == 0:
            return {'home': 0.33, 'draw': 0.34, 'away': 0.33}
        
        return {
            'home': home_wins / total,
            'draw': draws / total,
            'away': away_wins / total
        }
    
    def _calculate_goals_probability(self, match_data: Dict) -> Dict[str, float]:
        """Calcule les probabilités basées sur les statistiques de buts."""
        # Récupérer les stats de buts sur les 5 derniers matchs
        home_scored = match_data.get('home_goals_scored_5', 0)
        home_conceded = match_data.get('home_goals_conceded_5', 0)
        away_scored = match_data.get('away_goals_scored_5', 0)
        away_conceded = match_data.get('away_goals_conceded_5', 0)
        
        if home_scored + home_conceded + away_scored + away_conceded == 0:
            return {'home': 0.33, 'draw': 0.34, 'away': 0.33}
        
        # Force offensive relative
        home_attack = home_scored / 5 if home_scored > 0 else 0.5
        away_attack = away_scored / 5 if away_scored > 0 else 0.5
        
        # Force défensive relative (moins de buts encaissés = meilleure défense)
        home_defense = 5 / (home_conceded + 1)  # +1 pour éviter division par zéro
        away_defense = 5 / (away_conceded + 1)
        
        # Probabilités basées sur la différence de force
        home_strength = home_attack * away_defense
        away_strength = away_attack * home_defense
        
        total = home_strength + away_strength + 1.0  # 1.0 pour le match nul
        
        return {
            'home': home_strength / total,
            'draw': 1.0 / total,
            'away': away_strength / total
        }
    
    def _calculate_expected_goals(self, match_data: Dict) -> Tuple[float, float]:
        """Calcule les buts attendus pour chaque équipe."""
        home_scored_5 = match_data.get('home_goals_scored_5', 0) / 5
        home_conceded_5 = match_data.get('home_goals_conceded_5', 0) / 5
        away_scored_5 = match_data.get('away_goals_scored_5', 0) / 5
        away_conceded_5 = match_data.get('away_goals_conceded_5', 0) / 5
        
        # Moyenne des buts marqués et encaissés
        home_goals = (home_scored_5 + away_conceded_5) / 2
        away_goals = (away_scored_5 + home_conceded_5) / 2
        
        # Ajustement pour l'avantage domicile
        home_goals *= 1.15
        
        return round(home_goals, 2), round(away_goals, 2)
    
    def _calculate_confidence(self, match_data: Dict) -> float:
        """Calcule le niveau de confiance de la prédiction (0-100)."""
        confidence = 50.0  # Base
        
        # Plus de données = plus de confiance
        if len(match_data.get('home_form', [])) >= 5:
            confidence += 15
        if len(match_data.get('away_form', [])) >= 5:
            confidence += 15
        if len(match_data.get('h2h', {}).get('matches', [])) >= 3:
            confidence += 10
        if match_data.get('odds'):
            confidence += 10
        
        return min(100, confidence)
    
    def _calculate_ev_analysis(self, home_prob: float, draw_prob: float, 
                               away_prob: float, odds: Dict) -> Dict[str, Dict[str, float]]:
        """
        Calcule l'Expected Value (EV) pour chaque résultat.
        
        EV = (Probabilité * Cote) - 1
        Un EV positif indique une valeur potentielle.
        """
        if not odds:
            return {}
        
        ev_analysis = {}
        
        outcomes = {
            '1 (Victoire Domicile)': {'prob': home_prob, 'odd': odds.get('1', 0)},
            'X (Match Nul)': {'prob': draw_prob, 'odd': odds.get('X', 0)},
            '2 (Victoire Extérieur)': {'prob': away_prob, 'odd': odds.get('2', 0)},
        }
        
        for outcome, data in outcomes.items():
            prob = data['prob']
            odd = data['odd']
            
            if odd > 0:
                ev = (prob * odd) - 1
                ev_percent = ev * 100
                
                ev_analysis[outcome] = {
                    'probability': prob * 100,
                    'odd': odd,
                    'ev': ev_percent,
                    'value_bet': ev > 0.05  # EV > 5% considéré comme value bet
                }
        
        return ev_analysis
    
    def _generate_recommendation(self, home_prob: float, draw_prob: float,
                                  away_prob: float, ev_analysis: Dict,
                                  match_data: Dict) -> str:
        """Génère une recommandation basée sur les probabilités et l'EV."""
        # Chercher les value bets
        value_bets = []
        for outcome, data in ev_analysis.items():
            if data.get('value_bet'):
                value_bets.append((outcome, data['ev']))
        
        if value_bets:
            # Trier par EV décroissant
            value_bets.sort(key=lambda x: x[1], reverse=True)
            best_bet = value_bets[0]
            return f"VALUE BET: {best_bet[0]} (EV: +{best_bet[1]:.1f}%)"
        
        # Sinon, recommander le résultat le plus probable
        probs = [
            ('Victoire Domicile', home_prob),
            ('Match Nul', draw_prob),
            ('Victoire Extérieur', away_prob)
        ]
        probs.sort(key=lambda x: x[1], reverse=True)
        
        best_outcome, best_prob = probs[0]
        
        if best_prob > 0.5:
            return f"FAVORI: {best_outcome} ({best_prob*100:.1f}%)"
        elif best_prob > 0.4:
            return f"LÉGER FAVORI: {best_outcome} ({best_prob*100:.1f}%)"
        else:
            return f"MATCH ÉQUILIBRÉ: {best_outcome} légèrement favoris ({best_prob*100:.1f}%)"
    
    def _identify_key_factors(self, match_data: Dict, home_prob: float, 
                              away_prob: float) -> List[str]:
        """Identifie les facteurs clés influençant la prédiction."""
        factors = []
        
        # Analyser la forme
        home_form = match_data.get('home_form', [])
        away_form = match_data.get('away_form', [])
        
        if home_form:
            home_wins = sum(1 for m in home_form if m.get('result') == 'V')
            if home_wins >= 4:
                factors.append(f"✅ {match_data['home_team']} en excellente forme ({home_wins}/5 victoires)")
            elif home_wins <= 1:
                factors.append(f"⚠️ {match_data['home_team']} en mauvaise forme ({home_wins}/5 victoires)")
        
        if away_form:
            away_wins = sum(1 for m in away_form if m.get('result') == 'V')
            if away_wins >= 4:
                factors.append(f"✅ {match_data['away_team']} en excellente forme ({away_wins}/5 victoires)")
            elif away_wins <= 1:
                factors.append(f"⚠️ {match_data['away_team']} en mauvaise forme ({away_wins}/5 victoires)")
        
        # Analyser H2H
        h2h = match_data.get('h2h', {})
        if h2h.get('team1_wins', 0) >= 3:
            factors.append(f"📊 {match_data['home_team']} domine l'historique H2H")
        elif h2h.get('team2_wins', 0) >= 3:
            factors.append(f"📊 {match_data['away_team']} domine l'historique H2H")
        
        # Analyser les buts
        home_goals = match_data.get('home_goals_scored_5', 0)
        away_goals = match_data.get('away_goals_scored_5', 0)
        if home_goals >= 10:
            factors.append(f"⚽ {match_data['home_team']} très offensif ({home_goals} buts en 5 matchs)")
        if away_goals >= 10:
            factors.append(f"⚽ {match_data['away_team']} très offensif ({away_goals} buts en 5 matchs)")
        
        # Différence de probabilité
        prob_diff = abs(home_prob - away_prob)
        if prob_diff > 0.3:
            factors.append("📈 Écart significatif entre les deux équipes")
        elif prob_diff < 0.1:
            factors.append("⚖️ Match très équilibré sur le papier")
        
        return factors
