# 📚 ODDS FETCHER MODULE

## 🎯 Obiettivo

Il modulo **OddsFetcher** gestisce il recupero automatico delle quote reali dai bookmaker disponibili nelle API di api-football, arricchendo i nostri picks con informazioni reali di mercato.

---

## 🏗️ Architettura

### File Principali

1. **`core/odds_fetcher.py`** - Modulo principale per fetching quote
2. **`adapters/odds_api.py`** - Client API per comunicazione con api-football
3. **`core/daily_league_analyzer.py`** - Integrazione nel flusso di analisi
4. **`cli/daily_display.py`** - Visualizzazione quote nel terminale

---

## 🔧 Funzionalità

### 1. **Multi-Bookmaker Support**
- ✅ Non si limita a Bet365
- ✅ Cerca quote su **TUTTI** i bookmaker disponibili
- ✅ Preferisce bookmaker prioritari (Bet365, Bwin, William Hill, Betfair)
- ✅ Fallback automatico se bookmaker preferito non ha il mercato

### 2. **Mapping Mercati -> Bet ID (verificato)**
SSOT: `core/odds_markets.py`. Ogni id e' stato verificato su un payload reale
(`/odds?fixture=1550128`, AS Roma-Inter, Serie A 2026). Mercato senza id verificato = **nessuna quota**
(meglio niente che una quota sbagliata), con un solo warning per mercato per run.

| Nostro Mercato | Bet ID | Nome API |
|---|---|---|
| Match Result | 1 | Match Winner |
| Match Goals | 5 | Goals Over/Under |
| Both Teams to Score | 8 | Both Teams Score |
| Exact Score | 10 | Exact Score |
| Double Chance | 12 | Double Chance |
| Total Corners | 45 | Corners Over Under |
| Total Cards | 80 | Cards Over/Under |
| Total Shots | 211 | Total Shots |
| Total Shots on Goal | 87 | Total ShotOnGoal |
| `<Squadra> Corners` | 57 casa / 58 trasferta | Home/Away Corners Over/Under |
| `<Squadra> Cards` | 82 casa / 83 trasferta | Home/Away Team Total Cards |
| `<Squadra> Goals` | 16 casa / 17 trasferta | Total - Home / Total - Away |
| `<Squadra> Shots`, `<Squadra> Shots on Goal` | nessuno | esistono solo quote per GIOCATORE (240/241/269/275/276) |
| `Player Card - <nome>` | 102 / 251 | Player to be booked (vedi sotto) |

