"""Download open datasets used for persona clustering curation.

JobCannon (CC-BY-4.0) is the primary fetch. O*NET is best-effort
(zip layout changes; bridge CSV works offline without it).

Run from project root:
  .venv\\Scripts\\python scripts/08_1_fetch_external_clustering_data.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "data" / "external"
JOBCANNON = EXTERNAL / "jobcannon"
ONET = EXTERNAL / "onet"

JOBCANNON_FILES = {
    "riasec.csv": (
        "https://raw.githubusercontent.com/PeterKolomiets/"
        "jobcannon-psychometric-dataset/main/riasec.csv"
    ),
    "career_match.csv": (
        "https://raw.githubusercontent.com/PeterKolomiets/"
        "jobcannon-psychometric-dataset/main/career_match.csv"
    ),
}

# Best-effort public O*NET database zip (version may move; failures are OK)
ONET_ZIP_CANDIDATES = [
    "https://www.onetcenter.org/dl_files/database/db_29_2_text.zip",
    "https://www.onetcenter.org/dl_files/database/db_28_3_text.zip",
]


def _download(url: str, dest: Path, timeout: int = 120) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "GlosCareerMatch/1.0 (research; local demo)"})
    with urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def fetch_jobcannon() -> list[str]:
    done = []
    for name, url in JOBCANNON_FILES.items():
        dest = JOBCANNON / name
        print(f"Fetching JobCannon {name} …")
        _download(url, dest)
        done.append(str(dest.relative_to(ROOT)))
        print(f"  → {dest} ({dest.stat().st_size:,} bytes)")
    return done


def fetch_onet() -> list[str]:
    ONET.mkdir(parents=True, exist_ok=True)
    for url in ONET_ZIP_CANDIDATES:
        try:
            print(f"Trying O*NET zip: {url}")
            req = Request(url, headers={"User-Agent": "GlosCareerMatch/1.0"})
            with urlopen(req, timeout=180) as resp:
                payload = resp.read()
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                wanted = ("Interests.txt", "Occupation Data.txt")
                extracted = []
                for member in zf.namelist():
                    base = Path(member).name
                    if base in wanted:
                        out = ONET / base
                        out.write_bytes(zf.read(member))
                        extracted.append(str(out.relative_to(ROOT)))
                        print(f"  → {out}")
                if extracted:
                    return extracted
        except Exception as exc:  # noqa: BLE001 — best-effort fetch
            print(f"  skipped: {exc}")
    print(
        "O*NET download unavailable — continuing with "
        "data/curated/occupation_to_sector.csv only."
    )
    return []


def main() -> None:
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    got = []
    try:
        got.extend(fetch_jobcannon())
    except Exception as exc:  # noqa: BLE001
        print(f"JobCannon fetch failed: {exc}")
        print("Place riasec.csv / career_match.csv under data/external/jobcannon/ manually.")
    got.extend(fetch_onet())
    print(f"Done. Files ready: {len(got)}")
    for g in got:
        print(f"  - {g}")


if __name__ == "__main__":
    main()
