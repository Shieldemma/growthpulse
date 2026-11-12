import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]

from growthpulse.datagen import GenConfig, generate, write_dataset  # noqa: E402


@pytest.fixture(scope="session")
def quick_tables():
    """Small (scale 0.15) synthetic dataset, generated once per test session."""
    return generate(GenConfig(seed=7, scale=0.15))


@pytest.fixture(scope="session")
def quick_pipeline(tmp_path_factory):
    """Full local pipeline (generate -> DuckDB -> dbt build+tests -> analytics -> report) on a small dataset in a temp dir."""
    from growthpulse import pipeline
    d = tmp_path_factory.mktemp("gp")
    res = pipeline.run(regenerate=True, seed=7, scale=0.15, n_boot=30, raw_dir=d / "raw", db_path=d / "gp.duckdb",
                       report_path=d / "report.md", export_dir=d / "exports", status_path=d / "status.json", log=lambda *_: None)
    return {"dir": d, "result": res, "db": d / "gp.duckdb", "raw": d / "raw"}
