# Backtest — validazione dei modelli predittivi

Backtesting offline e rigoroso dei modelli di previsione, per rispondere a una
domanda sola: **il modello prevede meglio del caso, e quanto?** — *prima* di
scommettere un euro.

Tutto gira offline sui dati di stagione salvati in cache: una sola chiamata API
per scaricare una stagione, poi zero.

---

## Avvio rapido

```bash
# 1) Backtest del modello attuale su una stagione (scarica+cachea al primo giro)
python run_backtest.py --season 2024                 # Serie A 2024/25

# 2) Confronto modelli sui gol/1X2 (baseline vs Poisson-forze vs Dixon-Coles)
python run_backtest.py --season 2024 --compare

# 3) Modello 1X2 avanzato: ablation delle tecniche (multi-stagione, decay, shrink)
python run_advanced.py --league 135 --target-season 2024 --history 2022,2023

# 4) Ensemble: Poisson-forze vs Glicko-2 vs media dei due
python run_advanced.py --target-season 2024 --history 2022,2023 --ensemble
```

Opzioni utili: `--league <id>` (135=Serie A, 39=Premier, 140=Liga, 78=Bundes),
`--season/--target-season <anno>` (l'anno è quello d'inizio: 2024 = 2024/25),
`--refresh` (riscarica), `--min-matches N`, `--k <shrinkage>`, `--xi <decay>`.

