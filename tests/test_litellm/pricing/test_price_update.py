"""Classifying what upstream changed, so the right things merge and the rest get read.

Every case runs against fixtures rather than a live fetch, so the tests say what the rules
are instead of what upstream published today.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from scripts.update_model_prices import FLAG_IN_USE, FLAG_LARGE, FLAG_TO_ZERO, classify, history_lines

BASE: Final = {
    "gpt-4o": {"litellm_provider": "openai", "input_cost_per_token": 0.0000025},
    "claude-opus-4": {"litellm_provider": "anthropic", "input_cost_per_token": 0.000015},
}


class TestClassification:
    def test_a_new_model_is_an_addition(self) -> None:
        upstream: Final = {**BASE, "gpt-5": {"litellm_provider": "openai", "input_cost_per_token": 0.000001}}
        diff: Final = classify(current=BASE, upstream=upstream)
        assert [a.model for a in diff.additions] == ["gpt-5"]
        assert diff.changes == () and diff.removals == ()

    def test_a_moved_price_is_a_change(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.000003}}
        diff: Final = classify(current=BASE, upstream=upstream)
        assert len(diff.changes) == 1
        assert (diff.changes[0].model, diff.changes[0].field) == ("gpt-4o", "input_cost_per_token")
        assert diff.changes[0].old == Decimal("0.0000025")
        assert diff.changes[0].new == Decimal("0.000003")

    def test_a_model_gone_from_upstream_is_a_removal(self) -> None:
        upstream: Final = {k: v for k, v in BASE.items() if k != "claude-opus-4"}
        diff: Final = classify(current=BASE, upstream=upstream)
        assert [r.model for r in diff.removals] == ["claude-opus-4"]

    def test_an_unchanged_file_produces_nothing(self) -> None:
        diff: Final = classify(current=BASE, upstream=dict(BASE))
        assert (diff.additions, diff.changes, diff.removals) == ((), (), ())

    def test_a_new_field_on_an_existing_model_is_a_change_not_an_addition(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "output_cost_per_token": 0.00001}}
        diff: Final = classify(current=BASE, upstream=upstream)
        assert diff.additions == ()
        assert [c.field for c in diff.changes] == ["output_cost_per_token"]

    def test_a_numeric_non_price_field_is_ignored(self) -> None:
        """Only money moves need a reviewer. A context window is a number too, so this case
        has to use one: a string field is filtered out by the decimal conversion anyway and
        would pass even with the price-field rule removed."""
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "max_input_tokens": 128000}}
        assert classify(current=BASE, upstream=upstream).changes == ()


class TestFlags:
    def test_a_change_over_fifty_percent_is_flagged(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.000004}}
        assert FLAG_LARGE in classify(current=BASE, upstream=upstream).changes[0].flags

    def test_a_change_under_fifty_percent_is_not_flagged_as_large(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.000003}}
        assert FLAG_LARGE not in classify(current=BASE, upstream=upstream).changes[0].flags

    def test_a_change_to_zero_is_always_flagged(self) -> None:
        """A price of zero turns every future call on that model into free usage."""
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0}}
        flags: Final = classify(current=BASE, upstream=upstream).changes[0].flags
        assert FLAG_TO_ZERO in flags

    def test_a_model_seen_in_production_is_flagged_however_small_the_change(self) -> None:
        """A 1% move on a model nobody uses can merge. The same move on a model in traffic
        changes a real bill, so somebody reads it."""
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.00000251}}
        diff: Final = classify(current=BASE, upstream=upstream, in_use=frozenset({"gpt-4o"}))
        assert FLAG_IN_USE in diff.changes[0].flags

    def test_a_model_not_in_production_carries_no_in_use_flag(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.00000251}}
        diff: Final = classify(current=BASE, upstream=upstream, in_use=frozenset({"claude-opus-4"}))
        assert FLAG_IN_USE not in diff.changes[0].flags


class TestAutoMerge:
    def test_additions_alone_can_merge_themselves(self) -> None:
        upstream: Final = {**BASE, "gpt-5": {"litellm_provider": "openai", "input_cost_per_token": 0.000001}}
        assert classify(current=BASE, upstream=upstream).can_auto_merge

    def test_nothing_at_all_can_merge(self) -> None:
        assert classify(current=BASE, upstream=dict(BASE)).can_auto_merge

    def test_any_change_blocks_auto_merge(self) -> None:
        """A changed price is somebody's bill moving. It is read before it lands."""
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.0000026}}
        assert not classify(current=BASE, upstream=upstream).can_auto_merge

    def test_a_removal_blocks_auto_merge(self) -> None:
        upstream: Final = {k: v for k, v in BASE.items() if k != "gpt-4o"}
        assert not classify(current=BASE, upstream=upstream).can_auto_merge


class TestRemovalsNeverDelete:
    def test_a_removal_is_proposed_as_retired_not_deleted(self) -> None:
        """A model retired upstream still has to price the months it was in use."""
        upstream: Final = {k: v for k, v in BASE.items() if k != "gpt-4o"}
        removal: Final = classify(current=BASE, upstream=upstream).removals[0]
        assert removal.action == "retire"
        assert removal.action != "delete"


class TestHistoryLines:
    def test_every_change_becomes_one_history_line(self) -> None:
        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.000003}}
        diff: Final = classify(current=BASE, upstream=upstream)
        lines: Final = history_lines(diff, effective_from="2026-10-05", source="upstream abc123", approved_by="ne")
        assert len(lines) == 1
        assert '"old": "0.0000025"' in lines[0] and '"new": "0.000003"' in lines[0]

    def test_an_addition_writes_no_history_line(self) -> None:
        """History records a price that moved. A model that did not exist has no old price."""
        upstream: Final = {**BASE, "gpt-5": {"litellm_provider": "openai", "input_cost_per_token": 0.000001}}
        diff: Final = classify(current=BASE, upstream=upstream)
        assert history_lines(diff, effective_from="2026-10-05", source="x", approved_by="ne") == ()

    def test_the_lines_parse_back_as_price_changes(self) -> None:
        from litellm.pricing.history import parse_history

        upstream: Final = {**BASE, "gpt-4o": {**BASE["gpt-4o"], "input_cost_per_token": 0.000003}}
        diff: Final = classify(current=BASE, upstream=upstream)
        lines: Final = history_lines(diff, effective_from="2026-10-05", source="x", approved_by="ne")
        parsed: Final = parse_history(lines)
        assert parsed[0].model == "gpt-4o"
        assert parsed[0].new == Decimal("0.000003")


class TestSchemaValidation:
    def test_upstream_that_is_not_an_object_is_refused(self) -> None:
        with pytest.raises(ValueError):
            classify(current=BASE, upstream=["not", "a", "mapping"])  # pyright: ignore[reportArgumentType]  # the point of the test

    def test_a_suspiciously_small_upstream_file_is_refused(self) -> None:
        """Upstream shipping two models where there were thousands is a broken fetch, not a
        price change, and merging it would silently unprice most of the product."""
        with pytest.raises(ValueError):
            classify(current={f"m{i}": {"input_cost_per_token": 1} for i in range(1000)}, upstream=BASE)
