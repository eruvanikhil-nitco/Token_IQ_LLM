"""Decide whether a request's prompt and response are kept in the spend log.

Capture is a trade in two directions. Bodies are effectively the entire size of the spend log
table, and they hold what people actually typed, so keeping everything is expensive and
sometimes inappropriate. Keeping nothing means an observer gateway that records no traffic.

A single global switch forces one answer for the whole gateway, so it tends to be left off.
This resolves the question per request instead:

    team override  ->  provider override  ->  global default  ->  off

Team wins because that is how these rules actually get written. Nobody says "do not log
Bedrock traffic"; they say "do not retain HR's conversations". The rule follows the people, so
the people-shaped setting is the one that decides.

Provider sits underneath for the volume case: one cheap chatty model can dominate the table
even when nothing about it is sensitive.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

GLOBAL_KEY: Final = "store_prompts_in_spend_logs"
BY_TEAM_KEY: Final = "store_prompts_by_team"
BY_PROVIDER_KEY: Final = "store_prompts_by_provider"


def _as_bool(value: object) -> bool | None:
    """Read a setting that may arrive as a bool or as a string from YAML or the database.

    None means "not configured", which is different from False and must stay distinguishable:
    an unset team falls through to the provider rule, a team set to false does not.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered: Final = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    return None


def _lookup(settings: Mapping[str, object], key: str, subject: str | None) -> bool | None:
    """The override for one team or provider, or None when nothing is configured for it."""
    if not subject:
        return None
    table: Final = settings.get(key)
    if not isinstance(table, Mapping):
        return None
    return _as_bool(table.get(subject))


def should_capture(
    settings: Mapping[str, object],
    team_id: str | None = None,
    team_alias: str | None = None,
    provider: str | None = None,
    env_default: bool | None = None,
) -> bool:
    """Whether to store the prompt and response for this request.

    `team_alias` is accepted alongside `team_id` so the setting can be written against the
    readable name people know rather than a uuid nobody can check at a glance. An id entry
    wins over an alias entry, since it is the unambiguous one.
    """
    by_team: Final = _lookup(settings, BY_TEAM_KEY, team_id)
    if by_team is not None:
        return by_team

    by_alias: Final = _lookup(settings, BY_TEAM_KEY, team_alias)
    if by_alias is not None:
        return by_alias

    by_provider: Final = _lookup(settings, BY_PROVIDER_KEY, provider)
    if by_provider is not None:
        return by_provider

    # The legacy global key keeps its original semantics: only an explicit true short
    # circuits, and anything else falls through to the environment variable. Upstream tests
    # pin that, and quietly making config-false authoritative here would change behaviour for
    # every deployment that relies on the env var as an override.
    #
    # The team and provider rules above are deliberately not like that. They are new, they
    # name a specific subject, and a rule that says "never capture this team" has to mean it.
    global_setting: Final = _as_bool(settings.get(GLOBAL_KEY))
    if global_setting is True:
        return True

    return env_default is True
