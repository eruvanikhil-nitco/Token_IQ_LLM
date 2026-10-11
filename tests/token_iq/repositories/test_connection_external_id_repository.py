"""The external ID store, whose one job is to never hand out a second value for one connection.

The customer takes this value into their own AWS account and writes it into a role's trust
policy. Every test here is about the same failure: issuing a fresh value for a connection that
already has one, which leaves a role AWS will refuse and an error message that points at nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from types import SimpleNamespace
from typing import Final
from unittest.mock import AsyncMock, MagicMock

import pytest

from token_iq.repositories.connection_external_id_repository import (
    AlreadyIssued,
    ConnectionExternalIdRepository,
    FreshlyMinted,
)

ISSUED_AT: Final = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def _row(external_id: str = "tiq-stored") -> SimpleNamespace:
    return SimpleNamespace(
        provider="bedrock",
        credential_name="aws-main",
        external_id=external_id,
        issued_at=ISSUED_AT,
    )


def _client(found: object = None) -> tuple[MagicMock, MagicMock]:
    table = MagicMock()
    table.find_unique = AsyncMock(return_value=found)
    table.create = AsyncMock(return_value=_row())
    client = MagicMock()
    client.db.providerconnectionexternalid = table
    return client, table


def _mint() -> str:
    return "tiq-minted"


class TestIssuingOne:
    @pytest.mark.asyncio
    async def test_a_connection_with_none_gets_a_fresh_one(self) -> None:
        client, table = _client(found=None)

        result = await ConnectionExternalIdRepository(client).issue("bedrock", "aws-main", mint=_mint)

        assert isinstance(result, FreshlyMinted)
        assert result.external_id == "tiq-minted"
        assert table.create.await_args.kwargs["data"]["external_id"] == "tiq-minted"

    @pytest.mark.asyncio
    async def test_it_is_stored_against_the_connection_that_asked(self) -> None:
        client, table = _client(found=None)

        await ConnectionExternalIdRepository(client).issue("bedrock", "aws-main", mint=_mint)

        written = table.create.await_args.kwargs["data"]
        assert (written["provider"], written["credential_name"]) == ("bedrock", "aws-main")

    @pytest.mark.asyncio
    async def test_a_connection_that_already_has_one_gets_that_one_back(self) -> None:
        """The whole point. The customer's trust policy is already written against the stored
        value, so minting a second one locks them out of a role they have already created.
        """
        client, table = _client(found=_row("tiq-stored"))

        result = await ConnectionExternalIdRepository(client).issue("bedrock", "aws-main", mint=_mint)

        assert isinstance(result, AlreadyIssued)
        assert result.external_id == "tiq-stored"
        table.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_asking_twice_hands_back_the_same_value(self) -> None:
        """What a reload of the dialog does. A different value on the second read is the bug this
        store exists to prevent, so it is asserted end to end rather than only per branch.
        """
        counter = count(1)
        client, table = _client(found=None)

        first = await ConnectionExternalIdRepository(client).issue(
            "bedrock", "aws-main", mint=lambda: f"tiq-{next(counter)}"
        )
        table.find_unique = AsyncMock(return_value=_row(first.external_id))
        second = await ConnectionExternalIdRepository(client).issue(
            "bedrock", "aws-main", mint=lambda: f"tiq-{next(counter)}"
        )

        assert second.external_id == first.external_id

    @pytest.mark.asyncio
    async def test_two_at_once_settle_on_the_one_that_was_written(self) -> None:
        """Two clicks on the same button. Both read nothing, both try to write, and the loser of
        that race must come back with the winner's value rather than its own or an error.
        """
        from prisma.errors import UniqueViolationError

        client, table = _client(found=None)
        table.create = AsyncMock(side_effect=UniqueViolationError(data={}))
        table.find_unique = AsyncMock(side_effect=[None, _row("tiq-winner")])

        result = await ConnectionExternalIdRepository(client).issue("bedrock", "aws-main", mint=_mint)

        assert isinstance(result, AlreadyIssued)
        assert result.external_id == "tiq-winner"

    @pytest.mark.asyncio
    async def test_a_row_written_but_unreadable_raises_rather_than_minting_again(self) -> None:
        """A write that collided and then could not be read back is not an empty store. Treating
        it as one is how a second value gets issued, which is the failure with no recovery.
        """
        from prisma.errors import UniqueViolationError

        client, table = _client(found=None)
        table.create = AsyncMock(side_effect=UniqueViolationError(data={}))
        table.find_unique = AsyncMock(side_effect=[None, None])

        with pytest.raises(RuntimeError):
            await ConnectionExternalIdRepository(client).issue("bedrock", "aws-main", mint=_mint)


class TestReadingOne:
    @pytest.mark.asyncio
    async def test_finds_the_stored_value(self) -> None:
        client, _ = _client(found=_row("tiq-stored"))

        assert await ConnectionExternalIdRepository(client).find("bedrock", "aws-main") == "tiq-stored"

    @pytest.mark.asyncio
    async def test_a_connection_with_none_reads_as_none(self) -> None:
        client, _ = _client(found=None)

        assert await ConnectionExternalIdRepository(client).find("bedrock", "aws-main") is None

    @pytest.mark.asyncio
    async def test_reading_never_mints(self) -> None:
        """Reading is reading. A read that minted would hand a connection its second value the
        first time anything looked at it.
        """
        client, table = _client(found=None)

        await ConnectionExternalIdRepository(client).find("bedrock", "aws-main")

        table.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_blank_stored_value_reads_as_none(self) -> None:
        """The column carries no check constraint, and a blank would be presented to a customer
        as the value to write into their trust policy.
        """
        client, _ = _client(found=_row(""))

        assert await ConnectionExternalIdRepository(client).find("bedrock", "aws-main") is None


class TestItLooksUpTheRightConnection:
    """One installation holds several accounts per provider.

    Keyed by provider alone, a lookup returns whichever account was stored first, so a second
    connection is handed the external ID minted for the first and its role is never trusted. The
    key is the pair, and these assert the pair reaches the query rather than only the result.
    """

    @pytest.mark.asyncio
    async def test_a_read_asks_for_the_provider_and_the_account(self) -> None:
        client, table = _client(found=_row())

        await ConnectionExternalIdRepository(client).find("bedrock", "aws-main")

        asked = table.find_unique.await_args.kwargs["where"]
        assert asked == {"provider_credential_name": {"provider": "bedrock", "credential_name": "aws-main"}}

    @pytest.mark.asyncio
    async def test_issuing_asks_for_the_provider_and_the_account(self) -> None:
        client, table = _client(found=None)

        await ConnectionExternalIdRepository(client).issue("bedrock", "aws-second", mint=_mint)

        asked = table.find_unique.await_args.kwargs["where"]
        assert asked == {"provider_credential_name": {"provider": "bedrock", "credential_name": "aws-second"}}

    @pytest.mark.asyncio
    async def test_two_accounts_on_one_provider_are_different_connections(self) -> None:
        client, table = _client(found=None)

        await ConnectionExternalIdRepository(client).issue("bedrock", "aws-first", mint=_mint)
        await ConnectionExternalIdRepository(client).issue("bedrock", "aws-second", mint=_mint)

        names = [
            call.kwargs["where"]["provider_credential_name"]["credential_name"]
            for call in table.find_unique.await_args_list
        ]
        assert names == ["aws-first", "aws-second"]
