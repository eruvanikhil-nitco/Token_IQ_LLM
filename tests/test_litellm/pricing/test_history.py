"""Price history: what a model cost on a given day, not what it costs now.

Without this, re-running a closed month values it at today's prices and nobody can tell,
because the figure still looks like a figure.
"""

from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal
from typing import Final

import pytest

from litellm.pricing.history import PriceChange, PriceHistory, parse_history


def _history(*lines: str) -> PriceHistory:
    return PriceHistory.from_lines(lines)


CHANGE: Final = (
    '{"model":"gpt-4o","provider":"openai","field":"input_cost_per_token",'
    '"old":"0.0000025","new":"0.0000020","effective_from":"2026-06-01",'
    '"source":"upstream abc123","approved_by":"ne"}'
)


class TestLookup:
    def test_returns_the_price_in_effect_on_the_day_asked_about(self) -> None:
        history: Final = _history(CHANGE)
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 7, 1)) == Decimal("0.0000020")

    def test_a_day_before_the_change_gets_the_old_price(self) -> None:
        """The reason this exists. Last quarter must not be valued at this quarter's prices."""
        history: Final = _history(CHANGE)
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 5, 31)) == Decimal("0.0000025")

    def test_the_day_of_the_change_uses_the_new_price(self) -> None:
        history: Final = _history(CHANGE)
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 6, 1)) == Decimal("0.0000020")

    def test_two_changes_give_three_distinct_periods(self) -> None:
        second: Final = (
            '{"model":"gpt-4o","provider":"openai","field":"input_cost_per_token",'
            '"old":"0.0000020","new":"0.0000015","effective_from":"2026-08-01",'
            '"source":"upstream def456","approved_by":"ne"}'
        )
        history: Final = _history(CHANGE, second)
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 5, 1)) == Decimal("0.0000025")
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 7, 1)) == Decimal("0.0000020")
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 9, 1)) == Decimal("0.0000015")

    def test_lines_out_of_order_still_resolve_correctly(self) -> None:
        """The file is appended to by a job, so date order is a hope rather than a guarantee."""
        second: Final = (
            '{"model":"gpt-4o","provider":"openai","field":"input_cost_per_token",'
            '"old":"0.0000020","new":"0.0000015","effective_from":"2026-08-01",'
            '"source":"x","approved_by":"ne"}'
        )
        assert _history(second, CHANGE).price_on(
            "gpt-4o", "input_cost_per_token", date(2026, 7, 1)
        ) == Decimal("0.0000020")

    def test_a_model_with_no_history_returns_nothing_rather_than_guessing(self) -> None:
        """The caller falls back to the current price. This must not invent one."""
        assert _history(CHANGE).price_on("claude-opus-4", "input_cost_per_token", date(2026, 7, 1)) is None

    def test_a_field_with_no_history_is_independent_of_one_that_has_it(self) -> None:
        history: Final = _history(CHANGE)
        assert history.price_on("gpt-4o", "output_cost_per_token", date(2026, 7, 1)) is None

    def test_history_for_one_field_does_not_leak_into_another(self) -> None:
        output: Final = (
            '{"model":"gpt-4o","provider":"openai","field":"output_cost_per_token",'
            '"old":"0.00001","new":"0.000008","effective_from":"2026-06-01",'
            '"source":"x","approved_by":"ne"}'
        )
        history: Final = _history(CHANGE, output)
        assert history.price_on("gpt-4o", "input_cost_per_token", date(2026, 7, 1)) == Decimal("0.0000020")
        assert history.price_on("gpt-4o", "output_cost_per_token", date(2026, 7, 1)) == Decimal("0.000008")


