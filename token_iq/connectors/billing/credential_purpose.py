"""Which stored credentials read a provider's bill, and whether one is fit to.

A billing credential is an organisation admin key that can read an account's costs. It is
never used to serve models and is never shown back, so one marker on `credential_info`
identifies it for the ingestion job, the credential endpoints and the dashboard alike.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from token_iq.connectors.billing.cloud_rows import TABLE_PATTERN

BILLING_PURPOSE: Final = "billing_ingestion"

BILLING_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"openai", "anthropic", "openrouter", "bedrock", "azure", "vertex_ai"}
)

_ADMIN_KEY_PREFIXES: Final = MappingProxyType({"openai": "sk-admin-", "anthropic": "sk-ant-admin"})
"""Cost reports answer only to an organisation admin key. An ordinary key saves fine and then
fails every sync with a 401, so the kind of key is checked before it is stored."""

_AZURE_REQUIRED: Final = ("subscription_id",)
_VERTEX_REQUIRED: Final = ("billing_project_id", "billing_export_table")

_REQUIRED_FIELDS: Final = MappingProxyType(
    {"azure": _AZURE_REQUIRED, "vertex_ai": _VERTEX_REQUIRED}
)


def is_billing_credential(credential_info: Mapping[str, object] | None) -> bool:
    """Whether this credential is marked for reading a provider's bill."""
    return credential_info is not None and credential_info.get("purpose") == BILLING_PURPOSE


def _strings_only(values: Mapping[str, object]) -> Mapping[str, str]:
    """The string-valued entries, so a credential carrying a number cannot reach boto3."""
    return MappingProxyType({k: v for k, v in values.items() if isinstance(v, str)})


def _present(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _billing_export_table_problem(value: object) -> str | None:
    """`vertex.py` refuses a table reference that fails this pattern at fetch time, so a
    credential that skipped the check here would save cleanly and then never fetch."""
    if not isinstance(value, str) or value == "" or TABLE_PATTERN.fullmatch(value):
        return None
    return "This is not a BigQuery table reference. A billing export table is written project.dataset.table."


def billing_credential_problem(
    credential_info: Mapping[str, object],
    credential_values: Mapping[str, object],
    *,
    require_keys: bool,
) -> str | None:
    """Why this billing credential cannot read its provider's bill, or None when it can."""
    provider: Final = credential_info.get("provider")
    if not isinstance(provider, str) or provider not in BILLING_PROVIDERS:
        return f"A billing credential needs a provider, one of: {', '.join(sorted(BILLING_PROVIDERS))}."

    if provider == "bedrock":
        from token_iq.connectors.billing.bedrock import NoCredential, read_sign_in

        sign_in: Final = read_sign_in(_strings_only(credential_values))
        if require_keys and isinstance(sign_in, NoCredential):
            return f"A billing credential for bedrock {sign_in.why}."
        return None

    required_fields: Final = _REQUIRED_FIELDS.get(provider)
    if required_fields is not None:
        missing: Final = tuple(name for name in required_fields if not _present(credential_values.get(name)))
        if require_keys and missing:
            return f"A billing credential for {provider} needs {' and '.join(missing)}."
        return _billing_export_table_problem(credential_values.get("billing_export_table"))

    api_key: Final = credential_values.get("api_key")
    if not _present(api_key):
        return f"A {provider} billing credential needs an api_key." if require_keys else None

    prefix: Final = _ADMIN_KEY_PREFIXES.get(provider)
    if prefix is not None and isinstance(api_key, str) and not api_key.startswith(prefix):
        return (
            f"This is not a {provider} admin key. Cost reports need an organisation admin key, "
            f"which starts with {prefix}."
        )
    return None
