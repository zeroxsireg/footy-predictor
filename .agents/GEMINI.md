# ⚽ Footy Predictor — Regole per l'Agente

## Identità del Progetto
Footy Predictor è un'applicazione avanzata di analisi calcistica, stima di probabilità pre-partita, backtesting rigoroso e selezione di value bet.
Stack: Python 3.11+, Pytest, API-Football v3 REST (api-sports.io), Redis Cache (con offline mode trasparente), SQLite (`player_history.db`), Next.js 16 + React 19 + Tailwind CSS v4 per la web app Tactical Match Telemetry.
Documentazione di riferimento: `docs/AI_AGENT_ARCHITECTURE.md`, `docs/AGENT_PERSONAS.md`, `docs/ODDS_FETCHER.md`, `docs/UI_SYSTEM.md`, `backtest/README.md`.

## Lingua
- Documentazione, commit message, commenti architetturali, spiegazioni all'utente: **italiano**
- Codice sorgente (nomi variabili, funzioni, classi, docstring inline): **inglese**

---

## Regole — Test & Validazione

1. **Mai toccare il DB o i dati reali nei test.**
   - Divieto di scrivere su `player_history.db` durante i test; usare sempre SQLite `:memory:` o file temporanei effimeri.
   - Divieto assoluto di corrompere o alterare i dataset storici scaricati in `backtest/data/`.
2. **Suite test verde prima di dichiarare completato.**
   - Eseguire sempre `pytest -p no:pytest_anchorpy` (il flag disabilita un plugin locale rotto; tutti i 148 test devono passare).
   - Per il frontend `web/`: `./web/node_modules/.bin/tsc --project web/tsconfig.json --noEmit` a 0 errori e `npm --prefix web run lint` pulito.
3. **Mutation check.** Un test che non può fallire non protegge da nulla.
   - Dopo aver scritto o modificato un test, verificare che fallisca mutando la logica sotto test prima di ritenerlo valido.
4. **Nessuna chiamata di rete a pagamento nei test.**
   - Usare sempre mock e fixture per simulare risposte di API-Football (`adapters/`), senza consumare le quote API.

---

## Regole — Architettura Quantitativa & Betting

5. **Garanzia Point-in-Time inviolabile nel Backtest.**
   - In `backtest/engine.py` vale rigorosamente `snapshot -> predict -> update`.
   - Per prevedere la partita $N$ si usano SOLO i dati fino a $N-1$. Nessun dato post-partita può entrare nelle feature.
6. **Separazione tra Stima di Probabilità e Azione di Mercato.**
   - Gli analizzatori in `analyzers/` sono stimatori di probabilità puri ($P_{model}$). Non contengono logica di quote o stake.
   - Calcolo dell'edge, de-vigging, expected value e sizing sono competenza esclusiva di `core/edge_calculator.py`, `core/pick_selector.py` e `betting/orchestrator.py`.
7. **De-vigging e calcolo Expected Value ($EV$).**
   - Mai calcolare l'edge su quote lorde senza rimuovere l'aggio del bookmaker.
   - Regola per la value bet: $EV = (P_{nostra} \times Quota) - 1 > \tau$ (soglia minima standard $3\%$).
8. **Kelly Frazionato obbligatorio.**
   - Vietato il Full Kelly. Usare sempre Fractional Kelly (Quarter Kelly $0.25 \times f^*$) e applicare un cap massimo di esposizione per scommessa (max 2-5% del bankroll).

---

## Regole — Backend, Cache & Dati

9. **Offline-First e Resilienza Cache.**
   - Redis Cache (`utils/redis_cache.py`) deve sempre degradare in graceful offline mode in caso di mancata connessione. L'app non deve MAI crashare perché Redis è spento.
10. **Rate Limiting e Batching Quote.**
    - `core/odds_fetcher.py` e gli adapter devono recuperare quote a batch controllati (massimo 5 fixture per richiesta) con pause per rispettare i rate limit di API-Football ed evitare HTTP 429.
11. **Prioritizzazione Bookmaker e Tracciabilità.**
    - Bet365 prioritario, poi Bwin, William Hill, Betfair. Ogni pick deve tracciare il fornitore reale della quota.

---

## Regole — Qualità del Codice & Frontend Brutalista

12. **Niente spaghetti code, niente monoliti (SRP).**
    - Componenti piccoli e focalizzati. Se un file supera 300 righe, scomporlo in sottomoduli, classi o hook dedicati.
13. **SSOT sempre.**
    - Nessuna costante, mapping di leghe o quota duplicata. Usare `config/leagues.py` e `core/config.py`.
14. **Frontend Tactical Match Telemetry (`docs/UI_SYSTEM.md`):**
    - **Zero Border Radius**: categoricamente vietati bordi arrotondati (`border-radius: 0 !important`).
    - **CRT Scanlines**: preservare l'overlay scanline CSS.
    - **Token rigidi Tailwind v4**: usare solo i colori del design system (`bg-bg`, `bg-panel`, `border-line`, `text-fg`, `text-dim`, `text-red`, `bg-green`).
    - **Micro-tipografia**: titoli in Archivo Black, telemetria in JetBrains Mono maiuscolo.
15. **TypeScript Strict:**
    - Zero `any` di comodo; definire tipi speculari ai modelli Pydantic di `core/models.py`.

---

## Regole — Workflow e Condotta

20. **Feedback prioritario nello stesso ciclo:**
    - Se un test o una review evidenzia un problema, risolverlo immediatamente prima di proseguire con nuove feature.
21. **Verificare solo su fatti e comandi reali:**
    - Mai affermare che un modello converge, un test passa o un endpoint funziona senza aver eseguito il comando reale e verificato l'output.
