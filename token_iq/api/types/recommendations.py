"""Request and response shapes for the recommendations screen.

`figure` and `figure_kind` travel together all the way to the browser. A screen that received
only a number would have no way to know whether it may write "saving" beside it, and the one
mistake this whole feature exists to avoid is exactly that.
"""

from __future__ import annotations

from pydantic import BaseModel

from token_iq.repositories.recommendation_state_repository import DecisionState
from token_iq.types.recommendation import FigureKind, RecommendationKind


class EvidenceResponse(BaseModel):
    label: str
    value: str


class RecommendationResponse(BaseModel):
    rule_id: str
    kind: RecommendationKind
    title: str
    noticed: str
    evidence: tuple[EvidenceResponse, ...]
    figure: str | None
    figure_kind: FigureKind
    currency: str | None
    who_should_act: str
    state: DecisionState | None


class RecommendationsResponse(BaseModel):
    period_start: str
    period_end: str
    open: tuple[RecommendationResponse, ...]
    decided: tuple[RecommendationResponse, ...]


class DecisionBody(BaseModel):
    state: DecisionState
    note: str | None = None


class DecisionResponse(BaseModel):
    rule_id: str
    state: DecisionState | None