class TestExactness:
    def test_a_price_never_passes_through_a_binary_float(self) -> None:
        """A price that cannot survive a float round trip must still come back exactly."""
        line: Final = (
            '{"model":"m","provider":"p","field":"input_cost_per_token",'
            '"old":"0.1","new":"0.30000000000000004","effective_from":"2026-01-01",'
            '"source":"x","approved_by":"ne"}'
        )
        got: Final = _history(line).price_on("m", "input_cost_per_token", date(2026, 2, 1))
        assert got == Decimal("0.30000000000000004")
        assert str(got) == "0.30000000000000004"


class TestParsing:
    def test_blank_lines_and_comments_are_ignored(self) -> None:
        assert len(parse_history(["", "   ", CHANGE])) == 1

    def test_a_malformed_line_is_rejected_loudly(self) -> None:
        """A silently skipped line is a price change that quietly never happened."""
        with pytest.raises(ValueError):
            parse_history(["{not json"])

    def test_a_line_missing_a_required_field_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            parse_history(['{"model":"m","field":"input_cost_per_token","new":"1"}'])

    def test_a_change_round_trips_through_its_own_serialisation(self) -> None:
        change: Final = PriceChange(
            model="m",
            provider="p",
            field="input_cost_per_token",
            old=Decimal("0.1"),
            new=Decimal("0.2"),
            effective_from=date(2026, 1, 1),
            source="upstream abc",
            approved_by="ne",
        )
        assert parse_history([change.as_line()])[0] == change


class TestTheShippedFile:
    def test_the_history_file_exists_and_parses(self) -> None:
        """It ships with the code, so a corrupt line is a build-time problem, not a runtime one."""
        from litellm.pricing.history import HISTORY_PATH, load_history

        assert HISTORY_PATH.is_file(), f"{HISTORY_PATH} is missing"
        load_history()

    def test_it_lives_beside_the_prices_it_describes(self) -> None:
        from litellm.pricing.history import HISTORY_PATH

        assert HISTORY_PATH.parent == pathlib.Path(
            "data/pricing"
        ).resolve() or HISTORY_PATH.parent.name == "pricing"


class TestPriceAsOf:
    """The caller-facing lookup: history when it knows, the current list otherwise."""


    def test_history_wins_for_a_date_it_covers(self) -> None:
        """The recorded value is deliberately one the current list cannot also produce.

        An earlier version of this test used gpt-4o's real present-day price, so it passed
        whether the lookup consulted history or fell straight through to the price list.
        """
        from litellm.pricing.history import PriceHistory, price_as_of

        history = PriceHistory.from_lines(
            [
                '{"model":"gpt-4o","provider":"openai","field":"input_cost_per_token",'
                '"old":"0.00000777777","new":"0.00000888888","effective_from":"2026-06-01",'
                '"source":"x","approved_by":"ne"}'
            ]
        )
        got = price_as_of("gpt-4o", "input_cost_per_token", date(2026, 5, 1), history=history)
        assert got == Decimal("0.00000777777")

    def test_a_known_model_missing_the_field_resolves_to_nothing_rather_than_zero(self) -> None:
        """gpt-4o is priced, but not for a field that does not exist. Zero would read as free."""
        from litellm.pricing.history import PriceHistory, price_as_of

        got = price_as_of("gpt-4o", "cost_per_unicorn", date(2026, 5, 1), history=PriceHistory(()))
        assert got is None

    def test_falls_back_to_the_current_list_when_history_is_silent(self) -> None:
        from litellm.pricing.history import PriceHistory, price_as_of

        empty = PriceHistory(changes=())
        got = price_as_of("gpt-4o", "input_cost_per_token", date(2026, 5, 1), history=empty)
        assert got is not None and got > 0, "the bundled list prices gpt-4o, so this must resolve"

    def test_an_unknown_model_resolves_to_nothing_rather_than_zero(self) -> None:
        """Zero would turn a real cost into free usage, and nothing downstream could tell."""
        from litellm.pricing.history import PriceHistory, price_as_of

        got = price_as_of("not-a-real-model", "input_cost_per_token", date(2026, 5, 1), history=PriceHistory(()))
        assert got is None
