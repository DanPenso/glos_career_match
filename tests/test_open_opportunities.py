"""Open-opportunities flags: FAA cache join + NCS live course rules."""

from __future__ import annotations

from datetime import date

import pandas as pd

from glos_recommender.open_opportunities import (
    OPEN_LABEL,
    course_is_open,
    course_open_url,
    filter_employers_with_open,
    open_apprenticeship_index,
    open_fields_for_course,
    open_fields_for_employer,
    open_fields_for_military,
    vacancy_page_url,
)


def test_vacancy_page_url_prefers_faa() -> None:
    url = vacancy_page_url(
        "VAC123",
        "https://www.findapprenticeship.service.gov.uk/apprenticeship/VAC123",
    )
    assert url.endswith("/apprenticeship/VAC123")
    assert vacancy_page_url("VAC999", "") == (
        "https://www.findapprenticeship.service.gov.uk/apprenticeship/VAC999"
    )


def test_employer_open_join_by_normalised_name() -> None:
    doc = {
        "fetched_at": "2026-09-08T12:00:00+00:00",
        "vacancies": [
            {
                "vacancy_reference": "1",
                "title": "Dental nurse",
                "employer_name": "Example Care Ltd",
                "employer_key": "example care",
                "closing_date": "2027-01-01T00:00:00+00:00",
                "vacancy_url": (
                    "https://www.findapprenticeship.service.gov.uk/apprenticeship/1"
                ),
            },
            {
                "vacancy_reference": "2",
                "title": "Care assistant",
                "employer_name": "Example Care Limited",
                "employer_key": "example care",
                "closing_date": "2027-01-01T00:00:00+00:00",
                "vacancy_url": (
                    "https://www.findapprenticeship.service.gov.uk/apprenticeship/2"
                ),
            },
        ],
    }
    index = open_apprenticeship_index(doc)
    info = open_fields_for_employer("Example Care Ltd", index=index)
    assert info["open_now"] is True
    assert info["open_label"] == OPEN_LABEL
    assert info["open_count"] == 2
    assert info["open_url"].endswith("/apprenticeship/1")
    assert open_fields_for_employer("Unknown CIC", index=index)["open_now"] is False

    companies = pd.DataFrame(
        [
            {"company_id": "a", "name": "Example Care Ltd"},
            {"company_id": "b", "name": "Closed Bakery"},
        ]
    )
    filtered = filter_employers_with_open(companies, index=index)
    assert list(filtered["company_id"]) == ["a"]


def test_closed_vacancy_is_not_open() -> None:
    doc = {
        "fetched_at": "2026-09-08T12:00:00+00:00",
        "vacancies": [
            {
                "vacancy_reference": "old",
                "title": "Expired",
                "employer_name": "Old Co",
                "employer_key": "old co",
                "closing_date": "2020-01-01T00:00:00+00:00",
                "vacancy_url": (
                    "https://www.findapprenticeship.service.gov.uk/apprenticeship/old"
                ),
            }
        ],
    }
    assert open_apprenticeship_index(doc) == {}


def test_course_open_flexible_or_future_start() -> None:
    today = date(2026, 9, 8)
    flexible = {
        "source": "ncs_course_directory",
        "website": "https://college.example/apply",
        "flexible_start": True,
        "title": "NVQ Care",
    }
    assert course_is_open(flexible, today=today)
    info = open_fields_for_course(flexible)
    assert info["open_now"] is True
    assert info["open_url"] == "https://college.example/apply"

    future = {
        "source": "ncs_course_directory",
        "website": "https://college.example/tlevel",
        "start_date": "2026-10-01",
        "flexible_start": False,
    }
    assert course_is_open(future, today=today)

    past = {
        "source": "ncs_course_directory",
        "website": "https://college.example/old",
        "start_date": "2026-01-01",
        "flexible_start": False,
        "source_date": "2026-06",
    }
    assert course_is_open(past, today=today) is False


def test_course_snapshot_fallback_and_stale() -> None:
    today = date(2026, 9, 8)
    fresh = {
        "source": "ncs_course_directory",
        "website": "https://college.example/now",
        "source_date": "2026-08",
    }
    stale = {
        "source": "ncs_course_directory",
        "website": "https://college.example/old",
        "source_date": "2026-06",
    }
    assert course_is_open(fresh, today=today)
    assert course_is_open(stale, today=today) is False


def test_course_find_a_course_url_when_no_website() -> None:
    row = {
        "source": "ncs_course_directory",
        "course_id": "NCS-10001467-bb7253c5-ac59-42a2-8435-38fe6bf03632",
        "course_run_id": "run-1",
        "flexible_start": True,
        "website": "",
    }
    url = course_open_url(row)
    assert "find-a-course/course-details" in url
    assert "courseId=bb7253c5-ac59-42a2-8435-38fe6bf03632" in url
    assert course_is_open(row, today=date(2026, 9, 8))


def test_military_never_open() -> None:
    info = open_fields_for_military({"title": "Army medic", "website": "https://www.army.mod.uk/careers/"})
    assert info["open_now"] is False
    assert info["open_url"] == ""
