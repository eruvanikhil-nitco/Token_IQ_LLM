"""Finding the credentials a tool connector may use.

Split from the runner so the endpoints can look credentials up without importing the job, and
kept beside `provider_billing/scheduled.py` in shape so the two read the same way.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Any, Final

from litellm.types.proxy.provider_billing import BillingCredential
from token_iq.connectors.tools.credential_purpose import is_tool_credential

INTERVAL_SECONDS: Final = 3600
"""Hourly rather than every five minutes. These endpoints report a day at a time and several
are rate limited per team, so polling them like a provider bill would spend a customer's limit
on our own questions."""


def build_tool_credentials_lookup(
    *,
    prisma_client: Any,  # any-ok: PrismaClient is an untyped runtime wrapper
) -> Callable[[str], Awaitable[tuple[BillingCredential, ...]]]:
    """Every stored credential marked for reading one tool's usage.

    Values come through CredentialAccessor rather than off the row, so the decryption this
    needs is the same code path the request router uses.
    """

    async def credentials_for(tool: str) -> tuple[BillingCredential, ...]:
        from litellm.litellm_core_utils.credential_accessor import CredentialAccessor
        from litellm.repositories.credentials_repository import CredentialsRepository

        rows: Final = await CredentialsRepository(prisma_client).find_all()
        return tuple(
            BillingCredential(name=name, values=MappingProxyType({key: str(value) for key, value in values.items()}))
            for row in rows
            if isinstance(info := getattr(row, "credential_info", None), Mapping)
            and is_tool_credential(info)
            and info.get("tool") == tool
            and isinstance(name := getattr(row, "credential_name", None), str)
            and isinstance(values := CredentialAccessor.get_credential_values(name), Mapping)
        )

    return credentials_for
