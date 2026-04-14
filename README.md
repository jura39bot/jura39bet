# BetIntel — Sports Betting Intelligence

## Mission

Produce premium predictive analysis and value bet reports on football, tennis, basketball, road cycling, and MotoGP. Delivered automatically to subscribers before every match day.

## Project Structure

```
betintel/
├── README.md           — This file
├── reports/            — Final reports delivered to subscribers
│   └── SAMPLE_REPORT.md
├── data/               — Raw scraped data from sources
│   └── SAMPLE_DATA.json
├── models/             — EV calculation outputs and model results
│   └── SAMPLE_MODEL_OUTPUT.json
├── website/            — Static website files
│   └── index.html
└── config/             — Configuration files
    └── leagues.json
```

## Pipeline

1. **Data Analyst** → scrapes Sofascore, FBref, OddsPortal → outputs to `data/`
2. **Model Agent** → calculates EV, identifies value bets → outputs to `models/`
3. **Writer** → writes readable reports → outputs to `reports/`
4. **QA Agent** → reviews reports before publish
5. **Publisher** → sends approved reports via email/Telegram

## Coverage

- **Priority 1 (Football):** Premier League, La Liga, Serie A, Ligue 1
- **Priority 2:** ATP/WTA tennis, NBA/EuroLeague basketball, road cycling, MotoGP

## Quality Standards

- Minimum +5% EV threshold for value bets
- All odds must be < 24h old
- Every pick: match, market, selection, odds, model probability, EV%
- Zero tolerance for fabricated data
