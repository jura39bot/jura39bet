# BetIntel CLI

Interface en ligne de commande pour obtenir les prédictions et cotes des matchs de football.

## Installation

```bash
# Cloner le repo
git clone https://github.com/jura39bot/jura39bet.git
cd jura39bet

# Installer les dépendances
pip install -r requirements.txt
```

## Utilisation

### Commandes disponibles

```bash
# Rechercher un match par équipe
python cli.py search "PSG"

# Prédiction pour un match spécifique
python cli.py predict "PSG" "Liverpool"
python cli.py predict "PSG" "Liverpool" --verbose  # Détails complets

# Lister les matchs du jour
python cli.py list --date today
python cli.py list --date tomorrow
python cli.py list --date 2026-04-15

# Afficher les cotes d'un match
python cli.py odds "PSG" "Liverpool"

# Afficher les matchs en direct
python cli.py live
```

### Options globales

- `--date` : Spécifier une date (today, tomorrow, YYYY-MM-DD)
- `--league` : Filtrer par ligue
- `--verbose, -v` : Afficher les détails complets
- `--limit` : Limiter le nombre de résultats

## Structure du projet

```
betintel/
├── cli.py              # Interface CLI principale
├── predictor.py        # Module de prédiction
├── utils.py            # Fonctions utilitaires
├── data/
│   ├── __init__.py
│   └── merge.py        # Fusion des données Sofascore + OddsPortal
├── scrapers/
│   ├── sofascore.py    # Scraper Sofascore
│   └── oddsportal.py   # Scraper OddsPortal
└── config/
    └── sources.json    # Configuration des sources
```

## Algorithme de prédiction

Le prédicteur utilise plusieurs facteurs pondérés :

1. **Forme récente (35%)** : Résultats des 5 derniers matchs
2. **H2H historique (25%)** : Historique des confrontations directes
3. **Stats de buts (25%)** : Buts marqués/encaissés
4. **Avantage domicile (15%)** : Bonus pour l'équipe à domicile

### Calcul de l'Expected Value (EV)

```
EV = (Probabilité estimée × Cote) - 1
```

Un EV positif (>5%) indique une value bet potentielle.

## Exemple de sortie

```
================================================================================
  🎯 PRÉDICTION: PSG vs Liverpool
================================================================================

  Probabilités calculées:

  PSG (Victoire)                 ████████████████████                    45.2%
  Match Nul                      ████████████                            28.4%
  Liverpool (Victoire)           ████████████                            26.4%

  Buts attendus:
    PSG: 1.85
    Liverpool: 1.12

  Niveau de confiance: 75%

  Recommandation: VALUE BET: 1 (Victoire Domicile) (EV: +12.5%)

  Analyse Expected Value (EV):
    1 (Victoire Domicile)        Cote: 2.10 | Proba: 45.2% | EV: +12.5% [VALUE]
    X (Match Nul)                Cote: 3.40 | Proba: 28.4% | EV: -3.4%
    2 (Victoire Extérieur)       Cote: 3.80 | Proba: 26.4% | EV: +0.3%

  Facteurs clés:
    ✅ PSG en excellente forme (4/5 victoires)
    ⚠️ Liverpool en mauvaise forme (1/5 victoires)
    📊 PSG domine l'historique H2H
    ⚽ PSG très offensif (12 buts en 5 matchs)

================================================================================
```

## Notes

- Les données sont fusionnées depuis Sofascore (stats) et OddsPortal (cotes)
- Le scraping doit être exécuté avant d'utiliser la CLI pour obtenir des données fraîches
- Les prédictions sont basées sur des modèles statistiques et ne garantissent pas les résultats
