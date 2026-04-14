#!/usr/bin/env python3
"""
BetIntel CLI - Interface en ligne de commande pour les prédictions et cotes football

Usage:
    python cli.py search "PSG"                    # Rechercher un match par équipe
    python cli.py predict "PSG" "Liverpool"       # Prédiction pour un match spécifique
    python cli.py list --date today               # Lister les matchs du jour
    python cli.py odds "PSG" "Liverpool"          # Afficher les cotes
"""

import argparse
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from predictor import MatchPredictor
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from utils import format_match_table, format_odds_table, format_prediction_output

class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'


def setup_parser() -> argparse.ArgumentParser:
    """Configure l'argument parser principal."""
    parser = argparse.ArgumentParser(
        prog='betintel',
        description='🎯 BetIntel CLI - Prédictions et cotes football en temps réel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s search "PSG"                    Rechercher les matchs du PSG
  %(prog)s predict "PSG" "Liverpool"       Prédiction pour PSG vs Liverpool
  %(prog)s list --date today               Lister les matchs d'aujourd'hui
  %(prog)s odds "PSG" "Liverpool"          Afficher les cotes du match
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # Commande: search
    search_parser = subparsers.add_parser(
        'search',
        help='Rechercher un match par nom d\'équipe'
    )
    search_parser.add_argument(
        'team',
        type=str,
        help='Nom de l\'équipe à rechercher'
    )
    search_parser.add_argument(
        '--date',
        type=str,
        default='today',
        help='Date des matchs (today, tomorrow, YYYY-MM-DD)'
    )
    search_parser.add_argument(
        '--league',
        type=str,
        help='Filtrer par ligue (premier_league, la_liga, etc.)'
    )
    
    # Commande: predict
    predict_parser = subparsers.add_parser(
        'predict',
        help='Prédiction pour un match spécifique'
    )
    predict_parser.add_argument(
        'home_team',
        type=str,
        help='Nom de l\'équipe à domicile'
    )
    predict_parser.add_argument(
        'away_team',
        type=str,
        help='Nom de l\'équipe à l\'extérieur'
    )
    predict_parser.add_argument(
        '--date',
        type=str,
        help='Date du match (YYYY-MM-DD)'
    )
    predict_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Afficher les détails complets de la prédiction'
    )
    
    # Commande: list
    list_parser = subparsers.add_parser(
        'list',
        help='Lister les matchs disponibles'
    )
    list_parser.add_argument(
        '--date',
        type=str,
        default='today',
        help='Date des matchs (today, tomorrow, YYYY-MM-DD)'
    )
    list_parser.add_argument(
        '--league',
        type=str,
        help='Filtrer par ligue'
    )
    list_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Nombre maximum de matchs à afficher'
    )
    
    # Commande: odds
    odds_parser = subparsers.add_parser(
        'odds',
        help='Afficher les cotes d\'un match'
    )
    odds_parser.add_argument(
        'home_team',
        type=str,
        help='Nom de l\'équipe à domicile'
    )
    odds_parser.add_argument(
        'away_team',
        type=str,
        help='Nom de l\'équipe à l\'extérieur'
    )
    odds_parser.add_argument(
        '--bookmaker',
        type=str,
        help='Filtrer par bookmaker spécifique'
    )
    
    # Commande: live
    live_parser = subparsers.add_parser(
        'live',
        help='Afficher les matchs en direct'
    )
    live_parser.add_argument(
        '--league',
        type=str,
        help='Filtrer par ligue'
    )
    
    return parser


def parse_date(date_str: str) -> str:
    """Parse une chaîne de date et retourne le format YYYY-MM-DD."""
    if date_str.lower() == 'today':
        return datetime.now().strftime('%Y-%m-%d')
    elif date_str.lower() == 'tomorrow':
        return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        # Vérifier le format YYYY-MM-DD
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            print(f"{Colors.RED}❌ Format de date invalide. Utilisez: today, tomorrow, ou YYYY-MM-DD{Colors.RESET}")
            sys.exit(1)


