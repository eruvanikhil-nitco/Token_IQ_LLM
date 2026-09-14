import pytest

from litellm.proxy.auth.token_iq_plan import (
    PLAN_ENV,
    PLANS,
    KnownPlan,
    TokenIqPlan,
    UnknownPlan,
    lookup_plan,
    require_plan,
)


def test_an_installation_with_no_plan_configured_runs_on_the_standard_plan():
    assert lookup_plan({}) == KnownPlan(PLANS["standard"])


def test_a_blank_plan_setting_is_treated_as_unset():
    assert lookup_plan({PLAN_ENV: "   "}) == KnownPlan(PLANS["standard"])


def test_a_configured_plan_name_is_honoured_despite_surrounding_whitespace():
    assert lookup_plan({PLAN_ENV: "  standard "}) == KnownPlan(PLANS["standard"])


def test_the_standard_plan_unlocks_gated_features_and_caps_nothing():
    standard = PLANS["standard"]
    assert standard.unlocks_gated_features is True
    assert standard.is_over_user_limit(total_users=1_000_000) is False
    assert standard.is_over_team_limit(team_count=1_000_000) is False


def test_an_unknown_plan_is_reported_rather_than_guessed():
    assert lookup_plan({PLAN_ENV: "enterprize"}) == UnknownPlan(requested="enterprize")


def test_a_misspelt_plan_stops_startup_and_names_the_real_plans():
    with pytest.raises(ValueError, match=r"enterprize.*standard"):
        require_plan({PLAN_ENV: "enterprize"})


@pytest.mark.parametrize(("total_users", "over"), [(2, False), (3, True)])
def test_a_user_cap_refuses_only_beyond_the_cap(total_users, over):
    capped = TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=2, max_teams=None)
    assert capped.is_over_user_limit(total_users=total_users) is over


@pytest.mark.parametrize(("team_count", "over"), [(5, False), (6, True)])
def test_a_team_cap_refuses_only_beyond_the_cap(team_count, over):
    capped = TokenIqPlan(name="capped", unlocks_gated_features=True, max_users=None, max_teams=5)
    assert capped.is_over_team_limit(team_count=team_count) is over
