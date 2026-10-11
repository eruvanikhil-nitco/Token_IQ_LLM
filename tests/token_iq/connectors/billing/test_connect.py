"""What a new connection may carry, and what has to pass before it is stored.

Three rules, each failing in a direction worth a test. The allowlist stops a caller putting a
field into a billing credential that the connector would act on. The external ID comes from the
store rather than the request, because it is the whole security property of the role method. And
nothing is stored unless the live test passed, which is the blueprint's own promise and the one
the customer is relying on when they paste a key.
"""

from __future__ import annotations

from typing import Final

import pytest

from token_iq.connectors.billing.connect import (
    AccountStored,
    NotStored,
    connect_account,
    permitted_values,
    values_for_connection,
)
from token_iq.gateway.types.proxy.management_endpoints.team_endpoints import BillingProbeResponse
from token_iq.types.provider_billing import BillingCredential

ROLE_ARN: Final = "arn:aws:iam::123456789012:role/token-iq-read-only"


def _probe(outcome: str, *, facts: int = 2, detail: str | None = None) -> BillingProbeResponse:
    return BillingProbeResponse(
        provider="bedrock",
        credential_name="aws-main",
        outcome=outcome,
        facts_found=facts,
        sample_cost=None,
        detail=detail,
    )


class _Recorder:
    """A stand-in for the credential store, recording whether it was written to at all."""

    def __init__(self) -> None:
        self.stored: list[BillingCredential] = []

    async def __call__(self, credential: BillingCredential) -> None:
        self.stored.append(credential)


class TestWhichFieldsAConnectionMayCarry:
    def test_keeps_the_fields_the_connector_reads(self) -> None:
        kept = permitted_values("bedrock", {"role_arn": ROLE_ARN, "service_name": "Amazon Bedrock"})

        assert kept == {"role_arn": ROLE_ARN, "service_name": "Amazon Bedrock"}

    def test_drops_a_field_the_provider_has_no_business_with(self) -> None:
        """An allowlist rather than a denylist. A billing credential carrying `api_base` would
        point a connector somewhere other than the provider, and the caller chose the value.
        """
        kept = permitted_values("anthropic", {"api_key": "sk-ant-admin01-x", "api_base": "https://evil.test"})

        assert kept == {"api_key": "sk-ant-admin01-x"}

    def test_drops_an_external_id_the_caller_supplied(self) -> None:
        # The one field a caller must never set. Accepting it would let somebody present a value
        # they chose, which is exactly what the external ID exists to prevent.
        kept = permitted_values("bedrock", {"role_arn": ROLE_ARN, "external_id": "tiq-chosen-by-me"})

        assert "external_id" not in kept

    def test_drops_an_empty_field_rather_than_storing_a_blank(self) -> None:
        """A blank is not a value. Stored, it makes a credential look like it carries a field it
        does not, and `read_sign_in` then names the wrong half as the missing one.
        """
        kept = permitted_values("bedrock", {"role_arn": ROLE_ARN, "aws_access_key_id": ""})

        assert kept == {"role_arn": ROLE_ARN}

    def test_a_provider_nothing_is_known_about_keeps_nothing(self) -> None:
        assert permitted_values("not-a-provider", {"api_key": "x"}) == {}


class TestWhereTheExternalIdComesFrom:
    def test_a_role_sign_in_gets_the_stored_id(self) -> None:
        values = values_for_connection("bedrock", {"role_arn": ROLE_ARN}, "tiq-stored")

        assert values == {"role_arn": ROLE_ARN, "external_id": "tiq-stored"}

    def test_the_stored_id_wins_over_one_in_the_request(self) -> None:
        """Not a merge order detail. The customer's trust policy is written against the stored
        value, so a request that carried a different one would save a connection AWS refuses.
        """
        values = values_for_connection("bedrock", {"role_arn": ROLE_ARN, "external_id": "tiq-mine"}, "tiq-stored")

        assert values["external_id"] == "tiq-stored"

    def test_nothing_minted_yet_leaves_the_role_incomplete(self) -> None:
        # Left incomplete on purpose: `read_sign_in` then refuses a role ARN with no external ID,
        # which is the refusal that already exists rather than a second one invented here.
        values = values_for_connection("bedrock", {"role_arn": ROLE_ARN}, None)

        assert "external_id" not in values

    def test_a_provider_that_does_not_sign_in_with_a_role_gets_no_id(self) -> None:
        """An external ID on an Anthropic credential reads as a field that does something. It
        does not: nothing in that connector looks at it.
        """
        values = values_for_connection("anthropic", {"api_key": "sk-ant-admin01-x"}, "tiq-stored")

        assert "external_id" not in values


