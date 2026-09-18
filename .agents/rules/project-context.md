# ⚽ Footy Predictor — Mappa del Progetto

## Struttura Moduli Python

```text
footy-predictor/
├── main.py                          # Entry point CLI (chiama cli/simple_main.py)
├── cli/                             # Interfaccia terminale con Rich
│   ├── simple_main.py               # Router degli argomenti (interactive, matchday, config, etc.)
│   ├── interactive_menu.py          # Menu navigabile campionato/partita
│   ├── daily_display.py             # Visualizzazione giornata e quote reali
│   └── match_display.py             # Telemetria statistica del singolo match
├── core/                            # Logica di business e modelli quantitativi
│   ├── config.py                    # Impostazioni globali Pydantic
│   ├── models.py                    # Dataclass e modelli Pydantic
│   ├── edge_calculator.py           # Calcolo edge, Expected Value ed Kelly Criterion
│   ├── odds_fetcher.py              # Recupero quote multi-bookmaker (vedi docs/ODDS_FETCHER.md)
│   ├── pick_selector.py             # Selezione dei value picks
│   ├── daily_league_analyzer.py     # Orchestrazione analisi campionato
│   └── bookmaker_manager.py         # Mappatura e priorità bookmaker
├── analyzers/                       # Plugin analyzers modulari di mercato
│   ├── base.py                      # Interfaccia BaseAnalyzer
│   ├── result_analyzer.py           # Analisi 1X2
│   ├── goals_analyzer.py            # Under/Over e BTTS
│   ├── cards_analyzer.py            # Cartellini totali squadra
│   ├── corners_analyzer.py          # Corner totali
│   ├── shots_analyzer.py            # Tiri in porta
│   ├── score_analyzer.py            # Risultato esatto
│   └── player_cards_analyzer.py     # Cartellini per singolo giocatore
├── betting/                         # Orchestrazione strategie di scommessa
│   └── orchestrator.py              # BettingOrchestrator (collega analyzer e odds)
├── adapters/                        # Client verso API-Football (v3 REST)
│   ├── http_client.py               # Client HTTP con retry e backoff
│   ├── football_api.py              # Endpoint fixtures, stats, roster
│   ├── odds_api.py                  # Endpoint quote e mapping scommesse
│   ├── live_service.py              # Servizio dati live
│   └── roster_service.py            # Formazioni e rose
├── backtest/                        # Framework di backtesting point-in-time
│   ├── engine.py                    # Replay cronologico anti-leakage
│   ├── models.py                    # Modelli baseline, Poisson e Dixon-Coles
│   ├── advanced.py                  # Modello multi-stagione + time decay + bayesian shrinkage
│   ├── glicko.py                    # Glicko-2 soccer rating model
│   ├── ensemble.py                  # Modello ensemble Poisson/Glicko
│   ├── metrics.py                   # RPS, Brier Score, Brier Skill Score, calibrazione
│   ├── ablation.py                  # Test di ablazione componenti
│   ├── clv.py                       # Closing Line Value analysis
│   └── bankroll.py                  # Simulazione bankroll e drawdown
├── database/                        # Persistenza SQLite
│   ├── db_manager.py                # Gestore SQLite per player_history.db
│   └── schema.sql                   # Schema per storico cartellini/presenze
├── services/                        # Servizi di coordinamento dati
│   └── data_service.py
└── utils/                           # Utilità di caching e logging
    └── redis_cache.py               # Cache Redis con graceful offline fallback
```

---

## Struttura Web Client (`web/`)

Applicazione Next.js 16 con architettura **Tactical Match Telemetry** (CRT/Brutalista):

```text
web/
├── app/                             # Next.js App Router
│   ├── layout.tsx                   # Substrate scuro, scanline overlay, font imports
│   ├── page.tsx                     # Dashboard telemetrica principale
│   ├── globals.css                  # Token @theme Tailwind v4, CRT scanlines, zero-radius
│   └── types.ts                     # Tipi TypeScript speculari ai modelli Pydantic
├── public/                          # Asset statici e JSON sincronizzati
├── scripts/
│   └── sync-data.mjs                # Pipeline sync dai dati generati da Python
├── package.json                     # Next.js 16, React 19, Tailwind v4
└── tsconfig.json                    # Strict TypeScript configuration
```

---

## Documentazione Tecnica (`docs/`)

| File | Contenuto |
|---|---|
| [`docs/AI_AGENT_ARCHITECTURE.md`](file:///Users/sireg/Documents/Projects/footy-predictor/docs/AI_AGENT_ARCHITECTURE.md) | Architettura, permessi, e governance a 3 livelli degli agenti |
| [`docs/AGENT_PERSONAS.md`](file:///Users/sireg/Documents/Projects/footy-predictor/docs/AGENT_PERSONAS.md) | 6 prompt operativi completi e 14 lezioni trasversali di regia |
| [`docs/ODDS_FETCHER.md`](file:///Users/sireg/Documents/Projects/footy-predictor/docs/ODDS_FETCHER.md) | Architettura odds fetcher, mapping mercati e multi-bookmaker |
| [`docs/UI_SYSTEM.md`](file:///Users/sireg/Documents/Projects/footy-predictor/docs/UI_SYSTEM.md) | Design system Tactical Match Telemetry, token e variabili CSS |
| [`backtest/README.md`](file:///Users/sireg/Documents/Projects/footy-predictor/backtest/README.md) | Guida al backtest, modelli Dixon-Coles/Poisson, garanzia point-in-time |

---

## Numeri di Riferimento

- **148 test pytest** (`pytest -p no:pytest_anchorpy` — 100% passanti)
- **0 errori TypeScript** (`./web/node_modules/.bin/tsc --project web/tsconfig.json --noEmit`)
- **0 warning linter** (`npm --prefix web run lint`)
- **Metriche benchmark 1X2**: RPS ~0.19–0.21 con modello `advanced.py` (multi-stagione + shrinkage)
