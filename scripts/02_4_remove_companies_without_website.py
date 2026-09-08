"""Remove seed employers with no public website from seed/master and related tables."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.labels import public_employer_website  # noqa: E402

SEED = ROOT / "data" / "seed" / "companies_seed.csv"
MASTER = ROOT / "app" / "app_data" / "companies_master.csv"
OPP_SEED = ROOT / "data" / "seed" / "opportunities_seed.csv"
OPP_MASTER = ROOT / "app" / "app_data" / "opportunities_master.csv"
VERIFIED = ROOT / "data" / "seed" / "verified_programmes.csv"
OUT = ROOT / "data" / "processed" / "companies_removed_no_website.csv"


def _filter_by_company_id(path: Path, drop_ids: set[str], id_col: str = "company_id") -> int:
    if not path.exists():
        return 0
    df = pd.read_csv(path, dtype=str).fillna("")
    if id_col not in df.columns:
        return 0
    before = len(df)
    keep = ~df[id_col].astype(str).isin(drop_ids)
    df = df.loc[keep]
    removed = before - len(df)
    if removed:
        df.to_csv(path, index=False)
    return removed


def main() -> None:
    seed = pd.read_csv(SEED, dtype=str).fillna("")
    no_site = seed[seed["website"].map(public_employer_website) == ""].copy()
    drop_ids = set(no_site["company_id"].astype(str))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    no_site.to_csv(OUT, index=False)
    print(f"Removing {len(drop_ids)} seed employers without public website")
    print(f"Audit log: {OUT}")

    before_seed = len(seed)
    seed = seed[~seed["company_id"].astype(str).isin(drop_ids)]
    seed.to_csv(SEED, index=False)
    print(f"companies_seed: {before_seed} -> {len(seed)}")

    if MASTER.exists():
        master = pd.read_csv(MASTER, dtype=str).fillna("")
        before = len(master)
        # Drop the same company_ids; do not wipe all vacancy rows without websites
        master = master[~master["company_id"].astype(str).isin(drop_ids)]
        master.to_csv(MASTER, index=False)
        print(f"companies_master: {before} -> {len(master)} (removed {before - len(master)})")

    for label, path in (
        ("opportunities_seed", OPP_SEED),
        ("opportunities_master", OPP_MASTER),
        ("verified_programmes", VERIFIED),
    ):
        n = _filter_by_company_id(path, drop_ids)
        print(f"{label}: removed {n} rows linked to dropped employers")

    # Confirm none left in seed without website
    seed2 = pd.read_csv(SEED, dtype=str).fillna("")
    left = seed2[seed2["website"].map(public_employer_website) == ""]
    print(f"seed remaining without website: {len(left)}")
    print(f"seed with public website: {seed2['website'].map(lambda u: bool(public_employer_website(u))).sum()}")


if __name__ == "__main__":
    main()
