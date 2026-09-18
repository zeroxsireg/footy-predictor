# PRUNE LOG — potatura v2-lean (prima passata)

Branch `v2-lean`. Tutto il rimosso è recuperabile da `main`. Modifiche NON committate.

## Numeri prima / dopo

| Metrica | Prima | Dopo |
|---|---|---|
| Moduli Python (esclusi tests/web) | 116 | 91 |
| Righe Python (esclusi tests/web) | 15.667 | 11.303 |
| Test raccolti/passati | 308 | 259 |
| pytest (exit) | 0 | 0 |

## Eliminati (righe)

- cli/: interactive.py 334, daily_display.py 283, match_display.py 270, daily_analysis.py 190, daily/ (advanced_filters 252, batch_runner 130, report_exporter 101, __init__ 1), utility_menu.py 134, utility/ (cache_manager 106, roster_updater 101, stats_updater 111, __init__ 1), main_menu.py 62.
- core/: daily_league_analyzer.py 381, daily_analyzer.py 16, pick_selector.py 218, bookmaker_manager.py 323, analyzer.py 111. Motivo: nessun import da moduli tenuti (verificato con grep); bookmaker_manager non importato da nessuno.
- services/data_service.py 261 (cartella services/ rimossa), utils/team_id_manager.py 169: importati solo da moduli/test eliminati.
- backtest/: gbm.py 94, features.py 146, glicko.py 137, ensemble.py 104 (nessun valore dimostrato).
- Radice: run_gbm.py 105.

## Test eliminati / modificati

- tests/test_backtest_gbm.py (testa solo gbm/features), tests/test_backtest_glicko.py (testa solo glicko/ensemble), tests/test_default_season.py (testa solo team_id_manager e data_service).
- tests/test_pick_selector.py: rimossi i test dei combo (`_calculate_combo_odds`, `_generate_combinations`, summary) e `_get_market_category` (codice rimosso); i test `annotate_value` restano; `select_value_picks` ora testato direttamente su `core.value_selection` (wrapper rimosso).
- tests/test_cli_display.py: rimossi i 3 test su `match_display` (odds enrichment, quota n/d, errore rete) e i relativi helper/import; restano quelli di betting_render e player_cards_display.

## Spostati in research/ (con research/__init__.py)

generate_json, predict_match, predict_round, predict_upcoming, run_advanced, run_backtest, run_bankroll, run_cards, run_cards_multi, run_clv, run_multigol, run_player_cards, run_xg, run_xg_multi. Eseguibili con `python -m research.<nome>`; docstring, README.md, backtest/README.md aggiornati. run_advanced: rimossi `--ensemble`, `--xi` e `_run_ensemble`.

## Modificati

- cli/simple_main.py: router minimale con solo `config` e `cache` + help. `config` non stampa più nemmeno gli ultimi 4 caratteri della chiave API (mostra "configured"/"MISSING").
- README.md (comandi/struttura), backtest/README.md, docstring in backtest/runner.py e xg_data.py.

## Non toccati / note

- web/scripts/sync-data.mjs cita ancora `generate_json.py` in un messaggio d'errore (web congelata): ora e' `research/generate_json.py`.
- docs/AGENT_PERSONAS.md cita `run_bankroll.py` (docs esclusa dalla potatura).
- `pandas` in requirements.txt non e' piu' importato da nessun .py (ne' sklearn era dichiarato).

## Seconda passata (candidati)

analyzers/ (~1.100 righe), betting/orchestrator.py 129, core/player_predictions.py 451, core/player_card_model.py 239, utils/roster_monitor.py 319, utils/redis_cache.py 501, adapters/roster_service.py 356, roster_fallback.py 136, team_stats_service.py 283, database/db_manager.py 269, cli/betting_render.py 160 / player_cards_display.py 88.
