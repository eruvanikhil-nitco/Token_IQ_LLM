"""Provider-level and model-level views over the catalogue and today's usage.

Two questions this answers that nothing in the dashboard answers today:

  - Per provider: how many models does the catalogue know, how many have we actually
    configured, and what did they cost today.
  - Per model: is this one configured, and what would it cost if we called it.

The "configured" flag is the point. LiteLLM's catalogue lists what it can price; the
model_list holds what this proxy can actually serve. Nothing in the UI shows the gap
between them, which is exactly the question asked when someone says "can we use X".

Usage comes from `LiteLLM_DailyUserSpend`, which already carries `custom_llm_provider`,
`api_requests` and `spend`, so a provider rollup is a group-by rather than a scan of raw
spend logs.

See docs/decisions/0016-providers-tab.md
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import groupby
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from token_iq import gateway

# The daily table buckets by whole UTC day, so "today" here means the current UTC day
# plus the previous one. Calling it 24h would overstate what the rollup can answer.
_ROLLUP_DAYS: Final = 2

_COST_FIELDS: Final = ("input_cost_per_token", "output_cost_per_token")

# Params that prove someone deliberately supplied credentials. `api_key` alone is not
# enough: Bedrock, Vertex and Azure each authenticate their own way, and a deployment
# configured with one of those is as set up as an OpenAI one with a key.
#
# Ambient credentials cannot appear here at all, because they are not in the model list:
# an EC2 instance role or Google application default credentials leave litellm_params
# holding nothing but a model name. Such a deployment is listed only once it has served
# traffic, which `_is_set_up` treats as its own proof of being configured.
_CREDENTIAL_FIELDS: Final = frozenset(
    {
        "api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_role_name",
        "aws_profile_name",
        "aws_web_identity_token",
        "aws_bedrock_runtime_endpoint",
        "vertex_credentials",
        "azure_ad_token",
        "azure_ad_token_provider",
        "azure_username",
        "azure_password",
        "tenant_id",
        "client_secret",
    }
)

_FEATURE_FIELDS: Final = MappingProxyType(
    {
        "supports_vision": "vision",
        "supports_function_calling": "function calling",
        "supports_reasoning": "reasoning",
        "supports_prompt_caching": "prompt caching",
    }
)


class ProviderRow(BaseModel):
    """One provider, as the Overview table renders it."""

    provider: str
    models_configured: int = Field(description="Deployments on this proxy served by this provider")
    models_in_catalogue: int = Field(description="Models the local catalogue can price for this provider")
    has_credentials: bool = Field(description="Whether at least one configured deployment carries a key")
    is_configured: bool = Field(
        default=True,
        description="False when this provider only appears in recorded traffic, with no deployment left for it",
    )
    requests: int = 0
    spend: float = 0.0
    last_used: str | None = Field(
        default=None,
        description="Latest UTC day this provider served traffic, over all history rather than the rollup window",
    )


class ProviderOverviewResponse(BaseModel):
    """The four stat blocks plus the provider table beneath them."""

    total_providers: int
    total_models: int
    total_requests: int
    total_spend: float
    rollup_days: int = Field(description="How many whole UTC days the request and spend figures cover")
    providers: list[ProviderRow]  # writable-ok: FastAPI serialises the response model directly


class CatalogueModel(BaseModel):
    """One model, as the Models table renders it."""

    model_name: str
    provider: str
    configured: bool = Field(description="Whether this proxy has a deployment for it")
    mode: str | None = None
    max_input_tokens: int | None = None
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    features: list[str] = Field(  # writable-ok: FastAPI serialises the response model directly
        default_factory=list,
        description="Capability flags the catalogue advertises, e.g. vision or function calling",
    )


class ProviderModelsResponse(BaseModel):
    provider: str | None = Field(description="The provider filtered on, or None for every provider")
    total: int
    configured: int
    models: list[CatalogueModel]  # writable-ok: FastAPI serialises the response model directly


def _catalogue_entries() -> Mapping[str, Mapping[str, object]]:
    """Catalogue rows that name a provider, keyed by model name."""
    return {
        name: entry
        for name, entry in gateway.model_cost.items()
        if isinstance(entry, dict) and isinstance(entry.get("litellm_provider"), str)
    }


def _catalogue_counts() -> Mapping[str, int]:
    """How many catalogue models each provider can be priced for."""
    providers: Final = sorted(str(entry["litellm_provider"]) for entry in _catalogue_entries().values())
    return {provider: len(tuple(group)) for provider, group in groupby(providers)}


def _features_of(entry: Mapping[str, object]) -> list[str]:
    return [label for field, label in _FEATURE_FIELDS.items() if entry.get(field) is True]


def _numeric(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _configured_by_provider(model_list: Sequence[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    """Group the proxy's deployments by the provider their model string names."""
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for deployment in model_list:
        params = deployment.get("litellm_params")
        if not isinstance(params, dict):
            continue
        model = params.get("model")
        if not isinstance(model, str):
            continue
        provider = model.split("/", 1)[0] if "/" in model else "openai"
        grouped.setdefault(provider, []).append(deployment)
    return grouped


