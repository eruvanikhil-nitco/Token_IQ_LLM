"""The rule nothing enforced: the same provider spend arriving through two connections.

Four rules keep this product from counting money twice and they are not variations of one. A
re-fetched fact is stopped by the database, a tool row already on a provider bill is stopped by the
cost line's type, and a gateway figure is stopped by the same type. The fourth had nothing: a
customer with two credentials on one provider, where one reads an account the other already covers.

It cannot be detected from what any provider tells us. No connector learns the provider's own
account identifier, so two connections reading one AWS account and two connections reading two
genuinely separate AWS accounts are indistinguishable by their credentials alone. Dropping one on a
guess halves a customer's bill, which is exactly as wrong as doubling it and harder to notice.

What is distinguishable is the figure. Two accounts reporting the same amount, to every digit, for
the same day and the same meter is one account read twice; two real accounts billing the identical
fraction of a cent on the same model and day is not something that happens. So that is the signal,
it is reported for a person to resolve, and nothing is dropped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

from token_iq.truth.cost_line import ProviderCostFact
from token_iq.truth.dedup import double_count_risks

DAY: Final = datetime(2026, 9, 15, tzinfo=timezone.utc)
NEXT_DAY: Final = datetime(2026, 9, 16, tzinfo=timezone.utc)


def _fact(
    amount: str,
    *,
    account: str,
    provider: str = "bedrock",
    day: datetime = DAY,
    model: str | None = "anthropic.claude-3-5-sonnet",
    meter: str | None = "input",
    currency: str = "USD",
) -> ProviderCostFact:
    return ProviderCostFact(
        day=day,
        provider=provider,
        credential_name=account,
        model=model,
        meter=meter,
        evidence="reconciled",
        currency=currency,
        amount=Decimal(amount),
    )


class TestTheSameFigureUnderTwoAccounts:
    def test_two_accounts_reporting_the_identical_figure_are_reported(self) -> None:
        risks: Final = double_count_risks(
            (_fact("12.34000000", account="aws-management"), _fact("12.34000000", account="aws-member"))
        )

        assert len(risks) == 1
        assert risks[0].accounts == ("aws-management", "aws-member")

    def test_the_risk_names_what_it_was_found_on(self) -> None:
        # A reader has to be able to check it against their own provider console, which means the
        # day, the model and the meter, not just a count.
        risks: Final = double_count_risks(
            (_fact("12.34", account="aws-one", meter="output"), _fact("12.34", account="aws-two", meter="output"))
        )

        assert (risks[0].provider, risks[0].day, risks[0].meter) == ("bedrock", DAY, "output")
        assert risks[0].amount == Decimal("12.34")

    def test_three_accounts_on_one_figure_are_one_risk_naming_all_three(self) -> None:
        risks: Final = double_count_risks(
            (
                _fact("5.00", account="aws-a"),
                _fact("5.00", account="aws-b"),
                _fact("5.00", account="aws-c"),
            )
        )

        assert len(risks) == 1
        assert risks[0].accounts == ("aws-a", "aws-b", "aws-c")

    def test_accounts_are_named_in_a_stable_order(self) -> None:
        # The list is read off rows whose order the database does not promise, and a pair that
        # swaps itself on every reload is a row somebody cannot point at.
        risks: Final = double_count_risks(
            (_fact("5.00", account="zzz-later"), _fact("5.00", account="aaa-first"))
        )

        assert risks[0].accounts == ("aaa-first", "zzz-later")


class TestWhatIsNotADuplicate:
    def test_two_accounts_with_different_figures_are_two_accounts(self) -> None:
        """The false positive that matters. A customer with a development account and a production
        account on one provider is ordinary, and calling that a double count would send them to
        delete a connection that was telling the truth."""
        risks: Final = double_count_risks(
            (_fact("12.34", account="aws-dev"), _fact("98.76", account="aws-prod"))
        )

        assert risks == ()

    def test_the_same_account_twice_is_not_a_pair(self) -> None:
        # One account's own rows for a day, one per meter or one per usage type, are not each
        # other's duplicates. The database already stops a genuinely re-fetched fact.
        risks: Final = double_count_risks(
            (_fact("5.00", account="aws-one"), _fact("5.00", account="aws-one"))
        )

        assert risks == ()

    def test_the_same_figure_on_different_days_is_not_a_pair(self) -> None:
        risks: Final = double_count_risks(
            (_fact("5.00", account="aws-one"), _fact("5.00", account="aws-two", day=NEXT_DAY))
        )

        assert risks == ()

    def test_the_same_figure_on_different_models_is_not_a_pair(self) -> None:
        # Two accounts each billing the same amount against a different model is two accounts
        # working, not one account read twice.
        risks: Final = double_count_risks(
            (
                _fact("5.00", account="aws-one", model="anthropic.claude-3-5-sonnet"),
                _fact("5.00", account="aws-two", model="amazon.titan-text-express"),
            )
        )

        assert risks == ()

    def test_the_same_figure_on_different_meters_is_not_a_pair(self) -> None:
        risks: Final = double_count_risks(
            (
                _fact("5.00", account="aws-one", meter="input"),
                _fact("5.00", account="aws-two", meter="output"),
            )
        )

        assert risks == ()

    def test_the_same_figure_on_different_providers_is_not_a_pair(self) -> None:
        # Two providers charging the same amount on the same day says nothing about either.
        risks: Final = double_count_risks(
            (
                _fact("5.00", account="aws-one", provider="bedrock"),
                _fact("5.00", account="or-one", provider="openrouter"),
            )
        )

        assert risks == ()

    def test_the_same_number_in_two_currencies_is_not_a_pair(self) -> None:
        risks: Final = double_count_risks(
            (
                _fact("5.00", account="aws-one", currency="USD"),
                _fact("5.00", account="aws-two", currency="EUR"),
            )
        )

        assert risks == ()

    def test_a_zero_is_never_a_pair(self) -> None:
        """Two accounts with nothing on a model is the commonest figure a provider reports, and
        pairing them would put a risk on the list for every unused model in a customer's estate."""
        risks: Final = double_count_risks(
            (_fact("0", account="aws-one"), _fact("0.00", account="aws-two"))
        )

        assert risks == ()

    def test_nothing_at_all_is_no_risk(self) -> None:
        assert double_count_risks(()) == ()


class TestWhatItDoesNotDo:
    def test_it_drops_nothing(self) -> None:
        """The whole decision. Reporting a suspicion costs a reader one look at their provider
        console; acting on it halves a bill that may have been right, and nothing downstream could
        tell that it had been halved."""
        facts: Final = (_fact("12.34", account="aws-one"), _fact("12.34", account="aws-two"))

        risks: Final = double_count_risks(facts)

        assert len(risks) == 1
        assert sum(fact.amount for fact in facts) == Decimal("24.68")
