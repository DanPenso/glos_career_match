"""Download Companies House BasicCompanyData, rank top GL/BS employers, upsert seed.

Usage:
  .venv\\Scripts\\python scripts/01_fetch_companies_house_employers.py
  .venv\\Scripts\\python scripts/01_fetch_companies_house_employers.py --top 100 --rebuild

Notes:
  - Free monthly snapshot (no API key). Large download ~400MB+ to data/raw/.
  - Ranking uses accounts category as a size proxy (not exact headcount).
  - Includes Gloucestershire (GL*) and Bristol (BS*) registered offices.
  - Public-sector anchors (GCHQ, CGI, …) are merged from
    data/seed/public_sector_anchors.csv because they rarely appear as local CH rows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.etl.companies_house import (
    CH_ZIP,
    download_basic_company_data,
    load_gl_companies_from_zip,
    load_public_anchors,
    rank_gl_employers,
    ranked_to_seed_rows,
    upsert_into_seed,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=100, help="Top N CH employers to consider")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use existing data/raw/companies_house_basic.zip only",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="After upsert, run build_company_masters.py",
    )
    parser.add_argument(
        "--reset-seed-to-curated",
        type=int,
        default=0,
        metavar="N",
        help="Before upsert, keep only the first N rows of companies_seed.csv (e.g. 27)",
    )
    parser.add_argument(
        "--candidates-out",
        type=Path,
        default=ROOT / "data" / "seed" / "companies_house_top100.csv",
    )
    args = parser.parse_args()

    if not args.skip_download:
        print("Downloading / verifying Companies House BasicCompanyData zip…")
        path = download_basic_company_data(CH_ZIP, force=args.force_download)
        print(f"  Using {path} ({path.stat().st_size / 1e6:.1f} MB)")
    elif not CH_ZIP.exists():
        raise SystemExit(f"Missing {CH_ZIP}; run without --skip-download")

    print("Filtering Active companies with GL* / BS* registered-office postcodes…")
    gl = load_gl_companies_from_zip(CH_ZIP)
    print(f"  GL/BS active rows: {len(gl)}")

    print(f"Ranking top {args.top} by accounts-category size proxy (balanced GL/BS)…")
    ranked = rank_gl_employers(gl, top_n=args.top)
    print(f"  Ranked unique employers: {len(ranked)}")
    if "region" in ranked.columns:
        print(ranked["region"].value_counts().to_string())

    seed_shaped = ranked_to_seed_rows(ranked)
    args.candidates_out.parent.mkdir(parents=True, exist_ok=True)
    # Persist audit trail with CH number + score
    audit = ranked[
        [
            "name",
            "company_number",
            "town",
            "postcode",
            "account_category",
            "size_score",
            "size_band",
            "sectors",
            "website",
        ]
    ].copy()
    audit.to_csv(args.candidates_out, index=False)
    print(f"  Wrote candidates -> {args.candidates_out}")

    seed_path = ROOT / "data" / "seed" / "companies_seed.csv"
    if args.reset_seed_to_curated > 0:
        import pandas as pd

        curated = pd.read_csv(seed_path).head(args.reset_seed_to_curated)
        curated.to_csv(seed_path, index=False)
        print(f"Reset seed to first {len(curated)} curated rows")

    anchors = load_public_anchors()
    print(f"Public-sector anchors available: {len(anchors)}")

    stats = upsert_into_seed(
        seed_path,
        seed_shaped,
        anchors=anchors,
    )
    print(
        f"Seed upsert: before={stats['seed_before']} "
        f"added={stats['added']} after={stats['seed_after']}"
    )

    if args.rebuild:
        import subprocess

        print("Rebuilding company/opportunity masters...")
        subprocess.check_call(
            [sys.executable, str(ROOT / "scripts" / "build_company_masters.py")],
            cwd=str(ROOT),
        )


if __name__ == "__main__":
    main()
