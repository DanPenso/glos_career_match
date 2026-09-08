"""Load intake taxonomy, psych questions, and pathway cards from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_DIR = PROJECT_ROOT / "data" / "taxonomy"


# Load a YAML file into a dict.
def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# Load intake form options (interests, quals, …).
def load_intake_options(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or TAXONOMY_DIR / "intake_options.yaml")


# Load psych / RIASEC question bank.
def load_psych_questions(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or TAXONOMY_DIR / "psych_questions.yaml")


# Load pathway cards YAML.
def load_pathways(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    return _load_yaml(path or TAXONOMY_DIR / "pathways.yaml")


# Pathway cards that match the given sectors.
def pathways_for_sectors(sectors: set[str] | list[str]) -> list[dict[str, Any]]:
    """Return pathway cards for the leaver's target sectors (deduped by id)."""
    catalogue = load_pathways()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for sector in sectors:
        for card in catalogue.get(sector, []) or []:
            cid = card.get("id") or card.get("title")
            if cid in seen:
                continue
            seen.add(str(cid))
            out.append({**card, "sector": sector})
    return out
