"""Write generated tables to CSV + a metadata file with checksums (proof of reproducibility)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from . import schema
from .assumptions import GenConfig


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_dataset(tables: dict, out_dir: Path, cfg: GenConfig) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"synthetic": True, "seed": cfg.seed, "scale": cfg.scale, "start_date": cfg.start_date,
            "end_date": cfg.end_date, "gross_margin_assumption": cfg.gross_margin, "tables": {}}
    for name in schema.TABLES:
        df = tables[name][schema.columns(name)]
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False, date_format="%Y-%m-%d %H:%M:%S" if "TIMESTAMP" in
                  [c[1] for c in schema.TABLES[name]["columns"]] else "%Y-%m-%d")
        meta["tables"][name] = {"rows": int(len(df)), "sha256": _sha256(path)}
    with open(out_dir / "_generation_metadata.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)
    truth = {"WARNING": "SYNTHETIC GROUND TRUTH - used only to validate the analysis, never as an input to it.",
             "experiments": tables["_ground_truth"], "assumptions": {
                 "brand_displacement": cfg.brand_displacement, "halo_strength": cfg.halo_strength,
                 "halo_decay_per_day": cfg.halo_decay_per_day, "config": asdict(cfg)}}
    with open(out_dir / "_ground_truth.json", "w") as f:
        json.dump(truth, f, indent=2, default=str)
    return meta


def read_ground_truth(raw_dir: Path) -> dict | None:
    p = Path(raw_dir) / "_ground_truth.json"
    return json.loads(p.read_text()) if p.exists() else None
