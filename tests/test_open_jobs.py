"""Reed live-jobs flags: join by employer name, skip apprenticeships."""

from __future__ import annotations

from glos_recommender.open_jobs import (
    JOBS_OPEN_LABEL,
    is_apprenticeship_title,
    open_fields_for_employer_jobs,
    open_jobs_index,
    slim_reed_job,
)


def _job(
    *,
    job_id: str,
    title: str,
    employer: str,
    employer_key: str,
    expiration: str = "01/01/2028",
) -> dict:
    return {
        "job_id": job_id,
        "title": title,
        "employer_name": employer,
        "employer_key": employer_key,
        "location_name": "Cheltenham",
        "expiration_date": expiration,
        "job_url": f"https://www.reed.co.uk/jobs/{job_id}",
    }


def test_employer_jobs_join_by_normalised_name() -> None:
    doc = {
        "fetched_at": "2026-09-11T12:00:00+00:00",
        "jobs": [
            _job(
                job_id="1",
                title="Graduate software engineer",
                employer="Example Care Ltd",
                employer_key="example care",
            ),
            _job(
                job_id="2",
                title="Healthcare assistant",
                employer="Example Care Limited",
                employer_key="example care",
            ),
        ],
    }
    index = open_jobs_index(doc)
    info = open_fields_for_employer_jobs("Example Care Ltd", index=index)
    assert info["jobs_open_now"] is True
    assert info["jobs_open_label"] == JOBS_OPEN_LABEL
    assert info["jobs_open_count"] == 2
    assert "reed.co.uk/jobs/1" in info["jobs_open_url"]
    assert info["jobs_open_source"] == "reed_jobseeker"
    assert open_fields_for_employer_jobs("Unknown CIC", index=index)["jobs_open_now"] is False


def test_expired_job_is_not_open() -> None:
    doc = {
        "fetched_at": "2026-09-11T12:00:00+00:00",
        "jobs": [
            _job(
                job_id="old",
                title="Expired role",
                employer="Old Co",
                employer_key="old co",
                expiration="01/01/2020",
            )
        ],
    }
    assert open_jobs_index(doc) == {}


def test_apprenticeship_titles_are_dropped() -> None:
    assert is_apprenticeship_title("Software apprentice")
    assert is_apprenticeship_title("Degree Apprenticeship — Engineering")
    assert not is_apprenticeship_title("Graduate software engineer")
    slim = slim_reed_job(
        {
            "jobId": "99",
            "jobTitle": "Business apprentice",
            "employerName": "Example Care Ltd",
            "locationName": "Gloucester",
            "jobUrl": "https://www.reed.co.uk/jobs/99",
            "expirationDate": "01/01/2028",
        }
    )
    assert slim is None
    doc = {
        "fetched_at": "2026-09-11T12:00:00+00:00",
        "jobs": [
            _job(
                job_id="9",
                title="Engineering apprentice",
                employer="Example Care Ltd",
                employer_key="example care",
            )
        ],
    }
    assert open_jobs_index(doc) == {}


def test_slim_reed_job_keeps_local_listing() -> None:
    slim = slim_reed_job(
        {
            "jobId": 40126680,
            "jobTitle": "Graduate nurse",
            "employerName": "Example Care Ltd",
            "locationName": "Cheltenham",
            "jobUrl": "https://www.reed.co.uk/jobs/graduate-nurse/40126680",
            "expirationDate": "30/09/2027",
        }
    )
    assert slim is not None
    assert slim["job_id"] == "40126680"
    assert slim["employer_key"] == "example care"
    assert slim_reed_job(
        {
            "jobId": "1",
            "jobTitle": "Remote analyst",
            "employerName": "National Co",
            "locationName": "United Kingdom",
            "jobUrl": "https://www.reed.co.uk/jobs/1",
        }
    ) is None
