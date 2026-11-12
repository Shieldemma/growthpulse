# Marketing Mix Model

Code lives in `src/growthpulse/mmm/` (kept inside the package so it can be imported and tested):
`transforms.py` (adstock, saturation) -> `data.py` (prep, chronological split, leakage-free `FeatureBuilder`) -> `model.py` (fit, CV tuning, evaluation, bootstrap, sensitivity, diagnostics) -> `budget.py` (optimiser, response curves) -> `run.py` (orchestration).

Run: `python scripts/run_pipeline.py` (step 4) - or in Python:
```python
from growthpulse.mmm.run import run_mmm
results = run_mmm(weekly_dataframe, n_boot=300)   # dict of DataFrames: fit, comparison, channel summary, scenarios, ...
```
Outputs are stored in DuckDB schema `gp_analytics` (`mmm_*` tables) and shown on dashboard page 8. Full method and caveats: `docs/methodology.md`.

**Meridian (Google's Bayesian MMM) is not included.** It needs a different dependency stack (TensorFlow Probability, specific Python versions) and is best added as an optional advanced module *after* this transparent baseline; follow Google's current installation instructions if you add it.
