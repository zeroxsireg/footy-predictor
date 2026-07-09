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

## Limiti dati (piano API-Football Free)

- Stagioni accessibili: **2022–2024** (2025/26 bloccata).
- **Quote storiche non disponibili** (`/odds` torna vuoto) → impossibile misurare
  il CLV. Serve un tier a pagamento.
- Niente **xG** sul piano Free.

---

## Prossima fase (con tier a pagamento)

La ricerca è chiara: il collo di bottiglia è l'**input**, non l'architettura.

1. **xG al posto dei gol**: alimentare i λ del Poisson con la media smussata
   degli Expected Goals prodotti/subiti. È il salto di qualità più impattante.
2. **Quote storiche → tracking CLV**: l'unico test di profittabilità reale.
3. Ricordare che l'edge retail è *operativo* (bookmaker soft, mercati Asian a
   basso margine, Kelly frazionale), non solo modellistico.
