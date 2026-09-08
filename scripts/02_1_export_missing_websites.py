"""Patch known employer websites and export employers missing a public site."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.labels import public_employer_website  # noqa: E402

SEED = ROOT / "data" / "seed" / "companies_seed.csv"
MASTER = ROOT / "app" / "app_data" / "companies_master.csv"
OUT_DIR = ROOT / "data" / "processed"

NBA_URL = "https://www.newbreweryarts.org.uk/"
NBA_SUMMARY = (
    "Cirencester craft centre with classes, workshops, exhibitions, cafe and shop — "
    "a local creative organisation for making, learning and visitor experience. "
    "Routes vary — check their site for opportunities and courses."
)

# Hand-verified official sites (extend as you find more).
KNOWN_SITES: dict[str, str] = {
    "new brewery arts limited": NBA_URL,
    "new brewery arts": NBA_URL,
}


def _norm_name(name: str) -> str:
    return " ".join(str(name or "").lower().split())


def patch_known(path: Path) -> int:
    df = pd.read_csv(path, dtype=str).fillna("")
    updated = 0
    for i, row in df.iterrows():
        key = _norm_name(row.get("name", ""))
        url = KNOWN_SITES.get(key)
        if not url:
            # partial key match for "New Brewery Arts Limited"
            for k, u in KNOWN_SITES.items():
                if k in key or key.startswith(k):
                    url = u
                    break
        if not url:
            continue
        cur = public_employer_website(row.get("website"))
        if cur == url:
            continue
        df.at[i, "website"] = url
        summary = str(row.get("summary") or "")
        if (
            "companies house" in summary.lower()
            or "nature of business" in summary.lower()
            or not summary.strip()
        ) and "brewery arts" in key:
            df.at[i, "summary"] = NBA_SUMMARY
        updated += 1
    if updated:
        df.to_csv(path, index=False)
    return updated


def export_missing() -> tuple[int, int]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seed = pd.read_csv(SEED, dtype=str).fillna("")
    seed["public_website"] = seed["website"].map(public_employer_website)
    missing_seed = seed[seed["public_website"] == ""].copy()
    cols = [
        c
        for c in (
            "company_id",
            "name",
            "town",
            "postcode",
            "sectors",
            "source",
            "website",
            "summary",
        )
        if c in missing_seed.columns
    ]
    # Add blank column for you to fill
    out_seed = missing_seed[cols].sort_values("name")
    out_seed["proposed_website"] = ""
    out_seed.to_csv(OUT_DIR / "companies_missing_website_seed.csv", index=False)

    master = pd.read_csv(MASTER, dtype=str).fillna("")
    master["public_website"] = master["website"].map(public_employer_website)
    missing_master = master[master["public_website"] == ""].copy()
    mcols = [
        c
        for c in ("company_id", "name", "town", "postcode", "sectors", "source", "website")
        if c in missing_master.columns
    ]
    missing_master[mcols].sort_values(
        ["source", "name"] if "source" in mcols else ["name"]
    ).to_csv(OUT_DIR / "companies_missing_website_all.csv", index=False)

    return len(out_seed), len(missing_master)


def main() -> None:
    n1 = patch_known(SEED)
    n2 = patch_known(MASTER)
    print(f"Patched known sites: seed={n1}, master={n2}")
    n_seed, n_all = export_missing()
    print(f"Missing public website (seed/curated list): {n_seed}")
    print(f"Missing public website (full master): {n_all}")
    print(f"Fill-in sheet: {OUT_DIR / 'companies_missing_website_seed.csv'}")
    print(f"Full reference: {OUT_DIR / 'companies_missing_website_all.csv'}")
    seed = pd.read_csv(SEED, dtype=str).fillna("")
    missing = seed[seed["website"].map(public_employer_website) == ""].sort_values("name")
    print("\n--- Seed employers needing a website URL ---")
    for _, r in missing.iterrows():
        print(f"{r['company_id']}\t{r['name']}\t{r.get('town', '')}\t{r.get('postcode', '')}")


if __name__ == "__main__":
    main()
