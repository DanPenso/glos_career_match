from glos_recommender.intake_config import load_intake_options


def test_interest_groups_keep_passions_out_of_sector_map() -> None:
    options = load_intake_options()
    groups = {g["id"]: g["items"] for g in options["interest_groups"]}
    assert set(groups) == {"enjoy", "study"}

    mapped = options["interest_to_sector"]
    passions = set(options["passions"])

    for item in groups["enjoy"] + groups["study"]:
        assert item in mapped
        assert item not in passions

    for item in passions:
        assert item not in mapped
        assert item in options["interest_icons"]
