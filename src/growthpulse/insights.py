"""Automated weekly insight brief (deterministic) + an LLM-ready prompt (AI-assisted narrative, human-checked).

All numbers are computed here from the BI tables; an LLM would only be asked to PHRASE them. Nothing in this module calls an
AI service. The prompt file tells the model to use only the supplied facts, so figures can be verified against the JSON.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import bi


def _pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.0%}"


def build_facts(con, weeks: int = 8) -> dict:
    d = con.sql(f"select week_start, channel_name, spend_usd, new_customers, signups from {bi.local_ref('rpt_marketing_daily')}").df()
    d["week_start"] = pd.to_datetime(d["week_start"])
    last = d.week_start.max()
    cut_recent = last - pd.Timedelta(weeks=weeks - 1)
    cut_prev = cut_recent - pd.Timedelta(weeks=weeks)
    recent, prev = d[d.week_start >= cut_recent], d[(d.week_start >= cut_prev) & (d.week_start < cut_recent)]

    def agg(x):
        g = x.groupby("channel_name").agg(spend=("spend_usd", "sum"), customers=("new_customers", "sum"), signups=("signups", "sum"))
        g["cac"] = np.where((g.spend > 0) & (g.customers > 0), g.spend / g.customers.replace(0, np.nan), np.nan)
        return g
    a, b = agg(recent), agg(prev)
    rows = []
    for ch in a.index:
        r, p = a.loc[ch], b.loc[ch] if ch in b.index else None
        ch_row = {"channel": ch, "spend_recent": float(r.spend), "customers_recent": float(r.customers), "cac_recent": None if pd.isna(r.cac) else float(r.cac)}
        if p is not None:
            ch_row.update({"spend_change": None if p.spend == 0 else float(r.spend / p.spend - 1),
                           "customers_change": None if p.customers == 0 else float(r.customers / p.customers - 1),
                           "cac_change": None if pd.isna(p.cac) or pd.isna(r.cac) else float(r.cac / p.cac - 1)})
        rows.append(ch_row)
    wk = d[d.channel_name.isin(["paid_search", "paid_social", "display", "affiliate"])].groupby("week_start").agg(spend=("spend_usd", "sum"), customers=("new_customers", "sum")).sort_index()
    anomalies = []
    for col in ("spend", "customers"):
        z = (wk[col] - wk[col].rolling(12).mean().shift(1)) / wk[col].rolling(12).std().shift(1)
        for dt, v in z[(z.abs() > 2.5) & (z.index >= last - pd.Timedelta(weeks=26))].items():
            anomalies.append({"week_start": str(dt.date()), "metric": f"paid {col}", "z_score_vs_trailing_12w": round(float(v), 2)})
    fresh = con.sql(f"select * from {bi.local_ref('bi_data_freshness')}").df().iloc[0]
    exp = con.sql(f"select experiment_id, significant, mde_relative, verdict from {bi.local_ref('bi_experiment_results')}").df()
    open_items = [f"{r.experiment_id}: {r.verdict}" for r in exp.itertuples() if not r.significant]
    diag = con.sql(f"select check_name from (select \"check\" as check_name, status from {bi.local_ref('bi_mmm_diagnostics')}) where status <> 'ok'").df().check_name.tolist()
    return {"window": f"last {weeks} weeks (through the week starting {last.date()}) vs the previous {weeks} weeks", "data_label": "SYNTHETIC DATA",
            "data_end_date": str(pd.Timestamp(fresh.data_end_date).date()), "channels": rows, "anomalies": anomalies,
            "open_items": open_items, "mmm_diagnostics_flagged": diag}


def render_brief(facts: dict) -> str:
    L = ["# Weekly growth insight brief (auto-generated)\n", f"> **{facts['data_label']}.** Window: {facts['window']}. Numbers are computed deterministically; read them before sharing.\n",
         "| Channel | Spend (recent) | Spend change | Customers | Customers change | CAC | CAC change |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(facts["channels"], key=lambda x: -x["spend_recent"]):
        L.append(f"| {r['channel']} | ${r['spend_recent']:,.0f} | {_pct(r.get('spend_change'))} | {r['customers_recent']:,.0f} | {_pct(r.get('customers_change'))} | "
                 f"{'n/a' if r['cac_recent'] is None else '$%.0f' % r['cac_recent']} | {_pct(r.get('cac_change'))} |")
    L.append("\n## Anomalies in the last 26 weeks (paid totals, |z| > 2.5 vs trailing 12 weeks)")
    L += [f"- {a['week_start']}: {a['metric']} z = {a['z_score_vs_trailing_12w']}" for a in facts["anomalies"]] or ["- none"]
    L.append("\n## Open items")
    L += [f"- {x}" for x in facts["open_items"]] or ["- none"]
    L.append("\n## Model health")
    L.append("- MMM diagnostics flagged: " + (", ".join(facts["mmm_diagnostics_flagged"]) or "none"))
    return "\n".join(L) + "\n"


def render_llm_prompt(facts: dict) -> str:
    return ("You are a senior growth analyst writing a 150-word weekly note for a marketing director.\n"
            "RULES: use ONLY the numbers in the JSON below; do not invent causes; say 'associated with' not 'caused by' unless an experiment is cited; "
            "mention that the data are synthetic; flag open items and anomalies; end with two concrete next steps.\n\n"
            "FACTS (JSON):\n```json\n" + json.dumps(facts, indent=2, default=str) + "\n```\n"
            "A human must verify every figure against the dashboard before this is shared.\n")


def write_outputs(con, out_dir) -> dict:
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    facts = build_facts(con)
    (out_dir / "weekly_insight_brief.md").write_text(render_brief(facts))
    (out_dir / "weekly_insight_llm_prompt.md").write_text(render_llm_prompt(facts))
    return {"channels": len(facts["channels"]), "anomalies": len(facts["anomalies"])}
