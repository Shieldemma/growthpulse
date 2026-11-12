# Incrementality experiments

* Data generator: `src/growthpulse/datagen/experiments.py` (three simulated randomised holdouts with KNOWN true effects: a real lift, a null effect, and an underpowered pilot).
* Analysis: `src/growthpulse/experiment.py` (z-test, Newcombe and Katz intervals, SRM, balance, contamination, CACE, power/MDE, business impact).
* Results: DuckDB tables `gp_analytics.experiment_*`; dashboard page 7; tests in `tests/test_experiment.py`.
* Truth file (never used by the analysis): `data/raw/_ground_truth.json`.

These are **simulated** experiments, not company experiments. See the dashboard page "How this would change for a real campaign".
