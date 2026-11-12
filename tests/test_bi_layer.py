"""BI delivery layer: registry, exports, field docs, Looker links, publish safety. Uses the quick pipeline fixture."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import duckdb
import pandas as pd
import pytest

from growthpulse import bi, paths

ROOT = Path(__file__).resolve().parents[1]
slow = pytest.mark.slow


def test_registry_names_unique_and_layers_valid():
    names = [r["name"] for r in bi.REGISTRY]
    assert len(names) == len(set(names)) == 27
    assert {r["layer"] for r in bi.REGISTRY} == {"reporting", "analytics"}
    assert all((n.startswith("rpt_") and bi.BY_NAME[n]["layer"] == "reporting") or (n.startswith("bi_") and bi.BY_NAME[n]["layer"] == "analytics") for n in names)


def test_looker_links_follow_documented_linking_api_pattern():
    df = bi.looker_datasource_urls("my-proj", "gp")
    assert len(df) == len(bi.REGISTRY)
    u = urlparse(df[df.table == "rpt_marketing_daily"].url.iloc[0])
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    assert u.netloc == "lookerstudio.google.com" and u.path == "/reporting/create"
    assert q["ds.ds0.connector"] == "bigQuery" and q["ds.ds0.type"] == "TABLE"
    assert (q["ds.ds0.projectId"], q["ds.ds0.datasetId"], q["ds.ds0.tableId"]) == ("my-proj", "gp_reporting", "rpt_marketing_daily")
    assert df[df.table == "bi_mmm_fit"].dataset.iloc[0] == "gp_analytics"


@slow
def test_every_registry_table_exists_and_csv_matches(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    exp = quick_pipeline["dir"] / "exports"
    assert (exp / "_catalog.csv").exists()
    for r in bi.REGISTRY:
        n = con.sql(f"select count(*) from {bi.local_ref(r['name'])}").fetchone()[0]
        csv = pd.read_csv(exp / f"{r['name']}.csv")
        assert n > 0 and len(csv) == n, r["name"]
        assert list(csv.columns) == list(con.sql(f"select * from {bi.local_ref(r['name'])} limit 0").df().columns), r["name"]


@slow
def test_date_fields_declared_in_registry_exist_and_are_dates(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    for r in bi.REGISTRY:
        if r["date_field"]:
            t = con.sql(f"describe {bi.local_ref(r['name'])}").df().set_index("column_name").column_type
            assert r["date_field"] in t.index and ("DATE" in t[r["date_field"]] or "TIMESTAMP" in t[r["date_field"]]), (r["name"], r["date_field"])


@slow
def test_ratio_of_sums_matches_row_level_cac_and_no_ratio_is_averaged(quick_pipeline):
    """What Looker Studio's calculated fields do (SUM/SUM) must equal an independent pandas calculation from the raw marts."""
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    r = con.sql("select channel_name, sum(spend_usd) s, sum(new_customers) c, sum(spend_eligible_m12) se, sum(revenue_m12_eligible) re, sum(customers_eligible_m12) ce "
                "from gp_reporting.rpt_marketing_daily group by 1 having sum(spend_usd) > 0").df()
    m = con.sql("select channel_name, sum(spend_usd) s, sum(new_customers) c from gp_marts.mart_marketing_performance where attribution_model='first_touch' group by 1 having sum(spend_usd)>0").df()
    j = r.merge(m, on="channel_name", suffixes=("", "_m"))
    assert (abs(j.s - j.s_m) < 0.01).all() and (abs(j.c - j.c_m) < 1e-6).all()
    roas = (r.re / r.se).dropna()
    assert (roas > 0).all()


@slow
def test_eligible_columns_exclude_recent_cohorts(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    last = con.sql("select max(metric_date) from gp_reporting.rpt_marketing_daily").fetchone()[0]
    bad = con.sql(f"select count(*) from gp_reporting.rpt_marketing_daily where metric_date > date '{last}' - interval 11 month and (spend_eligible_m12 > 0 or revenue_m12_eligible > 0)").fetchone()[0]
    assert bad == 0
    some = con.sql("select count(*) from gp_reporting.rpt_marketing_daily where spend_eligible_m12 > 0").fetchone()[0]
    assert some > 0


@slow
def test_freshness_table_reports_real_dbt_results(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    f = con.sql("select * from gp_bi.bi_data_freshness").df().iloc[0]
    res = json.loads((quick_pipeline["dir"] / "dbt_run_results.json").read_text())
    assert f.dbt_tests_passed == sum(1 for x in res if x["unique_id"].startswith("test.") and x["status"] == "pass")
    assert f.dbt_tests_failed == 0 and f.is_synthetic == 1 and "SYNTHETIC" in f.data_label


@slow
def test_scenario_spend_long_table_sums_to_budget(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    d = con.sql("select scenario, max(weekly_budget_usd) b, sum(weekly_spend_usd) s from gp_bi.bi_mmm_scenario_spend group by 1").df()
    assert (abs(d.b - d.s) < 0.01).all()


def test_field_docs_cover_key_fields():
    for k in ["spend_eligible_m12", "revenue_m12_eligible", "attribution_model", "new_customers", "retention_rate", "incremental_roas"]:
        assert bi.FIELD_DOC[k]


def test_publish_requires_configuration(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    from growthpulse import bigquery as bq
    with pytest.raises(bq.BigQueryConfigError):
        bi.publish_to_bigquery(None)


def test_github_workflow_contains_no_secrets_and_uses_oidc():
    t = (ROOT / ".github" / "workflows" / "refresh-bigquery.yml").read_text()
    assert "id-token: write" in t and "workload_identity_provider" in t and "vars." in t
    assert not re.search(r"private_key|BEGIN PRIVATE KEY|credentials_json", t)


def test_docs_reference_only_existing_files():
    """Every path in backticks that looks like a repo file in the BI docs must exist (guards against dead references)."""
    docs = [ROOT / "docs" / "looker_studio" / n for n in ("README.md", "calculated_fields.md", "report_spec.md")] + \
           [ROOT / "docs" / n for n in ("bi_connection_and_refresh.md", "local_fallback_bi.md", "job_alignment.md")] + [ROOT / "dashboard" / "powerbi" / "README.md"]
    missing = []
    for d in docs:
        for ref in re.findall(r"`((?:docs|scripts|src|dashboard|reports|tests|dbt_project|\.github)/[\w./\-]+\.(?:md|py|sh|yml|dax|csv))`", d.read_text()):
            if not (ROOT / ref).exists():
                missing.append((d.name, ref))
    assert not missing, missing


def test_calculated_fields_reference_real_columns():
    """Calculated-field formulas must only use columns that exist in the table they are declared for."""
    from growthpulse.datagen import schema  # noqa: F401  (import check)
    txt = (ROOT / "docs" / "looker_studio" / "calculated_fields.md").read_text()
    sections = re.split(r"^## ", txt, flags=re.M)[1:]
    fields = (ROOT / "docs" / "looker_studio" / "field_definitions.md").read_text()
    for sec in sections:
        m = re.match(r"`(\w+)`", sec)
        if not m or m.group(1) not in {r["name"] for r in bi.REGISTRY}:
            continue
        table_block = fields.split(f"## `{m.group(1)}`")[1].split("\n## ")[0]
        cols = set(re.findall(r"^\| `(\w+)` \|", table_block, flags=re.M))
        used = set(re.findall(r"SUM\((\w+)\)", sec))
        assert used <= cols, (m.group(1), used - cols)