@dataclass(frozen=True, slots=True)
class _ProviderUsage:
    """Requests and spend a provider accumulated over the rollup window."""

    requests: int = 0
    spend: float = 0.0


def _usage_by_provider(usage_rows: Sequence[Mapping[str, object]]) -> Mapping[str, _ProviderUsage]:
    """Total requests and spend per provider.

    Rows with no provider are failed calls that never reached one. Counting them would
    inflate requests while contributing nothing to spend.
    """
    named: Final = sorted(
        (
            (provider, row)
            for row in usage_rows
            if isinstance(provider := row.get("custom_llm_provider"), str) and provider
        ),
        key=lambda pair: pair[0],
    )
    return {
        provider: _ProviderUsage(
            requests=sum(int(row.get("api_requests") or 0) for _, row in rows),
            spend=sum(float(row.get("spend") or 0.0) for _, row in rows),
        )
        for provider, group in groupby(named, key=lambda pair: pair[0])
        if (rows := tuple(group))
    }


def has_credentials(deployments: Sequence[Mapping[str, object]]) -> bool:
    """Whether any deployment carries credentials someone deliberately supplied.

    Public because `/v2/model/info` filters on the same rule, and two definitions of
    "configured" drifting apart would be worse than the coupling.
    """
    return any(
        isinstance(params := deployment.get("litellm_params"), dict)
        and any(params.get(field) for field in _CREDENTIAL_FIELDS)
        for deployment in deployments
    )


def _is_set_up(row: ProviderRow) -> bool:
    """Whether the client actually set this provider up.

    A key is the positive signal. Recorded traffic is the other one: a provider that
    served requests was plainly configured at the time, and hiding it now would drop real
    spend out of the totals above the table.

    Everything else is a deployment nobody can call, which is what a sample config full of
    `os.environ/...` placeholders for unset variables leaves behind.
    """
    return row.has_credentials or row.requests > 0 or row.last_used is not None


def build_provider_overview(
    *,
    model_list: Sequence[Mapping[str, object]],
    usage_rows: Sequence[Mapping[str, object]],
    last_used_by_provider: Mapping[str, str] = MappingProxyType({}),
) -> ProviderOverviewResponse:
    """Merge configured deployments, the catalogue and recent usage into one table.

    Only providers this gateway is actually set up for are listed: see `_is_set_up`. A
    config file that ships example deployments pointing at unset environment variables
    would otherwise fill the page with providers nobody configured and nothing can call.

    A provider that served traffic but has no deployment left still gets a row, flagged
    `is_configured=False`. Dropping it would hide real spend from the totals, which is the
    opposite of what an observer gateway is for.

    `last_used_by_provider` is queried over all history rather than the rollup window, so a
    provider last called a month ago reads as a date instead of "never".

    Pure: usage rows are passed in rather than queried, so the shape is testable without
    a database.
    """
    catalogue_counts: Final = _catalogue_counts()
    configured: Final = _configured_by_provider(model_list)
    usage: Final = _usage_by_provider(usage_rows)

    candidates: Final = tuple(
        ProviderRow(
            provider=provider,
            models_configured=len(configured.get(provider, ())),
            models_in_catalogue=catalogue_counts.get(provider, 0),
            has_credentials=has_credentials(configured.get(provider, ())),
            is_configured=provider in configured,
            requests=usage.get(provider, _ProviderUsage()).requests,
            spend=round(usage.get(provider, _ProviderUsage()).spend, 8),
            last_used=last_used_by_provider.get(provider),
        )
        for provider in sorted(configured.keys() | usage.keys())
    )

    rows: Final = tuple(row for row in candidates if _is_set_up(row))

    return ProviderOverviewResponse(
        total_providers=len(rows),
        total_models=sum(row.models_configured for row in rows),
        total_requests=sum(row.requests for row in rows),
        total_spend=round(sum(row.spend for row in rows), 8),
        rollup_days=_ROLLUP_DAYS,
        providers=list(rows),
    )


