"""What this build reads from each user tool, in the words the What We Fetch tab shows.

Deliberately modest, like the provider profiles it mirrors: every line describes behaviour
that exists in this repository today. None of these connectors has run against a real account,
so anything stated here as verified would read as a promise the first customer could disprove.

The most important line on this screen is the one saying what a tool cannot tell us. A
customer who reads that Copilot reports no cost, or that Claude Code on an API account is
already on their Anthropic bill, will not spend a week wondering why the numbers look the way
they do.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

_NO_BACKFILL: Final = (
    "Each run re-reads the most recent window. There is no first-connection backfill yet, so "
    "usage from before this connection was made is not loaded."
)

_UNVERIFIED: Final = (
    "This connector has never run against a real account, because none is available to this "
    "project yet. It is written to the vendor's published API and tested against their own "
    "documented responses, which settles everything except whether their real responses match."
)


@dataclass(frozen=True, slots=True)
class ToolFetchProfile:
    tool: str
    display_name: str
    endpoint: str
    endpoint_url: str
    what_it_gives: str
    what_it_cannot_give: str
    backfill_note: str
    verification_note: str


CLAUDE_CODE: Final = ToolFetchProfile(
    tool="claude_code",
    display_name="Claude Code",
    endpoint="Claude Code Usage Report",
    endpoint_url="https://api.anthropic.com/v1/organizations/usage_report/claude_code",
    what_it_gives=(
        "Per person per day, an estimated cost and token count for each model they used, keyed by their email address."
    ),
    what_it_cannot_give=(
        "When Claude Code is billed to your Anthropic API organisation, that money is already "
        "on the Anthropic bill this product reads, so it is shown here to say who spent it and "
        "is deliberately left out of totals. Only usage on a Pro, Team or Enterprise plan is "
        "counted as spend of its own."
    ),
    backfill_note=_NO_BACKFILL,
    verification_note=_UNVERIFIED,
)

CURSOR: Final = ToolFetchProfile(
    tool="cursor",
    display_name="Cursor",
    endpoint="Team Usage Events",
    endpoint_url="https://api.cursor.com/teams/filtered-usage-events",
    what_it_gives=(
        "One row per request, with the person's email, the model and what Cursor charged, "
        "rolled up here into a daily figure per person and model."
    ),
    what_it_cannot_give=(
        "Cursor buys the models itself and bills you, so none of this appears on a provider "
        "bill and all of it counts as spend of its own."
    ),
    backfill_note=_NO_BACKFILL,
    verification_note=_UNVERIFIED,
)

COPILOT: Final = ToolFetchProfile(
    tool="copilot",
    display_name="GitHub Copilot",
    endpoint="Copilot Billing Seats",
    endpoint_url="https://api.github.com/orgs/{org}/copilot/billing/seats",
    what_it_gives=("Who holds a licence, when it was assigned, when they were last active and which plan it is on."),
    what_it_cannot_give=(
        "No cost at all. GitHub does not publish what a seat costs, because the price is on "
        "your contract, so the figure is set once here rather than guessed. Last activity is "
        "also empty unless that person turned telemetry on in their editor, so an empty value "
        "is not evidence a licence is unused."
    ),
    backfill_note="Seats are read as they stand now rather than as a history.",
    verification_note=_UNVERIFIED,
)

TOOL_FETCH_PROFILES: Final[Mapping[str, ToolFetchProfile]] = MappingProxyType(
    {profile.tool: profile for profile in (CLAUDE_CODE, CURSOR, COPILOT)}
)
