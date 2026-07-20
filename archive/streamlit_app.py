"""
ARCHIVED — Streamlit prototype (superseded by Next.js web/ + FastAPI api/).

Run only if you need the old UI:
  .venv\\Scripts\\streamlit run archive/streamlit_app.py

Product path: uvicorn api.main:app + cd web && npm run dev
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from glos_recommender.briefing import generate_briefing
from glos_recommender.personas import persona_bundle
from glos_recommender.intake_config import (
    load_intake_options,
    load_psych_questions,
    pathways_for_sectors,
)
from glos_recommender.labels import fit_label, hiring_label, overall_label
from glos_recommender.matching import load_companies, load_opportunities, match_companies

load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="Glos Career Match",
    page_icon="🗺️",
    layout="wide",
)


@st.cache_data
def _companies():
    return load_companies()


@st.cache_data
def _opportunities():
    return load_opportunities()


@st.cache_data
def _options():
    return load_intake_options()


@st.cache_data
def _psych():
    return load_psych_questions()


def render_intake() -> dict | None:
    options = _options()
    psych = _psych()

    st.header("Tell us about you")
    st.caption(
        "Answer a few questions and we’ll recommend three Gloucestershire organisations "
        "that regularly offer routes for school and university leavers."
    )
    st.info(
        "**Live demo — not official careers advice.** Matches are illustrative. "
        "Vacancy-derived profiles may include closed or archived adverts — always check "
        "[Find an apprenticeship](https://www.findapprenticeship.service.gov.uk/) and employer sites. "
        "When you hit **Find my top 3 companies**, briefings are written with OpenAI if "
        "`OPENAI_API_KEY` is set in `.env` (otherwise an offline template is used)."
    )

    col1, col2 = st.columns(2)
    with col1:
        leaver_type = st.selectbox("I am a…", options["leaver_types"])
        location = st.selectbox("Where I’m based / will work", options["locations"])
        qualification_level = st.selectbox(
            "Highest qualification level (current or expected)",
            options["qualification_levels"],
        )
        availability = st.selectbox("Availability", options["availability"])

    with col2:
        if "University" in leaver_type:
            course_choices = options["course_areas"]["university"]
        else:
            course_choices = options["course_areas"]["school_college"]
        courses = st.multiselect("Courses studied / studying", course_choices)
        interests = st.multiselect("Interests (pick up to 5)", options["interests"], max_selections=5)
        passions = st.multiselect("What you enjoy most (pick up to 4)", options["passions"], max_selections=4)
        work_experience = st.multiselect("Work experience so far", options["work_experience_types"])

    st.subheader("Work-style questions")
    st.caption(psych.get("disclaimer", ""))
    psych_answers = {}
    questions = psych["questions"]
    # Lay out as 3 columns × 2 rows (instead of a single 6×1 stack)
    for row_start in range(0, len(questions), 3):
        cols = st.columns(3)
        for col, q in zip(cols, questions[row_start : row_start + 3]):
            with col:
                labels = {opt["label"]: opt["id"] for opt in q["options"]}
                choice = st.radio(q["prompt"], list(labels.keys()), key=q["id"])
                psych_answers[q["id"]] = labels[choice]

    if st.button("Find my top 3 companies", type="primary"):
        if not interests and not courses:
            st.warning("Please select at least one course or interest.")
            return None
        return {
            "leaver_type": leaver_type,
            "location": location,
            "courses": courses,
            "interests": interests,
            "passions": passions,
            "work_experience": work_experience,
            "qualification_level": qualification_level,
            "availability": availability,
            "psych_answers": psych_answers,
        }
    return None


def render_how_to_use_advice():
    """Guidance panel aligned with good CEIAG / Gatsby-style next steps."""
    st.header("How to use this advice")
    st.caption(
        "This demo is a starting point for exploration — not a final career decision. "
        "Use it like a careers conversation checklist."
    )
    with st.expander("Read this before you act on your matches", expanded=True):
        st.markdown(
            """
**Treat matches as options, not a verdict**  
Your top 3 are suggestions based on interests and routes. You can disagree, explore further, or pick a different path.

**1. Check the fit in your own words**  
For each employer, ask: *Does this match what I enjoy? What skills would I use? What would a normal week look like?*

**2. Follow a training route, not only a brand name**  
Use the pathway cards (teacher training, hospitality, trades, etc.). Good guidance links **learning → experience → application**.

