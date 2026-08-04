#!/usr/bin/env python3
"""Fetch the aggregated 6-dataset corpus from Kaggle and stage it locally.

Canonical source:
  https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data
  DOI: 10.34740/kaggle/dsv/18346203

Downloads via kagglehub (requires ~/.kaggle/kaggle.json or KAGGLE_USERNAME /
KAGGLE_KEY env vars), then symlinks/copies known files into data/raw/<source>/
so every ingest adapter finds its input at a stable path. Unknown files are
listed so the MAPPING table can be extended as the Kaggle layout evolves.

Usage:  python3 data/fetch_kaggle.py [--copy]   (default: symlink)
"""
import argparse, os, shutil, sys
from pathlib import Path

DATASET = "rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data"
RAW = Path(__file__).resolve().parent / "raw"

# filename-substring (lowercase) -> staging subdirectory
MAPPING = [
    ("per_flight", "uav_ew_bench_2026"),
    ("per_point", "uav_ew_bench_2026"),
    ("crossings", "uav_ew_bench_2026"),
    ("uavids", "uavids_2025"),
    ("_label.bin", "hcrl_uavcan"),
    ("uav-cas_ts", "uav_cas"),
    ("uav-cas_stat", "uav_cas"),
    ("ulg", "uav_attack_whelan"),
    ("ulog", "uav_attack_whelan"),
    ("gps_spoof", "uav_attack_whelan"),
    ("jamming", "uav_attack_whelan"),
    ("datamut", "datamut_sim"),
]


def stage(src: Path, dest_dir: Path, copy: bool):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        return
    if copy:
        shutil.copy2(src, dest)
    else:
        dest.symlink_to(src)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", action="store_true", help="copy instead of symlink")
    a = ap.parse_args()

    try:
        import kagglehub
    except ImportError:
        print("pip install kagglehub  (and configure Kaggle credentials)"); return 1

    path = Path(kagglehub.dataset_download(DATASET))
    print("Kaggle cache:", path)

    staged, unknown = 0, []
    for f in sorted(path.rglob("*")):
        if not f.is_file():
            continue
        name = f.name.lower()
        for needle, sub in MAPPING:
            if needle in name:
                stage(f, RAW / sub, a.copy); staged += 1
                break
        else:
            unknown.append(str(f.relative_to(path)))

    print(f"staged {staged} files under {RAW}")
    if unknown:
        print(f"{len(unknown)} unmapped files (extend MAPPING if needed):")
        for u in unknown[:20]:
            print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
