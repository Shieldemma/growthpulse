import json

import pandas as pd
import streamlit as st

from growthpulse import paths, validation
from lib import data, ui


def render():
    ui.header("Data Quality and Pipeline Status", "Evidence that the pipeline ran, the tests passed and the totals reconcile.")
    st.caption("This page reads the real status files written by the pipeline; it does not display hardcoded 'green' values.")
    s = data.status()
    if not s:
        st.error("No pipeline status found.")
        st.code("python scripts/run_pipeline.py")
        return
    st.markdown(f"**Last pipeline run finished (UTC):** `{s.get('finished_utc')}`  \n**Database:** `{s.get('db_path')}`")
    steps = pd.DataFrame([{"step": x["step"], "status": x["status"], "seconds": x["seconds"]} for x in s["steps"]])
    st.dataframe(steps, width="stretch", hide_index=True)
    st.subheader("dbt models and tests")
    res = pd.DataFrame(data.dbt_results())
    if res.empty:
        ui.empty_state("No dbt results file.", "Run the pipeline to create data/processed/dbt_run_results.json.")
    else:
        res["type"] = res.unique_id.str.split(".").str[0]
        summ = res.groupby(["type", "status"]).size().unstack(fill_value=0)
        st.dataframe(summ, width="stretch")
        fails = res[res.status.isin(["fail", "error"])]
        if len(fails):
            st.error(f"{len(fails)} dbt nodes failed")
            st.dataframe(fails, width="stretch")
        else:
            st.success(f"All {len(res)} dbt nodes succeeded (models built, tests passed).")
        with st.expander("All dbt nodes"):
            st.dataframe(res, width="stretch", hide_index=True)
    st.subheader("Live validation (run now)")
    if data.db_ready():
        checks = pd.DataFrame(validation.run_checks())
        bad = checks[checks.status != "PASS"]
        (st.success if bad.empty else st.error)(f"{len(checks) - len(bad)}/{len(checks)} checks passed")
        st.dataframe(checks, width="stretch", hide_index=True)
    st.subheader("Data provenance")
    m = data.meta()
    if m:
        st.markdown(f"Synthetic data, seed `{m['seed']}`, scale `{m['scale']}`, {m['start_date']} to {m['end_date']}. Regenerating with the same seed reproduces identical files (SHA-256 below).")
        st.dataframe(pd.DataFrame([{"table": k, "rows": v["rows"], "sha256": v["sha256"][:16] + "..."} for k, v in m["tables"].items()]), width="stretch", hide_index=True)
    st.subheader("BigQuery + dbt mode")
    st.info("**Status: implemented, NOT verified.** The BigQuery/GA4 models and loaders were written and syntax-checked offline, but no Google Cloud credentials were available, so no cloud query was executed. "
            "See `docs/bigquery_setup.md` for the exact commands to verify it yourself.")
