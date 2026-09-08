"""Cache live Find an apprenticeship adverts for Gloucestershire + Bristol.

Source: DfE Display Advert API v2 (not the historical EES vacancies zip).
Requires FAA_DISPLAY_API_KEY in .env.

Usage (from project root):
  .venv\\Scripts\\python scripts/09_fetch_open_apprenticeships.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from glos_recommender.open_opportunities import (  # noqa: E402
    CACHE_PATH,
    fetch_open_apprenticeships,
    save_open_apprenticeships,
)


def main() -> int:
    try:
        doc = fetch_open_apprenticeships()
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    path = save_open_apprenticeships(doc)
    n = len(doc.get("vacancies") or [])
    print(f"Wrote {n} open GL/BS apprenticeships to {path}")
    if path.resolve() != CACHE_PATH.resolve():
        print(f"(default cache path is {CACHE_PATH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
