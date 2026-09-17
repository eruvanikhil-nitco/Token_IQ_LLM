from __future__ import annotations

from decimal import Decimal

from litellm.types.proxy.provider_billing import SummaryRow, TokenTotals

TOKENS = TokenTotals(input_tokens=100, output_tokens=20, cached_input_tokens=5, cache_write_tokens=2)


def _row(model, account="prod", evidence="reconciled", cost="1", facts=1) -> SummaryRow:
    return SummaryRow(
        model=model,
        credential_name=account,
        evidence=evidence,
        billed_cost=Decimal(cost),
        facts=facts,
    )


def test_spend_by_model_is_summed_across_accounts_and_ordered_by_cost():
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", "prod", cost="2"), _row("gpt-4o", "staging", cost="3"), _row("o3", cost="4")),
        TOKENS,
    )

    assert [(m.model, m.billed_cost) for m in summary.by_model] == [
        ("gpt-4o", Decimal("5")),
        ("o3", Decimal("4")),
    ]


def test_spend_by_account_is_summed_across_models():
    """A company running two accounts needs to see which one is spending, which is the
    whole reason several accounts per provider are read separately."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", "prod", cost="2"), _row("o3", "prod", cost="3"), _row("o3", "staging", cost="1")),
        TOKENS,
    )

    assert [(a.credential_name, a.billed_cost) for a in summary.by_account] == [
        ("prod", Decimal("5")),
        ("staging", Decimal("1")),
    ]


def test_a_row_with_no_model_is_kept_and_labelled_rather_than_dropped():
    """Web search and code execution charges carry no model. Dropping them would make the
    breakdown add up to less than the bill."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary((_row(None, cost="7"),), TOKENS)

    assert summary.by_model[0].model is None
    assert summary.total_cost == Decimal("7")


def test_the_total_equals_the_sum_of_the_parts():
    """If the headline figure and the breakdown disagree, a reader cannot trust either."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", cost="2"), _row("o3", cost="3"), _row(None, cost="1")), TOKENS
    )

    assert summary.total_cost == Decimal("6")
    assert sum(m.billed_cost for m in summary.by_model) == summary.total_cost
    assert sum(a.billed_cost for a in summary.by_account) == summary.total_cost


def test_evidence_is_split_so_a_reader_knows_what_the_provider_actually_asserted():
    """reconciled means the provider asserted dollars. allocated means only our own gateway
    events exist. Showing one number for both would overstate how much of this is confirmed."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", evidence="reconciled", cost="4"), _row("o3", evidence="allocated", cost="1")),
        TOKENS,
    )

    assert summary.by_evidence["reconciled"] == Decimal("4")
    assert summary.by_evidence["allocated"] == Decimal("1")


def test_an_empty_window_summarises_to_zero_rather_than_failing():
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary((), TokenTotals(0, 0, 0, 0))

    assert summary.total_cost == Decimal(0)
    assert summary.by_model == ()
    assert summary.facts == 0


def test_models_tied_on_cost_break_the_tie_by_name_so_order_is_stable_across_runs():
    """Set iteration order is not stable across process runs. Two models at the exact same
    cost must still come out in the same order every time, or a spend ranking would appear
    to reshuffle itself between page loads with no data having changed."""
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("zeta", cost="3"), _row("alpha", cost="3"), _row(None, cost="3")),
        TOKENS,
    )

    assert [m.model for m in summary.by_model] == ["alpha", "zeta", None]


def test_accounts_tied_on_cost_break_the_tie_by_name_so_order_is_stable_across_runs():
    from litellm.provider_billing.usage_summary import build_usage_summary

    summary = build_usage_summary(
        (_row("gpt-4o", "zeta-account", cost="3"), _row("o3", "alpha-account", cost="3")),
        TOKENS,
    )

    assert [a.credential_name for a in summary.by_account] == ["alpha-account", "zeta-account"]
