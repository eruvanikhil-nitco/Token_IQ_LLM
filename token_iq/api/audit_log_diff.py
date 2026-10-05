"""Turn an audit row's before and after snapshots into the list of fields that changed.

`LiteLLM_AuditLog` stores whole rows on either side of a change. That is the right thing to
store, because it can answer questions nobody thought to ask yet, but it is the wrong thing to
show: a team update writes forty fields of which one moved.

Reading a diff is what makes an audit trail useful. "max_budget 1.0 -> 5.0" answers the
question; two forty-field JSON blobs make the reader do the work.

Pure: snapshots come in as arguments, so this is exercised without a database.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, Field

# Never surface these, whatever a caller asks for. The write path already masks the key it
# returns, but a row written by an older build, or a field added upstream later, should not
# become a way to read secrets out of the audit trail.
_REDACTED_FIELDS: Final = frozenset(
    {
        "key",
        "token",
        "api_key",
        "master_key",
        "password",
        "hashed_password",
        "aws_secret_access_key",
        "vertex_credentials",
        "client_secret",
        "azure_ad_token",
    }
)

_REDACTED_PLACEHOLDER: Final = "[redacted]"

# Fields that change on every write and say nothing about intent. Showing them buries the one
# field the operator actually changed.
_NOISE_FIELDS: Final = frozenset({"updated_at", "created_at", "updated_by", "created_by"})


class FieldChange(BaseModel):
    """One field that differs between the two snapshots."""

    field: str
    before: str | None = Field(default=None, description="Value before the change, rendered for display")
    after: str | None = Field(default=None, description="Value after the change, rendered for display")


def _render(value: object) -> str:
    """A single-line rendering of a value, short enough to sit in a table cell."""
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return str(value)
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _as_mapping(snapshot: object) -> Mapping[str, object]:
    """Snapshots are stored as JSON and can arrive as a dict or as a JSON string."""
    if isinstance(snapshot, Mapping):
        return snapshot
    if isinstance(snapshot, str) and snapshot.strip():
        try:
            parsed: Final = json.loads(snapshot)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _display(field: str, value: object) -> str:
    return _REDACTED_PLACEHOLDER if field in _REDACTED_FIELDS else _render(value)


def diff_snapshots(
    before: object,
    after: object,
    include_noise: bool = False,
    after_is_patch: bool | None = None,
) -> list[FieldChange]:
    """Fields that differ between two row snapshots, sorted by name.

    A creation has no before, so every field reads as newly set; a deletion has no after, so
    every field reads as removed. Both fall out of the same comparison.

    An update is not symmetric. The write path stores the whole row in `before_value` but only
    the fields the caller actually sent in `updated_values`, so a team update records 19 fields
    before and 2 after. Comparing those as two snapshots reports 17 fields deleted, which is
    both wrong and drowns the one field that moved. When `after` is a strict subset of `before`
    it is treated as a patch and only its own fields are compared. Pass `after_is_patch`
    explicitly to override the guess.
    """
    before_map: Final = _as_mapping(before)
    after_map: Final = _as_mapping(after)

    is_patch: Final = (
        after_is_patch
        if after_is_patch is not None
        else bool(before_map) and bool(after_map) and set(after_map) < set(before_map)
    )
    fields: Final = sorted(after_map) if is_patch else sorted(set(before_map) | set(after_map))

    return [
        FieldChange(
            field=field,
            before=None if field not in before_map else _display(field, before_map[field]),
            after=None if field not in after_map else _display(field, after_map[field]),
        )
        for field in fields
        if (include_noise or field not in _NOISE_FIELDS) and before_map.get(field) != after_map.get(field)
    ]


def summarise(changes: list[FieldChange], limit: int = 3) -> str:
    """A one-line summary for a table row, naming the first few fields that moved."""
    if not changes:
        return "no field changes"
    names: Final = [change.field for change in changes[:limit]]
    remainder: Final = len(changes) - len(names)
    listed: Final = ", ".join(names)
    return listed if remainder <= 0 else f"{listed} and {remainder} more"