class TestNothingIsStoredUntilTheTestPasses:
    @pytest.mark.asyncio
    async def test_a_working_connection_is_stored(self) -> None:
        store = _Recorder()

        result = await connect_account(
            provider="bedrock",
            credential_name="aws-main",
            values={"role_arn": ROLE_ARN, "external_id": "tiq-stored"},
            probe=lambda _: _answer(_probe("fetched")),
            store=store,
        )

        assert isinstance(result, AccountStored)
        assert [credential.name for credential in store.stored] == ["aws-main"]

    @pytest.mark.asyncio
    async def test_a_connection_that_answered_with_nothing_is_still_stored(self) -> None:
        """A fresh account with no spend in the window is a working connection, not a failed one.
        Requiring a figure would make a quiet account impossible to connect.
        """
        store = _Recorder()

        result = await connect_account(
            provider="bedrock",
            credential_name="aws-main",
            values={"role_arn": ROLE_ARN, "external_id": "tiq-stored"},
            probe=lambda _: _answer(_probe("fetched", facts=0, detail="The provider reported nothing")),
            store=store,
        )

        assert isinstance(result, AccountStored)
        assert result.facts_found == 0
        assert len(store.stored) == 1

    @pytest.mark.asyncio
    async def test_a_failed_test_stores_nothing(self) -> None:
        store = _Recorder()

        result = await connect_account(
            provider="bedrock",
            credential_name="aws-main",
            values={"role_arn": ROLE_ARN, "external_id": "tiq-stored"},
            probe=lambda _: _answer(_probe("failed", facts=0, detail="cost explorer: AccessDenied")),
            store=store,
        )

        assert isinstance(result, NotStored)
        assert store.stored == []

    @pytest.mark.asyncio
    async def test_the_reason_the_test_failed_is_carried_back(self) -> None:
        """ "Could not connect" sends somebody back to a form with no idea which field is wrong.
        AWS says AccessDenied for a trust policy that does not match, and that is the message.
        """
        result = await connect_account(
            provider="bedrock",
            credential_name="aws-main",
            values={"role_arn": ROLE_ARN},
            probe=lambda _: _answer(_probe("not_configured", facts=0, detail="carries a role ARN with no external ID")),
            store=_Recorder(),
        )

        assert isinstance(result, NotStored)
        assert result.outcome == "not_configured"
        assert result.detail is not None
        assert "external ID" in result.detail

    @pytest.mark.asyncio
    async def test_the_test_runs_against_the_values_being_offered(self) -> None:
        """Not against whatever is already stored. `run_billing_probe` reads stored credentials,
        so a connect flow that reused it unchanged would test the previous connection and report
        a brand new key as working.
        """
        seen: list[BillingCredential] = []

        async def probe(credential: BillingCredential) -> BillingProbeResponse:
            seen.append(credential)
            return _probe("fetched")

        await connect_account(
            provider="bedrock",
            credential_name="aws-main",
            values={"role_arn": ROLE_ARN, "external_id": "tiq-stored"},
            probe=probe,
            store=_Recorder(),
        )

        assert [credential.values["external_id"] for credential in seen] == ["tiq-stored"]

    @pytest.mark.asyncio
    async def test_a_provider_with_no_connector_stores_nothing(self) -> None:
        store = _Recorder()

        result = await connect_account(
            provider="kore",
            credential_name="kore-main",
            values={},
            probe=lambda _: _answer(_probe("no_connector", facts=0, detail="This build ships no connector")),
            store=store,
        )

        assert isinstance(result, NotStored)
        assert store.stored == []


async def _answer(response: BillingProbeResponse) -> BillingProbeResponse:
    return response
