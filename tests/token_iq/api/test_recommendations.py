from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from fastapi import HTTPException

from token_iq.gateway.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from token_iq.api.recommendations import recommendations_response
from token_iq.types.recommendation import Evidence, Recommendation

START: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
END: Final = datetime(2026, 9, 30, tzinfo=timezone.utc)
MEMBER: Final = UserAPIKeyAuth(user_role=LitellmUserRoles.INTERNAL_USER, api_key="sk-test", user_id="u-1")

ESCAPED: Final = Recommendation(
    rule_id="escaped_spend",
    kind="business",
    title="Spend is reaching a provider without passing through the gateway",
    noticed="This money is already being spent.",
    evidence=(Evidence(label="Unclaimed difference", value="0.00774700"),),
    figure=Decimal("0.00774700"),
    figure_kind="already_spent_unwatched",
    currency="USD",
    who_should_act="an admin",
)

CONCENTRATION: Final = Recommendation(
    rule_id="provider_concentration",
    kind="business",
    title="Almost all provider spend goes through one provider",
    noticed="This is a risk rather than a cost.",
    evidence=(Evidence(label="Largest provider", value="openrouter"),),
    figure=None,
    figure_kind="none",
    currency=None,
    who_should_act="an admin",
)


def _body(cards, states):
    return recommendations_response(period_start=START, period_end=END, cards=cards, states=states)


def test_every_amount_crosses_as_a_string() -> None:
    body: Final = _body((ESCAPED,), {})
    assert body.open[0].figure == "0.00774700"
    assert isinstance(body.open[0].figure, str)


def test_a_card_with_no_figure_sends_null_rather_than_zero() -> None:
    body: Final = _body((CONCENTRATION,), {})
    assert body.open[0].figure is None
    assert body.open[0].figure_kind == "none"
    assert body.open[0].currency is None


def test_the_figure_kind_travels_so_a_screen_cannot_call_it_a_saving() -> None:
    body: Final = _body((ESCAPED,), {})
    assert body.open[0].figure_kind == "already_spent_unwatched"


def test_a_dismissed_card_leaves_the_open_list_but_is_still_reported() -> None:
    body: Final = _body((ESCAPED,), {"escaped_spend": "dismissed"})
    assert body.open == ()
    assert body.decided[0].rule_id == "escaped_spend"
    assert body.decided[0].state == "dismissed"


def test_a_card_marked_done_is_reported_as_done_not_dismissed() -> None:
    body: Final = _body((ESCAPED,), {"escaped_spend": "done"})
    assert body.decided[0].state == "done"


def test_a_decision_about_another_card_does_not_hide_this_one() -> None:
    body: Final = _body((ESCAPED, CONCENTRATION), {"escaped_spend": "dismissed"})
    assert tuple(c.rule_id for c in body.open) == ("provider_concentration",)
    assert tuple(c.rule_id for c in body.decided) == ("escaped_spend",)


def test_the_evidence_survives_into_the_response() -> None:
    body: Final = _body((ESCAPED,), {})
    assert body.open[0].evidence[0].value == "0.00774700"


def test_the_period_is_reported_back_so_a_reader_knows_what_was_examined() -> None:
    body: Final = _body((ESCAPED,), {})
    assert body.period_start == "2026-09-01"
    assert body.period_end == "2026-09-30"


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_cross_team_recommendations() -> None:
    from token_iq.api.recommendations import recommendations

    with pytest.raises(HTTPException) as caught:
        await recommendations(period_start="2026-09-01", period_end="2026-09-30", user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_non_admin_cannot_dismiss_a_card() -> None:
    from token_iq.api.recommendations import decide_recommendation
    from token_iq.api.types.recommendations import DecisionBody

    with pytest.raises(HTTPException) as caught:
        await decide_recommendation(
            rule_id="escaped_spend", body=DecisionBody(state="dismissed"), user_api_key_dict=MEMBER
        )
    assert caught.value.status_code == 403


def test_a_decision_we_do_not_recognise_is_refused_by_validation() -> None:
    from pydantic import ValidationError

    from token_iq.api.types.recommendations import DecisionBody

    with pytest.raises(ValidationError):
        DecisionBody(state="maybe")  # pyright: ignore[reportArgumentType]  # the point of the test
