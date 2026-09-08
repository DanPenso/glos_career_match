"""Build companies/opportunities masters from seed + GL apprenticeship vacancies."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.etl.vacancies import (
    ensure_vacancies_available,
    merge_seed_with_vacancies,
)


def split_tags(series: pd.Series) -> pd.Series:
    return series.fillna("").apply(
        lambda x: [t.strip() for t in str(x).split("|") if t.strip()]
    )


def main() -> None:
    seed_dir = ROOT / "data" / "seed"
    raw_dir = ROOT / "data" / "raw"
    processed = ROOT / "data" / "processed"
    app_data = ROOT / "app" / "app_data"
    processed.mkdir(parents=True, exist_ok=True)
    app_data.mkdir(parents=True, exist_ok=True)

    zip_path = ensure_vacancies_available(raw_dir / "apprenticeship_vacancies.zip")
    companies, opportunities, stats = merge_seed_with_vacancies(
        pd.read_csv(seed_dir / "companies_seed.csv"),
        pd.read_csv(seed_dir / "opportunities_seed.csv"),
        zip_path=zip_path,
    )

    companies = companies.copy()
    companies["sector_list"] = split_tags(companies["sectors"])
    companies["entry_route_list"] = split_tags(companies["entry_routes"])
    companies["role_family_list"] = split_tags(companies["role_families"])
    companies["n_sectors"] = companies["sector_list"].str.len()
    companies["n_entry_routes"] = companies["entry_route_list"].str.len()
    companies["priority_employer"] = companies["priority_employer"].astype(int)

    opp_counts = opportunities.groupby("company_id").size().rename("n_opportunities")
    companies = companies.merge(opp_counts, on="company_id", how="left")
    companies["n_opportunities"] = companies["n_opportunities"].fillna(0).astype(int)

    companies.to_pickle(processed / "companies_master.pkl")
    opportunities.to_pickle(processed / "opportunities_master.pkl")
    companies.to_csv(app_data / "companies_master.csv", index=False)
    opportunities.to_csv(app_data / "opportunities_master.csv", index=False)

    print("Merge stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"Saved companies_master: {companies.shape}")
    print(f"Saved opportunities_master: {opportunities.shape}")


if __name__ == "__main__":
    main()
