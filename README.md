# ⚽ Footy Predictor CLI

Un'applicazione CLI per analizzare le partite di calcio della prossima giornata con statistiche dettagliate delle squadre.

## 🎯 Funzionalità

### 🎮 **Menu Interattivo**
- **8 Campionati Supportati**: Serie A, Premier League, La Liga, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Serie A Brasiliana
- **Selezione Intelligente**: Scegli campionato → scegli partita specifica
- **Minime Chiamate API**: Solo 3 chiamate per partita (vs 11+ del comando tradizionale)

### 📊 **Statistiche Avanzate**
- **Statistiche Stagionali**: Gol, cartellini, clean sheets, rigori
- **Under/Over**: Percentuali 1.5, 2.5, 3.5 gol (fatti e subiti)
- **Forma Recente**: Ultimi risultati e punti forma
- **Confronto Dettagliato**: Home vs Away con tutte le metriche

### 🔮 **Predizioni**
- **Gol Attesi**: Basati su attacco vs difesa
- **Cartellini Attesi**: Media cartellini gialli per partita
- **Note Informative**: Spiegazioni su dati disponibili

### ⚡ **Performance**
- **Cache Intelligente**: League ID salvati per campionati principali
- **Rate Limiting**: 1 secondo tra chiamate API
- **Gestione Errori**: Fallback automatici per stagioni precedenti

## 🛠 Installazione

### Prerequisiti
- Python 3.11+
- API Key di [API-Football](https://www.api-football.com/)

### Setup

1. **Clona il repository**:
```bash
git clone <repository-url>
cd footy-predictor
```

2. **Installa le dipendenze**:
```bash
pip install -r requirements.txt
```

3. **Configura l'API Key**:
```bash
# Copia il file di esempio
cp env.example .env

# Modifica il file .env con la tua API key
nano .env
```

4. **Installa il pacchetto** (opzionale):
```bash
pip install -e .
```

## ⚙️ Configurazione

Modifica il file `.env` con i tuoi parametri:

```env
API_FOOTBALL_KEY=your_api_key_here
API_FOOTBALL_BASE=https://v3.football.api-sports.io
DEFAULT_COUNTRY=Italy
DEFAULT_LEAGUE=Serie A
DEFAULT_SEASON=2024
```

## 🚀 Utilizzo

### Menu Interattivo (RACCOMANDATO) 🎯
```bash
# Menu interattivo per scegliere campionato e partita specifica
python main.py interactive
```
**Vantaggi:**
- ✅ **Minime chiamate API** (solo per la partita selezionata)
- ✅ **8 campionati disponibili** (Serie A, Premier League, La Liga, etc.)
- ✅ **Selezione partita specifica** con date e orari
- ✅ **Interfaccia user-friendly** con emoji e menu guidati

### Comando Tradizionale
```bash
# Analizza TUTTE le partite della prossima giornata (più chiamate API)
python main.py matchday
```

### Opzioni Avanzate
```bash
# Specifica campionato e stagione
python main.py matchday --league "Premier League" --country "England" --season 2025

# Usa le abbreviazioni
python main.py matchday -l "La Liga" -c "Spain" -s 2025
```

### Altri Comandi
```bash
# Mostra configurazione attuale
python main.py config

# Aiuto
python main.py --help
```

### Se Installato
```bash
# Usa il comando diretto
matchday

# O il comando completo
footy-predictor matchday
```

## 📊 Output di Esempio

### Menu Interattivo
```
🏆 FOOTY PREDICTOR - ANALISI INTERATTIVA
==================================================

📋 SELEZIONA CAMPIONATO:
------------------------------
1. 🇮🇹 Italia - Serie A
2. 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Premier League
3. 🇪🇸 Spagna - La Liga
4. 🇩🇪 Germania - Bundesliga
5. 🇫🇷 Francia - Ligue 1
6. 🏆 Europa - UEFA Champions League
7. 🥈 Europa - UEFA Europa League
0. Esci

🎯 Scegli un campionato (1-8, 0 per uscire): 1

⚽ PARTITE DISPONIBILI - 🇮🇹 Italia Serie A
==================================================

📅 28/09/2025
--------------------
 1. ⚽ AS Roma vs Verona
     🕐 13:00 | 🏟️ Stadio Olimpico
 2. ⚽ Inter vs Milan
     🕐 18:00 | 🏟️ San Siro

🎯 Scegli una partita (1-2, 0 per tornare indietro): 1
```

### Analisi Dettagliata
```
🏆 Match 1: AS Roma vs Verona
📅 28/09/2025 13:00
🏟️ Stadio Olimpico

📊 TEAM STATISTICS COMPARISON
----------------------------------------
Statistic            🏠 AS Roma       ✈️ Verona      
Matches Played       4               4              
Goals For/Against    3/1             2/6            
Goals per Game       0.75            0.50           
Recent Form          WWLW            DLDD           
Form Points (L5)     9               3              
Clean Sheets         3 (75.0%)       1 (25.0%)      
Over 1.5 Goals       0.0%            0.0%           
Over 2.5 Goals       0.0%            0.0%           
Over 1.5 Conceded    0.0%            25.0%          
Penalties            0/0             1/1            
W-D-L Record         3W-0D-1L        0W-3D-1L       

🔮 EXPECTED COMBINED STATS
------------------------------
Total Goals:        1.5
Total Yellow Cards: 3.0
📝 Note: Shots e Corners disponibili solo per singole partite, non stagionali
```

## 🏗 Struttura Progetto

```
footy-predictor/
├── cli/                    # Interfaccia CLI
│   ├── main.py             # Comandi Typer
│   └── display.py          # Output Rich
├── adapters/               # Connettori API
│   └── football_api.py     # Client API-Football
├── core/                   # Logica business
│   ├── models.py           # Modelli dati
│   ├── analyzer.py         # Analisi partite
│   └── config.py           # Configurazione
├── utils/                  # Utilità (future)
├── main.py                 # Entry point
├── setup.py                # Installazione
├── requirements.txt        # Dipendenze
└── README.md               # Documentazione
```

## 🔧 Sviluppo

### Aggiungere Nuove Funzionalità
1. Modelli dati → `core/models.py`
2. Logica API → `adapters/football_api.py`
3. Analisi → `core/analyzer.py`
4. Display → `cli/display.py`
5. Comandi CLI → `cli/main.py`

### Test
```bash
# Test rapido
python main.py config
python main.py matchday
```

## 📈 Roadmap Future

- [ ] Cache per ridurre chiamate API
- [ ] Rate limiting intelligente
- [ ] Predizioni più sofisticate (ML)
- [ ] Supporto per più campionati
- [ ] Export dati (CSV, JSON)
- [ ] Statistiche storiche head-to-head
- [ ] Grafici e visualizzazioni

## 🤝 Contributi

Contributi benvenuti! Apri una issue o pull request.

## 📄 Licenza

MIT License - vedi file LICENSE per dettagli.

## 🔗 Links

- [API-Football Documentation](https://www.api-football.com/documentation-v3)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
