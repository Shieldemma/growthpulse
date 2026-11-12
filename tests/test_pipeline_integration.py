"""End-to-end tests: they run the real pipeline (including dbt build + 100+ dbt data tests) on a small dataset."""
import json

import duckdb
import pandas as pd
import pytest

from growthpulse import attribution as A, paths, validation, warehouse

pytestmark = pytest.mark.slow


def test_pipeline_completes_and_validation_passes(quick_pipeline):
    res = quick_pipeline["result"]
    assert all(s["status"] == "ok" for s in res["steps"]), [s for s in res["steps"] if s["status"] != "ok"]
    bad = [c for c in res["checks"] if c["status"] != "PASS"]
    assert not bad, bad


def test_dbt_tests_all_passed(quick_pipeline):
    results = json.loads((quick_pipeline["dir"] / "dbt_run_results.json").read_text())
    tests = [r for r in results if ".test." in r["unique_id"] or r["unique_id"].startswith("test.")]
    assert len(tests) > 90
    assert all(r["status"] == "pass" for r in tests), [r for r in tests if r["status"] != "pass"][:3]


def test_sql_attribution_matches_python_reference(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    tp = con.sql(f"select customer_id, session_ts, channel_name from {paths.INTERMEDIATE}.int_touchpoints").df()
    sql = con.sql(f"select attribution_model, channel_name, sum(credit) c from {paths.INTERMEDIATE}.int_attribution_credit group by 1,2").df()
    for model in A.MODELS:
        ref = A.channel_credit(tp, model)
        got = sql[sql.attribution_model == model].set_index("channel_name").c
        pd.testing.assert_series_equal(ref.sort_index(), got.sort_index(), check_names=False, atol=1e-6, rtol=1e-9)


def test_join_grain_no_double_counting(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    q = lambda s: con.sql(s).fetchone()[0]
    assert q(f"select count(*) - count(distinct payment_id) from {paths.MARTS}.fct_payments") == 0
    assert q(f"select count(*) - count(distinct customer_id) from {paths.MARTS}.fct_customer_revenue") == 0
    raw_spend = q(f"select sum(spend_usd) from {paths.RAW_SCHEMA}.ad_spend_daily")
    for m in A.MODELS:
        assert q(f"select sum(spend_usd) from {paths.MARTS}.mart_marketing_performance where attribution_model='{m}'") == pytest.approx(raw_spend)
    raw_net = q(f"select sum(gross_amount_usd) from {paths.RAW_SCHEMA}.payments") - q(f"select sum(refund_amount_usd) from {paths.RAW_SCHEMA}.refunds")
    assert q(f"select sum(net_revenue_usd) from {paths.MARTS}.fct_customer_revenue") == pytest.approx(raw_net)


def test_mmm_input_matches_spend_and_has_no_gaps(quick_pipeline):
    con = duckdb.connect(str(quick_pipeline["db"]), read_only=True)
    w = con.sql(f"select * from {paths.MARTS}.mart_mmm_weekly order by week_start").df()
    assert len(w) == 156 and (pd.to_datetime(w.week_start).diff().dropna().dt.days == 7).all()
    assert w.spend_total.sum() == pytest.approx(con.sql(f"select sum(spend_usd) from {paths.RAW_SCHEMA}.ad_spend_daily").fetchone()[0])


def test_dbt_tests_can_actually_fail(quick_pipeline, tmp_path):
    """Mutation test: corrupt a COPY of the raw data and confirm dbt's tests catch it (so green does not mean 'tests are empty')."""
    import shutil
    db = tmp_path / "corrupt.duckdb"
    shutil.copy(quick_pipeline["db"], db)
    con = duckdb.connect(str(db))
    con.execute(f"insert into {paths.RAW_SCHEMA}.payments select * from {paths.RAW_SCHEMA}.payments limit 1")      # duplicate payment id
    con.execute(f"update {paths.RAW_SCHEMA}.ad_spend_daily set spend_usd = -5 where rowid = 0")                     # negative spend
    con.close()
    r = warehouse.run_dbt(["build"], "duckdb", db, "2025-12-28")
    assert r.returncode != 0
    failed = [x["unique_id"] for x in warehouse.dbt_results() if x["status"] in ("fail", "error")]
    assert any("payment_id" in f for f in failed) and any("spend_usd" in f for f in failed), failed
    # restore the shared dbt artefacts to the healthy run so later tests/readers are not confused
    warehouse.run_dbt(["build"], "duckdb", quick_pipeline["db"], "2025-12-28")


def test_validation_detects_missing_database(tmp_path):
    checks = validation.run_checks(db_path=tmp_path / "nope.duckdb", raw_dir=tmp_path, root=tmp_path)
    assert any(c["status"] == "FAIL" for c in checks)


def test_report_is_generated_from_data_and_labels_synthetic(quick_pipeline):
    md = (quick_pipeline["dir"] / "report.md").read_text()
    assert "SYNTHETIC" in md and "Executive summary" in md and "FACTS" in md and "RECOMMENDATIONS" in md
    recs = duckdb.connect(str(quick_pipeline["db"]), read_only=True).sql(f"select * from {paths.ANALYTICS}.recommendations").df()
    assert len(recs) == 4 and recs.recommended_action.notna().all()
