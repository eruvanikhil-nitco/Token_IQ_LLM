"""Does our Azure connector speak the API Azure documents?

The request shape and the response shape below are taken from Microsoft's Cost Management
Query reference: a POST carrying a query definition, and a response whose `properties` holds
`columns` describing each position and `rows` of bare values in that order, with `nextLink`
carrying the next page.
https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage

The column-order contract is the interesting one. A response is a list of unlabelled values,
so reading a cost by position instead of by column name is silently wrong the day Azure adds
a column, and a mocked client can never catch it because we build the mock in the same order
we read it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest

from tests.test_litellm.provider_billing.contract.conftest import Reply, Vendor

SINCE: Final = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL: Final = datetime(2026, 9, 3, tzinfo=timezone.utc)
CREDENTIAL: Final = {"subscription_id": "sub-not-a-real-id"}

COLUMNS: Final = (
    {"name": "Cost", "type": "Number"},
    {"name": "UsageDate", "type": "Number"},
    {"name": "ServiceName", "type": "String"},
    {"name": "Currency", "type": "String"},
)


def _body(*rows: tuple[object, ...], next_link: str | None = None) -> dict[str, object]:
    return {
        "properties": {
            "columns": list(COLUMNS),
            "rows": [list(row) for row in rows],
            "nextLink": next_link,
        }
    }


def _row(cost: object = 1.25, day: int = 20260901) -> tuple[object, ...]:
    return (cost, day, "Cognitive Services", "USD")


async def _fetch(vendor: Vendor):
    from token_iq.connectors.billing.azure import AzureBillingConnector

    async def token_factory(_name: str, _values: object) -> str:
        return "entra-token-not-real"

    return await AzureBillingConnector(
        http_client_factory=vendor.client_factory(),
        token_factory=token_factory,
        base_url="https://management.azure.test",
    ).fetch(since=SINCE, until=UNTIL, credential_name="azure-prod", credential_values=CREDENTIAL)


@pytest.mark.asyncio
async def test_it_posts_to_the_path_azure_documents_for_the_subscription(vendor):
    stand_in: Final = vendor(Reply(json=_body(_row())))

    await _fetch(stand_in)

    assert stand_in.last.method == "POST"
    assert stand_in.last.path == "/subscriptions/sub-not-a-real-id/providers/Microsoft.CostManagement/query"


@pytest.mark.asyncio
async def test_it_names_the_api_version_azure_requires(vendor):
    """Cost Management rejects a request with no api-version outright."""
    stand_in: Final = vendor(Reply(json=_body(_row())))

    await _fetch(stand_in)

    assert stand_in.last.params["api-version"]


@pytest.mark.asyncio
async def test_it_authenticates_with_the_entra_token_as_a_bearer(vendor):
    stand_in: Final = vendor(Reply(json=_body(_row())))

    await _fetch(stand_in)

    assert stand_in.last.headers["authorization"] == "Bearer entra-token-not-real"


@pytest.mark.asyncio
async def test_it_asks_for_actual_daily_cost_over_the_window(vendor):
    import json

    stand_in: Final = vendor(Reply(json=_body(_row())))

    await _fetch(stand_in)

    sent: Final = json.loads(stand_in.last.body)
    assert sent["type"] == "ActualCost"
    assert sent["timeframe"] == "Custom"
    assert sent["dataset"]["granularity"] == "Daily"
    assert sent["timePeriod"]["from"] == "2026-09-01T00:00:00Z"
    assert sent["timePeriod"]["to"] == "2026-09-03T00:00:00Z"


@pytest.mark.asyncio
async def test_the_query_body_is_something_json_can_actually_serialise(vendor):
    """A frozen mapping here raises inside the HTTP client rather than in review, which is a
    failure nothing but a real request reproduces."""
    stand_in: Final = vendor(Reply(json=_body(_row())))

    await _fetch(stand_in)

    assert stand_in.last.body


@pytest.mark.asyncio
async def test_a_cost_is_read_by_column_name_not_by_position(vendor):
    """The same row with the columns declared in a different order must still read correctly.
    This is the assertion a mocked client cannot make, because the mock and the parser share
    whatever order the test author happened to pick."""
    from token_iq.types.provider_billing import Fetched

    reordered: Final = {
        "properties": {
            "columns": [
                {"name": "UsageDate", "type": "Number"},
                {"name": "ServiceName", "type": "String"},
                {"name": "Currency", "type": "String"},
                {"name": "Cost", "type": "Number"},
            ],
            "rows": [[20260901, "Cognitive Services", "USD", 1.25]],
            "nextLink": None,
        }
    }
    stand_in: Final = vendor(Reply(json=reordered))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.25")


@pytest.mark.asyncio
async def test_a_cost_with_more_digits_than_a_float_can_hold_survives(vendor):
    """Azure sends the cost as a JSON number, so this is where a float decode corrupts a bill."""
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(
        Reply(
            text='{"properties":{"columns":[{"name":"Cost","type":"Number"},{"name":"UsageDate","type":"Number"},'
            '{"name":"ServiceName","type":"String"},{"name":"Currency","type":"String"}],'
            '"rows":[[0.10000000000000000555,20260901,"Cognitive Services","USD"]],"nextLink":null}}'
        )
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.10000000000000000555")


@pytest.mark.asyncio
async def test_it_follows_the_next_link_to_the_end(vendor):
    from token_iq.types.provider_billing import Fetched

    stand_in: Final = vendor(
        Reply(json=_body(_row(), next_link="https://management.azure.test/next-page")),
        Reply(json=_body(_row(cost=2.5, day=20260902))),
    )

    result: Final = await _fetch(stand_in)

    assert isinstance(result, Fetched)
    assert len(stand_in.requests) == 2
    assert stand_in.requests[1].url == "https://management.azure.test/next-page"
    assert len(result.facts) == 2


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(401, False), (403, False), (429, True), (500, True), (503, True)],
)
@pytest.mark.asyncio
async def test_it_turns_an_error_into_a_reason_rather_than_raising(vendor, status: int, retryable: bool):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(json={"error": "nope"}, status=status))

    result: Final = await _fetch(stand_in)

    assert isinstance(result, FetchFailed)
    assert result.retryable is retryable
    assert result.reason


@pytest.mark.asyncio
async def test_a_body_that_is_not_json_is_a_failure_not_a_crash(vendor):
    from token_iq.types.provider_billing import FetchFailed

    stand_in: Final = vendor(Reply(text="<html>service unavailable</html>"))

    assert isinstance(await _fetch(stand_in), FetchFailed)
