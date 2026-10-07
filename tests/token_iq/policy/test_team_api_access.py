from __future__ import annotations

import pytest

from token_iq.policy.team_api_access import DEFAULT_API_ACCESS_MODE, assert_route_allowed

SHARED = "/v1/chat/completions"
PROVIDER = "/anthropic/v1/messages"


class TestBothIsTheDefaultAndRestrictsNothing:
    def test_the_default_is_both(self):
        """Every team that existed before this setting could use either address. A default
        that silently narrowed that would break them on upgrade."""
        assert DEFAULT_API_ACCESS_MODE == "both"

    @pytest.mark.parametrize("route", [SHARED, PROVIDER, "/openrouter/chat/completions", "/bedrock/model/x/converse"])
    def test_both_allows_every_model_address(self, route: str):
        assert_route_allowed(mode="both", route=route)


class TestCourierClosesTheSharedAddress:
    def test_the_shared_address_is_refused(self):
        """This is the promise a customer buys: in courier mode every request from the team
        is provably one this gateway never opened. Leaving the translating address open
        would make that a hope rather than a guarantee."""
        with pytest.raises(Exception, match=r"(?i)courier") as exc:
            assert_route_allowed(mode="courier", route=SHARED)

        message = str(exc.value).lower()
        assert "courier" in message
        assert "/anthropic" in message, "a refusal that does not say where to go leaves the caller guessing"

    @pytest.mark.parametrize("route", [PROVIDER, "/openrouter/chat/completions", "/bedrock/model/x/converse"])
    def test_provider_addresses_stay_open(self, route: str):
        assert_route_allowed(mode="courier", route=route)


class TestTranslatorClosesTheProviderAddresses:
    def test_a_provider_address_is_refused(self):
        with pytest.raises(Exception, match=r"(?i)translating") as exc:
            assert_route_allowed(mode="translator", route=PROVIDER)

        message = str(exc.value).lower()
        assert "translating" in message
        assert "/v1/chat/completions" in message

    def test_the_shared_address_stays_open(self):
        assert_route_allowed(mode="translator", route=SHARED)


class TestOnlyModelRequestsAreGated:
    """The bug this class exists for: the first version refused everything that was not a
    provider address, so a courier team's own keys got 403 on /team/info, /key/info and
    /models. Proven against a live proxy before it was fixed. Which way a team writes its
    model requests says nothing about whether it may read its own key."""

    @pytest.mark.parametrize(
        "route",
        ["/team/info", "/key/info", "/models", "/user/info", "/health", "/key/generate", "/v1/models"],
    )
    @pytest.mark.parametrize("mode", ["courier", "translator"])
    def test_management_and_info_addresses_are_never_closed(self, mode: str, route: str):
        assert_route_allowed(mode=mode, route=route)  # pyright: ignore[reportArgumentType]  # parametrized literal


class TestTheRefusalNamesTheWayOut:
    def test_courier_refusal_names_the_route_that_was_refused(self):
        with pytest.raises(Exception, match="/v1/embeddings") as exc:
            assert_route_allowed(mode="courier", route="/v1/embeddings")

        assert "/v1/embeddings" in str(exc.value)
