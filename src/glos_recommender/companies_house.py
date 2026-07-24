"""Companies House free data product → Gloucestershire employer candidates.

Uses the monthly BasicCompanyData snapshot (OGL / free public data product).
Employee headcount is not in the free file; we rank by accounts category as a
size proxy (GROUP/FULL/MEDIUM ahead of SMALL/MICRO).
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from .vacancies import normalise_employer_name
from .labels import sic_activity

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SEED_DIR = PROJECT_ROOT / "data" / "seed"
CH_ZIP = RAW_DIR / "companies_house_basic.zip"

DOWNLOAD_PAGE = "http://download.companieshouse.gov.uk/en_output.html"
ONE_FILE_TMPL = (
    "http://download.companieshouse.gov.uk/BasicCompanyDataAsOneFile-{ym}-01.zip"
)

# Accounts category → relative size score (proxy for headcount)
ACCOUNT_SCORE: dict[str, int] = {
    "GROUP": 100,
    "FULL": 95,
    "MEDIUM": 80,
    "SMALL": 55,
    "TOTAL EXEMPTION FULL": 50,
    "AUDIT EXEMPTION SUBSIDIARY": 45,
    "TOTAL EXEMPTION SMALL": 40,
    "UNAUDITED ABRIDGED": 35,
    "MICRO ENTITY": 15,
    "DORMANT": 0,
    "NO ACCOUNTS FILED": 5,
    "ACCOUNTS TYPE NOT AVAILABLE": 5,
}

# SIC text / code fragments → project sector tags
SIC_SECTOR_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"62\d{2}|software|computer|information technology|cyber|data process", re.I), ["cyber_digital"]),
    (re.compile(r"85\d{2}|education|school|university|college", re.I), ["education_training"]),
    (re.compile(r"86\d{2}|87\d{2}|hospital|health|social work|residential care|medical", re.I), ["health_care"]),
    (re.compile(r"84\d{2}|public administration|defence|justice|fire service", re.I), ["public_sector"]),
    (re.compile(r"41\d{2}|42\d{2}|43\d{2}|construction|civil engineering|electrical installation|plumbing", re.I), ["construction_green"]),
    (re.compile(r"55\d{2}|56\d{2}|hotel|restaurant|beverage|food and beverage|accommodation", re.I), ["hospitality_tourism"]),
    (re.compile(r"47\d{2}|retail|sale of", re.I), ["hospitality_retail"]),
    (re.compile(r"01\d{2}|02\d{2}|03\d{2}|10\d{2}|agriculture|crop|animal|food product", re.I), ["agri_tech_food"]),
    (re.compile(r"30\d{2}|28\d{2}|25\d{2}|26\d{2}|27\d{2}|manufacture|aerospace|aircraft|machinery|electronic", re.I), ["aerospace_manufacturing"]),
    (re.compile(r"35\d{2}|electricity|gas|steam|energy", re.I), ["construction_green"]),
    (re.compile(r"90\d{2}|91\d{2}|93\d{2}|creative|arts|entertainment|sports", re.I), ["creative_events"]),
    (re.compile(r"64\d{2}|65\d{2}|66\d{2}|69\d{2}|70\d{2}|accounting|financial|consultancy|head office", re.I), ["business_professional"]),
]

_SKIP_NAME = re.compile(
    r"\b("
    r"dormant|strike off|liquidation|in administration|llc member|"
    r"nominees?|secretar(?:y|ial)\s+services|"
    r"holdings?|investment(?:s)?|pension|property\s+company|"
    r"trustees?|fund|spv|plc\s+nominee"
    r")\b",
    re.I,
)
_HOLDING_SIC = re.compile(
    r"activities of (other )?holding|6420[59]|head offices",
    re.I,
)


def resolve_bulk_zip_url() -> str:
    """Pick the latest BasicCompanyDataAsOneFile URL (try current/previous months)."""
    today = pd.Timestamp.utcnow().normalize()
    for months_back in range(0, 4):
        ym = (today - pd.DateOffset(months=months_back)).strftime("%Y-%m")
        url = ONE_FILE_TMPL.format(ym=ym)
        try:
            req = Request(url, headers={"User-Agent": "GlosCareerMatch/1.0"})
            req.get_method = lambda: "HEAD"  # type: ignore[method-assign]
            with urlopen(req, timeout=30) as resp:
                if 200 <= getattr(resp, "status", 200) < 300:
                    return url
        except HTTPError as e:
            if e.code != 404:
                # Some mirrors reject HEAD; try this URL on download anyway
                return url
        except Exception:
            continue
    return ONE_FILE_TMPL.format(ym="2026-07")


def download_basic_company_data(
    dest: Path | None = None,
    force: bool = False,
) -> Path:
    dest = dest or CH_ZIP
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force and dest.stat().st_size > 50_000_000:
        return dest
    url = resolve_bulk_zip_url()
    req = Request(url, headers={"User-Agent": "GlosCareerMatch/1.0"})
    with urlopen(req, timeout=600) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return dest


def _account_score(category: Any) -> int:
    if pd.isna(category) or not str(category).strip():
        return 5
    key = str(category).strip().upper()
    if key in ACCOUNT_SCORE:
        return ACCOUNT_SCORE[key]
    for frag, score in ACCOUNT_SCORE.items():
        if frag in key:
            return score
    return 10


def _size_band(score: int) -> str:
    if score >= 80:
        return "large"
    if score >= 40:
        return "medium"
    return "sme"


def map_sic_to_sectors(*sic_texts: Any) -> list[str]:
    blob = " ".join(str(s) for s in sic_texts if pd.notna(s) and str(s).strip())
    if not blob:
        return ["business_professional"]
    found: list[str] = []
    for pattern, tags in SIC_SECTOR_RULES:
        if pattern.search(blob):
            for t in tags:
                if t not in found:
                    found.append(t)
    return found[:3] or ["business_professional"]


def _title_name(name: str) -> str:
    s = re.sub(r"\s+", " ", str(name).strip())
    if s.isupper() or s.islower():
        s = s.title()
    # Fix common Ltd casing after title()
    s = re.sub(r"\bLtd\b", "Ltd", s)
    s = re.sub(r"\bPlc\b", "PLC", s)
    s = re.sub(r"\bUk\b", "UK", s)
    return s


def load_gl_companies_from_zip(zip_path: Path | None = None) -> pd.DataFrame:
    """Stream BasicCompanyData CSV; keep Active companies with GL* or BS* postcodes.

    Name kept for backward compatibility with fetch scripts.
    """
    zip_path = zip_path or CH_ZIP
    if not zip_path.exists():
        download_basic_company_data(zip_path)

    want = {
        "CompanyName",
        "CompanyNumber",
        "RegAddress.PostTown",
        "RegAddress.PostCode",
        "CompanyCategory",
        "CompanyStatus",
        "Accounts.AccountCategory",
        "SICCode.SicText_1",
        "SICCode.SicText_2",
        "SICCode.SicText_3",
        "IncorporationDate",
    }

    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV in {zip_path}")
        with zf.open(csv_names[0]) as f:
            for chunk in pd.read_csv(
                f,
                usecols=lambda c: c.strip() in want,
                dtype=str,
                chunksize=100_000,
                low_memory=False,
            ):
                # CH CSV headers often have leading spaces
                chunk.columns = [c.strip() for c in chunk.columns]
                status = chunk["CompanyStatus"].fillna("")
                pc = chunk["RegAddress.PostCode"].fillna("").str.upper().str.strip()
                mask = status.str.lower().eq("active") & pc.str.match(
                    r"^(?:GL|BS)\d", na=False
                )
                part = chunk.loc[mask].copy()
                if len(part):
                    frames.append(part)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def rank_gl_employers(
    gl_df: pd.DataFrame,
    top_n: int = 100,
    *,
    balance_regions: bool = True,
) -> pd.DataFrame:
    """Rank GL/BS-registered active companies by accounts-category size proxy.

    When balance_regions is True, take roughly half from GL* and half from BS*
    so Bristol density does not crowd out Gloucestershire employers.
    """
    if gl_df.empty:
        return gl_df

    df = gl_df.copy()
    df["name"] = df["CompanyName"].map(_title_name)
    df["employer_key"] = df["name"].map(normalise_employer_name)
    df = df[df["employer_key"].str.len() > 1]
    df = df[~df["name"].map(lambda n: bool(_SKIP_NAME.search(str(n))))]
    df["account_category"] = df["Accounts.AccountCategory"].fillna("")
    df["size_score"] = df["account_category"].map(_account_score)
    df = df[df["size_score"] > 0]  # drop dormant

    df["sic_blob"] = (
        df.get("SICCode.SicText_1", pd.Series("", index=df.index)).fillna("")
        + " "
        + df.get("SICCode.SicText_2", pd.Series("", index=df.index)).fillna("")
        + " "
        + df.get("SICCode.SicText_3", pd.Series("", index=df.index)).fillna("")
    )
    # Holding / head-office SICs are poor leaver destinations — demote heavily
    holding_sic = df["sic_blob"].map(lambda s: bool(_HOLDING_SIC.search(str(s))))
    df.loc[holding_sic, "size_score"] = (df.loc[holding_sic, "size_score"] * 0.25).astype(int)
    df = df[df["size_score"] >= 40]  # keep SMALL+ trading-scale after demotion

    # One row per normalised employer — keep highest size score
    df = df.sort_values(["size_score", "CompanyName"], ascending=[False, True])
    df = df.drop_duplicates(subset=["employer_key"], keep="first")

    df["sectors_list"] = [
        map_sic_to_sectors(a, b, c)
        for a, b, c in zip(
            df.get("SICCode.SicText_1", ""),
            df.get("SICCode.SicText_2", ""),
            df.get("SICCode.SicText_3", ""),
        )
    ]
    df["sectors"] = df["sectors_list"].map(lambda xs: "|".join(xs))
    df["size_band"] = df["size_score"].map(_size_band)
    df["town"] = (
        df["RegAddress.PostTown"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.title()
        .replace({"": "", "Nan": ""})
    )
    df["postcode"] = (
        df["RegAddress.PostCode"]
        .astype(str)
        .str.upper()
        .str.extract(r"^((?:GL|BS)\d{1,2})", expand=False)
        .fillna("GL")
    )
    df["region"] = df["postcode"].map(
        lambda p: "bristol" if str(p).upper().startswith("BS") else "gloucestershire"
    )
    df["town"] = [
        t
        if t
        else ("Bristol" if r == "bristol" else "Gloucestershire")
        for t, r in zip(df["town"], df["region"])
    ]
    df["company_number"] = df["CompanyNumber"].astype(str).str.strip()
    df["website"] = df["company_number"].map(
        lambda n: f"https://find-and-update.company-information.service.gov.uk/company/{n}"
    )
    df["sic_text"] = df.get("SICCode.SicText_1", pd.Series("", index=df.index)).fillna("")

    if balance_regions and top_n > 1:
        per = max(1, top_n // 2)
        gl_part = df[df["region"] == "gloucestershire"].head(per)
        bs_part = df[df["region"] == "bristol"].head(top_n - len(gl_part))
        # If one region is short, backfill from the other
        combined = pd.concat([gl_part, bs_part], ignore_index=True)
        if len(combined) < top_n:
            rest = df[~df["employer_key"].isin(set(combined["employer_key"]))].head(
                top_n - len(combined)
            )
            combined = pd.concat([combined, rest], ignore_index=True)
        df = combined.sort_values(["size_score", "CompanyName"], ascending=[False, True])
    else:
        df = df.head(top_n)

    return df.reset_index(drop=True)


def ranked_to_seed_rows(ranked: pd.DataFrame, id_start: int = 100) -> pd.DataFrame:
    """Convert ranked CH rows to companies_seed schema."""
    rows: list[dict[str, Any]] = []
    for i, r in ranked.iterrows():
        sectors = str(r["sectors"])
        roles = {
            "cyber_digital": "software|cyber|analyst",
            "aerospace_manufacturing": "engineer_ops|manufacturing|technician",
            "construction_green": "technician|field_ops|engineer_ops",
            "health_care": "care|admin",
            "education_training": "teaching_support|admin",
            "hospitality_tourism": "customer_success|ops",
            "hospitality_retail": "sales|customer_success",
            "agri_tech_food": "field_ops|technician",
            "public_sector": "admin|ops",
            "creative_events": "content|events",
            "business_professional": "admin|finance|project_coord",
        }
        primary = sectors.split("|")[0] if sectors else "business_professional"
        role_families = roles.get(primary, "ops|admin")
        sic = str(r.get("sic_text") or "")[:120]
        activity = sic_activity(sic)
        region_label = "Bristol" if str(r.get("postcode", "")).upper().startswith("BS") else "Gloucestershire"
        if activity:
            summary = (
                f"{r['town']}-based employer working in {activity.lower()}. "
                "Routes vary — check careers pages and Find an Apprenticeship."
            )
        else:
            summary = (
                f"{r['town']}-based {region_label} employer. "
                "Routes vary — check careers pages and Find an Apprenticeship."
            )
        profile = (
            f"{r['name']} {r['town']} {region_label} {sectors.replace('|', ' ')} "
            f"apprenticeship graduate school leaver {activity or sic}"
        )
        rows.append(
            {
                "company_id": f"GLC{id_start + int(i):03d}",
                "name": r["name"],
                "town": r["town"],
                "postcode": r["postcode"],
                "sectors": sectors,
                "entry_routes": "apprenticeship|school_leaver|graduate",
                "role_families": role_families,
                "size_band": r["size_band"],
                "priority_employer": 1,
                "hiring_signal": "medium" if r["size_score"] >= 80 else "low",
                "website": r["website"],
                "summary": summary[:500],
                "profile_text": profile[:800],
            }
        )
    return pd.DataFrame(rows)


def load_public_anchors(path: Path | None = None) -> pd.DataFrame:
    path = path or SEED_DIR / "public_sector_anchors.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def upsert_into_seed(
    seed_path: Path,
    new_rows: pd.DataFrame,
    anchors: pd.DataFrame | None = None,
) -> dict[str, int]:
    """Append employers missing from seed (normalised name). Keep existing curated rows."""
    seed = pd.read_csv(seed_path)
    seed_keys = set(seed["name"].map(normalise_employer_name))

    extras = []
    if anchors is not None and len(anchors):
        extras.append(anchors)
    if new_rows is not None and len(new_rows):
        extras.append(new_rows)
    if not extras:
        return {"seed_before": len(seed), "added": 0, "seed_after": len(seed)}

    candidates = pd.concat(extras, ignore_index=True)
    candidates["employer_key"] = candidates["name"].map(normalise_employer_name)
    to_add = candidates[~candidates["employer_key"].isin(seed_keys)].copy()
    to_add = to_add.drop_duplicates(subset=["employer_key"], keep="first")

    if to_add.empty:
        return {"seed_before": len(seed), "added": 0, "seed_after": len(seed)}

    # Assign fresh IDs after max GLC###
    max_id = 0
    for cid in seed["company_id"].astype(str):
        m = re.match(r"GLC(\d+)$", cid)
        if m:
            max_id = max(max_id, int(m.group(1)))

    out_rows = []
    for j, (_, row) in enumerate(to_add.iterrows()):
        d = row.to_dict()
        d.pop("employer_key", None)
        d["company_id"] = f"GLC{max_id + j + 1:03d}"
        # Keep only seed columns
        out_rows.append({c: d.get(c, "") for c in seed.columns})

    merged = pd.concat([seed, pd.DataFrame(out_rows)], ignore_index=True)
    merged.to_csv(seed_path, index=False)
    return {
        "seed_before": len(seed),
        "added": len(out_rows),
        "seed_after": len(merged),
    }
