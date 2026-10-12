"""The wiring the connect dialog depends on.

The rules themselves are tested in `tests/token_iq/connectors/billing/test_connect.py` without a
database. What is asserted here is the part that only exists at the boundary: the catalogue's
vendor key translating to the provider whose bill is read, the probe reading the credential being
offered rather than one already stored, and the request shape refusing a name that cannot be
stored safely.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Final

import pytest
from pydantic import ValidationError

from token_iq.api.connect import (
    build_candidate_probe,
    connect_to_wire,
    external_id_to_wire,
    provider_or_400,
)
from token_iq.api.types.connect import (
    AccountConnected,
    ConnectionTestFailed,
    ConnectRequest,
    ExternalIdAlreadyIssued,
    ExternalIdMinted,
)
from token_iq.connectors.billing.connect import AccountStored, NotStored
from token_iq.repositories.connection_external_id_repository import AlreadyIssued, FreshlyMinted
from token_iq.types.provider_billing import BillingCredential, Fetched, NotConfigured, ProviderUsageFact

ISSUED_AT: Final = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


class _Connector:
    """A connector that records the credential values it was asked to fetch with."""

    def __init__(self, provider: str, result: object) -> None:
        self._provider = provider
        self._result = result
        self.seen: list[dict[str, str]] = []

    @property
    def provider(self) -> str:
        return self._provider

    async def fetch(self, *, since, until, credential_name, credential_values):  # noqa: ANN001, ANN003
        self.seen.append(dict(credential_values))
        return self._result


class TestWhichProviderAVendorBills:
    def test_the_catalogue_key_becomes_the_provider_whose_bill_is_read(self) -> None:
        """Two vocabularies, not a mistake in either. The catalogue groups by the account a
        customer signs into, so it says aws; what gets stored is the provider whose bill that
        account carries, which is bedrock.
        """
        assert provider_or_400("aws") == "bedrock"
        assert provider_or_400("claudeall") == "anthropic"

    def test_a_vendor_whose_spend_is_on_no_provider_bill_is_refused(self) -> None:
        # The counting rule at the boundary. Storing a seat vendor under a provider would feed
        # tool spend into a provider figure, which is the one addition that is never allowed.
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as refused:
            provider_or_400("github")

        assert refused.value.status_code == 400

    def test_an_unknown_vendor_is_refused_rather_than_guessed_at(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            provider_or_400("not-a-vendor")


class TestTheExternalIdOnTheWire:
    def test_a_fresh_one_says_it_was_just_minted(self) -> None:
        wire = external_id_to_wire(FreshlyMinted(external_id="tiq-new"), "bedrock")

        assert isinstance(wire, ExternalIdMinted)
        assert wire.external_id == "tiq-new"

    def test_one_issued_earlier_says_when(self) -> None:
        """So the dialog can say the role may already exist. A customer told to create a stack
        they created last week goes and creates a second one.
        """
        wire = external_id_to_wire(AlreadyIssued(external_id="tiq-old", issued_at=ISSUED_AT), "bedrock")

        assert isinstance(wire, ExternalIdAlreadyIssued)
        assert wire.issued_at is not None
        assert wire.issued_at.startswith("2026-10-11")

    def test_one_issued_at_an_unknown_time_still_carries_its_value(self) -> None:
        wire = external_id_to_wire(AlreadyIssued(external_id="tiq-old", issued_at=None), "bedrock")

        assert isinstance(wire, ExternalIdAlreadyIssued)
        assert wire.external_id == "tiq-old"

    def test_the_two_states_are_not_interchangeable(self) -> None:
        reissued = external_id_to_wire(AlreadyIssued(external_id="tiq-old", issued_at=ISSUED_AT), "bedrock")

        assert not isinstance(reissued, ExternalIdMinted)

    def test_a_state_outside_the_union_is_not_quietly_dropped(self) -> None:
        class Invented:
            pass

        with pytest.raises(Exception):  # noqa: B017  # the point is that it does not return None
            result = external_id_to_wire(Invented(), "bedrock")  # pyright: ignore[reportArgumentType]  # on purpose
            assert result is not None, "an unknown state returned None instead of raising"


class TestTheConnectResultOnTheWire:
    def test_a_stored_account_says_so_and_how_much_it_found(self) -> None:
        wire = connect_to_wire(AccountStored(provider="bedrock", credential_name="aws-main", facts_found=4))

        assert isinstance(wire, AccountConnected)
        assert wire.facts_found == 4

    def test_a_failed_test_carries_the_outcome_and_the_reason(self) -> None:
        wire = connect_to_wire(
            NotStored(
                provider="bedrock",
                credential_name="aws-main",
                outcome="failed",
                detail="cost explorer: AccessDenied",
            )
        )

        assert isinstance(wire, ConnectionTestFailed)
        assert wire.outcome == "failed"
        assert wire.detail is not None
        assert "AccessDenied" in wire.detail

    def test_a_failure_is_never_readable_as_a_success(self) -> None:
        wire = connect_to_wire(NotStored(provider="bedrock", credential_name="aws-main", outcome="failed", detail=None))

        assert not isinstance(wire, AccountConnected)


class TestTheTestRunsAgainstWhatIsBeingOffered:
    @pytest.mark.asyncio
    async def test_the_candidate_values_reach_the_connector(self) -> None:
        """The failure this exists to prevent: probing the stored credential instead, which
        reports a brand new key as working because an older one happened to work.
        """
        connector = _Connector("bedrock", Fetched(facts=(), watermark=ISSUED_AT))
        probe = build_candidate_probe(provider="bedrock", connectors=(connector,))

        await probe(BillingCredential(name="aws-main", values={"role_arn": "arn:x", "external_id": "tiq-new"}))

        assert connector.seen == [{"role_arn": "arn:x", "external_id": "tiq-new"}]

    @pytest.mark.asyncio
    async def test_a_working_candidate_reports_what_it_fetched(self) -> None:
        fact = ProviderUsageFact(
            fact_key="bedrock:aws-main:2026-10-10:all",
            provider="bedrock",
            credential_name="aws-main",
            grain="day",
            bucket_start=ISSUED_AT,
            evidence="reconciled",
            billed_cost=Decimal("1.25"),
            model=None,
            raw={},
        )
        connector = _Connector("bedrock", Fetched(facts=(fact,), watermark=ISSUED_AT))
        probe = build_candidate_probe(provider="bedrock", connectors=(connector,))

        answer = await probe(BillingCredential(name="aws-main", values={"role_arn": "arn:x"}))

        assert answer.outcome == "fetched"
        assert answer.facts_found == 1

    @pytest.mark.asyncio
    async def test_an_incomplete_candidate_comes_back_with_the_connector_s_own_reason(self) -> None:
        connector = _Connector("bedrock", NotConfigured(reason="carries a role ARN with no external ID"))
        probe = build_candidate_probe(provider="bedrock", connectors=(connector,))

        answer = await probe(BillingCredential(name="aws-main", values={"role_arn": "arn:x"}))

        assert answer.outcome == "not_configured"
        assert answer.detail is not None
        assert "external ID" in answer.detail

    @pytest.mark.asyncio
    async def test_a_provider_this_build_cannot_read_says_so(self) -> None:
        probe = build_candidate_probe(provider="bedrock", connectors=())

        answer = await probe(BillingCredential(name="aws-main", values={}))

        assert answer.outcome == "no_connector"


class TestTheRequestShape:
    def test_an_account_name_may_be_an_ordinary_name(self) -> None:
        assert ConnectRequest(vendor="aws", credential_name="aws-main").credential_name == "aws-main"

    def test_a_name_carrying_characters_that_need_escaping_is_refused(self) -> None:
        """It is stored, echoed in error messages and shown in sync history, so it is bounded to
        characters that need no escaping anywhere it is read back.
        """
        with pytest.raises(ValidationError):
            ConnectRequest(vendor="aws", credential_name="aws main</script>")

    def test_an_empty_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ConnectRequest(vendor="aws", credential_name="")

    def test_an_unbounded_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ConnectRequest(vendor="aws", credential_name="a" * 200)

    def test_values_default_to_none_at_all_rather_than_being_required(self) -> None:
        # The oauth and role methods start with nothing typed in, so a request with no values is
        # a real one that the shape must accept and the probe must then refuse.
        assert ConnectRequest(vendor="aws", credential_name="aws-main").values == {}


class TestTheRoleTemplateIsServed:
    def test_it_points_at_the_template_that_ships(self) -> None:
        from token_iq.api.connect import ROLE_TEMPLATE_PATH

        assert ROLE_TEMPLATE_PATH.is_file()

    def test_it_serves_the_file_the_trust_policy_test_guards(self) -> None:
        """Byte for byte, not a copy. A template rebuilt in the endpoint is one whose trust policy
        `test_bedrock_role_template.py` is no longer checking.
        """
        from pathlib import Path

        from token_iq.api.connect import ROLE_TEMPLATE_PATH
        from token_iq.connectors.billing import bedrock

        guarded = Path(bedrock.__file__).with_name("bedrock_read_only_role.yaml")

        assert ROLE_TEMPLATE_PATH.read_bytes() == guarded.read_bytes()

    def test_the_template_asks_for_the_external_id_and_nothing_secret(self) -> None:
        # What the dialog promises beside it. A template that took an access key would make the
        # reassurance copy false.
        from token_iq.api.connect import ROLE_TEMPLATE_PATH

        text = ROLE_TEMPLATE_PATH.read_text(encoding="utf-8")

        assert "ExternalId" in text
        assert "aws_secret_access_key" not in text


class TestARefusalReachesTheCaller:
    """A refusal whose detail cannot be serialised arrives as a generic 500 with the reason gone.

    Asserting the status code never notices, because nothing in a unit test serialises the detail.
    This endpoint's refusals are the only thing standing between a wrong form field and a message
    nobody can act on, so the serialisation is asserted rather than assumed. Found by curling the
    live proxy: both 400s came back as "Internal server error".
    """

    @pytest.mark.asyncio
    async def test_a_vendor_with_no_provider_bill_says_why(self) -> None:
        import json

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as refused:
            provider_or_400("github")

        assert refused.value.status_code == 400
        assert "github" in json.dumps(refused.value.detail)

    @pytest.mark.asyncio
    async def test_every_refusal_survives_the_json_encoder(self) -> None:
        import json

        from token_iq.api.connect import _proxy_error

        assert json.loads(json.dumps(_proxy_error(400, "the reason").detail)) == {"error": "the reason"}


class TestTheRowTheDatabaseTakes:
    """Prisma serialises the row with `json.dumps`, and a read-only view is not serialisable.

    Found by connecting a real account: the live test passed, then the write raised and the caller
    got a 500 with nothing stored, which is the worst of both answers. So the row goes through the
    same serialiser here rather than being assumed to survive it.
    """

    @staticmethod
    def _item() -> object:
        from token_iq.gateway.types.utils import CredentialItem

        return CredentialItem(
            credential_name="or-main",
            credential_values={"api_key": "already-encrypted"},
            credential_info={"purpose": "billing_ingestion", "provider": "openrouter"},
        )

    def test_the_row_survives_the_serialiser_prisma_uses(self) -> None:
        import json

        from token_iq.api.connect import credential_row

        row = credential_row(self._item(), stored_by="admin")  # pyright: ignore[reportArgumentType]  # built above

        assert json.loads(json.dumps(row))["credential_name"] == "or-main"

    def test_it_records_who_stored_it(self) -> None:
        from token_iq.api.connect import credential_row

        row = credential_row(self._item(), stored_by="admin")  # pyright: ignore[reportArgumentType]  # built above

        assert (row["created_by"], row["updated_by"]) == ("admin", "admin")

    def test_it_carries_the_billing_marker_the_ingestion_job_looks_for(self) -> None:
        # Without it the credential is stored and no sync ever reads it, so the account shows as
        # connected and reports nothing. The Json columns arrive as strings, which is the shape
        # the ingestion job reads back, so the marker is asserted through that rather than before.
        import json

        from token_iq.api.connect import credential_row

        row = credential_row(self._item(), stored_by=None)  # pyright: ignore[reportArgumentType]  # built above

        info = json.loads(str(row["credential_info"]))
        assert info == {"purpose": "billing_ingestion", "provider": "openrouter"}


class TestTheTemplatesOtherParameter:
    """The principal a customer's role must trust, asked of AWS rather than configured.

    What is asserted here is the boundary: every state reaching the client as itself, and the
    derived ARN being one the template's own pattern accepts. The parsing is tested in
    `tests/token_iq/connectors/billing/test_aws_principal.py`.
    """

    def test_a_known_principal_reaches_the_client(self) -> None:
        from token_iq.api.connect import principal_to_wire
        from token_iq.connectors.billing.aws_principal import PrincipalKnown

        wire: Final = principal_to_wire(PrincipalKnown(arn="arn:aws:iam::123456789012:role/tiq"))

        assert (wire.kind, wire.arn) == ("known", "arn:aws:iam::123456789012:role/tiq")

    def test_a_derived_principal_carries_what_it_came_from_and_its_caveat(self) -> None:
        from token_iq.api.connect import principal_to_wire
        from token_iq.connectors.billing.aws_principal import principal_from_caller_arn

        wire: Final = principal_to_wire(
            principal_from_caller_arn("arn:aws:sts::123456789012:assumed-role/tiq-task/abc")
        )

        assert wire.kind == "derived"
        assert wire.arn == "arn:aws:iam::123456789012:role/tiq-task"
        assert wire.session_arn.startswith("arn:aws:sts::")
        assert wire.note != ""

    def test_an_unknown_principal_is_its_own_state_rather_than_an_empty_arn(self) -> None:
        """An empty parameter pasted into CloudFormation is a stack that will not deploy, and a
        guessed one is a role trusting a principal that never presents itself."""
        from token_iq.api.connect import principal_to_wire
        from token_iq.connectors.billing.aws_principal import PrincipalUnknown

        wire: Final = principal_to_wire(PrincipalUnknown(reason="no credentials here"))

        assert wire.kind == "unknown"
        assert not hasattr(wire, "arn")
        assert wire.reason == "no credentials here"

    def test_every_arn_it_offers_is_one_the_template_accepts(self) -> None:
        # The template declares the pattern itself, so a value failing it is a stack that refuses
        # to deploy with nothing on either side to say why.
        import re

        from token_iq.api.connect import ROLE_TEMPLATE_PATH, principal_to_wire
        from token_iq.connectors.billing.aws_principal import principal_from_caller_arn

        template: Final = ROLE_TEMPLATE_PATH.read_text(encoding="utf-8")
        pattern: Final = re.search(r'AllowedPattern: "(\^arn[^"]+)"', template)
        assert pattern is not None

        for caller in (
            "arn:aws:iam::123456789012:role/tiq",
            "arn:aws:iam::123456789012:user/tiq",
            "arn:aws:sts::123456789012:assumed-role/tiq-task/session",
        ):
            wire = principal_to_wire(principal_from_caller_arn(caller))
            assert wire.kind != "unknown", caller
            assert re.match(pattern.group(1), wire.arn), f"{caller} gave {wire.arn}"
