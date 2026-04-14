"""
BetIntel Utils Module

Fonctions utilitaires pour le formatage, les calculs et l'affichage.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional


class Colors:
    """Codes couleur pour l'affichage terminal."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Couleurs standard
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Couleurs claires
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    
    # Backgrounds
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


def format_match_table(matches: List[Dict], title: str = "Matchs", 
                       show_score: bool = False) -> str:
    """
    Formate une liste de matchs en tableau ASCII.
    
    Args:
        matches: Liste des matchs à afficher
        title: Titre du tableau
        show_score: Afficher le score actuel (pour les matchs live)
        
    Returns:
        Chaîne formatée
    """
    if not matches:
        return f"{Colors.YELLOW}Aucun match à afficher{Colors.RESET}"
    
    lines = []
    
    # Header
    lines.append(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    # Colonnes
    if show_score:
        header = f"  {'Heure':<8} {'Domicile':<25} {'Score':<10} {'Extérieur':<25} {'Ligue':<15}"
    else:
        header = f"  {'Heure':<8} {'Domicile':<25} {'vs':<5} {'Extérieur':<25} {'Ligue':<15}"
    
    lines.append(f"{Colors.DIM}{header}{Colors.RESET}")
    lines.append(f"{Colors.DIM}{'-'*80}{Colors.RESET}")
    
    # Lignes de matchs
    for match in matches:
        kickoff = match.get('kickoff', '')
        if kickoff:
            try:
                dt = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M')
            except:
                time_str = '--:--'
        else:
            time_str = match.get('time', '--:--')
        
        home = match.get('home_team', 'TBD')[:23]
        away = match.get('away_team', 'TBD')[:23]
        league = match.get('league', 'Unknown')[:13]
        
        if show_score and match.get('live'):
            home_score = match.get('home_score', '-')
            away_score = match.get('away_score', '-')
            score = f"{home_score}-{away_score}"
            minute = match.get('current_minute', '')
            live_indicator = f" {Colors.RED}[{minute}']{Colors.RESET}"
            line = f"  {Colors.BRIGHT_GREEN}{time_str:<8}{Colors.RESET} {home:<25} {score:<10} {away:<25} {league:<15}{live_indicator}"
        else:
            line = f"  {time_str:<8} {home:<25} {'vs':<5} {away:<25} {league:<15}"
        
        lines.append(line)
    
    lines.append(f"{Colors.DIM}{'='*80}{Colors.RESET}\n")
    
    return '\n'.join(lines)


def format_odds_table(odds: Dict, home_team: str, away_team: str) -> str:
    """
    Formate les cotes en tableau.
    
    Args:
        odds: Dictionnaire des cotes (1, X, 2)
        home_team: Nom de l'équipe à domicile
        away_team: Nom de l'équipe à l'extérieur
        
    Returns:
        Chaîne formatée
    """
    if not odds:
        return f"{Colors.YELLOW}Aucune cote disponible{Colors.RESET}"
    
    lines = []
    lines.append(f"\n{Colors.BOLD}{Colors.CYAN}💰 COTES DISPONIBLES{Colors.RESET}\n")
    
    # Header
    header = f"  {'Résultat':<25} {'Cote':<10} {'Implied Prob':<15}"
    lines.append(header)
    lines.append(f"{Colors.DIM}{'-'*55}{Colors.RESET}")
    
    # Lignes de cotes
    outcomes = [
        (f"1 - {home_team} (Victoire)", odds.get('1', 0)),
        ("X - Match Nul", odds.get('X', 0)),
        (f"2 - {away_team} (Victoire)", odds.get('2', 0)),
    ]
    
    for outcome, odd in outcomes:
        if odd > 0:
            implied_prob = (1 / odd) * 100
            prob_color = Colors.GREEN if implied_prob < 50 else Colors.YELLOW if implied_prob < 70 else Colors.RED
            line = f"  {outcome:<25} {odd:<10.2f} {prob_color}{implied_prob:>6.1f}%{Colors.RESET}"
            lines.append(line)
    
    # Bookmaker
    bookmaker = odds.get('bookmaker', 'Unknown')
    lines.append(f"\n  {Colors.DIM}Source: {bookmaker}{Colors.RESET}")
    lines.append('')
    
    return '\n'.join(lines)


def format_prediction_output(prediction, verbose: bool = False) -> str:
    """
    Formate la sortie d'une prédiction.
    
    Args:
        prediction: Objet PredictionResult
        verbose: Afficher les détails complets
        
    Returns:
        Chaîne formatée
    """
    lines = []
    
    # Header du match
    lines.append(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{Colors.CYAN}  🎯 PRÉDICTION: {prediction.home_team} vs {prediction.away_team}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    # Probabilités
    lines.append(f"  {Colors.BOLD}Probabilités calculées:{Colors.RESET}\n")
    
    probs = [
        (f"{prediction.home_team} (Victoire)", prediction.home_win_prob, Colors.GREEN),
        ("Match Nul", prediction.draw_prob, Colors.YELLOW),
        (f"{prediction.away_team} (Victoire)", prediction.away_win_prob, Colors.RED),
    ]
    
    # Trier par probabilité décroissante
    probs.sort(key=lambda x: x[1], reverse=True)
    
    for outcome, prob, color in probs:
        bar_length = int(prob / 2)  # Barre de 50 caractères max
        bar = '█' * bar_length
        lines.append(f"  {outcome:<30} {color}{bar:<50} {prob:>5.1f}%{Colors.RESET}")
    
    lines.append('')
    
    # Buts attendus
    lines.append(f"  {Colors.BOLD}Buts attendus:{Colors.RESET}")
    lines.append(f"    {prediction.home_team}: {prediction.home_goals_expected:.2f}")
    lines.append(f"    {prediction.away_team}: {prediction.away_goals_expected:.2f}")
    lines.append('')
    
    # Confiance
    conf_color = Colors.GREEN if prediction.confidence >= 70 else Colors.YELLOW if prediction.confidence >= 50 else Colors.RED
    lines.append(f"  {Colors.BOLD}Niveau de confiance:{Colors.RESET} {conf_color}{prediction.confidence:.0f}%{Colors.RESET}")
    lines.append('')
    
    # Recommandation
    rec_color = Colors.BRIGHT_GREEN if 'VALUE BET' in prediction.recommendation else Colors.BRIGHT_CYAN
    lines.append(f"  {Colors.BOLD}Recommandation:{Colors.RESET} {rec_color}{prediction.recommendation}{Colors.RESET}")
    lines.append('')
    
    # Analyse EV
    if prediction.ev_analysis:
        lines.append(f"  {Colors.BOLD}Analyse Expected Value (EV):{Colors.RESET}\n")
        
        for outcome, ev_data in prediction.ev_analysis.items():
            ev = ev_data['ev']
            ev_color = Colors.BRIGHT_GREEN if ev > 0 else Colors.RED if ev < 0 else Colors.WHITE
            value_indicator = f" {Colors.BG_GREEN}{Colors.BLACK} VALUE {Colors.RESET}" if ev_data.get('value_bet') else ""
            
            line = f"    {outcome:<30} Cote: {ev_data['odd']:.2f} | Proba: {ev_data['probability']:.1f}% | EV: {ev_color}{ev:+.1f}%{Colors.RESET}{value_indicator}"
            lines.append(line)
        
        lines.append('')
    
    # Facteurs clés
    if prediction.key_factors:
        lines.append(f"  {Colors.BOLD}Facteurs clés:{Colors.RESET}")
        for factor in prediction.key_factors:
            lines.append(f"    {factor}")
        lines.append('')
    
    # Détails verbose
    if verbose and prediction.match_data:
        lines.append(f"  {Colors.BOLD}{Colors.DIM}Détails supplémentaires:{Colors.RESET}\n")
        
        # Forme récente
        home_form = prediction.match_data.get('home_form', [])
        away_form = prediction.match_data.get('away_form', [])
        
        if home_form:
            form_str = ' '.join([m.get('result', '?') for m in home_form[:5]])
            lines.append(f"    Forme {prediction.home_team}: {form_str}")
        
        if away_form:
            form_str = ' '.join([m.get('result', '?') for m in away_form[:5]])
            lines.append(f"    Forme {prediction.away_team}: {form_str}")
        
        # Stats buts
        home_scored = prediction.match_data.get('home_goals_scored_5', 0)
        home_conceded = prediction.match_data.get('home_goals_conceded_5', 0)
        away_scored = prediction.match_data.get('away_goals_scored_5', 0)
        away_conceded = prediction.match_data.get('away_goals_conceded_5', 0)
        
        lines.append(f"    Buts {prediction.home_team} (5 matchs): {home_scored} marqués, {home_conceded} encaissés")
        lines.append(f"    Buts {prediction.away_team} (5 matchs): {away_scored} marqués, {away_conceded} encaissés")
        
        lines.append('')
    
    lines.append(f"{Colors.DIM}{'='*80}{Colors.RESET}\n")
    
    return '\n'.join(lines)


def format_form_string(form_list: List[Dict], max_matches: int = 5) -> str:
    """
    Formate la forme récente en chaîne de caractères.
    
    Args:
        form_list: Liste des matchs récents
        max_matches: Nombre maximum de matchs à afficher
        
    Returns:
        Chaîne formatée (ex: "V V D W L")
    """
    results = []
    for match in form_list[:max_matches]:
        result = match.get('result', '?')
        if result == 'V':
            results.append(f"{Colors.GREEN}V{Colors.RESET}")
        elif result == 'D':
            results.append(f"{Colors.YELLOW}D{Colors.RESET}")
        elif result == 'L':
            results.append(f"{Colors.RED}D{Colors.RESET}")
        else:
            results.append(f"{Colors.DIM}?{Colors.RESET}")
    
    return ' '.join(results)


def calculate_implied_probability(odds: float) -> float:
    """
    Calcule la probabilité implicite à partir des cotes.
    
    Args:
        odds: Cote du bookmaker
        
    Returns:
        Probabilité implicite en pourcentage
    """
    if odds <= 0:
        return 0.0
    return (1 / odds) * 100


def calculate_ev(probability: float, odds: float) -> float:
    """
    Calcule l'Expected Value (EV) d'un pari.
    
    Formula: EV = (Probability * Odds) - 1
    
    Args:
        probability: Probabilité estimée (0-1)
        odds: Cote du bookmaker
        
    Returns:
        EV en pourcentage
    """
    if odds <= 0:
        return -1.0
    ev = (probability * odds) - 1
    return ev * 100


def find_value_bets(probabilities: Dict[str, float], odds: Dict[str, float],
                    threshold: float = 0.05) -> List[Dict]:
    """
    Identifie les value bets (EV positif).
    
    Args:
        probabilities: Dictionnaire des probabilités estimées
        odds: Dictionnaire des cotes
        threshold: Seuil minimum d'EV pour considérer comme value bet
        
    Returns:
        Liste des value bets identifiés
    """
    value_bets = []
    
    for outcome, prob in probabilities.items():
        odd = odds.get(outcome, 0)
        if odd > 0:
            ev = calculate_ev(prob, odd)
            if ev > threshold * 100:  # Convertir threshold en pourcentage
                value_bets.append({
                    'outcome': outcome,
                    'probability': prob * 100,
                    'odds': odd,
                    'ev': ev,
                    'implied_prob': calculate_implied_probability(odd)
                })
    
    # Trier par EV décroissant
    value_bets.sort(key=lambda x: x['ev'], reverse=True)
    
    return value_bets


def normalize_probabilities(probs: Dict[str, float]) -> Dict[str, float]:
    """
    Normalise un dictionnaire de probabilités pour que la somme = 1.
    
    Args:
        probs: Dictionnaire des probabilités brutes
        
    Returns:
        Dictionnaire normalisé
    """
    total = sum(probs.values())
    if total == 0:
        return {k: 1/len(probs) for k in probs}
    return {k: v / total for k, v in probs.items()}


def fuzzy_match_team_name(team_name: str, candidates: List[str]) -> Optional[str]:
    """
    Recherche floue d'un nom d'équipe dans une liste de candidats.
    
    Args:
        team_name: Nom recherché
        candidates: Liste des noms possibles
        
    Returns:
        Meilleur candidat ou None
    """
    team_lower = team_name.lower()
    
    # Recherche exacte d'abord
    for candidate in candidates:
        if candidate.lower() == team_lower:
            return candidate
    
    # Recherche partielle
    for candidate in candidates:
        cand_lower = candidate.lower()
        if team_lower in cand_lower or cand_lower in team_lower:
            return candidate
    
    # Recherche par mots
    team_words = set(team_lower.split())
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        cand_words = set(candidate.lower().split())
        common = team_words & cand_words
        score = len(common) / max(len(team_words), len(cand_words))
        
        if score > best_score and score > 0.5:
            best_score = score
            best_match = candidate
    
    return best_match


def save_json(data: Any, filepath: str, indent: int = 2):
    """
    Sauvegarde des données en JSON.
    
    Args:
        data: Données à sauvegarder
        filepath: Chemin du fichier
        indent: Indentation JSON
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)


def load_json(filepath: str) -> Any:
    """
    Charge des données depuis un fichier JSON.
    
    Args:
        filepath: Chemin du fichier
        
    Returns:
        Données chargées
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_datetime(dt: datetime, format_str: str = "%d/%m/%Y %H:%M") -> str:
    """
    Formate un datetime en chaîne lisible.
    
    Args:
        dt: Objet datetime
        format_str: Format de sortie
        
    Returns:
        Chaîne formatée
    """
    return dt.strftime(format_str)


def parse_datetime(date_str: str) -> Optional[datetime]:
    """
    Parse une chaîne de date en datetime.
    
    Args:
        date_str: Chaîne de date (ISO format ou autre)
        
    Returns:
        Objet datetime ou None
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Essayer ISO format avec timezone
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        pass
    
    return None
