# ⚽ Footy Predictor CLI

Applicazione CLI in Python per analizzare le partite di calcio: statistiche
dettagliate delle squadre, predizioni pre-partita e picks di scommessa basati su
modelli statistici, con quote reali dai bookmaker.

Consuma le API di [API-Football](https://www.api-football.com/) (api-sports.io).

---

## 🎯 Funzionalità

- **Menu interattivo** — scegli campionato → scegli partita → analisi completa.
- **Statistiche avanzate** — gol, cartellini, clean sheet, forma, Under/Over,
  confronto casa/trasferta.
- **Analyzer modulari** — mercati gol, tiri, corner, cartellini, risultato (1X2),
  risultato esatto, coordinati da un orchestrator a plugin.
- **Quote reali** — recupero multi-bookmaker via `core/odds_fetcher.py`
  (vedi [`docs/ODDS_FETCHER.md`](docs/ODDS_FETCHER.md)).
- **Edge & Kelly** — `core/edge_calculator.py`: edge vs quota, Expected Value,
  Kelly frazionato.
- **Backtesting rigoroso** — validazione dei modelli su stagioni storiche
  (vedi [`backtest/README.md`](backtest/README.md)).

---

## 🛠 Installazione

Prerequisiti: **Python 3.11+** e una **API key** di API-Football.

```bash
git clone <repository-url>
cd footy-predictor

pip install -r requirements.txt      # dipendenze runtime
cp env.example .env                  # poi inserisci la tua API key
```

### Configurazione (`.env`)

```env
API_FOOTBALL_KEY=la_tua_chiave        # obbligatoria
API_FOOTBALL_BASE=https://v3.football.api-sports.io
DEFAULT_COUNTRY=Italy
DEFAULT_LEAGUE=Serie A
DEFAULT_SEASON=2025

# Redis (cache). Se non raggiungibile, il sistema va in "offline mode" senza crash.
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=none
REDIS_SSL=true
REDIS_DB=0
```

> I campi `API_FOOTBALL_KEY`, `REDIS_HOST` e `REDIS_PASSWORD` devono esistere nel
> `.env`; per il solo backtest Redis non serve davvero (basta un valore
> segnaposto, la cache va in offline mode).

---

## 🚀 Utilizzo

```bash
python main.py interactive     # 🎯 Menu guidato (RACCOMANDATO)
python main.py matchday        # analizza la prossima giornata
python main.py config          # mostra la configurazione corrente
```

| Comando | Descrizione |
|---|---|
| `interactive` | Menu: scegli campionato e partita, poi analisi completa |
| `matchday` | Analizza tutte le partite della prossima giornata |
| `config` | Mostra la configurazione corrente |
| `cache` | Statistiche della cache Redis |
| `bookmakers` | Elenca i bookmaker disponibili |
| `bets` | Elenca i mercati di scommessa disponibili |
| `players` | Statistiche giocatori presenti in cache |

Opzioni per `matchday`:

```bash
python main.py matchday --league "Serie A" --country "Italy" --season 2025
python main.py matchday -l "Premier League" -c "England" -s 2025
```

> **Nota leghe:** di default è abilitata **solo la Serie A** (`config/leagues.py`).
> Le altre (Premier, Liga, Bundesliga, Ligue 1, coppe) si riattivano impostando
> `enabled=True` nella rispettiva `LeagueConfig`.

---

## 🏗 Struttura del progetto

```
footy-predictor/
├── main.py               # entry point → cli/simple_main.py (router argv)
├── cli/                  # router comandi, menu interattivo, display
├── adapters/             # client API-Football (http, football_api, odds_api,
│                         #   roster/stats/live services)
├── analyzers/            # analyzer di mercato + orchestrator plugin registry
├── betting/              # BettingOrchestrator (coordina gli analyzer)
├── core/                 # config, models, edge_calculator, odds_fetcher,
│                         #   pick_selector, daily_league_analyzer, ...
├── config/               # leagues.py (leghe supportate)
├── database/             # db_manager + schema.sql (storico giocatori, SQLite)
├── services/             # data_service
├── utils/                # redis_cache e utilità varie
├── backtest/             # backtesting dei modelli (README dedicato)
├── tests/                # suite pytest
├── docs/                 # documentazione aggiuntiva
├── requirements.txt      # dipendenze runtime
├── requirements-dev.txt  # dipendenze di test
├── pytest.ini
└── .github/workflows/    # CI (GitHub Actions)
```

Aggiungere una funzionalità: modelli in `core/models.py`, logica API in
`adapters/`, analisi in `analyzers/`, display in `cli/`, comandi in
`cli/simple_main.py`.

---

## 🧪 Test & CI

```bash
pip install -r requirements-dev.txt
pytest -p no:pytest_anchorpy
```

> Il flag `-p no:pytest_anchorpy` disabilita un plugin globale rotto presente in
> alcuni ambienti locali; nella CI (ambiente pulito) non è necessario.

La CI GitHub Actions gira la suite su Python 3.11 e 3.12 con coverage.

---

## 🔬 Backtesting & ricerca modelli

Il pacchetto [`backtest/`](backtest/README.md) valida i modelli predittivi su
stagioni storiche reali, con replay **point-in-time** privo di data-leakage e
metriche (Brier, Brier Skill, RPS, calibrazione).

Sintesi dei risultati fin qui (5 leghe, ~3000 partite):

- I mercati **Over/Under e BTTS** non mostrano edge sfruttabile coi soli gol
  storici (limite noto del Poisson: sovradispersione).
- Il **1X2** è l'unico mercato con segnale reale; il miglior modello gratuito
  (multi-stagione + shrinkage + fattore campo globale) raggiunge **RPS ~0.19–0.21**,
  livello dei modelli accademici avanzati.
- Prossimo salto: **Expected Goals (xG)** e tracking del **Closing Line Value**
  (richiedono un tier dati a pagamento).

Dettagli, comandi ed esiti completi in [`backtest/README.md`](backtest/README.md).

---

## 🔗 Link utili

- [API-Football — documentazione v3](https://www.api-football.com/documentation-v3)
- [Rich](https://rich.readthedocs.io/) · [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
