# 🤖 AI Agent Architecture & Guidelines — Footy Predictor

Questo documento formalizza l'architettura di configurazione, le regole operative e i permessi di esecuzione per gli agenti AI (Google Antigravity / Gemini e Anthropic Claude Code) all'interno del repository **Footy Predictor**.

---

## 1. Obiettivi e Filosofia di Design

1. **Contesto Riproducibile e Permanente**:
   Eliminare la necessità di ri-spiegare a ogni nuova sessione di sviluppo i concetti quantitativi di mercato (edge, de-vigging, quote decimali, Kelly Criterion), i modelli predittivi statistici (Dixon-Coles, Poisson, Bayesian shrinkage, Glicko-2), l'invariante point-in-time del backtesting e le convenzioni visive del terminale Rich e della web app brutalista.
2. **Standardizzazione Cross-Agent**:
   Fornire una configurazione coordinata tra gli ambienti di sviluppo agentici:
   - **Antigravity / Gemini**: Caricamento gerarchico di regole imperative (`GEMINI.md`), mappa del progetto (`rules/project-context.md`) e skill on-demand (`skills/`).
   - **Claude Code**: Permessi sistematici basati su wildcard (`.claude/settings.json`) con protezione dell'integrità del repository, **più** le stesse regole imperative caricate via import (`@.agents/GEMINI.md`) dal `CLAUDE.md` in radice — nessuna duplicazione, SSOT unico per entrambi gli agenti.
3. **Guardrail di Sicurezza su Git, Dati e Modelli**:
   - **Git in Sola Lettura**: L'agente ha accesso autorizzato a comandi di ispezione (`git log`, `git diff`, `git blame`, `git status`, `git show`), ma **non può eseguire autonomamente `git commit` o `git push`**. A conclusione della feature, l'agente formula e suggerisce all'utente il messaggio di commit in italiano con la specifica del modulo o della fase.
   - **Isolamento dei Database e dei Dati di Storico nei Test**: Divieto categorico di corrompere o azzerare `player_history.db` reale o i dataset storici scaricati in `backtest/data/` durante l'esecuzione dei test. Utilizzo obbligatorio di database SQLite `:memory:` o temporanei effimeri per i test di persistenza.
   - **Protezione delle API Esterne & Zero Data Leakage**: Divieto di lanciare chiamate a raffica non cacheate verso le API a consumo di API-Football (`api-sports.io`). I test di integrazione e unitari devono impiegare mock e fixture locali.
4. **Preservazione nel Version Control (GitHub)**:
   I file di configurazione essenziali sono inclusi nel repository git per garantire che qualsiasi contributore o istanza dell'agente disponga istantaneamente del contesto operativo corretto al checkout del progetto.

---

## 2. Architettura a Tre Livelli (Antigravity / Gemini)

L'alberatura `.agents/` adotta un modello a tre livelli di granularità per ottimizzare l'uso della finestra di contesto ed evitare rumore cognitivo:

```text
.agents/
├── GEMINI.md                              # [Livello 1] Regole imperative always-on
├── rules/
│   └── project-context.md                 # [Livello 2] Mappa strutturale always-on
└── skills/
    ├── market-mechanics-betting/          # [Livello 3] Calcolo edge, Kelly, vig removal on-demand
    │   └── SKILL.md
    └── industrial-brutalist-ui/           # [Livello 3] Design system brutalista / CRT on-demand
        └── SKILL.md
```

### Livello 1 — Regole Imperative Always-On (`.agents/GEMINI.md`)
Regole assolute caricate automaticamente a ogni invocazione. Coprono:
- **Identità e Stack**: Python 3.11+, Pytest, API-Football v3 REST, Redis Cache con fallback graceful in memoria, SQLite (`player_history.db`), Next.js 16 + React 19 + Tailwind CSS v4 con design system brutalista e micro-tipografia CRT per il web client.
- **Convenzione Linguistica**: Italiano per documentazione, commit message, note e commenti architetturali; Inglese per codice sorgente, docstring inline e nomi di entità (classi, funzioni, variabili).
- **Invarianti di Test**:
  - Python test suite: `pytest -p no:pytest_anchorpy` (il flag evita il plugin locale deprecato; tutti i test devono essere sempre verdi, attualmente 148 test passanti).
  - Web client checks: `./web/node_modules/.bin/tsc --project web/tsconfig.json --noEmit` a 0 errori e `npm --prefix web run lint` a zero warning/errori.
- **Invarianti Architetturali di Dominio**:
  - *Separazione tra Analyzer e Strategia di Betting*: gli analyzer in `analyzers/` sono stimatori di probabilità puri ($P_{model}$). Non devono calcolare quote o decidere stake. Il confronto con le quote di mercato, il de-vigging, il calcolo dell'Expected Value ($EV$) e il dimensionamento dello stake con Kelly frazionato sono di competenza esclusiva di `core/edge_calculator.py`, `core/pick_selector.py` e `betting/orchestrator.py`.
  - *Anti-Leakage Point-in-Time nel Backtest*: in `backtest/engine.py`, il loop cronologico esegue rigorosamente `snapshot -> predict -> update`. Nessun dato relativo alla partita $N$ (gol, cartellini, risultato, formazioni effettive) può essere visibile durante la generazione del pronostico della partita $N$.
  - *Offline-First e Resilienza Cache*: Redis non è mai un blocco fatale. Se Redis non è raggiungibile o non è configurato, i moduli devono degradare trasparentemente in modalità offline senza lanciare eccezioni bloccanti per l'utente.
  - *Odds Fetching Responsabile*: batch controllati (massimo 5 fixture per volta con delay fisiologico) per rispettare i limiti di quota di API-Football ed evitare risposte HTTP 429.
  - *Web UI Brutalista*: conformità assoluta a `docs/UI_SYSTEM.md` — divieto categorico di bordi arrotondati (`border-radius: 0 !important`), palette scura a fosfori CRT, scanline CSS overlay, font Archivo Black e JetBrains Mono.

