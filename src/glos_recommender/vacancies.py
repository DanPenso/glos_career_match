"""Ingest DfE Find an Apprenticeship vacancy underlying data for Gloucestershire.

Source: Explore Education Statistics — Apprenticeships 2025/26
underlying vacancies file (RAAv2 / Find an Apprenticeship).
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_ZIP = RAW_DIR / "apprenticeship_vacancies.zip"

# EES release 2025/26 — apps_u12 underlying vacancies
VACANCIES_URL = (
    "https://content.explore-education-statistics.service.gov.uk"
    "/api/releases/5fa09991-9ced-4ca5-b626-73b747df272d"
    "/files/ddaf7ab2-0a9d-49e7-8a72-aea4b675f3fa"
)

USECOLS = [
    "vacancy_reference_number",
    "current_status",
    "date_posted",
    "vacancy_title",
    "vacancy_description",
    "skills_required",
    "employer_full_name",
    "vacancy_postcode",
    "vacancy_town",
    "sector_name",
    "education_level",
    "apprenticeship_type",
    "framework_or_standard_name",
    "number_of_positions",
]

# DfE sector_name → project taxonomy tags
SECTOR_MAP: dict[str, list[str]] = {
    "accountancy": ["business_professional"],
    "business": ["business_professional"],
    "business and administration": ["business_professional"],
    "sales, marketing and procurement": ["business_professional"],
    "legal, finance and accounting": ["business_professional"],
    "management consultancy": ["business_professional"],
    "digital industries": ["cyber_digital"],
    "digital": ["cyber_digital"],
    "information technology": ["cyber_digital"],
    "health and science": ["health_care"],
    "health": ["health_care"],
    "healthcare": ["health_care"],
    "dental health": ["health_care"],
    "adult care": ["health_care"],
    "care services": ["health_care"],
    "engineering": ["aerospace_manufacturing"],
    "engineering and manufacturing": ["aerospace_manufacturing"],
    "manufacturing": ["aerospace_manufacturing"],
    "transport and logistics": ["aerospace_manufacturing", "business_professional"],
    "automotive": ["aerospace_manufacturing"],
    "automotive retail": ["hospitality_retail", "aerospace_manufacturing"],
    "construction": ["construction_green"],
    "building and construction": ["construction_green"],
    "building services engineering": ["construction_green"],
    "electrotechnical": ["construction_green"],
    "property services": ["construction_green"],
    "surveying": ["construction_green"],
    "housing": ["construction_green"],
    "energy and utilities": ["construction_green"],
    "facilities management": ["construction_green", "business_professional"],
    "agriculture, environmental and animal care": ["agri_tech_food"],
    "agriculture": ["agri_tech_food"],
    "food and drink": ["agri_tech_food", "hospitality_tourism"],
    "horticulture": ["agri_tech_food"],
    "hospitality": ["hospitality_tourism"],
    "catering and hospitality": ["hospitality_tourism"],
    "travel": ["hospitality_tourism"],
    "event management": ["creative_events", "hospitality_tourism"],
    "retail": ["hospitality_retail"],
    "hair and beauty": ["hospitality_retail"],
    "customer service": ["business_professional", "hospitality_retail"],
    "public service": ["public_sector"],
    "protective services": ["public_sector"],
    "education and childcare": ["education_training"],
    "education and training": ["education_training"],
    "teaching and education": ["education_training"],
    "creative and design": ["creative_events"],
    "arts, media and publishing": ["creative_events"],
    "media": ["creative_events"],
    "logistics and supply chain": ["business_professional"],
}

ROLE_HINTS: dict[str, list[str]] = {
    "cyber_digital": ["software", "cyber", "data", "analyst"],
    "aerospace_manufacturing": ["engineer_ops", "manufacturing", "technician", "quality"],
    "agri_tech_food": ["field_ops", "ops", "technician"],
    "health_care": ["care", "admin"],
    "public_sector": ["admin", "ops", "project_support"],
    "creative_events": ["design", "content", "events"],
    "construction_green": ["technician", "field_ops", "ops", "engineer_ops"],
    "hospitality_retail": ["customer_success", "sales", "ops"],
    "hospitality_tourism": ["customer_success", "ops", "events"],
    "business_professional": ["admin", "finance", "sales", "project_coord"],
    "education_training": ["teaching_support", "admin", "care"],
}

_EDU_ORG = re.compile(
    r"\b("
    r"schools?|nurser(?:y|ies)|colleges?|universit(?:y|ies)|"
    r"(?:infant|junior|primary|secondary|special)\s+schools?|"
    r"(?:multi[-\s]?academy|academy)\s+trust|school\s+academy|"
    r"childcare|early\s*years|pupil\s*referral|alternative\s*provision"
    r")\b",
    re.I,
)
_EDU_ROLE = re.compile(
    r"\b("
    r"teaching\s*assistant|learning\s*support|early\s*years\s*(educator|assistant|practitioner)?|"
    r"nursery\s*assistant|childcare|classroom\s*assistant|send\s*assistant|"
    r"teacher\s*training|pgce|\bqts\b|lecturer|tutor"
    r")\b",
    re.I,
)
# Standalone "teacher" in titles (avoid matching random text)
_TEACHER_TITLE = re.compile(r"\b(teacher|teaching)\b", re.I)
_HOSP_ORG = re.compile(
    r"\b(hotel|hotels|restaurant|restaurants|hilton|premier\s*inn|travelodge|"
    r"greene\s*king|marston|pub|inns?|brasserie|cafe|café|catering|"
    r"hospitality|leisure)\b",
    re.I,
)
_HOSP_ROLE = re.compile(
    r"\b(chef|commis|kitchen|waiter|waitress|front\s*of\s*house|barista|"
    r"bartender|housekeep|receptionist|hospitality\s*supervisor|"
    r"food\s*(and|&)\s*beverage|f&b)\b",
    re.I,
)
_HAIR_ROLE = re.compile(r"\b(hair|barber|beauty|stylist|salon)\b", re.I)
# Hands-on built-environment trades (avoid bare "electrical" — catches aerospace/auto)
_TRADE_ROLE = re.compile(
    r"\b("
    r"plumb(?:er|ing)?|plumbing\s+and\s+domestic\s+heating|domestic\s+heating|"
    r"heating\s+(?:and\s+)?(?:plumbing|engineer)|gas\s+engineering|"
    r"installation\s+electrician|domestic\s+electrician|electrotechnical|"
    r"electrical\s+installation|maintenance\s+electrician|electrician|"
    r"bricklay(?:er|ing)|carpent(?:er|ry)|joinery|\bjoiner\b|"
    r"scaffold(?:er|ing)|groundwork(?:er)?|roof(?:er|ing)|"
    r"painter\s*(?:and|&)?\s*decorator|painting\s+and\s+decorating|"
    r"building\s+services|site\s+carpenter|bench\s+joiner|"
    r"civil\s+engineering|construction\s+(?:operative|site\s+supervisor)|"
    r"dry\s*lin(?:er|ing)|plaster(?:er|ing)|wall\s*and\s*floor\s*tiler"
    r")\b",
    re.I,
)
_TRADE_ORG = re.compile(
    r"\b("
    r"construction|builders?|building\s+services|scaffolding|"
    r"electrical\s+contract|plumbing|heating\s+engineer|"
    r"housebuild|developments?"
    r")\b",
    re.I,
)
_IT_SUPPORT_ROLE = re.compile(
    r"\b("
    r"ict|it\s+support|help\s*desk|service\s*desk|1st\s*line|2nd\s*line|"
    r"desktop\s+support|device\s+management|systems?\s+support|"
    r"information\s+communications\s+technician"
    r")\b",
    re.I,
)
_CYBER_STRONG_ROLE = re.compile(
    r"\b("
    r"cyber|soc|security\s+operations|penetration\s+test|incident\s+response|"
    r"threat|forensics|siem"
    r")\b",
    re.I,
)
_FINANCE_ROLE = re.compile(r"\b(finance|accounts?|bookkeep|payroll)\b", re.I)

_LEGAL_SUFFIX = re.compile(
    r"\b(limited|ltd|llc|plc|llp|inc|corporation|corp|group|uk|the)\b\.?",
    re.I,
)


def download_vacancies_zip(
    dest: Path | None = None,
    url: str = VACANCIES_URL,
    force: bool = False,
) -> Path:
    """Download the vacancies zip if missing (large ~90MB)."""
    dest = dest or DEFAULT_ZIP
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force and dest.stat().st_size > 1_000_000:
        return dest
    req = Request(url, headers={"User-Agent": "GlosCareerMatch/1.0"})
    with urlopen(req, timeout=300) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return dest


def load_vacancy_frame(zip_path: Path | None = None) -> pd.DataFrame:
    """Load underlying vacancies CSV from the EES zip."""
    zip_path = zip_path or DEFAULT_ZIP
    if not zip_path.exists():
        download_vacancies_zip(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise FileNotFoundError(f"No CSV inside {zip_path}")
        with zf.open(names[0]) as f:
            return pd.read_csv(f, usecols=USECOLS, low_memory=False)


def filter_gloucestershire(df: pd.DataFrame) -> pd.DataFrame:
    """Keep vacancies with GL* postcodes (Gloucestershire outward codes)."""
    out = df.copy()
    pc = out["vacancy_postcode"].astype(str).str.upper().str.strip()
    mask = pc.str.match(r"^GL\d", na=False)
    out = out.loc[mask].copy()
    out["vacancy_postcode"] = pc.loc[mask]
    out["postcode_district"] = out["vacancy_postcode"].str.extract(
        r"^(GL\d{1,2})", expand=False
    )
    return out


def map_sector(sector_name: Any) -> list[str]:
    if pd.isna(sector_name) or not str(sector_name).strip():
        return ["business_professional"]
    key = str(sector_name).strip().lower()
    if key in SECTOR_MAP:
        return list(SECTOR_MAP[key])
    for fragment, tags in SECTOR_MAP.items():
        if fragment in key or key in fragment:
            return list(tags)
    return ["business_professional"]


def infer_sectors(
    sector_name: Any,
    employer: str = "",
    title: str = "",
    standard: str = "",
) -> list[str]:
    """Map DfE sector plus employer/title cues (schools often mis-tagged upstream)."""
    employer_s = str(employer or "")
    title_s = str(title or "")
    standard_s = str(standard or "")
    blob = f"{employer_s} {title_s} {standard_s}"
    role_blob = f"{title_s} {standard_s}"

    # Avoid over-classifying generic ICT support/admin apprenticeships as cyber.
    if _IT_SUPPORT_ROLE.search(role_blob) and not _CYBER_STRONG_ROLE.search(role_blob):
        return ["business_professional"]
    if _FINANCE_ROLE.search(role_blob) and not _CYBER_STRONG_ROLE.search(role_blob):
        return ["business_professional"]

    # Built-environment trades before hospitality/education heuristics
    if _TRADE_ROLE.search(f"{title_s} {standard_s}") or (
        _TRADE_ORG.search(employer_s) and _TRADE_ROLE.search(blob)
    ):
        return ["construction_green"]

    # Hospitality craft titles win over false "academy"/"college" wording in job ads
    if _HOSP_ROLE.search(blob) or (
        _HOSP_ORG.search(employer_s) and not _EDU_ROLE.search(title_s)
    ):
        if not (_EDU_ROLE.search(title_s) or _TEACHER_TITLE.search(title_s)):
            return ["hospitality_tourism"]

    edu_hit = (
        _EDU_ORG.search(employer_s)
        or _EDU_ROLE.search(blob)
        or (_TEACHER_TITLE.search(title_s) and _EDU_ORG.search(blob))
    )
    if edu_hit and not _HOSP_ROLE.search(title_s) and not _TRADE_ROLE.search(title_s):
        tags = ["education_training"]
        if re.search(r"\b(nursery|early\s*years|childcare)\b", blob, re.I):
            tags.append("health_care")
        return tags

    if _HAIR_ROLE.search(blob) and not _HOSP_ORG.search(employer_s):
        return ["hospitality_retail"]
    if _HOSP_ORG.search(blob):
        return ["hospitality_tourism"]
    if _TRADE_ORG.search(employer_s):
        return ["construction_green"]

    return map_sector(sector_name)


def _majority_tags(series_of_lists: pd.Series, max_tags: int = 2) -> list[str]:
    """Keep the most common tags so mixed training agencies don't dominate matching."""
    counts: dict[str, int] = {}
    for items in series_of_lists:
        for item in items:
            counts[item] = counts.get(item, 0) + 1
    if not counts:
        return ["business_professional"]
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_n = ranked[0][1]
    # Keep tags within 50% of the top count, capped
    keep = [t for t, n in ranked if n >= max(1, int(0.5 * top_n))]
    return keep[:max_tags]


