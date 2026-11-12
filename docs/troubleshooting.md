# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `zsh: permission denied: /Users/you/.../growthpulse` or `is a directory` | You typed a folder path as a command | Use `cd /path/to/growthpulse` to enter a folder |
| `zsh: command not found: python` | macOS has `python3`, and the venv is not active | `python3 ...` or `source .venv/bin/activate` first |
| `ModuleNotFoundError: No module named 'growthpulse'` (or `duckdb`, `streamlit`) | venv not active, or `pip install -e .` skipped | `source .venv/bin/activate && pip install -r requirements.txt && pip install -e .` |
| Prompt has no `(.venv)` | New Terminal window | `source .venv/bin/activate` |
| `ERROR: Package requires a different Python` / pandas won't install | Python older than 3.11 | `brew install python@3.12`, delete `.venv`, rerun `bash scripts/setup_mac.sh` |
| `Missing raw CSVs ... Run python scripts/generate_data.py` | Pipeline run before data exists | `python scripts/run_pipeline.py --regenerate` |
| Dashboard: "The analytical database was not found" | Pipeline never completed | `python scripts/run_pipeline.py` then refresh |
| `IO Error: Could not set lock on file ... growthpulse.duckdb` | Another process (a second pipeline, a notebook, DB browser) holds the file | Close it, or stop the dashboard (Control+C) and rerun |
| `dbt: command not found` | venv not active | `source .venv/bin/activate` (or `python -m dbt.cli.main ...`) |
| dbt: `Could not find profile named 'growthpulse'` | dbt not told where `profiles.yml` is | `cd dbt_project && export DBT_PROFILES_DIR=.` |
| dbt: `Env var required but not provided: 'GCP_PROJECT_ID'` | Target is `bigquery` without config | `unset DBT_TARGET` (local) or set the variables (cloud) |
| dbt prints `MissingArgumentsPropertyInGenericTestDeprecation` | Newer dbt prefers an `arguments:` key under generic tests | Harmless warning; tests still run |
| Port 8501 in use | An old Streamlit is running | `streamlit run app/streamlit_app.py --server.port 8502` |
| Charts empty after changing filters | Selection excludes all data | Widen dates / re-select channels (the page shows a "No data" message) |
| Page numbers differ from the README example | Different seed/scale | Use defaults (`--seed 42 --scale 1.0`); same seed = identical data |
| `BigQueryConfigError: GCP_PROJECT_ID is not set` | BigQuery mode not configured | Follow `docs/bigquery_setup.md` steps 3-4 |
| BigQuery: `Access Denied` / `403` | Missing IAM roles or billing | Grant `BigQuery Job User`, `Data Editor`, `User`; enable billing |
| BigQuery: `Not found: Dataset ... was not found in location` | Datasets in different locations | Keep everything in `US` (`GP_BQ_LOCATION=US`) |
| BigQuery: `Query exceeded limit for bytes billed` | The safety cap protected you | Raise `GP_BQ_MAX_BYTES_BILLED` deliberately, or narrow the GA4 date vars |
| Tests: `StreamlitAPIException` / AppTest timeouts on a slow Mac | Heavy first render | Re-run; `python -m pytest -m "not slow"` skips them |

Still stuck? Run `python scripts/validate_project.py` and read the first FAIL line, then check `data/processed/pipeline_status.json`.
