"""Generate 200 frozen synthetic WORK intake journeys (50 × 4 strata).

Writes data/eval/journeys_200.jsonl. Strings come from data/taxonomy/*.yaml.
No PII. Age 16+ only (never under_16). Stratum label is no_quals, not neet.

Run from repo root:
  .venv\\Scripts\\python scripts/eval/generate_journeys_200.py
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import yaml

_SCRIPTS_EVAL = Path(__file__).resolve().parent
if str(_SCRIPTS_EVAL) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_EVAL))

from common import (  # noqa: E402
    JOURNEYS_PATH,
    N_PER_STRATUM,
    RANDOM_SEED,
    ROOT,
    STRATA,
    write_jsonl,
)

TAXONOMY_DIR = ROOT / "data" / "taxonomy"
INTAKE_PATH = TAXONOMY_DIR / "intake_options.yaml"
PRIORS_PATH = TAXONOMY_DIR / "persona_priors.yaml"
PSYCH_PATH = TAXONOMY_DIR / "psych_questions.yaml"

GL_LOCATIONS = [
    "Cheltenham",
    "Gloucester",
    "Stroud",
    "Cirencester / Cotswolds",
    "Tewkesbury / North Gloucestershire",
    "Forest of Dean",
    "Anywhere in Gloucestershire",
]
BS_LOCATIONS = [
    "Bristol",
    "South Gloucestershire / Filton",
    "Willing to commute / hybrid / Bristol",
]

PERSONAS = [
    "Technical Specialist",
    "Hands-on Maker",
    "People & Care",
    "Creative / Commercial",
]

# Persona-aligned psych option ids (all six questions).
PSYCH_BY_PERSONA: dict[str, dict[str, tuple[str, ...]]] = {
    "Technical Specialist": {
        "Q1_problem_style": ("analyse", "build"),
        "Q2_energy_source": ("discovered", "shipped"),
        "Q3_work_setting": ("office_hybrid", "workshop_lab"),
        "Q4_structure_vs_autonomy": ("clear_structure", "mix"),
        "Q5_risk_novelty": ("careful", "pioneer"),
        "Q6_team_role": ("specialist", "organiser"),
    },
    "Hands-on Maker": {
        "Q1_problem_style": ("build", "analyse"),
        "Q2_energy_source": ("shipped", "discovered"),
        "Q3_work_setting": ("workshop_lab", "office_hybrid"),
        "Q4_structure_vs_autonomy": ("mix", "clear_structure"),
        "Q5_risk_novelty": ("apply", "pioneer"),
        "Q6_team_role": ("specialist", "organiser"),
    },
    "People & Care": {
        "Q1_problem_style": ("people", "analyse"),
        "Q2_energy_source": ("helped", "influenced"),
        "Q3_work_setting": ("community", "office_hybrid"),
        "Q4_structure_vs_autonomy": ("mix", "clear_structure"),
        "Q5_risk_novelty": ("careful", "apply"),
        "Q6_team_role": ("connector", "organiser"),
    },
    "Creative / Commercial": {
        "Q1_problem_style": ("create", "people"),
        "Q2_energy_source": ("influenced", "shipped"),
        "Q3_work_setting": ("studio_events", "office_hybrid"),
        "Q4_structure_vs_autonomy": ("open_ended", "mix"),
        "Q5_risk_novelty": ("pioneer", "apply"),
        "Q6_team_role": ("ideas", "organiser"),
    },
}

SCHOOL_L2_L3 = [
    "Working towards GCSEs / Level 2",
    "GCSEs / Level 2",
    "A-levels / BTEC / T Levels / Level 3",
]
FE_VOC_L2_L3 = [
    "NVQ / City & Guilds / other technical",
    "GCSEs / Level 2",
    "A-levels / BTEC / T Levels / Level 3",
]
NO_QUALS = "No formal qualifications yet"
GRAD_L6 = "Undergraduate degree / Level 6"

SCHOOL_LEAVER_TYPE = "School leaver (Year 11 / 13)"
FE_LEAVER_TYPE = "College / FE leaver"
GRAD_LEAVER_TYPES = [
    "University undergraduate (final year)",
    "Recent graduate",
]

AGE_16_PLUS = ("16_17", "18_24", "25_plus")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Expected mapping in {path}")
    return data


def _invert_map(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    inv: dict[str, list[str]] = {}
    for label, sectors in mapping.items():
        for sector in sectors or []:
            inv.setdefault(str(sector), []).append(str(label))
    return inv


def _choice(rng: np.random.Generator, items: list[Any]) -> Any:
    if not items:
        raise ValueError("empty choice list")
    return items[int(rng.integers(0, len(items)))]


def _sample(rng: np.random.Generator, items: list[Any], k: int) -> list[Any]:
    if not items:
        return []
    k = max(1, min(k, len(items)))
    idx = rng.choice(len(items), size=k, replace=False)
    return [items[int(i)] for i in np.atleast_1d(idx)]


def _persona_cycle(rng: np.random.Generator, n: int) -> list[str]:
    base: list[str] = []
    while len(base) < n:
        base.extend(PERSONAS)
    base = base[:n]
    order = rng.permutation(len(base))
    return [base[int(i)] for i in order]


def _location(rng: np.random.Generator) -> str:
    pool = GL_LOCATIONS + GL_LOCATIONS + BS_LOCATIONS
    return _choice(rng, pool)


def _age_for_stratum(rng: np.random.Generator, stratum: str) -> str:
    if stratum == "school_leaver":
        return _choice(rng, ["16_17"] * 7 + ["18_24"] * 3)
    if stratum == "fe_leaver":
        return _choice(rng, ["16_17"] * 3 + ["18_24"] * 7)
    if stratum == "graduate":
        return _choice(rng, ["18_24"] * 7 + ["25_plus"] * 3)
    return _choice(rng, ["16_17"] * 4 + ["18_24"] * 4 + ["25_plus"] * 2)


def _psych_answers(rng: np.random.Generator, persona: str) -> dict[str, str]:
    prefs = PSYCH_BY_PERSONA[persona]
    answers: dict[str, str] = {}
    for qid, options in prefs.items():
        answers[qid] = options[0] if rng.random() < 0.75 else _choice(rng, list(options))
    return answers


def _interests_for_persona(
    rng: np.random.Generator,
    persona: str,
    priors: dict[str, Any],
    sector_to_interests: dict[str, list[str]],
    all_interests: list[str],
) -> list[str]:
    typical = list((priors.get(persona) or {}).get("typical_sectors") or [])
    pool: list[str] = []
    for sector in typical:
        pool.extend(sector_to_interests.get(sector, []))
    seen: list[str] = []
    for label in pool:
        if label in all_interests and label not in seen:
            seen.append(label)
    if len(seen) < 2:
        seen = list(all_interests)
    k = 2 if rng.random() < 0.55 else 3
    picked = _sample(rng, seen, k)
    if rng.random() < 0.18:
        extra = [x for x in all_interests if x not in picked]
        if extra:
            picked.append(_choice(rng, extra))
    return picked[:3]


def _courses_for_interests(
    rng: np.random.Generator,
    interests: list[str],
    stratum: str,
    interest_to_sector: dict[str, list[str]],
    sector_to_courses: dict[str, list[str]],
    school_courses: list[str],
    uni_courses: list[str],
) -> list[str]:
    catalogue = uni_courses if stratum == "graduate" else school_courses
    sectors: list[str] = []
    for interest in interests:
        sectors.extend(interest_to_sector.get(interest, []))
    pool: list[str] = []
    for sector in sectors:
        for course in sector_to_courses.get(sector, []):
            if course in catalogue and course not in pool:
                pool.append(course)
    if stratum == "no_quals":
        light = [c for c in catalogue if c in {"Other / Undecided", "Other"} or c in pool[:2]]
        if rng.random() < 0.35:
            return []
        pool = light or pool or catalogue
        return _sample(rng, pool, 1)
    if not pool:
        pool = list(catalogue)
    k = 1 if rng.random() < 0.45 else 2
    return _sample(rng, pool, k)


def _passions(rng: np.random.Generator, persona: str, all_passions: list[str]) -> list[str]:
    by_persona = {
        "Technical Specialist": [
            "Solving puzzles / problems",
            "Analysing numbers / patterns",
            "Protecting systems / people",
            "Making products people use",
        ],
        "Hands-on Maker": [
            "Building or fixing things",
            "Working outdoors",
            "Growing food / nature",
            "Making products people use",
        ],
        "People & Care": [
            "Helping people face-to-face",
            "Leading teams / organising",
            "Performing / presenting",
            "Protecting systems / people",
        ],
        "Creative / Commercial": [
            "Creating visual / written content",
            "Leading teams / organising",
            "Performing / presenting",
            "Making things work better",
        ],
    }
    pool = [p for p in by_persona[persona] if p in all_passions] or list(all_passions)
    return _sample(rng, pool, 2 if rng.random() < 0.6 else 1)


def _work_experience(rng: np.random.Generator, stratum: str, all_exp: list[str]) -> list[str]:
    pools = {
        "no_quals": [
            "None yet",
            "Volunteering",
            "Part-time retail / hospitality",
            "Caring responsibilities",
            "Family / small business",
        ],
        "school_leaver": [
            "None yet",
            "Work experience placement (school)",
            "Part-time retail / hospitality",
            "Sports coaching / mentoring",
            "Volunteering",
        ],
        "fe_leaver": [
            "Part-time retail / hospitality",
            "Volunteering",
            "Apprenticeship (previous)",
            "Family / small business",
            "Work experience placement (school)",
        ],
        "graduate": [
            "Internship / sandwich year",
            "1 year of industry exp",
            "Coding / personal projects",
            "Volunteering",
            "Part-time retail / hospitality",
        ],
    }
    pool = [x for x in pools[stratum] if x in all_exp] or list(all_exp)
    k = 1 if rng.random() < 0.7 else 2
    return _sample(rng, pool, k)


def _barriers_support(
    rng: np.random.Generator,
    all_barriers: list[str],
    all_support: list[str],
    all_must: list[str],
) -> tuple[list[str], list[str], list[str]]:
    barriers: list[str] = []
    if rng.random() < 0.45:
        pool = [b for b in all_barriers if b != "Prefer not to say"]
        barriers = _sample(rng, pool, 1 if rng.random() < 0.7 else 2)
    support = _sample(rng, all_support, 1)
    must_pool = [
        m
        for m in all_must
        if m != "Open to military info"
    ]
    k = 1 if rng.random() < 0.55 else 2
    must_haves = _sample(rng, must_pool or all_must, k)
    return barriers, support, must_haves


def _goal_proud(
    rng: np.random.Generator, persona: str, location: str, stratum: str
) -> tuple[str, str]:
    goals = {
        "Technical Specialist": [
            "I want to learn a digital skill I can use in a real workplace.",
            "I want a structured route into tech or data work locally.",
        ],
        "Hands-on Maker": [
            "I want paid practical work where I can learn on the job.",
            "I want a trade or engineering route I can travel to from town.",
        ],
        "People & Care": [
            "I want work that helps people and has a clear next step.",
            "I want to try health, education, or public-service routes nearby.",
        ],
        "Creative / Commercial": [
            "I want customer or creative work I can build a portfolio from.",
            "I want a first role in events, retail, or business support.",
        ],
    }
    proud = {
        "Technical Specialist": [
            "I finished a small website for a family event.",
            "I taught myself a short coding tutorial and made a demo page.",
        ],
        "Hands-on Maker": [
            "I helped repair a bike and logged what I changed.",
            "I built a small shelf at home and measured it myself.",
        ],
        "People & Care": [
            "I volunteered at a local club and helped new people settle in.",
            "I explained a topic to a classmate until it made sense.",
        ],
        "Creative / Commercial": [
            "I designed a poster for a community event.",
            "I helped run a stall and kept a simple takings list.",
        ],
    }
    if stratum == "no_quals":
        goals[persona] = [
            "I want a first step that does not assume lots of certificates.",
            "I want local paid work with training I can start from where I am.",
        ] + goals[persona]
    loc_bit = f" Based in {location}."
    goal = _choice(rng, goals[persona])
    if rng.random() < 0.5 and len(goal) + len(loc_bit) < 160:
        goal = goal.rstrip(".") + loc_bit
    return goal, _choice(rng, proud[persona])


def _leaver_and_quals(
    rng: np.random.Generator, stratum: str, all_leaver_types: list[str]
) -> tuple[str, str]:
    if stratum == "no_quals":
        return _choice(rng, all_leaver_types), NO_QUALS
    if stratum == "school_leaver":
        return SCHOOL_LEAVER_TYPE, _choice(rng, SCHOOL_L2_L3)
    if stratum == "fe_leaver":
        return FE_LEAVER_TYPE, _choice(rng, FE_VOC_L2_L3)
    return _choice(rng, GRAD_LEAVER_TYPES), GRAD_L6


def _availability(rng: np.random.Generator, all_avail: list[str]) -> str:
    return _choice(rng, all_avail)


def _apply_readiness(rng: np.random.Generator, all_ready: list[str]) -> str:
    return _choice(rng, all_ready)


def build_journeys(seed: int = RANDOM_SEED) -> list[dict[str, Any]]:
    intake = _load_yaml(INTAKE_PATH)
    priors_root = _load_yaml(PRIORS_PATH)
    psych = _load_yaml(PSYCH_PATH)
    priors = priors_root.get("personas") or {}

    all_leaver_types = list(intake["leaver_types"])
    all_locations = list(intake["locations"])
    all_interests = list(intake["interests"])
    all_passions = list(intake["passions"])
    all_exp = list(intake["work_experience_types"])
    all_quals = list(intake["qualification_levels"])
    all_avail = list(intake["availability"])
    all_barriers = list(intake["barriers"])
    all_must = list(intake["must_haves"])
    all_support = list(intake["support_available"])
    all_ready = list(intake["apply_readiness"])
    school_courses = list(intake["course_areas"]["school_college"])
    uni_courses = list(intake["course_areas"]["university"])
    interest_to_sector = {k: list(v) for k, v in (intake.get("interest_to_sector") or {}).items()}
    course_to_sector = {k: list(v) for k, v in (intake.get("course_to_sector") or {}).items()}
    sector_to_interests = _invert_map(interest_to_sector)
    sector_to_courses = _invert_map(course_to_sector)

    psych_ids = {q["id"] for q in psych.get("questions") or []}
    psych_opts = {
        q["id"]: {opt["id"] for opt in q.get("options") or []} for q in psych.get("questions") or []
    }

    allowed = {
        "leaver_types": set(all_leaver_types),
        "locations": set(all_locations),
        "interests": set(all_interests),
        "passions": set(all_passions),
        "work_experience": set(all_exp),
        "qualification_levels": set(all_quals),
        "availability": set(all_avail),
        "barriers": set(all_barriers),
        "must_haves": set(all_must),
        "support_available": set(all_support),
        "apply_readiness": set(all_ready),
        "courses": set(school_courses) | set(uni_courses),
    }
    if not set(GL_LOCATIONS + BS_LOCATIONS) <= allowed["locations"]:
        missing = set(GL_LOCATIONS + BS_LOCATIONS) - allowed["locations"]
        raise SystemExit(f"Location labels missing from taxonomy: {sorted(missing)}")

    journeys: list[dict[str, Any]] = []
    for stratum_idx, stratum in enumerate(STRATA):
        rng = np.random.default_rng(seed + (stratum_idx + 1) * 10_007)
        personas = _persona_cycle(rng, N_PER_STRATUM)
        for i in range(N_PER_STRATUM):
            journey_seed = int(seed + stratum_idx * 1_000 + i)
            persona = personas[i]
            leaver_type, qual = _leaver_and_quals(rng, stratum, all_leaver_types)
            location = _location(rng)
            age_band = _age_for_stratum(rng, stratum)
            interests = _interests_for_persona(
                rng, persona, priors, sector_to_interests, all_interests
            )
            courses = _courses_for_interests(
                rng,
                interests,
                stratum,
                interest_to_sector,
                sector_to_courses,
                school_courses,
                uni_courses,
            )
            passions = _passions(rng, persona, all_passions)
            experience = _work_experience(rng, stratum, all_exp)
            barriers, support, must_haves = _barriers_support(
                rng, all_barriers, all_support, all_must
            )
            goal, proud = _goal_proud(rng, persona, location, stratum)
            psych_answers = _psych_answers(rng, persona)

            question = {
                "leaver_type": leaver_type,
                "location": location,
                "age_band": age_band,
                "courses": courses,
                "interests": interests,
                "passions": passions,
                "work_experience": experience,
                "qualification_level": qual,
                "availability": _availability(rng, all_avail),
                "proud_example": proud,
                "goal_sentence": goal,
                "barriers": barriers,
                "must_haves": must_haves,
                "support_available": support,
                "apply_readiness": _apply_readiness(rng, all_ready),
                "psych_answers": psych_answers,
                "use_openai_briefing": True,
                "use_gemini_plan": False,
                "allow_anonymous_logging": False,
                "top_n": 3,
                "mode": "work",
            }
            _validate_question(
                question,
                allowed=allowed,
                psych_ids=psych_ids,
                psych_opts=psych_opts,
                stratum=stratum,
            )
            journeys.append(
                {
                    "journey_id": f"j_{stratum}_{i:03d}",
                    "stratum": stratum,
                    "seed": journey_seed,
                    "persona": persona,
                    "question": question,
                }
            )
    return journeys


def _validate_question(
    question: dict[str, Any],
    *,
    allowed: dict[str, set[str]],
    psych_ids: set[str],
    psych_opts: dict[str, set[str]],
    stratum: str,
) -> None:
    if question["mode"] != "work":
        raise SystemExit("mode must be work")
    if question.get("use_gemini_plan"):
        raise SystemExit("use_gemini_plan must be false")
    age = str(question["age_band"])
    if age == "under_16" or age not in AGE_16_PLUS:
        raise SystemExit(f"age_band must be 16+ declared band, got {age!r}")
    if stratum == "neet" or str(question.get("stratum") or "") == "neet":
        raise SystemExit("do not label a stratum neet")

    def _check(value: str, key: str) -> None:
        if value not in allowed[key]:
            raise SystemExit(f"{key} value not in taxonomy: {value!r}")

    _check(question["leaver_type"], "leaver_types")
    _check(question["location"], "locations")
    _check(question["qualification_level"], "qualification_levels")
    _check(question["availability"], "availability")
    _check(question["apply_readiness"], "apply_readiness")
    for key, field in (
        ("interests", "interests"),
        ("passions", "passions"),
        ("work_experience", "work_experience"),
        ("barriers", "barriers"),
        ("must_haves", "must_haves"),
        ("support_available", "support_available"),
        ("courses", "courses"),
    ):
        for item in question[field]:
            _check(str(item), key)

    if stratum == "no_quals" and question["qualification_level"] != NO_QUALS:
        raise SystemExit("no_quals must use No formal qualifications yet")
    if stratum == "school_leaver":
        if question["leaver_type"] != SCHOOL_LEAVER_TYPE:
            raise SystemExit("school_leaver must use Year 11/13 leaver type")
        if question["qualification_level"] not in SCHOOL_L2_L3:
            raise SystemExit("school_leaver quals must be Level 2–3-ish")
    if stratum == "fe_leaver":
        if question["leaver_type"] != FE_LEAVER_TYPE:
            raise SystemExit("fe_leaver must use College / FE leaver")
        if question["qualification_level"] not in FE_VOC_L2_L3:
            raise SystemExit("fe_leaver quals must be vocational Level 2–3")
    if stratum == "graduate":
        if question["leaver_type"] not in GRAD_LEAVER_TYPES:
            raise SystemExit("graduate must be recent grad or final-year UG")
        if question["qualification_level"] != GRAD_L6:
            raise SystemExit("graduate must be Level 6")

    answers = question["psych_answers"]
    if set(answers) != psych_ids:
        raise SystemExit(f"psych_answers keys mismatch: {sorted(answers)}")
    for qid, oid in answers.items():
        if oid not in psych_opts[qid]:
            raise SystemExit(f"unknown psych option {qid}={oid}")


def _summary(journeys: list[dict[str, Any]]) -> str:
    lines = [f"Generated {len(journeys)} journeys (seed={RANDOM_SEED})", ""]
    by_s = Counter(j["stratum"] for j in journeys)
    for stratum in STRATA:
        rows = [j for j in journeys if j["stratum"] == stratum]
        personas = Counter(j["persona"] for j in rows)
        locs = Counter(
            "BS" if j["question"]["location"] in BS_LOCATIONS else "GL"
            for j in rows
        )
        ages = Counter(j["question"]["age_band"] for j in rows)
        barriers_n = sum(1 for j in rows if j["question"]["barriers"])
        lines.append(
            f"- {stratum}: n={by_s[stratum]} | "
            f"personas={dict(personas)} | loc={dict(locs)} | "
            f"age={dict(ages)} | with_barriers={barriers_n}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate 200 stratified WORK intake journeys.")
    parser.add_argument("--out", type=Path, default=JOURNEYS_PATH)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args(argv)

    if args.seed != RANDOM_SEED:
        print(f"Warning: locked plan uses RANDOM_SEED={RANDOM_SEED}; got {args.seed}")

    journeys = build_journeys(seed=int(args.seed))
    if len(journeys) != N_PER_STRATUM * len(STRATA):
        raise SystemExit(f"expected 200 journeys, got {len(journeys)}")
    if any(j["stratum"] == "neet" for j in journeys):
        raise SystemExit("stratum neet is not allowed")

    out = args.out if args.out.is_absolute() else ROOT / args.out
    n = write_jsonl(out, journeys)
    print(_summary(journeys))
    print(f"Wrote {n} rows -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
