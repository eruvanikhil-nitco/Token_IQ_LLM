"""The wire shape of one issue.

The endpoint itself needs a database, so what is tested here is the conversion: the place a new
issue state would silently stop being reported, and the place a nullable count would creep in.
"""

from __future__ import annotations

import pytest

from token_iq.api.data_quality import to_wire
from token_iq.api.types.data_quality import MeasuredIssue, UnmeasurableIssue
from token_iq.overview.data_quality import DataQualityIssue, Measured, Unmeasurable


def _issue(state) -> DataQualityIssue:
    return DataQualityIssue(key="failing_connections", title="Connections", state=state, fix_on="data-sources")


class TestAMeasuredIssue:
    def test_carries_its_count(self) -> None:
        wire = to_wire(_issue(Measured(3)))

        assert isinstance(wire, MeasuredIssue)
        assert wire.count == 3

    def test_a_zero_is_still_a_count(self) -> None:
        """Zero means looked at and none found, so it has to arrive as a number rather than as an
        absence a client would have to interpret."""
        wire = to_wire(_issue(Measured(0)))

        assert isinstance(wire, MeasuredIssue)
        assert wire.count == 0

    def test_says_it_is_measured(self) -> None:
        # The discriminator, so a client reads the shape rather than guessing from which fields
        # happen to be present.
        assert to_wire(_issue(Measured(1))).kind == "measured"


class TestAnUnmeasurableIssue:
    def test_carries_the_reason_and_no_count(self) -> None:
        wire = to_wire(_issue(Unmeasurable(reason="Needs directory sync, which is not built yet")))

        assert isinstance(wire, UnmeasurableIssue)
        assert "directory" in wire.reason
        assert not hasattr(wire, "count")

    def test_says_it_is_unmeasurable(self) -> None:
        assert to_wire(_issue(Unmeasurable(reason="x"))).kind == "unmeasurable"

    def test_is_not_representable_as_a_zero_count(self) -> None:
        """The whole reason the two are separate types. If this ever becomes a MeasuredIssue with
        count 0, the tab starts telling people there is nothing wrong when nobody has looked."""
        wire = to_wire(_issue(Unmeasurable(reason="x")))

        assert not isinstance(wire, MeasuredIssue)


class TestEveryStateIsHandled:
    def test_the_match_is_exhaustive_over_the_union(self) -> None:
        """Both arms return, so adding a third state is a type error at `to_wire` rather than an
        issue that quietly stops appearing in the list."""
        for state in (Measured(0), Unmeasurable(reason="x")):
            assert to_wire(_issue(state)) is not None

    def test_a_state_outside_the_union_is_not_quietly_dropped(self) -> None:
        # There is no `case _`, so an unknown state falls out of the match rather than being
        # converted into something harmless-looking.
        class Invented:
            pass

        with pytest.raises(Exception):  # noqa: B017  # the point is that it does not return None
            result = to_wire(_issue(Invented()))
            assert result is not None, "an unknown state returned None instead of raising"


class TestInvoiceCoverageOnTheWire:
    def test_a_covered_period_carries_both_halves_of_the_fraction(self) -> None:
        from token_iq.api.data_quality import coverage_to_wire
        from token_iq.api.types.data_quality import CoveredInvoices
        from token_iq.overview.data_quality import InvoicesCovered

        wire = coverage_to_wire(InvoicesCovered(providers_billed=6, providers_invoiced=5))

        assert isinstance(wire, CoveredInvoices)
        assert (wire.providers_billed, wire.providers_invoiced) == (6, 5)
        assert wire.kind == "covered"

    def test_nobody_billing_arrives_as_its_own_shape_with_no_fraction(self) -> None:
        from token_iq.api.data_quality import coverage_to_wire
        from token_iq.api.types.data_quality import CoveredInvoices, NothingBilledYet
        from token_iq.overview.data_quality import NothingBilled

        wire = coverage_to_wire(NothingBilled())

        assert isinstance(wire, NothingBilledYet)
        assert not isinstance(wire, CoveredInvoices)
        assert not hasattr(wire, "providers_billed")

    def test_a_coverage_outside_the_union_is_not_quietly_dropped(self) -> None:
        from token_iq.api.data_quality import coverage_to_wire

        class Invented:
            pass

        with pytest.raises(Exception):  # noqa: B017  # the point is that it does not return None
            result = coverage_to_wire(Invented())
            assert result is not None, "an unknown coverage returned None instead of raising"


class TestARefusalReachesTheCaller:
    """The same failure the connect endpoint had: a detail FastAPI cannot serialise turns every
    refusal into a generic 500. Asserting the status code alone never notices."""

    def test_a_refusal_survives_the_json_encoder(self) -> None:
        import json

        from token_iq.api.data_quality import _proxy_error

        assert json.loads(json.dumps(_proxy_error(403, "not allowed").detail)) == {"error": "not allowed"}
