"""Build data/seed/verified_programmes.csv from curated seed opportunities.

Run after editing opportunities_seed.csv or companies_seed.csv:
  .venv\\Scripts\\python scripts/build_verified_programmes.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.programmes import validate_programmes

SEED_DIR = ROOT / "data" / "seed"
OUT_PATH = SEED_DIR / "verified_programmes.csv"
VERIFIED_DATE = date.today().isoformat()


def _careers_url(website: str) -> str:
    base = str(website or "").strip().rstrip("/")
    if not base.startswith("http"):
        return ""
    if base.endswith("/careers") or "/careers" in base:
        return base
    return f"{base}/careers"


def main() -> None:
    companies = pd.read_csv(SEED_DIR / "companies_seed.csv")
    opportunities = pd.read_csv(SEED_DIR / "opportunities_seed.csv")
    website_by_id = dict(zip(companies["company_id"], companies["website"]))

    rows: list[dict[str, str]] = []
    for _, opp in opportunities.iterrows():
        company_id = str(opp["company_id"])
        website = str(website_by_id.get(company_id) or "").strip()
        evidence = _careers_url(website) or website
        if not evidence.startswith("http"):
            continue
        rows.append(
            {
                "programme_id": str(opp["opportunity_id"]),
                "company_id": company_id,
                "programme_title": str(opp["title"]).strip(),
                "programme_type": str(opp["entry_route"]).strip(),
                "level": str(opp.get("level") or "").strip(),
                "summary": str(opp.get("description") or "").strip()[:240],
                "evidence_url": evidence,
                "last_verified_at": VERIFIED_DATE,
                "status": "active",
                "confidence": "verified",
            }
        )

    out = pd.DataFrame(rows)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} verified programmes -> {OUT_PATH}")

    warnings = validate_programmes(out)
    if warnings:
        print("Validation warnings:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("Validation OK")


if __name__ == "__main__":
    main()