**Correzioni rispetto alla versione precedente** (id sbagliati, verificati sul payload): Corners totali
era 12 (in realta' "Double Chance"; corretto 45), Cards totali era 11 ("Highest Scoring Half"; corretto 80),
Exact Score era 6 ("Goals Over/Under First Half"; corretto 10). I mercati per squadra cadevano sugli id dei
totali; ora usano l'id per-squadra. Il lato (casa/trasferta) si ricava con una chiamata `/fixtures?id=`
(cache in-process) confrontando il nome squadra del pick con quello della partita.

### 2b. **Priorita' bookmaker (regola 11)**
`BOOKMAKER_PRIORITY = (8, 6, 7, 3)` = Bet365, Bwin, William Hill, Betfair. La quota assegnata al pick e'
quella del primo bookmaker della lista che quota la selezione; solo se nessuno dei 4 la quota si usa il primo
bookmaker disponibile nel payload. Mai mescolare fornitori: ogni `MarketOdds` porta nome e id del
bookmaker reale. La miglior quota di mercato resta solo un log informativo. (Bug corretto: la lista
precedente `[8, 6, 5, 3]` conteneva l'id 5 = SBO invece di William Hill = 7.)

### 3. **Cache Intelligente**
- ✅ Cache `core/odds_cache.py`: dict in-process + Redis, TTL 600s controllato in lettura (timestamp nel valore)
- ✅ Redis spento o che solleva eccezioni = solo cache in memoria, mai crash
- ✅ Riduce chiamate API ripetute
- ✅ Quote sempre aggiornate

### 4. **Rate Limiting**
- ✅ Batch processing (`BATCH_SIZE = 5`, pausa `BATCH_PAUSE_SECONDS = 1.0` tra batch)
- ✅ Delay tra richieste per rispettare limiti API
- ✅ Gestione errori graceful

---

## 📊 Flusso di Lavoro

```
1. ANALISI PARTITE
   ↓
2. GENERAZIONE PICKS (senza quote)
   ↓
3. INIZIALIZZAZIONE ODDS FETCHER
   ↓
4. FETCH QUOTE PER OGNI PICK
   │
   ├─→ Prova bookmaker preferiti
   │   └─→ Bet365, Bwin, William Hill...
   │
   └─→ Se non trovato: cerca su TUTTI i bookmaker
       └─→ Ritorna prima quota disponibile
   ↓
5. ENRICHMENT PICKS
   ↓
6. DISPLAY CON QUOTE REALI
```

---

## 💻 Utilizzo

### Inizializzazione

```python
from core.odds_fetcher import OddsFetcher

fetcher = OddsFetcher()
await fetcher.initialize()
```

### Recupero Quote Singolo Mercato

```python
odds = await fetcher.get_odds_for_market(
    fixture_id=1234567,
    market="Match Goals",
    selection="Over 2.5"
)

if odds:
    print(f"Bookmaker: {odds.bookmaker_name}")
    print(f"Odds: {odds.odds}")
```

### Recupero Quote Multiple (Batch)

```python
picks = [
    ("Match Goals", "Over 2.5"),
    ("Both Teams to Score", "Yes"),
    ("Match Result", "Home Win"),
]

results = await fetcher.get_odds_for_multiple_picks(fixture_id, picks)

for key, odds in results.items():
    if odds:
        print(f"{key}: {odds.odds} ({odds.bookmaker_name})")
```

---

## 🎨 Output Esempio

```
💰 Recupero quote reali per 50 picks da bookmaker...
======================================================================
✅ Match Goals: Over 2.5 → 1.85 (Bet365)
✅ Both Teams to Score: Yes → 1.70 (William Hill)
✅ Total Corners: Over 9.5 → 1.95 (Bwin)
❌ Total Shots: Over 20.5 → Non disponibile
✅ Match Result: Home Win → 2.10 (Bet365)
...
======================================================================
📊 RIEPILOGO QUOTE:
   ✅ Quote trovate: 42/50
   ❌ Quote mancanti: 8/50

⚠️ Mercati senza quote disponibili:
   • Total Shots
   • Team Shots on Goal
   • Player Cards
======================================================================
```

---

## 📱 Display nei Picks

Le quote vengono mostrate automaticamente nell'analisi daily:

```
1. 🏟️  AS Roma vs Inter  │  📅 Sabato 18/10/2025 ⏰ 20:45
──────────────────────────────────────────────────────────────
   Pick 1: 🔥 Match Goals: Over 2.5
           💰 Quota: 1.85 (Bet365) │ 🔴 80.1%
           💬 Attesi 4.0 gol: 80.0% over 2.5

   Pick 2: 🔥 Both Teams to Score: Yes
           💰 Quota: 1.70 (William Hill) │ 🟠 66.7%
           💬 Entrambe con buon attacco: 66.7% BTTS
```

---

## ⚙️ Configurazione

### Bookmaker Prioritari

Modifica in `core/odds_markets.py`:

```python
from core.odds_markets import BOOKMAKER_PRIORITY  # (8, 6, 7, 3) Bet365, Bwin, William Hill, Betfair
```

### Cache TTL

```python
ODDS_CACHE_TTL = 600  # 10 minuti (in secondi), core/odds_markets.py
```

### Batch Size

```python
BATCH_SIZE = 5  # Richieste parallele per batch, core/odds_markets.py
```

---

## 🚨 Limitazioni Attuali

- ❌ Tiri per squadra (`<Squadra> Shots`, `<Squadra> Shots on Goal`): nessun bet id di squadra nell'API.
- ⚠️ `Total Shots` (211) e `Total Shots on Goal` (87) esistono solo su alcuni bookmaker (Bet365, 1xBet, Betano).
- ⚠️ Mercati per squadra: Bet365 e Betano hanno 82/83 (cards); i corner per squadra (57/58) sono su Bet365, Marathonbet, Pinnacle, 1xBet, Betano. William Hill/Bwin/Betfair spesso non li quotano: allora scatta il fallback.
- ⚠️ **Player to be booked (102/251)**: audit del 18/09/2026 su 3 partite Serie A NS (1550133, 1550128, 1550132), entrambi gli id: `results: 0`, e il payload `/odds?fixture=` completo (Bet365, William Hill, Marathonbet, Betfair, BetVictor, Pinnacle, SBO, 1xBet, Betano) non contiene ne' 102 ne' 251. Il mercato non e' quotato a 1-2 giorni dal calcio d'inizio; potrebbe comparire piu' vicino alla partita. Il parser (`core/odds_player_booked.py`) e' quindi costruito su una struttura **ipotizzata**, tollerante: `"Nome - Yes"`, `"Nome - No"`, `"Nome"` (vedi la fixture sintetica `tests/fixtures/odds_player_booked_synthetic.json`, marcata `synthetic`). Da verificare su un payload reale appena disponibile.

---

## 🧾 Audit payload reale (18/09/2026)

Chiamate API usate: 15. Bet id 102 e 251 esistono entrambi in `/odds/bets` con nome "Player to be booked".

Struttura `/odds` (verificata): `response[0].bookmakers[] = {id, name, bets[] = {id, name, values[] = {value, odd}}}`,
`odd` e' una stringa. Esempio reale di un mercato giocatore esistente (Bet365, bet 266 "Player Fouls Committed"):
`{"value": "Leonardo Balerdi - 1", "odd": "1.30"}` (nome in chiaro con accenti, nome completo, non iniziale).

Bookmaker con id (dal payload): 8 Bet365, 7 William Hill, 3 Betfair, 2 Marathonbet, 36 BetVictor, 4 Pinnacle, 5 SBO, 11 1xBet, 32 Betano. Bwin (6) non presente nelle partite ispezionate.

Valori: mercati over/under -> `"Over 4.5"` / `"Under 4.5"`; le linee possono essere intere (`"Over 9"`).

### Statistiche giocatore (`/players?team=&season=`, per il roster fallback)
- Una entry `statistics[]` PER COMPETIZIONE (es. Champions League id 2 + Serie A id 135): vanno sommate solo quelle campionato (`config/leagues.py`, `is_cup=False`) della squadra richiesta.
- Campi presenti: `games.{appearences, lineups, minutes, position, rating}`, `cards.{yellow, yellowred, red}`, `fouls.{committed, drawn}`, `tackles.{total, blocks, interceptions}`, `duels.{total, won}`, `shots`, `passes`, `dribbles`. Paginazione: 20 giocatori/pagina (Inter: 2 pagine).
- Copertura (Inter, 20 record Serie A): falli commessi non null 13/20, tackle non null 17/20, minuti > 0 18/20. Esempio: `{"fouls": {"drawn": 4, "committed": 4}, "tackles": {"total": 4, "interceptions": 1}, "cards": {"yellow": 2}}`.
- **Distanza percorsa / corsa: NO.** Nessun campo in `/players` ne' in `/fixtures/players` (verificato su fixture 1550120 Inter-Udinese: chiavi `games, offsides, shots, goals, passes, tackles, duels, dribbles, fouls, cards, penalty`). In `/fixtures/players` falli non null 12/44, tackle 14/44.
- Roster fallback: `adapters/roster_fallback.py::get_team_roster_with_fallback(api_client, team_id, season)` (ri-esportata da `adapters/roster_service.py`). Chiavi del dict: `id, name, position, appearances, lineups, minutes, yellow_cards, red_cards, fouls_committed, fouls_drawn, tackles_total, duels_total, team_id`.

---

## 🧪 Fixture di test

`tests/fixtures/`: `odds_team_markets_roma_inter.json` (reale, ridotto), `players_team_505_page1.json` (reale, ridotto a 4 giocatori), `odds_player_booked_synthetic.json` (SINTETICO). Nessuna chiave API nei file.

---

## 🔮 Sviluppi Futuri

### 1. **Best Odds Finder**
```python
# Confronta quote tra bookmaker e mostra la migliore
best_odds = fetcher.find_best_odds_across_bookmakers(fixture_id, market, selection)
```

### 2. **Value Bet Detection**
```python
# Identifica value bets (prob > implied prob from odds)
value_bets = fetcher.find_value_bets(picks)
```

### 3. **Odds Movement Tracking**
```python
# Traccia variazioni quote nel tempo
movements = fetcher.track_odds_movements(fixture_id, market, hours=24)
```

### 4. **Arbitrage Opportunities**
```python
# Identifica opportunità di arbitraggio
arbitrage = fetcher.find_arbitrage_opportunities(fixture_id)
```

---

## 🧪 Testing

### Test automatici (nessuna chiamata di rete)

```bash
pytest -p no:pytest_anchorpy -q tests/test_odds_names.py tests/test_odds_markets.py tests/test_odds_fetcher.py tests/test_roster_fallback.py
```

Il vecchio harness manuale con `fixture_id` fittizio in fondo a `core/odds_fetcher.py` e' stato rimosso.

---

## 📞 Support

Per domande o problemi:
- Verifica che `API_FOOTBALL_KEY` sia configurata in `.env`
- Controlla i log per errori API
- Verifica rate limiting (quota giornaliera del piano)

---

## ✅ Checklist Integrazione

- [x] Creato modulo `OddsFetcher`
- [x] Mapping automatico mercati → bet IDs
- [x] Integrato in `DailyLeagueAnalyzer`
- [x] Update display con quote reali
- [x] Cache Redis implementata
- [x] Rate limiting attivo
- [x] Multi-bookmaker support
- [x] Fallback graceful per mercati non disponibili
- [x] Error handling robusto

---

**🎉 Il modulo è pronto e completamente funzionale!**

