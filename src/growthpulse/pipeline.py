"""Local Demo Mode pipeline: generate -> load -> dbt build -> experiments + MMM -> report -> exports -> validate."""
from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import analytics, bi, insights, paths, reporting, validation, warehouse
from .datagen import GenConfig, generate, write_dataset


class PipelineError(RuntimeError):
    pass


def run(regenerate: bool = False, seed: int = 42, scale: float = 1.0, n_boot: int = 300,
        raw_dir: Path | None = None, db_path: Path | None = None, report_path: Path | None = None,
        export_dir: Path | None = None, status_path: Path | None = None, log=print) -> dict:
    raw_dir = Path(raw_dir or paths.DATA_RAW)
    db_path = Path(db_path or paths.DUCKDB_PATH)
    status_path = Path(status_path or paths.STATUS_JSON)
    report_path = Path(report_path or paths.REPORTS / "business_report.md")
    steps: list[dict] = []

    def step(name, fn):
        t = time.time()
        log(f"[{len(steps) + 1}] {name} ...")
        try:
            detail = fn()
            steps.append({"step": name, "status": "ok", "seconds": round(time.time() - t, 1), "detail": detail})
            log(f"    done in {time.time() - t:.1f}s")
            return detail
        except Exception as e:  # noqa: BLE001
            steps.append({"step": name, "status": "failed", "seconds": round(time.time() - t, 1), "detail": str(e)[:2000]})
            _save(status_path, steps, db_path)
            raise

    def gen():
        if regenerate or not (raw_dir / "_generation_metadata.json").exists():
            cfg = GenConfig(seed=seed, scale=scale)
            meta = write_dataset(generate(cfg), raw_dir, cfg)
            return {"generated": True, "rows": {k: v["rows"] for k, v in meta["tables"].items()}}
        return {"generated": False, "note": "reused existing CSVs (use --regenerate to rebuild)"}

    step("Generate SYNTHETIC data", gen)
    step("Load raw CSVs into DuckDB", lambda: warehouse.load_raw(raw_dir, db_path))
    end_date = warehouse.data_end_date(raw_dir)

    def dbt_build():
        r = warehouse.run_dbt(["build"], "duckdb", db_path, end_date)
        res = warehouse.dbt_results()
        status_path.parent.mkdir(parents=True, exist_ok=True)
        (status_path.parent / "dbt_run_results.json").write_text(json.dumps(res, indent=1))
        n_fail = sum(1 for x in res if x["status"] in ("fail", "error"))
        if r.returncode != 0:
            raise PipelineError(f"dbt build failed ({n_fail} failing nodes). Last output:\n" + (r.stdout or "")[-1500:] + (r.stderr or "")[-500:])
        return {"nodes": len(res), "passed": sum(1 for x in res if x["status"] in ("pass", "success")), "failed": n_fail}

    step("dbt build (models + tests) on DuckDB", dbt_build)
    step("Experiments + Marketing Mix Model", lambda: analytics.run_all(db_path, n_boot, raw_dir))

    def report():
        con = warehouse.connect(db_path)
        try:
            gm = json.loads((raw_dir / "_generation_metadata.json").read_text()).get("gross_margin_assumption", 0.8)
            md, econ, recs = reporting.build_report(con, gm, end_date)
            analytics.write_table(con, "recommendations", recs)
            analytics.write_table(con, "channel_economics", econ)
        finally:
            con.close()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md)
        return {"report": str(report_path), "words": len(md.split())}

    step("Generate business report + recommendations", report)

    def export():
        con = warehouse.connect(db_path)
        try:
            tables = bi.build_bi_tables(con, status_dir=status_path.parent, raw_dir=raw_dir)
            bi.write_bi_tables(con, tables)
            return bi.export_csv(con, export_dir)
        finally:
            con.close()

    step("Build BI tables + export CSVs (Looker Studio / Power BI / any BI tool)", export)

    def brief():
        con = warehouse.connect(db_path)
        try:
            return insights.write_outputs(con, report_path.parent)
        finally:
            con.close()

    step("Automated weekly insight brief + LLM-ready prompt", brief)
    checks = validation.run_checks(db_path, raw_dir, report_path=report_path, export_dir=Path(export_dir or paths.BI_EXPORTS))
    bad = [c for c in checks if c["status"] != "PASS"]
    steps.append({"step": "Validate outputs", "status": "ok" if not bad else "failed", "seconds": 0,
                  "detail": {"checks": len(checks), "failed": [c["check"] for c in bad]}})
    _save(status_path, steps, db_path, checks)
    return {"steps": steps, "checks": checks}


def _save(status_path: Path, steps, db_path, checks=None):
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps({"finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                       "db_path": str(db_path), "steps": steps, "validation": checks or []}, indent=1, default=str))
