import json

from token_iq.api.audit_log_diff import diff_snapshots, summarise


def _fields(changes) -> list[str]:
    return [change.field for change in changes]


def test_only_the_field_that_moved_is_reported() -> None:
    before = {"team_id": "t1", "max_budget": 1.0, "spend": 0.5, "models": ["gpt-4o"]}
    after = {"team_id": "t1", "max_budget": 5.0, "spend": 0.5, "models": ["gpt-4o"]}

    changes = diff_snapshots(before, after)

    # A team update writes the whole row; one field actually changed.
    assert _fields(changes) == ["max_budget"]
    assert changes[0].before == "1.0"
    assert changes[0].after == "5.0"


def test_a_creation_reads_as_every_field_newly_set() -> None:
    changes = diff_snapshots(None, {"team_id": "t1", "max_budget": 5.0})

    assert _fields(changes) == ["max_budget", "team_id"]
    assert all(change.before is None for change in changes)
    assert changes[0].after == "5.0"


def test_a_deletion_reads_as_every_field_removed() -> None:
    changes = diff_snapshots({"team_id": "t1", "max_budget": 5.0}, None)

    assert all(change.after is None for change in changes)
    assert changes[0].before == "5.0"


def test_secrets_are_never_surfaced_even_when_the_row_holds_them() -> None:
    before = {"api_key": "sk-real-secret-value", "spend": 0.0}
    after = {"api_key": "sk-a-different-secret", "spend": 1.0}

    changes = diff_snapshots(before, after)
    by_field = {change.field: change for change in changes}

    # The audit trail must not become a way to read keys back out.
    assert by_field["api_key"].before == "[redacted]"
    assert by_field["api_key"].after == "[redacted]"
    assert "sk-real-secret-value" not in json.dumps([c.model_dump() for c in changes])
    # A non-secret field alongside it is still shown normally.
    assert by_field["spend"].after == "1.0"


def test_every_known_secret_field_is_covered() -> None:
    secrets = {
        "key": "a",
        "token": "b",
        "api_key": "c",
        "master_key": "d",
        "password": "e",
        "aws_secret_access_key": "f",
        "vertex_credentials": "g",
        "client_secret": "h",
        "azure_ad_token": "i",
    }

    changes = diff_snapshots({}, secrets)

    assert all(change.after == "[redacted]" for change in changes)


def test_timestamps_are_hidden_because_they_move_on_every_write() -> None:
    before = {"max_budget": 1.0, "updated_at": "2026-09-01T00:00:00"}
    after = {"max_budget": 1.0, "updated_at": "2026-09-10T00:00:00"}

    # Nothing meaningful changed here; showing updated_at would imply otherwise.
    assert diff_snapshots(before, after) == []


def test_timestamps_can_be_asked_for_explicitly() -> None:
    before = {"updated_at": "2026-09-01T00:00:00"}
    after = {"updated_at": "2026-09-10T00:00:00"}

    assert _fields(diff_snapshots(before, after, include_noise=True)) == ["updated_at"]


def test_snapshots_stored_as_json_strings_are_read() -> None:
    # The write path json.dumps dicts before storing, so both shapes reach us.
    changes = diff_snapshots('{"max_budget": 1.0}', '{"max_budget": 5.0}')

    assert _fields(changes) == ["max_budget"]


def test_unparseable_snapshots_are_treated_as_empty_rather_than_raising() -> None:
    # A corrupt row must not break the whole audit page, and the readable side still shows.
    changes = diff_snapshots("not json at all", {"a": 1})

    assert _fields(changes) == ["a"]
    assert changes[0].before is None
    assert changes[0].after == "1"


def test_lists_and_dicts_render_on_one_line() -> None:
    changes = diff_snapshots({"models": ["a"]}, {"models": ["a", "b"]})

    assert changes[0].after == '["a", "b"]'


def test_identical_snapshots_produce_nothing() -> None:
    row = {"team_id": "t1", "max_budget": 1.0}

    assert diff_snapshots(row, dict(row)) == []


def test_summary_names_the_fields_that_moved() -> None:
    changes = diff_snapshots({}, {"a": 1, "b": 2})

    assert summarise(changes) == "a, b"


def test_summary_caps_the_list_so_a_table_cell_stays_readable() -> None:
    changes = diff_snapshots({}, {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})

    assert summarise(changes, limit=3) == "a, b, c and 2 more"


def test_summary_says_so_when_nothing_changed() -> None:
    assert summarise([]) == "no field changes"


def test_a_partial_update_reports_only_what_was_sent() -> None:
    # How the write path really stores an update: the whole row before, only the fields the
    # caller sent after. Comparing them as two snapshots claimed 17 fields were deleted.
    before = {
        "team_id": "t1",
        "max_budget": 1.0,
        "admins": [],
        "models": ["gpt-4o"],
        "blocked": False,
        "spend": 0.5,
    }
    after = {"team_id": "t1", "max_budget": 5.0}

    changes = diff_snapshots(before, after)

    assert _fields(changes) == ["max_budget"]
    assert changes[0].before == "1.0"
    assert changes[0].after == "5.0"


def test_untouched_fields_are_not_reported_as_deleted() -> None:
    before = {"a": 1, "b": 2, "c": 3}
    after = {"a": 9}

    changes = diff_snapshots(before, after)

    assert "b" not in _fields(changes)
    assert "c" not in _fields(changes)


def test_a_full_snapshot_still_reports_a_genuine_removal() -> None:
    # Not a subset, so this is a real before/after pair and the removal is real.
    before = {"a": 1, "b": 2}
    after = {"a": 1, "c": 3}

    changes = diff_snapshots(before, after)

    by_field = {c.field: c for c in changes}
    assert by_field["b"].after is None
    assert by_field["c"].before is None


def test_the_patch_guess_can_be_overridden() -> None:
    before = {"a": 1, "b": 2, "c": 3}
    after = {"a": 9}

    # Told explicitly that this is a full snapshot, the missing fields are removals again.
    changes = diff_snapshots(before, after, after_is_patch=False)

    assert _fields(changes) == ["a", "b", "c"]


def test_an_equal_key_set_is_not_treated_as_a_patch() -> None:
    # A strict subset only. Same keys on both sides is an ordinary comparison.
    changes = diff_snapshots({"a": 1, "b": 2}, {"a": 1, "b": 9})

    assert _fields(changes) == ["b"]
