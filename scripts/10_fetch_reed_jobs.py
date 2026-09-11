"""Cache live Reed Jobseeker listings for Gloucestershire + Bristol.

Requires REED_API_KEY in .env. Does not crawl employer websites.

Usage (from project root):
  .venv\\Scripts\\python scripts/10_fetch_reed_jobs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import dotenv_values, load_dotenv

load_dotenv(ROOT / ".env", override=True)

from glos_recommender.open_jobs import (  # noqa: E402
    CACHE_PATH,
    fetch_reed_jobs,
    save_reed_jobs,
)


def main() -> int:
    file_key = str(dotenv_values(ROOT / ".env").get("REED_API_KEY") or "").strip()
    try:
        doc = fetch_reed_jobs(api_key=file_key or None)
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    path = save_reed_jobs(doc)
    n = len(doc.get("jobs") or [])
    print(f"Wrote {n} open GL/BS Reed jobs to {path}")
    if path.resolve() != CACHE_PATH.resolve():
        print(f"(default cache path is {CACHE_PATH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
