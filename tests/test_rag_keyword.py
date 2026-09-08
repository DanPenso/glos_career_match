"""Keyword RAG ranking tests (no FAISS, no network, no master CSV)."""

from __future__ import annotations

from glos_recommender.rag import (
    load_evidence_cards,
    load_howto_cards,
    retrieve_evidence_keyword,
    retrieve_howto_keyword,
)


def _evidence_fixture_cards() -> list[dict]:
    return [
        {
            "id": "apprenticeship_cv",
            "strategy": "apprenticeship applications",
            "source_label": "Fixture — apprenticeship CV",
            "strength": "strong",
            "tags": ["apprenticeship", "cv", "application", "employer"],
            "claim": "Practise apprenticeship application and CV skills with an employer.",
            "do": "Draft a CV and check apprenticeship vacancies before you apply.",
            "do_not_claim": "Do not invent closing dates.",
        },
        {
            "id": "employer_encounters",
            "strategy": "employer encounters",
            "source_label": "Fixture — employer encounters",
            "strength": "moderate",
            "tags": ["employer", "encounters", "workplace"],
            "claim": "Meeting an employer helps you understand a real workplace.",
            "do": "Arrange one employer visit or careers talk this month.",
            "do_not_claim": "Do not treat a website as an encounter.",
        },
        {
            "id": "greenhouse_watering",
            "strategy": "greenhouse watering",
            "source_label": "Fixture — greenhouse",
            "strength": "moderate",
            "tags": ["greenhouse", "plants", "watering", "application"],
            "claim": "Water greenhouse plants on a regular application schedule.",
            "do": "Check soil moisture in the greenhouse before watering.",
            "do_not_claim": "Do not skip a week.",
        },
    ]


def _howto_fixture_cards() -> list[dict]:
    return [
        {
            "id": "cv_structure",
            "topic": "cv_structure",
            "source_label": "Fixture — CV structure",
            "tags": ["cv", "application", "prepare"],
            "tip": "Keep a CV to one page with clear headings for this application.",
            "do": "Write a short profile and two experience bullets that match the role.",
            "do_not_claim": "Do not claim a perfect CV guarantees an interview.",
        },
        {
            "id": "star_interview",
            "topic": "star_method",
            "source_label": "Fixture — STAR",
            "tags": ["interview", "star", "application"],
            "tip": "STAR helps you tell a clear interview story.",
            "do": "Practise one STAR example for the interview.",
            "do_not_claim": "Do not invent results.",
        },
        {
            "id": "greenhouse_pruning",
            "topic": "greenhouse_pruning",
            "source_label": "Fixture — pruning",
            "tags": ["greenhouse", "plants", "pruning", "application"],
            "tip": "Prune greenhouse plants so they stay healthy.",
            "do": "Prepare clean shears before you prune.",
            "do_not_claim": "Do not over-prune.",
        },
    ]


def _ids(hits: list[dict]) -> list[str]:
    return [str(hit["card"].get("id")) for hit in hits]


def test_evidence_keyword_ranks_relevant_above_unrelated() -> None:
    hits = retrieve_evidence_keyword(
        "apprenticeship application employer vacancies",
        top_k=4,
        cards=_evidence_fixture_cards(),
    )
    ids = _ids(hits)

    assert ids[0] == "apprenticeship_cv"
    assert "greenhouse_watering" in ids
    assert ids.index("apprenticeship_cv") < ids.index("greenhouse_watering")
    scores = [hit["score"] for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_howto_keyword_ranks_relevant_above_unrelated() -> None:
    hits = retrieve_howto_keyword(
        "how to write a CV for an application",
        top_k=4,
        cards=_howto_fixture_cards(),
    )
    ids = _ids(hits)

    assert ids[0] == "cv_structure"
    assert "greenhouse_pruning" in ids
    assert ids.index("cv_structure") < ids.index("greenhouse_pruning")
    scores = [hit["score"] for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_evidence_keyword_on_local_yaml_ranks_apprenticeship_above_mentoring() -> None:
    hits = retrieve_evidence_keyword(
        "apprenticeship vocational training routes",
        top_k=8,
        cards=load_evidence_cards(),
    )
    ids = _ids(hits)

    assert "yff_apprenticeships" in ids
    assert ids[0] == "yff_apprenticeships"
    if "yff_mentoring" in ids:
        assert ids.index("yff_apprenticeships") < ids.index("yff_mentoring")


def test_howto_keyword_on_local_yaml_ranks_interview_above_apprenticeship_search() -> None:
    hits = retrieve_howto_keyword(
        "STAR interview technique practise",
        top_k=8,
        cards=load_howto_cards(),
    )
    ids = _ids(hits)

    assert ids[0] in {"prospects_star", "ncs_interview_prep"}
    if "find_apprenticeship_search" in ids:
        interview_rank = min(
            ids.index(i) for i in ids if i in {"prospects_star", "ncs_interview_prep"}
        )
        assert interview_rank < ids.index("find_apprenticeship_search")
