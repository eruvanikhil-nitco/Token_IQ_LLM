"""Where one connection's external ID lives.

The value goes into the customer's own AWS account, written into a role's trust policy. So the
store's only real job is to never hand out a second value for the same connection: the primary key
is the connection itself, and a write that collides is resolved by reading the winner rather than
minting again.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Final, Protocol, TypeAlias

from typing_extensions import ReadOnly, TypedDict

if TYPE_CHECKING:
    from prisma import models as prisma_models

    _Row: TypeAlias = prisma_models.ProviderConnectionExternalId


class _ConnectionKey(TypedDict):
    """The compound primary key: a connection is a provider and an account name together."""

    provider: ReadOnly[str]
    credential_name: ReadOnly[str]


class _ExternalIdWhere(TypedDict):
    provider_credential_name: ReadOnly[_ConnectionKey]


class _ExternalIdCreate(TypedDict):
    provider: ReadOnly[str]
    credential_name: ReadOnly[str]
    external_id: ReadOnly[str]


@dataclasses.dataclass(frozen=True, slots=True)
class FreshlyMinted:
    """This connection had none, so one was generated and stored."""

    external_id: str


@dataclasses.dataclass(frozen=True, slots=True)
class AlreadyIssued:
    """This connection already had one, and this is it.

    Its own state rather than a flag, because the two mean different things to the person reading
    the dialog: a value issued earlier may already have a CloudFormation stack built against it,
    so there is nothing for them to do in AWS a second time.
    """

    external_id: str
    issued_at: datetime | None


IssuedExternalId: TypeAlias = FreshlyMinted | AlreadyIssued


class _ExternalIdTable(Protocol):
    async def find_unique(self, where: _ExternalIdWhere) -> _Row | None: ...

    async def create(self, data: _ExternalIdCreate) -> _Row: ...


class _PrismaDb(Protocol):
    @property
    def providerconnectionexternalid(self) -> _ExternalIdTable: ...


def _external_id_of(row: _Row | None) -> str | None:
    """The stored value, or None when there is nothing usable to present.

    An empty string is nothing usable. The column carries no check constraint, and a blank
    external ID would be presented to a customer as the value to write into a trust policy.
    """
    if row is None:
        return None
    return row.external_id if row.external_id != "" else None


class ConnectionExternalIdRepository:
    def __init__(self, prisma_client: object) -> None:
        self._prisma_client = prisma_client

    @property
    def _table(self) -> _ExternalIdTable:
        """The one hop that cannot be typed.

        `PrismaWrapper` forwards every table through `__getattr__`, so no table is visible on it
        statically. The protocol above is where the compound key and the field names are checked;
        this is only the reach through the wrapper to get there.
        """
        db: Final[_PrismaDb] = self._prisma_client.db  # pyright: ignore[reportAttributeAccessIssue]  # object has no .db
        return db.providerconnectionexternalid

    async def _row(self, provider: str, credential_name: str) -> _Row | None:
        where: Final[_ExternalIdWhere] = {
            "provider_credential_name": {"provider": provider, "credential_name": credential_name}
        }
        return await self._table.find_unique(where=where)

    async def find(self, provider: str, credential_name: str) -> str | None:
        """This connection's external ID, or None when it has never been issued one.

        A read never mints. A regenerated value locks the connection out against a trust policy
        already written for the old one, so the only place a value is created is `issue`.
        """
        return _external_id_of(await self._row(provider, credential_name))

    async def issue(self, provider: str, credential_name: str, *, mint: Callable[[], str]) -> IssuedExternalId:
        """This connection's external ID, generating one only if it has none.

        `mint` is injected so the generator stays where it is tested and this stays about
        storage. A collision means another request won the race, so its value is read back: the
        one thing that must never happen is two values for one connection.
        """
        existing: Final = await self._row(provider, credential_name)
        if (found := _external_id_of(existing)) is not None:
            return AlreadyIssued(external_id=found, issued_at=None if existing is None else existing.issued_at)

        from prisma.errors import UniqueViolationError

        minted: Final = mint()
        data: Final[_ExternalIdCreate] = {
            "provider": provider,
            "credential_name": credential_name,
            "external_id": minted,
        }
        try:
            await self._table.create(data=data)
        except UniqueViolationError:
            winner: Final = await self._row(provider, credential_name)
            if (settled := _external_id_of(winner)) is None:
                # A write that collided and then read back nothing is not an empty store. Minting
                # again here is how a connection gets its second value, which has no recovery.
                raise RuntimeError(
                    f"an external ID for {provider}/{credential_name} was written by another "
                    "request but could not be read back"
                ) from None
            return AlreadyIssued(external_id=settled, issued_at=None if winner is None else winner.issued_at)

        return FreshlyMinted(external_id=minted)
