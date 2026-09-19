"""Download the 9 Olist raw CSVs into data/raw/ and verify them (Day 1).

- Source: mirrored Olist CSVs on GitHub (the mirror hosts the same files that
  ship on Kaggle: 8 CSVs + the geolocation dataset as a zip).
- Verifies each file against the documented Kaggle row counts in config.
- Writes data/raw/_manifest.json (per-file rows + sha256) for Day 2 /
  schema tests. Stdlib-only so it runs before the venv finishes installing.

Usage:
    python -m src.data.download_olist
"""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from src.config import project_path, load_config

MANIFEST_NAME = "_manifest.json"


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {dest.name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "opencode-olist"})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(256 * 1024):
            fh.write(chunk)


def _count_rows(path: Path) -> int:
    """Data rows only (header excluded)."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # skip header
        return sum(1 for _ in reader)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(256 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _extract_geolocation(cfg: dict, raw_dir: Path, tmp_zip: Path) -> Path:
    """Geolocation ships zipped on the mirror; extract to the canonical name."""
    out_path = raw_dir / "olist_geolocation_dataset.csv"
    with zipfile.ZipFile(tmp_zip) as zf:
        # Expect exactly one CSV inside
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if len(members) != 1:
            raise RuntimeError(f"expected 1 CSV in {tmp_zip.name}, found {members}")
        with zf.open(members[0]) as src, open(out_path, "wb") as dst:
            while chunk := src.read(256 * 1024):
                dst.write(chunk)
    return out_path


def main() -> int:
    cfg = load_config()
    olist = cfg["olist"]
    raw_dir = project_path(cfg["paths"]["raw_data"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict = {}
    failures: list[str] = []

    for filename, spec in olist["files"].items():
        expected = spec["rows"]
        if filename == "olist_geolocation_dataset.csv":
            tmp_zip = raw_dir / olist["geo_zip_name"]
            _download(f'{olist["base_url"]}/{urllib.parse.quote(olist["geo_zip_name"])}', tmp_zip)
            path = _extract_geolocation(olist, raw_dir, tmp_zip)
            tmp_zip.unlink(missing_ok=True)
        else:
            path = raw_dir / filename
            _download(f'{olist["base_url"]}/{filename}', path)

        rows = _count_rows(path)
        sha = _sha256(path)
        ok = rows == expected
        manifest[filename] = {
            "rows": rows,
            "expected_rows": expected,
            "sha256": sha,
            "ok": ok,
        }
        status = "OK" if ok else f"MISMATCH (expected {expected})"
        print(f"  {filename}: {rows} rows  sha256={sha[:12]}  -> {status}")
        if not ok:
            failures.append(filename)

    (raw_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"\nManifest written to {raw_dir / MANIFEST_NAME}")

    if failures:
        print(f"FAILED verification for: {', '.join(failures)}")
        return 1
    print("All 9 Olist files verified against documented row counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())