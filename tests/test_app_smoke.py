"""Dashboard smoke tests: every page renders without exceptions, filters change results, empty/error states are friendly."""
import importlib
import sys

import pytest
from streamlit.testing.v1 import AppTest

from growthpulse import paths

pytestmark = pytest.mark.slow
PAGES = ["p01_executive", "p02_channels", "p03_funnel", "p04_unit_economics", "p05_cohorts",
         "p06_attribution", "p07_incrementality", "p08_mmm", "p09_quality", "p10_methodology"]


@pytest.fixture()
def app_env(quick_pipeline, monkeypatch):
    import streamlit as st
    st.cache_data.clear()
    from lib import data
    monkeypatch.setattr(paths, "DUCKDB_PATH", quick_pipeline["db"])
    monkeypatch.setattr(data, "DB", quick_pipeline["db"])
    monkeypatch.setattr(paths, "STATUS_JSON", quick_pipeline["dir"] / "status.json")
    monkeypatch.setattr(paths, "DATA_RAW", quick_pipeline["raw"])
    monkeypatch.setattr(paths, "DATA_PROCESSED", quick_pipeline["dir"])
    return quick_pipeline


def run_page(name):
    code = f"import sys; sys.path[:0]=['app','src']\nfrom views import {name}\n{name}.render()"
    return AppTest.from_string(code, default_timeout=180).run()


@pytest.mark.parametrize("name", PAGES)
def test_page_renders_without_exception(app_env, name):
    at = run_page(name)
    assert not at.exception, [e.value for e in at.exception]


def test_every_page_labels_synthetic_data(app_env):
    for name in PAGES[:9]:
        at = run_page(name)
        assert any("SYNTHETIC" in w.value for w in at.warning), name


def test_filters_change_computed_numbers(app_env):
    full = run_page("p02_channels")
    code = "import sys; sys.path[:0]=['app','src']\nfrom views import p02_channels\np02_channels.render()"
    at = AppTest.from_string(code, default_timeout=180).run()
    at.sidebar.multiselect(key="f_channels").set_value(["paid_search"]).run()
    assert not at.exception
    kp_full = {m.label: m.value for m in full.metric}
    kp_f = {m.label: m.value for m in at.metric}
    assert kp_full["Total spend"] != kp_f["Total spend"] and kp_f["Paid channels"] == "1"


def test_empty_selection_shows_friendly_state_not_error(app_env):
    code = "import sys; sys.path[:0]=['app','src']\nfrom views import p01_executive\np01_executive.render()"
    at = AppTest.from_string(code, default_timeout=180).run()
    at.sidebar.multiselect(key="f_channels").set_value([]).run()
    assert not at.exception and any("No data" in i.value for i in at.info)


def test_missing_database_gives_actionable_error(tmp_path, monkeypatch):
    from lib import data
    monkeypatch.setattr(data, "DB", tmp_path / "missing.duckdb")
    at = run_page("p01_executive")
    assert not at.exception and any("not found" in e.value for e in at.error)
