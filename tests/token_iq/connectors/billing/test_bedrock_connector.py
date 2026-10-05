from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CREDENTIAL = {"aws_access_key_id": "AKIA-test", "aws_secret_access_key": "secret"}


def _client(*pages: dict) -> MagicMock:
    client = MagicMock()
    client.get_cost_and_usage = MagicMock(side_effect=list(pages))
    return client


def _page(
    *groups: dict, start: str = "2026-09-11", estimated: bool = False, next_token: str | None = None
) -> dict:
    page: dict = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": start, "End": "2026-09-12"},
                "Total": {},
                "Groups": list(groups),
                "Estimated": estimated,
            }
        ]
    }
    if next_token is not None:
        page["NextPageToken"] = next_token
    return page


def _group(amount: str, usage_type: str = "USE1-Bedrock-Input-Tokens") -> dict:
    return {"Keys": [usage_type], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}


async def _fetch(client: MagicMock, credential_values=None):
    from token_iq.connectors.billing.bedrock import BedrockBillingConnector

    return await BedrockBillingConnector(cost_explorer_factory=lambda _values: client).fetch(
        since=NOW - timedelta(days=7),
        until=NOW,
        credential_name="acme-aws",
        credential_values=CREDENTIAL if credential_values is None else credential_values,
    )


@pytest.mark.asyncio
async def test_a_grouped_cost_becomes_a_day_fact():
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("1.25"))))

    assert isinstance(result, Fetched)
    fact = result.facts[0]
    assert fact.provider == "bedrock"
    assert fact.grain == "day"
    assert fact.billed_cost == Decimal("1.25")
    assert fact.bucket_start.date().isoformat() == "2026-09-11"
    assert fact.fact_key == "bedrock:acme-aws:2026-09-11:USE1-Bedrock-Input-Tokens"


@pytest.mark.asyncio
async def test_the_amount_string_keeps_its_precision():
    """Cost Explorer returns Amount as a string for exactly this reason."""
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("0.000001234567"))))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("0.000001234567")


@pytest.mark.asyncio
async def test_the_query_is_filtered_to_the_model_service_and_grouped_daily():
    """Without the service filter this ingests the customer's whole AWS bill and reports
    their EC2 spend as model spend."""
    client = _client(_page())
    await _fetch(client)

    call = client.get_cost_and_usage.call_args.kwargs
    assert call["Granularity"] == "DAILY"
    assert call["Filter"]["Dimensions"]["Key"] == "SERVICE"
    assert call["Filter"]["Dimensions"]["Values"] == ["Amazon Bedrock"]


@pytest.mark.asyncio
async def test_the_service_name_can_be_overridden_because_a_wrong_one_reports_zero():
    """A filter that matches nothing returns an empty result rather than an error, so a
    customer whose bill names the service differently would see a confident zero."""
    client = _client(_page())
    await _fetch(client, credential_values={**CREDENTIAL, "service_name": "Amazon Bedrock Marketplace"})

    assert client.get_cost_and_usage.call_args.kwargs["Filter"]["Dimensions"]["Values"] == [
        "Amazon Bedrock Marketplace"
    ]


@pytest.mark.asyncio
async def test_a_still_settling_day_is_not_recorded():
    """Cost Explorer lags roughly 34 hours for Bedrock. A partial day compared against our
    own figure would look like the gateway overcharging."""
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("9.99"), start=NOW.date().isoformat())))

    assert isinstance(result, Fetched)
    assert result.facts == ()


@pytest.mark.asyncio
async def test_an_estimated_day_is_still_recorded_because_it_self_corrects():
    """AWS marks a recent day Estimated and finalises it later. The fact key is stable per
    day, so the next run overwrites it with the settled figure."""
    from token_iq.types.provider_billing import Fetched

    result = await _fetch(_client(_page(_group("1.00"), estimated=True)))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("1.00")


@pytest.mark.asyncio
async def test_every_page_is_followed():
    from token_iq.types.provider_billing import Fetched

    client = _client(_page(_group("1.00"), next_token="tok"), _page(_group("2.00"), start="2026-09-10"))
    result = await _fetch(client)

    assert isinstance(result, Fetched)
    assert len(result.facts) == 2
    assert client.get_cost_and_usage.call_args_list[1].kwargs["NextPageToken"] == "tok"


@pytest.mark.asyncio
async def test_a_missing_credential_is_reported_not_raised():
    from token_iq.types.provider_billing import NotConfigured

    assert isinstance(await _fetch(_client(_page()), credential_values={}), NotConfigured)


@pytest.mark.asyncio
async def test_a_refused_key_is_a_permanent_failure_and_throttling_is_not():
    """Cost Explorer throttles aggressively and charges per request, so a retry next tick
    is right. An access-denied error will never fix itself."""
    from token_iq.types.provider_billing import FetchFailed

    throttled = MagicMock()
    throttled.get_cost_and_usage = MagicMock(side_effect=RuntimeError("ThrottlingException: rate exceeded"))
    denied = MagicMock()
    denied.get_cost_and_usage = MagicMock(side_effect=RuntimeError("AccessDeniedException: not authorized"))

    slow = await _fetch(throttled)
    refused = await _fetch(denied)

    assert isinstance(slow, FetchFailed) and slow.retryable is True
    assert isinstance(refused, FetchFailed) and refused.retryable is False


