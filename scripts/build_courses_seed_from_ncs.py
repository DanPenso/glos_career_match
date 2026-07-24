"""Build a Glos + Bristol FE/HE course seed from National Careers Service open data.

Source: DfE National Careers Service course directory (Open Government Licence v3.0)
https://www.gov.uk/government/publications/national-careers-service-course-directory

Usage (from project root):
  .venv\\Scripts\\python scripts/build_courses_seed_from_ncs.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SEED = ROOT / "data" / "seed"
OUT = SEED / "courses_seed.csv"
MICRO = SEED / "military_microcreds_seed.csv"

PROVIDERS_CSV = RAW / "ncs_providers_20260629.csv"
COURSES_CSV = RAW / "ncs_courses_20260629.csv"

# Postcode prefixes for Gloucestershire + Bristol
POSTCODE_RE = re.compile(r"^(GL|BS)\d", re.I)

# Title-first keyword → sector tags (aligned with intake_options.yaml)
TITLE_SECTORS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\b(cyber|software|computing|computer science|ICT|digital tech|programming|coding|network engineer|IT support|web design|data science|artificial intelligence)\b", re.I), ["cyber_digital"]),
    (re.compile(r"\b(aerospace|manufactur|mechanical|electrical engineer|engineering|CNC|mechatronic)\b", re.I), ["aerospace_manufacturing"]),
    (re.compile(r"\b(agricultur|horticultur|animal care|veterinary|food science|environment|sustainab|land-based|forestry)\b", re.I), ["agri_tech_food"]),
    (re.compile(r"\b(nurs|midwif|paramedic|health.?care|social care|dental|physiotherap|occupational therap|wellbeing|medical)\b", re.I), ["health_care"]),
    (re.compile(r"\b(policing|public.?service|law\b|legal|criminol|civil.?service)\b", re.I), ["public_sector"]),
    (re.compile(r"\b(creative|media|design|art\b|music|film|photography|drama|theatre|event.?manag)\b", re.I), ["creative_events"]),
    (re.compile(r"\b(construct|plumb|brick|carpentr|built.?environ|surveying|electrician|electrical install)\b", re.I), ["construction_green"]),
    (re.compile(r"\b(hospitality|tourism|cater|chef|culinary|hotel|travel)\b", re.I), ["hospitality_tourism"]),
    (re.compile(r"\b(retail|customer.?service|sales)\b", re.I), ["hospitality_retail"]),
    (re.compile(r"\b(business|management|account|financ|AAT|market|HR\b|admin|econom)\b", re.I), ["business_professional"]),
    (re.compile(r"\b(education|teach|early.?year|childcare|child development|learning.?support|teaching assistant)\b", re.I), ["education_training"]),
    (re.compile(r"\b(maths|mathematics|statistics|physics|chemistry|biology|science)\b", re.I), ["aerospace_manufacturing", "cyber_digital"]),
]

NCS_SECTOR_MAP: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"digital|IT\b|computing|information.?tech", re.I), ["cyber_digital"]),
    (re.compile(r"engineer|manufactur|transport", re.I), ["aerospace_manufacturing"]),
    (re.compile(r"health|care|science", re.I), ["health_care"]),
    (re.compile(r"construction|building", re.I), ["construction_green"]),
    (re.compile(r"hospitality|catering|leisure|tourism", re.I), ["hospitality_tourism"]),
    (re.compile(r"business|admin|finance|account", re.I), ["business_professional"]),
    (re.compile(r"education|childcare|teaching", re.I), ["education_training"]),
    (re.compile(r"agriculture|animal|environment", re.I), ["agri_tech_food"]),
    (re.compile(r"creative|arts|media|design", re.I), ["creative_events"]),
    (re.compile(r"retail|sales", re.I), ["hospitality_retail"]),
    (re.compile(r"public|legal|protective", re.I), ["public_sector"]),
]


def _sectors_from_text(title: str, ncs_sector: str = "", course_type: str = "") -> str:
    found: list[str] = []
    for pat, sectors in TITLE_SECTORS:
        if pat.search(title or ""):
            for s in sectors:
                if s not in found:
                    found.append(s)
    if not found:
        blob = f"{ncs_sector} {course_type}"
        for pat, sectors in NCS_SECTOR_MAP:
            if pat.search(blob):
                for s in sectors:
                    if s not in found:
                        found.append(s)
    return "|".join(found[:3]) if found else "business_professional"


PREFERRED_PROVIDER = re.compile(
    r"college|university|UWE|Hartpury|Cirencester|South Gloucestershire|Stroud|Gloucestershire|Bristol",
    re.I,
)
SCHOOL_PROVIDER = re.compile(r"\b(school|academy|high)\b", re.I)


def _entry_routes(education_level: str, study_mode: str, course_type: str) -> str:
    level = str(education_level or "").lower()
    mode = str(study_mode or "").lower()
    ctype = str(course_type or "").lower()
    routes: list[str] = []
    if "apprentice" in ctype or "apprentice" in level:
        routes.append("apprenticeship")
    if any(x in level for x in ("level 6", "level 7", "degree", "higher education", "he ")):
        routes.extend(["graduate", "higher_apprenticeship"])
    if any(x in level for x in ("level 3", "level 4", "level 5", "a level", "t level", "access")):
        routes.extend(["school_leaver", "apprenticeship"])
    if "part" in mode or "flexible" in mode:
        routes.append("internship")
    if not routes:
        routes = ["school_leaver", "apprenticeship"]
    # unique preserve order
    out: list[str] = []
    for r in routes:
        if r not in out:
            out.append(r)
    return "|".join(out)


def _region(postcode: str, town: str) -> str:
    pc = str(postcode or "").upper().replace(" ", "")
    town_l = str(town or "").lower()
    if pc.startswith("BS") or "bristol" in town_l:
        return "bristol"
    return "gloucestershire"


def _clean_url(url: str, fallback: str = "") -> str:
    u = str(url or "").strip()
    if u.startswith("http"):
        return u
    if u and not u.startswith("http"):
        return "https://" + u.lstrip("/")
    f = str(fallback or "").strip()
    if f.startswith("http"):
        return f
    if f:
        return "https://" + f.lstrip("/")
    return ""


def _is_local_row(row: pd.Series) -> bool:
    for col in ("LOCATION_POSTCODE",):
        pc = str(row.get(col) or "").strip().upper().replace(" ", "")
        if pc and POSTCODE_RE.match(pc[:4] if len(pc) >= 4 else pc):
            return True
    town = str(row.get("LOCATION_TOWN") or "").lower()
    county = str(row.get("LOCATION_COUNTY") or "").lower()
    regions = str(row.get("REGIONS") or "").lower()
    needles = (
        "gloucester",
        "cheltenham",
        "stroud",
        "cirencester",
        "tewkesbury",
        "forest of dean",
        "bristol",
        "filton",
        "south gloucestershire",
    )
    blob = f"{town} {county} {regions}"
    return any(n in blob for n in needles)


def build_courses() -> pd.DataFrame:
    providers = pd.read_csv(PROVIDERS_CSV, dtype=str).fillna("")
    provider_web = {
        str(r["PROVIDER_UKPRN"]): str(r.get("CONTACT_WEBSITE") or "")
        for _, r in providers.iterrows()
    }

    # Stream filter — file is ~95MB
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(COURSES_CSV, dtype=str, chunksize=50_000, low_memory=False):
        chunk = chunk.fillna("")
        mask = chunk.apply(_is_local_row, axis=1)
        local = chunk.loc[mask]
        if len(local):
            chunks.append(local)
    if not chunks:
        raise SystemExit("No local courses found — check filters / source file.")
    df = pd.concat(chunks, ignore_index=True)

    # Prefer classroom / substantial courses; drop tiny skills bootcamps noise later by sampling
    rows: list[dict] = []
    seen: set[str] = set()
    for _, r in df.iterrows():
        name = str(r.get("COURSE_NAME") or "").strip()
        if len(name) < 8:
            continue
        ukprn = str(r.get("PROVIDER_UKPRN") or "")
        course_id = str(r.get("COURSE_ID") or "")
        key = f"{ukprn}:{course_id}:{name.lower()}"
        if key in seen:
            continue
        seen.add(key)

        town = str(r.get("LOCATION_TOWN") or "").strip() or "Gloucestershire"
        postcode = str(r.get("LOCATION_POSTCODE") or "").strip()
        who = str(r.get("WHO_THIS_COURSE_IS_FOR") or "").strip()
        level = str(r.get("EDUCATION_LEVEL") or "").strip()
        sector_raw = str(r.get("SECTOR") or "").strip()
        ctype = str(r.get("COURSE_TYPE") or "").strip()
        study = str(r.get("STUDY_MODE") or "").strip()
        provider_name = ""
        # Provider name from providers file
        match_p = providers.loc[providers["PROVIDER_UKPRN"] == ukprn]
        if len(match_p):
            provider_name = str(
                match_p.iloc[0].get("TRADING_NAME")
                or match_p.iloc[0].get("PROVIDER_NAME")
                or ""
            ).strip()

        sectors = _sectors_from_text(name, sector_raw, ctype)
        summary_bits = [b for b in (who[:220] if who else "", f"Level: {level}" if level else "", f"Type: {ctype}" if ctype else "") if b]
        summary = " ".join(summary_bits) or f"{name} delivered by {provider_name or 'a local provider'}."
        website = _clean_url(str(r.get("COURSE_URL") or ""), provider_web.get(ukprn, ""))
        profile = " | ".join(
            [
                name,
                provider_name,
                town,
                level,
                sector_raw,
                ctype,
                who[:160],
                sectors.replace("|", " "),
            ]
        )
        provider_rank = 0
        if PREFERRED_PROVIDER.search(provider_name):
            provider_rank = 2
        elif SCHOOL_PROVIDER.search(provider_name):
            provider_rank = 0
        else:
            provider_rank = 1

        rows.append(
            {
                "course_id": f"NCS-{ukprn}-{course_id}"[:64],
                "title": name[:180],
                "provider": provider_name or f"UKPRN {ukprn}",
                "provider_ukprn": ukprn,
                "town": town,
                "postcode": postcode,
                "region": _region(postcode, town),
                "level": level or "See provider",
                "course_type": ctype,
                "study_mode": study,
                "sectors": sectors,
                "entry_routes": _entry_routes(level, study, ctype),
                "summary": summary[:400],
                "website": website,
                "profile_text": profile[:800],
                "provider_rank": provider_rank,
                "source": "ncs_course_directory",
                "source_date": "2026-06",
            }
        )

    out = pd.DataFrame(rows)
    # Always keep strong title matches for key career themes (better demo relevance)
    priority_pat = re.compile(
        r"\b(?:computer science|cyber|ICT|software|programming|network|CCNA|"
        r"nurs|health.?care|social care|engineer|construct|plumb|"
        r"business|AAT|education|early.?year|hospitality|tourism|"
        r"agricultur|digital data|T Level)\b",
        re.I,
    )
    priority = out[out["title"].str.contains(priority_pat, na=False)].copy()
    # Prefer colleges/unis; take diverse sectors
    out = out.sort_values(["provider_rank", "title"], ascending=[False, True])
    capped: list[pd.DataFrame] = [priority.head(40)]
    for sector in sorted({s for row in rows for s in str(row["sectors"]).split("|") if s}):
        subset = out[out["sectors"].str.contains(sector, regex=False)]
        capped.append(subset.head(8))
    # Prefer Gloucestershire rows for regional balance
    glos = out[out["region"] == "gloucestershire"].head(25)
    capped.append(glos)
    capped.append(out.head(40))
    final = pd.concat(capped, ignore_index=True).drop_duplicates(subset=["course_id"]).head(100)
    final = final.drop(columns=["provider_rank"], errors="ignore")
    final = final.sort_values(["region", "provider", "title"]).reset_index(drop=True)
    return final


def build_microcreds(courses: pd.DataFrame) -> pd.DataFrame:
    """Short / Level 3+ local courses suitable as PD exploration (not ELCAS-verified)."""
    level_ok = courses["level"].str.contains(
        r"level\s*[3-7]|higher|degree|htq|access", case=False, na=False, regex=True
    )
    shortish = courses["course_type"].str.contains(
        r"Skills Bootcamp|Higher Technical|Free Courses|Essential", case=False, na=False, regex=True
    ) | courses["title"].str.contains(
        r"certificate|diploma|award|unit|module|short|bootcamp|HTQ|access",
        case=False,
        na=False,
        regex=True,
    )
    pick = courses.loc[level_ok | shortish].copy()
    if pick.empty:
        pick = courses.head(20).copy()
    pick = pick.head(24)
    rows = []
    for i, r in pick.iterrows():
        rows.append(
            {
                "cred_id": f"MC-{r['course_id']}"[:64],
                "title": r["title"],
                "provider": r["provider"],
                "town": r["town"],
                "region": r["region"],
                "level": r["level"],
                "sectors": r["sectors"],
                "summary": (
                    f"{r['summary']} "
                    "Eligibility for Enhanced Learning Credits (ELC) must be checked on ELCAS "
                    "and with Education Staff — this demo does not confirm funding approval."
                )[:450],
                "website": r["website"],
                "elcas_status": "check_on_elcas",
                "profile_text": r["profile_text"],
                "source": "ncs_course_directory",
                "source_date": "2026-06",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    SEED.mkdir(parents=True, exist_ok=True)
    courses = build_courses()
    courses.to_csv(OUT, index=False)
    micro = build_microcreds(courses)
    micro.to_csv(MICRO, index=False)
    print(f"Wrote {len(courses)} courses -> {OUT}")
    print(f"Wrote {len(micro)} micro-creds -> {MICRO}")
    print(courses["region"].value_counts().to_string())


if __name__ == "__main__":
    main()