### Livello 2 — Mappa Strutturale Always-On (`.agents/rules/project-context.md`)
Fornisce le coordinate fisiche dell'alberatura (`core/`, `analyzers/`, `adapters/`, `betting/`, `backtest/`, `cli/`, `web/`, `tests/`), i numeri di riferimento attuali (148 test pytest passanti, 0 errori TypeScript) e l'indice della documentazione tecnica in `docs/` (`docs/ODDS_FETCHER.md`, `docs/UI_SYSTEM.md`, `docs/AGENT_PERSONAS.md`, `docs/AI_AGENT_ARCHITECTURE.md`) senza duplicarne il testo.

### Livello 3 — Skill Operative On-Demand (`.agents/skills/`)
Caricate esclusivamente quando l'agente esegue task specifici:
- **`market-mechanics-betting`**: Procedure operative per la conversione da quote bookmaker a probabilità implicite, rimozione dell'aggio (Shin / power / proportional de-vigging), calcolo del margine/edge ($Edge = P_{nostra} - P_{mercato}$), dimensionamento della puntata con Kelly frazionato (Quarter Kelly $0.25 \times f^*$), ottimizzazione Brier Score e Ranked Probability Score (RPS), mitigazione del drawdown e strategie di portafoglio.
- **`industrial-brutalist-ui`**: Regole formali per la Tactical Match Telemetry: griglie rigide ad alta densità informativa, token `@theme` in Tailwind v4 (`--color-bg: #0a0a0a`, `--color-panel: #101010`, `--color-line: #262626`, `--color-red: #e61919`, `--color-green: #4af626`), overlay scanline CRT, micro-tipografia mono-spaziata in maiuscolo e assenza totale di curve e layout-shift.

---

## 3. Configurazione Permessi CLI (`.claude/`)

La cartella `.claude/` gestisce i permessi pre-autorizzati per l'ambiente CLI Claude Code, garantendo autonomia operativa durante l'esecuzione di test, backtest e linting:

```text
.claude/
├── settings.json                          # Configurazione condivisa di progetto (versionata su GitHub)
└── settings.local.json                    # Configurazione locale per-macchina (ignorata da git)
```

### `settings.json` (Tracciato in Git)
Definisce i permessi sistematici strutturati con wildcard:
- **Esecuzione Test & Suite Pytest**: `pytest -p no:pytest_anchorpy *`, `pytest *`, `python -m pytest *`.
- **Esecuzione Script di Analisi e CLI**: `python main.py *`, `python run_*.py *`, `python predict_*.py *`.
- **Quality Assurance Frontend**: `npm --prefix web run *`, `npm --prefix web test *`, `./web/node_modules/.bin/tsc *`, `npx --prefix web eslint *`.
- **Ispezione Sistema e Processi**: `curl -s *`, `netstat *`, `ps aux *`, `ls -la *`, `grep *`.
- **Git di Sola Lettura**: `git log *`, `git diff *`, `git blame *`, `git status *`, `git show *`.

### `settings.local.json` (Ignorato in Git)
Ospita permessi specifici della workstation locale (es. percorsi custom per virtual environment o chiavi di test locali) protetti dalla regola in `.gitignore`.

---

## 4. Matrice di Tracciamento Version Control

| Percorso | Stato Git | Motivazione |
|----------|-----------|-------------|
| `.agents/GEMINI.md` | **Tracciato** | Regole core, invarianti matematici e identità condivisa del team |
| `.agents/rules/project-context.md` | **Tracciato** | Mappa architetturale condivisa e numeri di test di riferimento |
| `.agents/skills/market-mechanics-betting/` | **Tracciato** | Skill specialistica di calcolo quantitativo di edge e Kelly |
| `.agents/skills/industrial-brutalist-ui/` | **Tracciato** | Skill specialistica per la web app Tactical Match Telemetry |
| `.claude/settings.json` | **Tracciato** | Permessi di test e verifica standardizzati del progetto |
| `CLAUDE.md` (radice) | **Tracciato** | Import delle regole `.agents/GEMINI.md` per Claude Code (SSOT unico) |
| `.claude/settings.local.json` | **Ignorato** | Configurazioni hardware/OS individuali della workstation |
| `docs/AI_AGENT_ARCHITECTURE.md` | **Tracciato** | Documento tecnico di governance degli agenti (questo file) |
| `docs/AGENT_PERSONAS.md` | **Tracciato** | Schede e prompt operativi dei 6 specialisti del team |

---

## 5. Manutenzione e Aggiornamento delle Regole

1. **Modifiche all'Alberatura o ai Numeri di Test**:
   Quando vengono aggiunti nuovi analyzer in `analyzers/`, nuovi modelli in `backtest/models.py` o nuove pagine/componenti nel client `web/`, aggiornare la sezione *Numeri di Riferimento* in `.agents/rules/project-context.md` e la documentazione tecnica correlata.
2. **Aggiunta di Nuove Regole Imperative**:
   Inserire in `.agents/GEMINI.md` solo ed esclusivamente regole inderogabili con impatto sistemico (es. divieto di data leakage, separazione tra probabilità e stake, invariante zero-border-radius). Evitare istruzioni lunghe o tutorial: queste appartengono alle cartelle `skills/` o a `docs/`.
3. **Zero Duplicazione (SSOT)**:
   Non copiare mai il testo esteso di `docs/*.md` o di `backtest/README.md` all'interno dei prompt di configurazione. Usare sempre riferimenti relativi chiari, link espliciti e file di documentazione specializzati.