def build_provider_models(
    *,
    model_list: Sequence[Mapping[str, object]],
    provider: str | None,
) -> ProviderModelsResponse:
    """Every catalogue model for a provider, flagged by whether this proxy serves it."""
    configured_names: Final = {
        params["model"]
        for deployment in model_list
        if isinstance(params := deployment.get("litellm_params"), dict) and isinstance(params.get("model"), str)
    }

    models: Final = tuple(
        CatalogueModel(
            model_name=name,
            provider=str(entry["litellm_provider"]),
            configured=name in configured_names,
            mode=entry.get("mode") if isinstance(entry.get("mode"), str) else None,
            max_input_tokens=int(value) if isinstance(value := entry.get("max_input_tokens"), (int, float)) else None,
            input_cost_per_token=_numeric(entry.get(_COST_FIELDS[0])),
            output_cost_per_token=_numeric(entry.get(_COST_FIELDS[1])),
            features=_features_of(entry),
        )
        for name, entry in sorted(_catalogue_entries().items())
        if provider is None or entry["litellm_provider"] == provider
    )

    return ProviderModelsResponse(
        provider=provider,
        total=len(models),
        configured=sum(1 for model in models if model.configured),
        models=list(models),
    )


def rollup_start_date() -> str:
    """The earliest whole UTC day the request and spend figures cover, as YYYY-MM-DD."""
    return (datetime.now(timezone.utc) - timedelta(days=_ROLLUP_DAYS - 1)).strftime("%Y-%m-%d")


# Ranges the Models table offers. Keys are what the UI sends; values are whole UTC days
# back from today, because the daily table buckets by day and cannot answer a rolling
# window. "1 day" therefore means today's bucket, not the last 24 hours.
USAGE_RANGE_DAYS: Final = MappingProxyType({"day": 1, "week": 7, "month": 30})

DEFAULT_USAGE_RANGE: Final = "week"


class ModelUsageRow(BaseModel):
    """Usage for one model group over the selected range."""

    model_group: str
    providers: list[str] = Field(  # writable-ok: FastAPI serialises the response model directly
        default_factory=list,
        description="Providers that served this model group, so a model no longer configured can still be attributed",
    )
    requests: int = 0
    tokens: int = 0
    spend: float = 0.0


class ModelUsageResponse(BaseModel):
    range: str
    days: int = Field(description="Whole UTC days covered, counting today")
    start_date: str
    usage: list[ModelUsageRow]  # writable-ok: FastAPI serialises the response model directly


def usage_range_start(range_key: str) -> tuple[str, int]:
    """Start date and day count for a range key, falling back to the default."""
    days: Final = USAGE_RANGE_DAYS.get(range_key, USAGE_RANGE_DAYS[DEFAULT_USAGE_RANGE])
    start: Final = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    return start, days


def build_model_usage(
    *,
    range_key: str,
    start_date: str,
    days: int,
    usage_rows: Sequence[Mapping[str, object]],
) -> ModelUsageResponse:
    """Group daily rows by model group, carrying the providers that served each.

    Rows carrying no model group are dropped rather than bucketed under a blank key:
    they are failed calls that never resolved to a model, and a row of zeros against an
    unnamed model would read as a real model that costs nothing.

    `providers` lets the Models table place a model that recorded traffic but has since
    been removed from the model list, which otherwise has no provider to file it under.
    """
    named: Final = sorted(
        (
            (group, row)
            for row in usage_rows
            if isinstance(group := (row.get("model_group") or row.get("model")), str) and group
        ),
        key=lambda pair: pair[0],
    )

    return ModelUsageResponse(
        range=range_key if range_key in USAGE_RANGE_DAYS else DEFAULT_USAGE_RANGE,
        days=days,
        start_date=start_date,
        usage=[
            ModelUsageRow(
                model_group=group,
                providers=sorted(
                    {
                        provider
                        for _, row in rows
                        if isinstance(provider := row.get("custom_llm_provider"), str) and provider
                    }
                ),
                requests=sum(int(row.get("api_requests") or 0) for _, row in rows),
                tokens=sum(
                    int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0) for _, row in rows
                ),
                spend=round(sum(float(row.get("spend") or 0.0) for _, row in rows), 8),
            )
            for group, group_rows in groupby(named, key=lambda pair: pair[0])
            if (rows := tuple(group_rows))
        ],
    )