def map_entry_routes(education_level: Any, apprenticeship_type: Any) -> list[str]:
    text = f"{education_level or ''} {apprenticeship_type or ''}".lower()
    routes = ["apprenticeship"]
    if "higher" in text or "degree" in text or "level 6" in text or "level 7" in text:
        routes.append("higher_apprenticeship")
    if "level 2" in text or "intermediate" in text:
        routes.append("school_leaver")
    return sorted(set(routes))


def map_roles(sectors: list[str], title: str = "", skills: str = "") -> list[str]:
    roles: list[str] = []
    for s in sectors:
        roles.extend(ROLE_HINTS.get(s, ["ops"]))
    blob = f"{title} {skills}".lower()
    if any(k in blob for k in ("software", "developer", "it ", "digital", "cyber")):
        roles.extend(["software", "cyber"])
    if any(k in blob for k in ("engineer", "manufactur", "cnc", "mechanical")):
        roles.extend(["engineer_ops", "manufacturing", "technician"])
    if any(k in blob for k in ("account", "finance", "bookkeep")):
        roles.append("finance")
    if any(k in blob for k in ("care", "nurs", "dental", "health")):
        roles.append("care")
    if any(k in blob for k in ("teaching", "teacher", "early years", "nursery")):
        roles.append("teaching_support")
    if any(k in blob for k in ("chef", "kitchen", "waiter", "hospitality")):
        roles.extend(["customer_success", "ops"])
    if any(
        k in blob
        for k in (
            "plumb",
            "electric",
            "brick",
            "carpenter",
            "joiner",
            "scaffold",
            "groundwork",
            "building services",
        )
    ):
        roles.extend(["technician", "field_ops", "engineer_ops"])
    # Keep top unique hints
    seen: list[str] = []
    for r in roles:
        if r not in seen:
            seen.append(r)
    return seen[:5] or ["ops"]