Test: `pytest -p no:pytest_anchorpy` (il flag disabilita un plugin globale rotto
nell'ambiente locale; in CI non serve).

---

## La garanzia anti-leakage (point-in-time)

La regola d'oro: **per prevedere la partita N si usano solo i dati fino alla
N-1.** Il motore la impone *strutturalmente*: per ogni partita fa
`snapshot → predice → aggiorna`. L'aggiornamento avviene sempre **dopo** la
predizione, quindi il futuro non può contaminare il passato. Il test
`tests/test_backtest_engine.py::test_no_data_leakage` lo dimostra.

---

## Moduli

| File | Ruolo |
|---|---|
| `data.py` | Scarica una stagione dall'API e la cachea in `backtest/data/` (git-ignored). Cache-first. |
| `engine.py` | Replay cronologico point-in-time. `iter_scored_matches` (stat aggregate, baseline) e `iter_match_contexts` (split casa/trasferta + medie lega). |
| `models.py` | 3 modelli sui gol/1X2: `baseline` (attuale), `poisson_strength` (forze attacco/difesa + fattore campo), `dixon_coles` (+ correzione low-score). |
| `advanced.py` | Modello 1X2 avanzato: multi-stagione + time-decay `exp(-ξt)` + **fattore campo globale** + **shrinkage bayesiano**. |
| `glicko.py` | Rating Glicko-2 per il calcio (home advantage + margin-of-victory), 1X2 via rating→supremacy→Poisson. |
| `ensemble.py` | Confronto 3-vie (Poisson / Glicko-2 / media) in un unico passaggio point-in-time. |
| `ablation.py` | Isola l'effetto di ogni tecnica (multi-stagione, ξ, shrinkage) sulle stesse partite. |
| `metrics.py` | Brier, Brier Skill, calibrazione, **RPS** (standard per l'1X2). |
| `runner.py` / `report.py` | Orchestrazione e tabelle Rich. |

---

## Metriche

- **Brier score** — errore quadratico medio delle probabilità. 0 = perfetto,
  0.25 = testa-o-croce a 50%.
- **Brier Skill Score** — vs "prevedi sempre la frequenza di base". >0 = meglio
  del caso; <0 = peggio.
- **RPS (Ranked Probability Score)** — standard aureo per l'1X2: penalizza per
  distanza ordinale (sbagliare 1↔2 pesa più di 1↔X). Più basso è meglio.
- **Calibrazione** — quando il modello dice 70%, succede davvero ~70%?

---

## Cosa abbiamo imparato (sintesi del percorso)

Testato su ~3000 partite reali, 5 leghe europee, stagioni 2022–2024.

1. **Mercati gol (Over/Under, BTTS): nessun edge.** Brier Skill negativo su ogni
   mercato/stagione. Non è un bug: il Poisson assume equidispersione, ma i gol
   nel calcio sono sovradispersi → il modello è cronicamente troppo sicuro. Le
   linee Over/Under dei bookmaker sono molto efficienti.
2. **Dixon-Coles non aiuta sui gol** (corregge solo i punteggi ≤1 gol).
3. **Il 1X2 è l'unico mercato con segnale reale.** Il modello a forze
   (attacco/difesa + fattore campo) batte il baseline sul 1X2 in 5 leghe su 5.
4. **Miglior modello gratuito = `advanced.py`**: multi-stagione + shrinkage +
   fattore campo globale. **RPS ~0.19–0.21**, dentro la fascia dei modelli
   accademici avanzati (0.195–0.204). Cosa paga (isolato dall'ablation):
   *shrinkage* sempre, *multi-stagione* è la leva più forte, *time-decay*
   marginale e solo con ξ piccolo (~0.001–0.003/giorno).
5. **Glicko-2 ed ensemble non migliorano**: il Glicko usa solo W/D/L+margine,
   il Poisson usa tutti i gol (più segnale) → l'ensemble viene trascinato giù.

**Caveat fondamentale:** "modello competente" ≠ "batte il bookmaker". Battere la
frequenza di base non significa battere il margine del banco (~5%). Il vero
giudice è il **CLV (Closing Line Value)**, che richiede le quote storiche.

---

## Dati disponibili (stato verificato al 2026-09-18)

- **Fixture** in cache per le stagioni 2022–2026 (Serie A, Liga, Premier, Bundesliga;
  la 2026/27 è in corso).
- **xG per partita** in cache per 2022–2025 (Serie A) e 2023–2025 (Liga, Premier,
  Bundesliga): quasi completi (0–1 partite senza xG per lega-stagione).
- **Quote storiche** da football-data.co.uk (CSV, non da API-Football): Serie A e
  Premier 2024 e 2025, Liga solo 2025. Bundesliga non ha quote. Nessuna quota
  storica per cartellini, corner, tiri, multigol, BTTS e cartellini giocatore.
- **Attenzione alla fonte "sharp"**: nel 2025/26 le colonne Pinnacle di chiusura
  (`PSC*`) sono popolate solo per circa il 50% delle partite (Serie A: 198/380); per le
  altre la catena di fallback usa Bet365 chiusura. Non è "Pinnacle su tutte le partite".

---

## Risultati misurati (audit del 2026-09-18, dati in cache, nessuna chiamata API)

Modello xG-Poisson con shrinkage (`iter_xg_predictions`, k=5, xi=0) contro le quote di
chiusura Bet365 de-viggate, 1760 partite (Serie A e Premier 2024, Serie A/Liga/Premier
2025; le partite Liga con abbinamento nomi incoerente sono state escluse):

| Metrica | Modello | Mercato |
|---|---|---|
| RPS 1X2 | 0.2000 | 0.1956 |
| Accuratezza 1X2 | 52.3% | 53.0% |
| Brier Over/Under 2.5 | 0.2465 | 0.2450 |

- Il modello è **peggiore del mercato** sull'1X2 (differenza RPS +0.0044, IC95%
  da +0.0020 a +0.0067). Miscelare modello e mercato non migliora mai il solo mercato
  (peso ottimale del modello = 0).
- ROI 1X2 alle quote di chiusura Bet365: circa −12% (t = −3.0); con le migliori quote
  di chiusura tra bookmaker: circa −6%.
- ROI Over/Under 2.5: tra +1.6% e +7.6% a seconda di soglia e fonte, sempre con errore
  standard di 3–5 punti: **non distinguibile da zero**.
- Il modello **live** (analyzer `baseline`) è molto peggiore: RPS 1X2 0.2262 contro
  0.1894 del mercato, Brier Over/Under 2.5 0.2777 contro 0.2497 (Serie A 2024 e 2025).
- Cartellini giocatore (Serie A 2024, storia 2023): tasso base 12.1%, Brier skill −0.002,
  Precision@k 22.3%: discriminazione debole, nessuna calibrazione migliore della base.
- Simulazione bankroll 2025/26 con Quarter Kelly, cap 5%, soglia 5%: da 300 a circa
  135–147 con drawdown massimo 70–80% (il risultato Liga era influenzato da un bug di
  abbinamento nomi, in correzione).

Conclusione: nessun edge dimostrato. Servono molte più scommesse (ordine di 20.000)
per misurare un ROI del 2%; il modo efficiente è il CLV su quote di apertura e chiusura
registrate in avanti (forward test).

---

## Prossima fase

1. **Registro forward** delle previsioni con quote di apertura e di chiusura.
2. **Informazione che il mercato non ha già prezzato** (formazioni, infortuni): con soli
   gol e xG storici il peso ottimale nel blend è 0.
3. L'edge retail, se esiste, è *operativo* (bookmaker soft, line shopping, Kelly
   frazionale), non solo modellistico.
