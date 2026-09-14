"""Which gated features an installation may use, decided by its Token IQ plan."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

PLAN_ENV: Final = "TOKEN_IQ_PLAN"
DEFAULT_PLAN_NAME: Final = "standard"


@dataclass(frozen=True, slots=True)
class TokenIqPlan:
    name: str
    unlocks_gated_features: bool
    max_users: int | None
    max_teams: int | None

    def is_over_user_limit(self, total_users: int) -> bool:
        return self.max_users is not None and total_users > self.max_users

    def is_over_team_limit(self, team_count: int) -> bool:
        return self.max_teams is not None and team_count > self.max_teams


PLANS: Final[Mapping[str, TokenIqPlan]] = MappingProxyType(
    {
        "standard": TokenIqPlan(name="standard", unlocks_gated_features=True, max_users=None, max_teams=None),
    }
)


@dataclass(frozen=True, slots=True)
class KnownPlan:
    plan: TokenIqPlan


@dataclass(frozen=True, slots=True)
class UnknownPlan:
    requested: str


def lookup_plan(environ: Mapping[str, str]) -> KnownPlan | UnknownPlan:
    requested: Final = environ.get(PLAN_ENV, "").strip() or DEFAULT_PLAN_NAME
    plan: Final = PLANS.get(requested)
    return KnownPlan(plan) if plan is not None else UnknownPlan(requested)


def require_plan(environ: Mapping[str, str]) -> TokenIqPlan:
    """The installation's plan, or a startup failure naming the plans that exist."""
    match lookup_plan(environ):
        case KnownPlan(plan=plan):
            return plan
        case UnknownPlan(requested=requested):
            raise ValueError(
                f"{PLAN_ENV}={requested!r} is not a Token IQ plan. Known plans: {', '.join(sorted(PLANS))}"
            )