def normalise_employer_name(name: Any) -> str:
    if pd.isna(name):
        return ""
    s = str(name).lower().strip()
    s = _LEGAL_SUFFIX.sub(" ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title_case_town(town: Any) -> str:
    if pd.isna(town) or not str(town).strip():
        return "Gloucestershire"
    t = str(town).strip()
    if t.upper() in {"UK", "GLOUCESTERSHIRE"}:
        return "Gloucestershire"
    return t.title()


def _hiring_signal(statuses: pd.Series, n_live: int, n_recent: int) -> str:
    if n_live > 0:
        return "high"
    if n_recent >= 2 or (statuses == "Closed").any():
        return "medium"
    return "low"


def _size_band(n_vacancies: int) -> str:
    if n_vacancies >= 8:
        return "large"
    if n_vacancies >= 3:
        return "medium"
    return "sme"


def aggregate_employers(gl_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse GL vacancies into one company row per employer."""
    df = gl_df.copy()
    df["employer_key"] = df["employer_full_name"].map(normalise_employer_name)
    df = df[df["employer_key"].str.len() > 1]
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    df["_sectors"] = [
        infer_sectors(
            sn,
            employer=str(emp or ""),
            title=str(title or ""),
            standard=str(std or ""),
        )
        for sn, emp, title, std in zip(
            df["sector_name"],
            df["employer_full_name"],
            df["vacancy_title"],
            df["framework_or_standard_name"],
        )
    ]
    df["_routes"] = [
        map_entry_routes(e, a)
        for e, a in zip(df["education_level"], df["apprenticeship_type"])
    ]
    df["_roles"] = [
        map_roles(secs, str(t or ""), str(sk or ""))
        for secs, t, sk in zip(
            df["_sectors"], df["vacancy_title"], df["skills_required"]
        )
    ]

    rows: list[dict[str, Any]] = []
    for key, grp in df.groupby("employer_key", sort=False):
        # Prefer live, then closed, then archived; newest first
        status_rank = {"Live": 0, "Closed": 1, "Archived": 2}
        g = grp.copy()
        g["_rank"] = g["current_status"].map(lambda s: status_rank.get(str(s), 3))
        g = g.sort_values(["_rank", "date_posted"], ascending=[True, False])

        display_name = str(g["employer_full_name"].iloc[0]).strip()
        town_mode = g["vacancy_town"].dropna()
        town_mode = town_mode[town_mode.astype(str).str.strip().ne("")]
        town = _title_case_town(
            town_mode.mode().iloc[0] if len(town_mode) else "Gloucestershire"
        )
        pc_mode = g["postcode_district"].dropna()
        postcode = str(pc_mode.mode().iloc[0]) if len(pc_mode) else "GL"

        sectors = _majority_tags(g["_sectors"], max_tags=2)
        routes: list[str] = []
        roles: list[str] = []
        for col, bucket in (("_routes", routes), ("_roles", roles)):
            for items in g[col]:
                for item in items:
                    if item not in bucket:
                        bucket.append(item)

        n_live = int((g["current_status"] == "Live").sum())
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=365)
        n_recent = int((g["date_posted"] >= cutoff).sum())
        n_vac = len(g)

        titles = [
            str(t).strip()
            for t in g["vacancy_title"].dropna().head(4)
            if str(t).strip()
        ]
        standards = [
            str(t).strip()
            for t in g["framework_or_standard_name"].dropna().head(3)
            if str(t).strip()
        ]
        summary_bits = [
            f"Gloucestershire employer ({town}) with apprenticeship vacancies on Find an Apprenticeship.",
        ]
        if titles:
            summary_bits.append("Recent roles include: " + "; ".join(titles[:3]) + ".")
        if standards:
            summary_bits.append("Standards/frameworks: " + ", ".join(standards[:3]) + ".")
        summary = " ".join(summary_bits)

        profile_parts = [
            display_name,
            town,
            "Gloucestershire",
            " ".join(sectors),
            " ".join(routes),
            " ".join(roles),
            " ".join(titles),
            " ".join(standards),
            "apprenticeship school leaver",
        ]
        profile_text = " ".join(p for p in profile_parts if p)

        # Stable id from normalised name
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:8].upper()
        company_id = f"VAC{digest}"

        rows.append(
            {
                "company_id": company_id,
                "name": display_name,
                "town": town,
                "postcode": postcode,
                "sectors": "|".join(sectors[:4]),
                "entry_routes": "|".join(routes),
                "role_families": "|".join(roles[:5]),
                "size_band": _size_band(n_vac),
                "priority_employer": 0,
                "hiring_signal": _hiring_signal(g["current_status"], n_live, n_recent),
                "website": "",
                "summary": summary[:500],
                "profile_text": profile_text[:800],
                "source": "vacancies",
                "employer_key": key,
                "n_vacancies_raw": n_vac,
                "n_live_vacancies": n_live,
            }
        )

    return pd.DataFrame(rows)


def aggregate_opportunities(
    gl_df: pd.DataFrame,
    companies: pd.DataFrame,
    max_per_employer: int = 3,
) -> pd.DataFrame:
    """Build opportunity rows from the strongest vacancies per employer."""
    key_to_id = dict(zip(companies["employer_key"], companies["company_id"]))
    df = gl_df.copy()
    df["employer_key"] = df["employer_full_name"].map(normalise_employer_name)
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    status_rank = {"Live": 0, "Closed": 1, "Archived": 2}
    df["_rank"] = df["current_status"].map(lambda s: status_rank.get(str(s), 3))

    rows: list[dict[str, Any]] = []
    opp_i = 1
    for key, grp in df.groupby("employer_key", sort=False):
        company_id = key_to_id.get(key)
        if not company_id:
            continue
        g = grp.sort_values(["_rank", "date_posted"], ascending=[True, False]).head(
            max_per_employer
        )
        for _, v in g.iterrows():
            sectors = infer_sectors(
                v.get("sector_name"),
                employer=str(v.get("employer_full_name") or ""),
                title=str(v.get("vacancy_title") or ""),
                standard=str(v.get("framework_or_standard_name") or ""),
            )
            routes = map_entry_routes(v.get("education_level"), v.get("apprenticeship_type"))
            roles = map_roles(
                sectors,
                str(v.get("vacancy_title") or ""),
                str(v.get("skills_required") or ""),
            )
            level = str(v.get("education_level") or "Apprenticeship")
            desc = str(v.get("vacancy_description") or "")
            if len(desc) > 400:
                desc = desc[:397] + "..."
            skills = str(v.get("skills_required") or "")
            rows.append(
                {
                    "opportunity_id": f"VOP{opp_i:05d}",
                    "company_id": company_id,
                    "title": str(v.get("vacancy_title") or "Apprenticeship").strip()[:120],
                    "entry_route": routes[0] if routes else "apprenticeship",
                    "level": level[:80],
                    "role_family": roles[0] if roles else "ops",
                    "description": desc or "Apprenticeship vacancy in Gloucestershire.",
                    "typical_quals": skills[:200] if skills else "See vacancy listing",
                    "useful_projects": "Portfolio or course work linked to the standard; local work experience",
                    "application_tips": "Apply via Find an Apprenticeship; tailor CV to the standard and local employer",
                    "source": "vacancies",
                }
            )
            opp_i += 1
    return pd.DataFrame(rows)


def merge_seed_with_vacancies(
    seed_companies: pd.DataFrame,
    seed_opportunities: pd.DataFrame,
    zip_path: Path | None = None,
    max_opp_per_employer: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Merge curated seed employers with GL vacancy-derived employers.

    Seed rows win on name clash (priority_employer kept). Vacancy employers
    fill the long tail.
    """
    zip_path = zip_path or DEFAULT_ZIP
    raw = load_vacancy_frame(zip_path)
    gl = filter_gloucestershire(raw)
    vac_companies = aggregate_employers(gl)
    vac_opps = aggregate_opportunities(gl, vac_companies, max_per_employer=max_opp_per_employer)

    seed_c = seed_companies.copy()
    seed_c["employer_key"] = seed_c["name"].map(normalise_employer_name)
    if "source" not in seed_c.columns:
        seed_c["source"] = "seed"

    seed_keys = set(seed_c["employer_key"])
    # Also block near-matches contained in seed names
    new_companies = vac_companies[~vac_companies["employer_key"].isin(seed_keys)].copy()

    # Drop helper cols before concat for a clean master (keep n_* for EDA)
    companies = pd.concat([seed_c, new_companies], ignore_index=True)

    seed_o = seed_opportunities.copy()
    if "source" not in seed_o.columns:
        seed_o["source"] = "seed"
    # Only keep vacancy opps for companies that remain in the merged table
    keep_ids = set(companies["company_id"])
    vac_opps = vac_opps[vac_opps["company_id"].isin(keep_ids)]
    opportunities = pd.concat([seed_o, vac_opps], ignore_index=True)

    stats = {
        "raw_vacancies": int(len(raw)),
        "gl_vacancies": int(len(gl)),
        "vacancy_employers_total": int(len(vac_companies)),
        "vacancy_employers_added": int(len(new_companies)),
        "seed_companies": int(len(seed_c)),
        "merged_companies": int(len(companies)),
        "merged_opportunities": int(len(opportunities)),
        "live_gl_vacancies": int((gl["current_status"] == "Live").sum()),
    }
    return companies, opportunities, stats


def ensure_vacancies_available(zip_path: Path | None = None) -> Path:
    """Ensure zip exists locally; download if needed."""
    return download_vacancies_zip(zip_path or DEFAULT_ZIP)
