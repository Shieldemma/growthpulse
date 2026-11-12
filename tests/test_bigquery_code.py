"""BigQuery code tests that need NO credentials: configuration errors, schema mapping, offline SQL compile.
Live-cloud behaviour is NOT tested here (see docs/bigquery_setup.md for how to verify it yourself)."""
import pytest

from growthpulse import bigquery as bq
from growthpulse.datagen import schema


def test_missing_project_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(bq.BigQueryConfigError, match="GCP_PROJECT_ID"):
        bq.settings()


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")
    for k in ("GP_BQ_DATASET", "GP_BQ_RAW_DATASET", "GP_BQ_LOCATION"):
        monkeypatch.delenv(k, raising=False)
    s = bq.settings()
    assert s == {"project": "my-proj", "dataset": "growthpulse", "raw_dataset": "growthpulse_raw", "location": "US"}


def test_every_raw_column_maps_to_a_bigquery_type():
    for t, spec in schema.TABLES.items():
        for _, typ, _ in spec["columns"]:
            assert typ in schema.BQ_TYPE_MAP, (t, typ)
    fields = bq.bq_schema("payments")
    assert [f.name for f in fields] == schema.columns("payments")
    assert {f.name: f.field_type for f in fields}["payment_date"] == "DATE"


def test_no_credentials_means_error_not_fake_success(monkeypatch, tmp_path):
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "does_not_exist.json"))
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
    with pytest.raises(Exception):      # either BigQueryConfigError or a google-auth error: never a silent success
        bq.check_connection()


def test_no_secrets_in_repo_config():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for f in [root / "dbt_project" / "profiles.yml", root / ".env.example"]:
        text = f.read_text()
        assert "BEGIN PRIVATE KEY" not in text and "private_key" not in text
    assert "*.json" in (root / ".gitignore").read_text() or "service-account" in (root / ".gitignore").read_text()
