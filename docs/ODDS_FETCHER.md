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

### 2. **Mapping Automatico**
Il sistema mappa automaticamente i nostri mercati ai bet IDs delle API:

| Nostro Mercato | API Bet ID | Esempi |
|---------------|-----------|---------|
| Match Goals | 5 | Over 2.5, Under 3.5 |
| Both Teams to Score | 8 | Yes, No |
| Match Result | 1 | Home Win, Draw, Away Win |
| Total Corners | 12 | Over 9.5, Under 10.5 |
| Total Cards | 11 | Over 3.5, Under 4.5 |
| Exact Score | 6 | 2-1, 1-0 |

### 3. **Cache Intelligente**
- ✅ Redis cache con TTL di 10 minuti
- ✅ Riduce chiamate API ripetute
- ✅ Quote sempre aggiornate

### 4. **Rate Limiting**
- ✅ Batch processing (5 richieste alla volta)
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

Modifica in `core/odds_fetcher.py`:

```python
self.preferred_bookmakers = [8, 6, 5, 3]  # Bet365, Bwin, William Hill, Betfair
```

### Cache TTL

```python
self.cache_ttl = 600  # 10 minuti (in secondi)
```

### Batch Size

```python
batch_size = 5  # Richieste parallele per batch
```

---

## 🚨 Limitazioni Attuali

### Mercati NON Disponibili nelle API:
- ❌ **Total Shots** - API non fornisce quote
- ❌ **Shots on Goal** - API non fornisce quote
- ❌ **Team-specific Shots/Corners** - Spesso non disponibile
- ❌ **Player Cards** - Mercato nicchia, pochi bookmaker

### Soluzione:
Il sistema mostra "Quote non disponibili" per questi mercati, ma il pick rimane valido basato sulle nostre analisi statistiche.

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

### Test Manuale

```bash
cd /home/gepkot/Documenti/Projects/footy-predictor
source venv/bin/activate
python core/odds_fetcher.py
```

### Test con Fixture Reale

Modifica `test_odds_fetcher()` con un fixture_id reale:

```python
test_fixture_id = 1234567  # ID di una partita reale
```

---

## 📞 Support

Per domande o problemi:
- Verifica che `API_FOOTBALL_KEY` sia configurata in `.env`
- Controlla i log per errori API
- Verifica rate limiting (max 100 richieste/giorno per piano free)

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