@pytest.mark.asyncio
async def test_an_ungrouped_total_is_still_recorded():
    """A period with no Groups but a Total is a real charge Cost Explorer could not break
    down. Dropping it would understate the bill."""
    from token_iq.types.provider_billing import Fetched

    page = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-09-11", "End": "2026-09-12"},
                "Total": {"UnblendedCost": {"Amount": "3.50", "Unit": "USD"}},
                "Groups": [],
                "Estimated": False,
            }
        ]
    }
    result = await _fetch(_client(page))

    assert isinstance(result, Fetched)
    assert result.facts[0].billed_cost == Decimal("3.50")
    assert result.facts[0].fact_key == "bedrock:acme-aws:2026-09-11:all"


def test_each_fact_keeps_the_cost_explorer_group_it_came_from():
    from token_iq.connectors.billing.bedrock import _facts_from

    group = {"Keys": ["USE1-BedrockTokens"], "Metrics": {"UnblendedCost": {"Amount": "3.50", "Unit": "USD"}}}
    facts = _facts_from(
        [{"TimePeriod": {"Start": "2026-09-14"}, "Groups": [group]}],
        "acct",
        datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    assert facts[0].raw == group


ROLE_CREDENTIAL = {
    "role_arn": "arn:aws:iam::123456789012:role/token-iq-read-only",
    "external_id": "tiq-7f3a9c21-acme",
}


class TestAnAssumedRoleIsAccepted:
    """A long-lived access key in a customer's account is the thing to get rid of.

    An IAM role with an external ID is the recommended method: nothing secret is stored, Token IQ
    asks AWS for short-lived credentials each sync, and the customer can delete the role whenever
    they like. The external ID is what stops anyone who learns the role ARN assuming it from their
    own account.
    """

    @pytest.mark.asyncio
    async def test_a_credential_with_only_a_role_is_configured(self) -> None:
        """It used to demand both access keys, so a role-only credential was refused before it was
        ever tried."""
        from token_iq.types.provider_billing import Fetched

        assert isinstance(await _fetch(_client(_page()), credential_values=ROLE_CREDENTIAL), Fetched)

    @pytest.mark.asyncio
    async def test_access_keys_still_work_so_an_existing_connection_survives_the_upgrade(self) -> None:
        from token_iq.types.provider_billing import Fetched

        assert isinstance(await _fetch(_client(_page()), credential_values=CREDENTIAL), Fetched)

    @pytest.mark.asyncio
    async def test_neither_shape_is_still_not_configured(self) -> None:
        from token_iq.types.provider_billing import NotConfigured

        assert isinstance(await _fetch(_client(_page()), credential_values={}), NotConfigured)

    @pytest.mark.asyncio
    async def test_a_role_arn_without_an_external_id_is_refused(self) -> None:
        """Without it, anyone who learns the role ARN can ask AWS to assume it from their own
        account. A role with no external ID is worse than an access key, not better."""
        from token_iq.types.provider_billing import NotConfigured

        result = await _fetch(
            _client(_page()), credential_values={"role_arn": ROLE_CREDENTIAL["role_arn"]}
        )
        assert isinstance(result, NotConfigured)


class TestTheClientIsBuiltFromTemporaryCredentials:
    @staticmethod
    def _boto3(assumed: dict | None = None) -> MagicMock:
        boto3 = MagicMock()
        sts = MagicMock()
        sts.assume_role = MagicMock(
            return_value=assumed
            or {
                "Credentials": {
                    "AccessKeyId": "ASIA-temporary",
                    "SecretAccessKey": "temporary-secret",
                    "SessionToken": "temporary-token",
                }
            }
        )
        boto3.client = MagicMock(side_effect=lambda service, **kwargs: sts if service == "sts" else MagicMock())
        return boto3

    def test_the_role_is_assumed_with_the_external_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from token_iq.connectors.billing.bedrock import build_cost_explorer

        boto3 = self._boto3()
        monkeypatch.setitem(sys.modules, "boto3", boto3)
        build_cost_explorer(ROLE_CREDENTIAL)

        sts = boto3.client("sts")
        assumed = sts.assume_role.call_args.kwargs
        assert assumed["RoleArn"] == ROLE_CREDENTIAL["role_arn"]
        assert assumed["ExternalId"] == ROLE_CREDENTIAL["external_id"]

    def test_the_cost_explorer_uses_the_short_lived_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If it fell back to ambient credentials the sync would read Token IQ's own account
        rather than the customer's, and report their spend as zero."""
        import sys

        from token_iq.connectors.billing.bedrock import build_cost_explorer

        boto3 = self._boto3()
        monkeypatch.setitem(sys.modules, "boto3", boto3)
        build_cost_explorer(ROLE_CREDENTIAL)

        built = [c for c in boto3.client.call_args_list if c.args[0] == "ce"]
        assert len(built) == 1, built
        assert built[0].kwargs["aws_access_key_id"] == "ASIA-temporary"
        assert built[0].kwargs["aws_session_token"] == "temporary-token"

    def test_an_access_key_credential_assumes_no_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from token_iq.connectors.billing.bedrock import build_cost_explorer

        boto3 = self._boto3()
        monkeypatch.setitem(sys.modules, "boto3", boto3)
        build_cost_explorer(CREDENTIAL)

        assert not [c for c in boto3.client.call_args_list if c.args[0] == "sts"]
