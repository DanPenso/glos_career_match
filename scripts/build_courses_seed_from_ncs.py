"""Build a Glos + Bristol FE/HE course seed from National Careers Service open data.

Source: DfE National Careers Service course directory (Open Government Licence v3.0)
https://www.gov.uk/government/publications/national-careers-service-course-directory

Usage (from project root):
  .venv\\Scripts\\python scripts/build_courses_seed_from_ncs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
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

# NCS course type codes (GOV.UK code tables)
NCS_COURSE_TYPE_LABELS = {
    "1": "Essential skills",
    "2": "T Level",
    "3": "Higher Technical Qualification (HTQ)",
    "4": "Free Courses for Jobs",
    "5": "Multiply",
    "6": "Skills Bootcamp",
}

NVQ_TITLE = re.compile(r"\bNVQ\b|National Vocational Qual", re.I)
BOOTCAMP_TITLE = re.compile(r"\bSkills?\s*Bootcamp\b|\bBootcamp\b", re.I)
TLEVEL_TITLE = re.compile(r"\bT[\s-]?Level\b", re.I)
BTEC_TITLE = re.compile(r"\bBTEC\b", re.I)
ACCESS_TITLE = re.compile(r"\bAccess to Higher Education\b|\bAccess to HE\b", re.I)
DIPLOMA_TITLE = re.compile(r"\bDiploma\b", re.I)
CERTIFICATE_TITLE = re.compile(r"\bCertificate\b|\bAward\b", re.I)


def _course_type_label(title: str, course_type_code: str) -> str:
    """Human-readable type for UI (title heuristics first; funding codes last)."""
    t = title or ""
    code = str(course_type_code or "").strip().split(".")[0]
    # Qualification-style labels beat funding programme codes (1/4/5).
    if NVQ_TITLE.search(t):
        return "NVQ"
    if BOOTCAMP_TITLE.search(t) or code == "6":
        return "Skills Bootcamp"
    if TLEVEL_TITLE.search(t) or code == "2":
        return "T Level"
    if ACCESS_TITLE.search(t):
        return "Access to HE"
    if BTEC_TITLE.search(t):
        return "BTEC"
    if re.search(r"\bA[\s-]?Level\b|\bGCE\b", t, re.I):
        return "A Level"
    if DIPLOMA_TITLE.search(t):
        return "Diploma"
    if CERTIFICATE_TITLE.search(t):
        return "Certificate"
    if re.search(r"\bDegree\b|\bBSc\b|\bBA\b|\bHND\b|\bHNC\b", t, re.I):
        return "Higher education"
    if code == "3":
        return "Higher Technical Qualification (HTQ)"
    if code == "4":
        return "Free Courses for Jobs"
    if code == "1":
        return "Essential skills"
    if code == "5":
        return "Multiply"
    return NCS_COURSE_TYPE_LABELS.get(code, "FE / HE course")


def _entry_routes(education_level: str, study_mode: str, course_type: str, type_label: str) -> str:
    level = str(education_level or "").lower()
    mode = str(study_mode or "").lower()
    ctype = str(course_type or "").lower()
    label = str(type_label or "").lower()
    routes: list[str] = []
    if "apprentice" in ctype or "apprentice" in level or "nvq" in label:
        routes.append("apprenticeship")
    if "bootcamp" in label:
        routes.extend(["school_leaver", "apprenticeship", "internship"])
    if any(x in level for x in ("level 6", "level 7", "degree", "higher education", "he ")):
        routes.extend(["graduate", "higher_apprenticeship"])
    if any(x in level for x in ("level 3", "level 4", "level 5", "a level", "t level", "access")):
        routes.extend(["school_leaver", "apprenticeship"])
    if "t level" in label or "btec" in label or "access" in label:
        routes.extend(["school_leaver", "apprenticeship"])
    if "part" in mode or "flexible" in mode:
        routes.append("internship")
    if not routes:
        routes = ["school_leaver", "apprenticeship"]
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
        type_label = _course_type_label(name, ctype)
        summary_bits = [
            b
            for b in (
                who[:200] if who else "",
                f"Type: {type_label}",
                f"Level: {level}" if level else "",
            )
            if b
        ]
        summary = " ".join(summary_bits) or f"{name} delivered by {provider_name or 'a local provider'}."
        website = _clean_url(str(r.get("COURSE_URL") or ""), provider_web.get(ukprn, ""))
        profile = " | ".join(
            [
                name,
                provider_name,
                town,
                level,
                type_label,
                sector_raw,
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

        # Boost vocational routes in seed selection
        vocational_boost = 0
        if type_label in {"NVQ", "Skills Bootcamp"}:
            vocational_boost = 3
        elif type_label in {"T Level", "BTEC", "Higher Technical Qualification (HTQ)", "Free Courses for Jobs"}:
            vocational_boost = 2
        elif type_label in {"Access to HE", "Diploma", "Certificate"}:
            vocational_boost = 1

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
                "course_type_label": type_label,
                "study_mode": study,
                "sectors": sectors,
                "entry_routes": _entry_routes(level, study, ctype, type_label),
                "summary": summary[:400],
                "website": website,
                "profile_text": profile[:800],
                "provider_rank": provider_rank,
                "vocational_boost": vocational_boost,
                "source": "ncs_course_directory",
                "source_date": "2026-06",
            }
        )

    out = pd.DataFrame(rows)
    # Force-include NVQ + Skills Bootcamp rows (demo request)
    vocational = out[
        out["course_type_label"].isin(["NVQ", "Skills Bootcamp"])
        | out["title"].str.contains(r"\bNVQ\b|Bootcamp", case=False, na=False)
        | out["course_type"].astype(str).str.startswith("6")
    ].copy()

    priority_pat = re.compile(
        r"\b(?:computer science|cyber|ICT|software|programming|network|CCNA|"
        r"nurs|health.?care|social care|engineer|construct|plumb|"
        r"business|AAT|education|early.?year|hospitality|tourism|"
        r"agricultur|digital data|T Level|NVQ|Bootcamp|BTEC|Access)\b",
        re.I,
    )
    priority = out[out["title"].str.contains(priority_pat, na=False)].copy()
    out = out.sort_values(
        ["vocational_boost", "provider_rank", "title"],
        ascending=[False, False, True],
    )
    capped: list[pd.DataFrame] = [
        vocational.head(40),
        priority.head(40),
    ]
    for sector in sorted({s for row in rows for s in str(row["sectors"]).split("|") if s}):
        subset = out[out["sectors"].str.contains(sector, regex=False)]
        capped.append(subset.head(8))
    glos = out[out["region"] == "gloucestershire"].head(25)
    capped.append(glos)
    capped.append(out.head(50))
    final = (
        pd.concat(capped, ignore_index=True)
        .drop_duplicates(subset=["course_id"])
        .head(130)
    )
    final = final.drop(columns=["provider_rank", "vocational_boost"], errors="ignore")
    final = final.sort_values(["region", "provider", "title"]).reset_index(drop=True)
    return final


def build_microcreds(courses: pd.DataFrame) -> pd.DataFrame:
    """Short / Level 3+ local courses suitable as PD exploration (not ELCAS-verified)."""
    level_ok = courses["level"].astype(str).str.contains(
        r"level\s*[3-7]|higher|degree|htq|access|3|4|5|6|7",
        case=False,
        na=False,
        regex=True,
    )
    shortish = courses["course_type_label"].astype(str).str.contains(
        r"Bootcamp|HTQ|Free Courses|Essential|Certificate|NVQ|Diploma",
        case=False,
        na=False,
        regex=True,
    ) | courses["title"].str.contains(
        r"certificate|diploma|award|unit|module|short|bootcamp|HTQ|access|NVQ",
        case=False,
        na=False,
        regex=True,
    )
    pick = courses.loc[level_ok | shortish].copy()
    if pick.empty:
        pick = courses.head(20).copy()
    # Prefer vocational types in micro-cred list
    if "course_type_label" in pick.columns:
        pick["_rank"] = pick["course_type_label"].map(
            lambda x: 0
            if str(x) in {"NVQ", "Skills Bootcamp"}
            else 1
            if "HTQ" in str(x) or "Bootcamp" in str(x)
            else 2
        )
        pick = pick.sort_values(["_rank", "title"]).drop(columns=["_rank"])
    pick = pick.head(28)
    rows = []
    for _, r in pick.iterrows():
        rows.append(
            {
                "cred_id": f"MC-{r['course_id']}"[:64],
                "title": r["title"],
                "provider": r["provider"],
                "town": r["town"],
                "region": r["region"],
                "level": r["level"],
                "course_type_label": r.get("course_type_label", ""),
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
    from glos_recommender.role_families import ensure_role_families_column

    SEED.mkdir(parents=True, exist_ok=True)
    courses = ensure_role_families_column(build_courses())
    courses.to_csv(OUT, index=False)
    micro = ensure_role_families_column(build_microcreds(courses))
    micro.to_csv(MICRO, index=False)
    print(f"Wrote {len(courses)} courses -> {OUT}")
    print(f"Wrote {len(micro)} micro-creds -> {MICRO}")
    print(courses["region"].value_counts().to_string())
    if "course_type_label" in courses.columns:
        print(courses["course_type_label"].value_counts().head(15).to_string())


if __name__ == "__main__":
    main()