def cmd_search(args) -> int:
    """Exécute la commande search."""
    print(f"\n{Colors.CYAN}🔍 Recherche des matchs pour: {args.team}{Colors.RESET}\n")
    
    date = parse_date(args.date)
    predictor = MatchPredictor()
    
    matches = predictor.search_matches(args.team, date, args.league)
    
    if not matches:
        print(f"{Colors.YELLOW}⚠️ Aucun match trouvé pour '{args.team}' le {date}{Colors.RESET}")
        return 1
    
    print(format_match_table(matches, title=f"Matchs trouvés ({len(matches)})"))
    return 0


def cmd_predict(args) -> int:
    """Exécute la commande predict."""
    print(f"\n{Colors.CYAN}🎯 Analyse du match: {args.home_team} vs {args.away_team}{Colors.RESET}\n")
    
    predictor = MatchPredictor()
    
    # Récupérer ou simuler les données du match
    match_data = predictor.get_match_data(args.home_team, args.away_team, args.date)
    
    if not match_data:
        print(f"{Colors.YELLOW}⚠️ Match non trouvé. Vérifiez les noms des équipes.{Colors.RESET}")
        return 1
    
    # Calculer la prédiction
    prediction = predictor.predict(match_data)
    
    # Afficher le résultat
    print(format_prediction_output(prediction, verbose=args.verbose))
    
    return 0


def cmd_list(args) -> int:
    """Exécute la commande list."""
    date = parse_date(args.date)
    print(f"\n{Colors.CYAN}📅 Matchs du {date}{Colors.RESET}\n")
    
    predictor = MatchPredictor()
    matches = predictor.get_matches_for_date(date, args.league, limit=args.limit)
    
    if not matches:
        print(f"{Colors.YELLOW}⚠️ Aucun match trouvé pour cette date{Colors.RESET}")
        return 1
    
    print(format_match_table(matches, title=f"Matchs du {date} ({len(matches)} trouvés)"))
    return 0


def cmd_odds(args) -> int:
    """Exécute la commande odds."""
    print(f"\n{Colors.CYAN}💰 Cotes pour: {args.home_team} vs {args.away_team}{Colors.RESET}\n")
    
    predictor = MatchPredictor()
    match_data = predictor.get_match_data(args.home_team, args.away_team)
    
    if not match_data or not match_data.get('odds'):
        print(f"{Colors.YELLOW}⚠️ Cotes non disponibles pour ce match{Colors.RESET}")
        return 1
    
    print(format_odds_table(match_data['odds'], args.home_team, args.away_team))
    
    # Afficher l'EV si disponible
    if 'ev_analysis' in match_data:
        print(f"\n{Colors.CYAN}📊 Analyse EV (Expected Value):{Colors.RESET}")
        for outcome, ev_data in match_data['ev_analysis'].items():
            ev_color = Colors.GREEN if ev_data['ev'] > 0 else Colors.RED if ev_data['ev'] < 0 else Colors.YELLOW
            print(f"  {outcome}: {ev_color}EV = {ev_data['ev']:+.2f}%{Colors.RESET} (Probabilité: {ev_data['probability']:.1f}%)")
    
    return 0


def cmd_live(args) -> int:
    """Exécute la commande live."""
    print(f"\n{Colors.CYAN}⚽ Matchs en direct{Colors.RESET}\n")
    
    predictor = MatchPredictor()
    live_matches = predictor.get_live_matches(args.league)
    
    if not live_matches:
        print(f"{Colors.YELLOW}⚠️ Aucun match en cours{Colors.RESET}")
        return 1
    
    print(format_match_table(live_matches, title=f"Matchs en direct ({len(live_matches)})", show_score=True))
    return 0


def main() -> int:
    """Point d'entrée principal."""
    parser = setup_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Dispatcher vers la commande appropriée
    commands = {
        'search': cmd_search,
        'predict': cmd_predict,
        'list': cmd_list,
        'odds': cmd_odds,
        'live': cmd_live,
    }
    
    try:
        return commands[args.command](args)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ Interrompu par l'utilisateur{Colors.RESET}")
        return 130
    except Exception as e:
        print(f"{Colors.RED}❌ Erreur: {e}{Colors.RESET}")
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