**3. Verify live opportunities**  
Listings here can include closed or older apprenticeship adverts. Always confirm on  
[Find an apprenticeship](https://www.findapprenticeship.service.gov.uk/) or the employer’s careers page.

**4. Take one small step this month** (pick any 1–2)
- Talk to a careers adviser, tutor, or Careers Hub contact  
- Visit one employer / open day / CyNam or sector event  
- Add one portfolio, volunteering, or project piece from your briefing  
- Draft a short “why this route” paragraph for applications  

**5. Talk it through with a person**  
Personal guidance works best with a qualified adviser. Bring this page as a discussion aid — scores are ranking aids, not a psychometric diagnosis.

**6. Keep more than one door open**  
Strong career planning usually explores **two or three routes** (e.g. apprenticeship *and* college; TA *and* later teacher training).
"""
        )


def _render_pathway_cards(cards: list, *, expanded: bool = False):
    for card in cards:
        with st.expander(f"{card['title']}", expanded=expanded):
            if card.get("reason"):
                st.caption(card["reason"])
            st.write(card.get("summary", "").strip())
            steps = card.get("steps") or []
            if steps:
                st.markdown("**Typical steps**")
                for s in steps:
                    st.markdown(f"- {s}")
            anchors = card.get("local_anchors") or []
            if anchors:
                st.markdown("**Local anchors:** " + "; ".join(anchors))


def render_pathways(leaver: dict):
    sectors = leaver.get("interest_sectors") or leaver.get("target_sectors") or set()
    interest_cards = pathways_for_sectors(sectors)
    interest_ids = {str(p.get("id")) for p in interest_cards if p.get("id")}
    persona = persona_bundle(leaver, interest_pathway_ids=interest_ids, peer_limit=4)
    leaver["persona"] = persona.get("persona")

    if persona.get("persona"):
        st.subheader(f"Your career group: {persona['persona']}")
        if persona.get("persona_blurb"):
            st.write(persona["persona_blurb"])
        if persona.get("runner_up"):
            st.caption(
                f"Also close to **{persona['runner_up']}** — those routes are blended into the list below."
            )
        if persona.get("persona_disclaimer"):
            st.caption(persona["persona_disclaimer"])

        fit = persona.get("persona_fit") or []
        col_bars, col_map = st.columns(2)
        with col_bars:
            if fit:
                st.markdown("**How close you are to each group** (closest = 100)")
                for row in fit:
                    label = row["persona"]
                    if row.get("is_primary"):
                        label += " · closest"
                    elif row.get("is_runner_up"):
                        label += " · nearby"
                    st.caption(f"{label}: {row.get('closeness')}")
                    st.progress(min(1.0, float(row.get("closeness", 0)) / 100.0))
        with col_map:
            map_2d = persona.get("persona_map_2d")
            if map_2d and map_2d.get("you") and map_2d.get("centroids"):
                st.markdown("**Where you sit in the model**")
                st.caption("PCA map of the career groups — lime = you.")
                points = [
                    {
                        "label": "You",
                        "x": float(map_2d["you"]["x"]),
                        "y": float(map_2d["you"]["y"]),
                        "kind": "You",
                        "size": 400,
                    }
                ]
                for c in map_2d["centroids"]:
                    points.append(
                        {
                            "label": str(c.get("persona") or "Group"),
                            "x": float(c["x"]),
                            "y": float(c["y"]),
                            "kind": "Closest group"
                            if c.get("is_primary")
                            else "Other group",
                            "size": 280 if c.get("is_primary") else 180,
                        }
                    )
                map_df = pd.DataFrame(points)
                import plotly.express as px

                fig = px.scatter(
                    map_df,
                    x="x",
                    y="y",
                    color="kind",
                    text="label",
                    size="size",
                    color_discrete_map={
                        "You": "#b8f229",
                        "Closest group": "#0d5c54",
                        "Other group": "#8aa39c",
                    },
                    hover_data={"size": False, "x": False, "y": False},
                )
                fig.update_traces(textposition="top center")
                fig.update_layout(
                    height=360,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend_title_text="",
                    xaxis_title="",
                    yaxis_title="",
                    plot_bgcolor="#eef4f1",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "Cluster map unavailable — run `scripts/build_persona_model.py` then restart."
                )

    routes = (persona.get("training_routes") or interest_cards)[:4]
    if routes:
        st.header("Training routes for you")
        st.caption(
            "Ranked using your interests and your closest career groups in the model."
        )
        _render_pathway_cards(routes)


def render_matches(leaver: dict, ranked: pd.DataFrame):
    st.header("Your top 3 company matches")
    st.write(
        f"**Work-style signals:** {', '.join(leaver['psych'].get('dominant_riasec', [])) or 'n/a'}  \n"
        f"**Target sectors:** {', '.join(sorted(leaver['target_sectors'])) or 'n/a'}"
    )

    render_how_to_use_advice()
    render_pathways(leaver)

    opportunities = _opportunities()
    tabs = st.tabs([f"#{i+1} {row['name']}" for i, row in ranked.iterrows()])

    for rank_i, (tab, (_, row)) in enumerate(zip(tabs, ranked.iterrows())):
        with tab:
            st.subheader(row["name"])
            st.write(
                f"**{row['town']}** · {overall_label(rank_i)} · "
                f"[Website]({row['website']})"
            )
            st.write(row["summary"])

            m1, m2, m3 = st.columns(3)
            m1.metric(
                "How well does the sector fit my interests and experience?",
                fit_label(row["sector_score"]),
            )
            m2.metric("How well does their route fit yours?", fit_label(row["entry_score"]))
            m3.metric("Are they hiring for entry roles?", hiring_label(row.to_dict()))
            st.caption(
                "These labels compare your top matches — they are **not** your chances of getting a job. "
                "A ‘Worth exploring’ or ‘Check current openings’ result still means apply if the role interests you."
            )

            briefings = st.session_state.get("briefings") or {}
            text = briefings.get(row["company_id"])
            source = (st.session_state.get("briefing_sources") or {}).get(
                row["company_id"], "offline"
            )
            if text:
                if source == "openai":
                    st.caption("Briefing written with OpenAI")
                else:
                    st.caption("Offline briefing (no API key or OpenAI unavailable)")
                st.markdown(text)

            subset = opportunities[opportunities["company_id"] == row["company_id"]]
            if len(subset):
                st.markdown("#### Recent opportunities")
                st.dataframe(
                    subset[["title", "entry_route", "level", "typical_quals", "useful_projects"]],
                    use_container_width=True,
                    hide_index=True,
                )


def main():
    st.title("Gloucestershire Career Match")
    st.caption(
        "School & university leaver → top 3 local employers + personalised pathways · "
        "Non-commercial demo"
    )

    tab_intake, tab_explore, tab_about = st.tabs(["Match me", "Explore employers", "About"])

    with tab_intake:
        form = render_intake()
        if form:
            leaver, ranked = match_companies(form, _companies(), top_n=3)
            opportunities = _opportunities()
            briefings: dict[str, str] = {}
            sources: dict[str, str] = {}
            with st.spinner("Finding matches and writing your briefings…"):
                for _, row in ranked.iterrows():
                    text, source = generate_briefing(
                        leaver, row, opportunities, use_openai=True
                    )
                    briefings[str(row["company_id"])] = text
                    sources[str(row["company_id"])] = source
            st.session_state["leaver"] = leaver
            st.session_state["ranked"] = ranked
            st.session_state["briefings"] = briefings
            st.session_state["briefing_sources"] = sources

        if "ranked" in st.session_state:
            render_matches(st.session_state["leaver"], st.session_state["ranked"])

    with tab_explore:
        st.header("Employer directory")
        st.caption(
            "Includes curated priority employers and vacancy-derived organisations. "
            "Not a live jobs board."
        )
        st.dataframe(
            _companies()[
                ["name", "town", "sectors", "entry_routes", "hiring_signal", "website"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tab_about:
        st.markdown(
            """
### What this demo does
1. Collects courses, interests, passions, experience and 6 work-style questions  
2. Scores Gloucestershire employers with a hybrid matcher  
3. Returns your **top 3** with OpenAI briefings (or offline if no API key)

### Disclaimer (please read)
- This is a **non-commercial live demo**, not an official careers service.  
- Recommendations are **guidance only** — they do not guarantee interviews, places, or jobs.  
- Employer names are used factually; inclusion is **not an endorsement** by those organisations.  
- Apprenticeship vacancy data may include **closed or archived** adverts. Always verify on  
  [Find an apprenticeship](https://www.findapprenticeship.service.gov.uk/) or the employer’s site.  
- On **Find my top 3**, briefings are generated with OpenAI when `OPENAI_API_KEY` is set  
  (profile + match context are sent to OpenAI under their API terms); otherwise offline templates are used.  
- After you match, use the **How to use this advice** panel (options, pathways, verify live jobs, one next step, talk to an adviser).

### Data & open source
- Software: **MIT** licence (`LICENSE`)  
- Data sources & OGL attribution: **`DATA.md`**  
- Curated priority employers + DfE Find an Apprenticeship (GL postcodes, OGL)  
- Pathway cards for education, hospitality, and construction trades  

> Contains public sector information licensed under the  
> [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).  
> Source: Department for Education — Apprenticeships / Explore Education Statistics.

### ML pipeline notebooks
Run in order: `00_environment_setup` → `01_data_consolidation` →  
`02_feature_engineering` → `03_clustering` → `04_recommender_system` →  
`05_rag_briefing`, then refresh this app.
"""
        )


if __name__ == "__main__":
    main()
