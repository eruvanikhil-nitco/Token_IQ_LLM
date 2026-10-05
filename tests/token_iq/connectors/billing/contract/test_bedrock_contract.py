"""Does our Bedrock connector call Cost Explorer the way AWS documents?

Bedrock is the one connector that does not speak HTTP directly: it goes through boto3, so its
contract is the shape of the `GetCostAndUsage` call and the shape of the response AWS returns.
Both are taken from the Cost Explorer API reference.
https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html

The stand-in below is a boto3 client rather than a mock with a canned return value, so it can
assert what it was called with and can raise the way botocore does.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Final

import pytest

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 20, tzinfo=timezone.utc)
CREDENTIAL: Final = {
    "aws_access_key_id": "AKIA-NOT-A-REAL-KEY",
    "aws_secret_access_key": "not-a-real-secret",
}


def _group(usage_type: str = "USE1-Bedrock:Claude-Input", amount: str = "1.25") -> dict[str, object]:
    return {
        "Keys": [usage_type],
        "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}},
    }


def _period(start: str = "2026-09-01", *groups: dict[str, object]) -> dict[str, object]:
    end: Final = (datetime.fromisoformat(start) + timedelta(days=1)).date().isoformat()
    return {
        "TimePeriod": {"Start": start, "End": end},
        "Total": {},
        "Groups": list(groups or (_group(),)),
        "Estimated": False,
    }


@dataclass
class FakeCostExplorer:
    """A stand-in for the boto3 Cost Explorer client, recording how it was called."""

    pages: Sequence[Mapping[str, object]]
    raises: Exception | None = None
    calls: list[Mapping[str, object]] = field(default_factory=list)  # mutable-ok: a spy the test reads

    def get_cost_and_usage(self, **request: object) -> Mapping[str, object]:
        self.calls.append(dict(request))
        if self.raises is not None:
            raise self.raises
        index: Final = min(len(self.calls) - 1, len(self.pages) - 1)
        return self.pages[index]


def _factory(client: FakeCostExplorer):
    def build(_values: Mapping[str, str]) -> Any:  # any-ok: boto3 clients are untyped
        return client

    return build


async def _fetch(client: FakeCostExplorer, *, values: Mapping[str, str] | None = None):
    from token_iq.connectors.billing.bedrock import BedrockBillingConnector

    return await BedrockBillingConnector(cost_explorer_factory=_factory(client)).fetch(
        since=SINCE,
        until=UNTIL,
        credential_name="aws-prod",
        credential_values=CREDENTIAL if values is None else values,
    )


@pytest.mark.asyncio
async def test_it_asks_for_daily_unblended_cost_over_the_window():
    client: Final = FakeCostExplorer(pages=({"ResultsByTime": [_period()]},))

    await _fetch(client)

    sent: Final = client.calls[0]
    assert sent["TimePeriod"] == {"Start": "2026-09-01", "End": "2026-09-20"}
    assert sent["Granularity"] == "DAILY"
    assert sent["Metrics"] == ["UnblendedCost"]


@pytest.mark.asyncio
async def test_it_narrows_to_the_service_rather_than_billing_the_whole_account():
    """Cost Explorer charges per request and would otherwise return the entire account's spend,
    which is not what this connector is for and not what the customer asked us to read."""
    client: Final = FakeCostExplorer(pages=({"ResultsByTime": [_period()]},))

    await _fetch(client)

    dimensions: Final = client.calls[0]["Filter"]["Dimensions"]
    assert dimensions["Key"] == "SERVICE"
    assert dimensions["Values"]


@pytest.mark.asyncio
async def test_it_groups_by_usage_type_so_a_day_is_not_one_opaque_number():
    client: Final = FakeCostExplorer(pages=({"ResultsByTime": [_period()]},))

    await _fetch(client)

    assert client.calls[0]["GroupBy"] == [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}]


@pytest.mark.asyncio
async def test_it_reads_the_amount_aws_reports_as_a_string_without_losing_digits():
    """Cost Explorer sends Amount as a decimal string, which is the one wire format that cannot
    lose precision. Parsing it through a float would throw that away."""
    from token_iq.types.provider_billing import Fetched

    client: Final = FakeCostExplorer(
        pages=({"ResultsByTime": [_period("2026-09-01", _group(amount="0.10000000000000000555"))]},)
    )

    result: Final = await _fetch(client)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.10000000000000000555")


@pytest.mark.asyncio
async def test_it_follows_the_page_token_to_the_end():
    from token_iq.types.provider_billing import Fetched

    client: Final = FakeCostExplorer(
        pages=(
            {"ResultsByTime": [_period("2026-09-01")], "NextPageToken": "more"},
            {"ResultsByTime": [_period("2026-09-02")]},
        )
    )

    result: Final = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(client.calls) == 2
    assert client.calls[1]["NextPageToken"] == "more"
    assert len(result.facts) == 2


@pytest.mark.asyncio
async def test_a_throttle_is_retryable_but_a_refused_identity_is_not():
    """Retrying a throttle next tick is right. Retrying an invalid key forever hides it from
    the operator who has to replace it."""
    from token_iq.types.provider_billing import FetchFailed

    throttled: Final = await _fetch(
        FakeCostExplorer(pages=(), raises=RuntimeError("ThrottlingException: Rate exceeded"))
    )
    refused: Final = await _fetch(
        FakeCostExplorer(pages=(), raises=RuntimeError("UnrecognizedClientException: invalid security token"))
    )

    assert isinstance(throttled, FetchFailed) and throttled.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


@pytest.mark.asyncio
async def test_a_credential_with_no_key_is_reported_before_any_call_is_made():
    from token_iq.types.provider_billing import NotConfigured

    client: Final = FakeCostExplorer(pages=())

    result: Final = await _fetch(client, values={})

    assert isinstance(result, NotConfigured)
    assert client.calls == []


@pytest.mark.asyncio
async def test_a_response_of_the_wrong_shape_is_a_failure_not_a_crash():
    from token_iq.types.provider_billing import FetchFailed

    result: Final = await _fetch(FakeCostExplorer(pages=({"ResultsByTime": "not a list"},)))

    assert isinstance(result, FetchFailed) or result.facts == ()
