"""Export company_profiles.txt and opportunities.txt with Source: provenance lines.

Reads masters from app/app_data (or data/seed fallback). Does not rebuild FAISS —
run scripts/07_build_faiss_corpus.py afterwards if you want the index updated.

  .venv\\Scripts\\python scripts/04_export_rag_corpus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.labels import clean_company_summary  # noqa: E402
from glos_recommender.provenance import (  # noqa: E402
    classify_employer_source,
    source_label,
)

CORPUS_DIR = ROOT / "data" / "corpus"
APP_DATA = ROOT / "app" / "app_data"
SEED_DIR = ROOT / "data" / "seed"


def _load_companies() -> pd.DataFrame:
    for path in (
        APP_DATA / "companies_master.csv",
        SEED_DIR / "companies_seed.csv",
    ):
        if path.exists():
            return pd.read_csv(path)
    raise FileNotFoundError("No companies master/seed CSV found.")


def _load_opportunities() -> pd.DataFrame:
    for path in (
        APP_DATA / "opportunities_master.csv",
        SEED_DIR / "opportunities_seed.csv",
    ):
        if path.exists():
            return pd.read_csv(path)
    raise FileNotFoundError("No opportunities master/seed CSV found.")


def company_doc(row: pd.Series) -> str:
    data = row.to_dict()
    kind = classify_employer_source(data)
    summary = clean_company_summary(data.get("summary"))
    caveat = ""
    if kind == "vacancies":
        caveat = " Vacancy data may be historical or closed."
    elif kind == "companies_house":
        caveat = " Registry facts only — not a careers page."
    return (
        f"Company: {data.get('name')} ({data.get('town')}). "
        f"Sectors: {data.get('sectors')}. Entry routes: {data.get('entry_routes')}. "
        f"Roles: {data.get('role_families')}. {summary}{caveat} "
        f"Website: {data.get('website') or 'none on file'}. "
        f"Source: {source_label(kind)}."
    )


def opportunity_doc(row: pd.Series, name_by_id: dict[str, str]) -> str:
    data = row.to_dict()
    cid = str(data.get("company_id") or "")
    cname = name_by_id.get(cid, cid or "employer")
    src = str(data.get("source") or "").strip().lower()
    if src == "vacancies":
        source_line = "Find an apprenticeship open data (may be historical / closed)"
    elif src in {"seed", "curated", "manual"}:
        source_line = "Curated opportunity profile"
    else:
        source_line = source_label(src or "seed")
    return (
        f"Opportunity at {cname}: {data.get('title')} "
        f"({data.get('entry_route')}, {data.get('level')}). "
        f"{data.get('description')} Typical quals: {data.get('typical_quals')}. "
        f"Useful projects: {data.get('useful_projects')}. Tips: {data.get('application_tips')}. "
        f"Source: {source_line}."
    )


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    companies = _load_companies()
    opportunities = _load_opportunities()
    name_by_id = {
        str(r["company_id"]): str(r["name"])
        for _, r in companies.iterrows()
        if pd.notna(r.get("company_id"))
    }

    company_docs = [company_doc(r) for _, r in companies.iterrows()]
    opp_docs = [opportunity_doc(r, name_by_id) for _, r in opportunities.iterrows()]

    (CORPUS_DIR / "company_profiles.txt").write_text(
        "\n\n".join(company_docs), encoding="utf-8"
    )
    (CORPUS_DIR / "opportunities.txt").write_text(
        "\n\n".join(opp_docs), encoding="utf-8"
    )
    print(f"Wrote {len(company_docs)} company profiles -> {CORPUS_DIR / 'company_profiles.txt'}")
    print(f"Wrote {len(opp_docs)} opportunities -> {CORPUS_DIR / 'opportunities.txt'}")
    print("Next (optional): .venv\\Scripts\\python scripts/07_build_faiss_corpus.py")


if __name__ == "__main__":
    main()
