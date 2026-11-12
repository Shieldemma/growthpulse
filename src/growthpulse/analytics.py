"""Python-side analytics that run AFTER dbt: experiments and the MMM. Results are written to DuckDB schema gp_analytics."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import experiment as E
from . import geo_lift, lifecycle
from . import paths
from .datagen import read_ground_truth
from .mmm.run import run_mmm


def write_table(con, table: str, df: pd.DataFrame, schema: str = paths.ANALYTICS) -> int:
    con.execute(f"create schema if not exists {schema}")
    con.register("_tmp_df", df)
    con.execute(f"create or replace table {schema}.{table} as select * from _tmp_df")
    con.unregister("_tmp_df")
    return len(df)


def run_experiments(con, raw_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    cat = con.sql(f"select * from {paths.STAGING}.stg_experiment_catalog order by 1").df()
    assign = con.sql(f"select * from {paths.STAGING}.stg_experiment_assignments").df()
    results, balance, contam = [], [], []
    for _, r in cat.iterrows():
        d = assign[assign.experiment_id == r.experiment_id]
        res = E.analyze_experiment(d, r.test_spend_usd, r.attributed_revenue_usd, r.experiment_id, alpha=r.planned_alpha)
        row = res.to_dict()
        row.update(experiment_name=r.experiment_name, channel_id=r.channel_id, hypothesis=r.hypothesis,
                   outcome_window_days=int(r.outcome_window_days), alpha=r.planned_alpha)
        results.append(row)
        b = E.covariate_balance(d)
        b.insert(0, "experiment_id", r.experiment_id)
        balance.append(b)
        c = E.contamination_summary(d)
        contam.append({"experiment_id": r.experiment_id, **{k: v for k, v in c.items() if k != "interpretation"}})
    out = {"experiment_results": pd.DataFrame(results), "experiment_balance": pd.concat(balance, ignore_index=True),
           "experiment_contamination": pd.DataFrame(contam)}
    truth = read_ground_truth(raw_dir or paths.DATA_RAW)
    if truth:
        out["experiment_ground_truth"] = pd.DataFrame(
            [{"experiment_id": k, **v} for k, v in truth["experiments"].items()])
    return out


def run_geo_and_lifecycle(con, gross_margin: float = 0.80) -> dict[str, pd.DataFrame]:
    out = {}
    gcat = con.sql(f"select * from {paths.STAGING}.stg_geo_experiment_catalog").df().iloc[0]
    gout = con.sql(f"select * from {paths.STAGING}.stg_geo_daily_outcomes").df()
    res, weekly = geo_lift.analyze_geo_lift(gout, gcat)
    out["geo_lift_results"], out["geo_lift_weekly"] = res, weekly
    lcat = con.sql(f"select * from {paths.STAGING}.stg_lifecycle_experiment_catalog").df().iloc[0]
    users = con.sql(f"select * from {paths.STAGING}.stg_lifecycle_experiment_users").df()
    lres, lsum = lifecycle.analyze_lifecycle(users, lcat, gross_margin)
    out["lifecycle_results"], out["lifecycle_value"] = lres, lsum
    return out


def calibration_table(exp: pd.DataFrame, geo: pd.DataFrame, mmm_sum: pd.DataFrame) -> pd.DataFrame:
    """Compare the MMM's average ROI per channel with experiment-implied INCREMENTAL ROI (both are first-payment revenue per $).
    If the experiment value lies outside the MMM 90% interval the MMM is flagged as mis-calibrated for that channel and a
    calibration factor (experiment ROI / MMM ROI, bounded 0.25-4) is shown. This is a diagnostic, not an automatic correction."""
    m = mmm_sum.set_index("channel")
    rows = []
    evidence = [(r.experiment_id, r.channel_id.replace("ch_", ""), r.incremental_roas, "user-level holdout", bool(r.significant))
                for _, r in exp.iterrows()]
    evidence += [(r.experiment_id, "paid_search", r.incremental_roas, "geo holdout (DiD)", bool(r.significant)) for _, r in geo.iterrows()]
    for eid, ch, iroas, kind, sig in evidence:
        if ch not in m.index:
            continue
        r = m.loc[ch]
        inside = bool(r.avg_roi_p05 <= iroas <= r.avg_roi_p95)
        factor = float(np.clip(iroas / r.avg_roi, 0.25, 4.0)) if r.avg_roi > 0 and iroas > 0 else float("nan")
        rows.append({"channel": ch, "experiment_id": eid, "experiment_type": kind, "experiment_significant": sig,
                     "experiment_incremental_roas": iroas, "mmm_avg_roi": r.avg_roi, "mmm_roi_p05": r.avg_roi_p05,
                     "mmm_roi_p95": r.avg_roi_p95, "experiment_inside_mmm_interval": inside, "calibration_factor": factor,
                     "calibrated_mmm_roi": r.avg_roi * factor if not np.isnan(factor) else float("nan"),
                     "reading": ("Consistent: experiment lies inside the MMM interval." if inside else
                                 ("MMM over-states this channel versus the experiment." if iroas < r.avg_roi_p05 else "MMM under-states this channel versus the experiment."))
                                + ("" if sig else " (experiment itself not significant - treat with caution)")})
    return pd.DataFrame(rows)


def run_all(db_path=None, n_boot: int = 300, raw_dir: Path | None = None) -> dict[str, int]:
    from . import warehouse
    con = warehouse.connect(db_path)
    counts = {}
    try:
        for name, df in run_experiments(con, raw_dir).items():
            counts[name] = write_table(con, name, df)
        for name, df in run_geo_and_lifecycle(con).items():
            counts[name] = write_table(con, name, df)
        weekly = con.sql(f"select * from {paths.MARTS}.mart_mmm_weekly").df()
        mmm_out = run_mmm(weekly, n_boot=n_boot)
        for name, df in mmm_out.items():
            counts[name] = write_table(con, name, df)
        cal = calibration_table(con.sql(f"select * from {paths.ANALYTICS}.experiment_results").df(),
                                con.sql(f"select * from {paths.ANALYTICS}.geo_lift_results").df(), mmm_out["mmm_channel_summary"])
        counts["mmm_calibration"] = write_table(con, "mmm_calibration", cal)
    finally:
        con.close()
    return counts
