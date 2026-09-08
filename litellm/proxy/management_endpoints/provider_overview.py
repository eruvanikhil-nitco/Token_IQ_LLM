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

See project_usage/16-providers-tab.md
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

import litellm

# The daily table buckets by whole UTC day, so "today" here means the current UTC day
# plus the previous one. Calling it 24h would overstate what the rollup can answer.
_ROLLUP_DAYS: Final = 2

_COST_FIELDS: Final = ("input_cost_per_token", "output_cost_per_token")

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
    requests: int = 0
    spend: float = 0.0
    last_used: str | None = None


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
        for name, entry in litellm.model_cost.items()
        if isinstance(entry, dict) and isinstance(entry.get("litellm_provider"), str)
    }


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


def build_provider_overview(
    *,
    model_list: Sequence[Mapping[str, object]],
    usage_rows: Sequence[Mapping[str, object]],
) -> ProviderOverviewResponse:
    """Merge configured deployments, the catalogue and today's usage into one table.

    Pure: usage rows are passed in rather than queried, so the shape is testable without
    a database.
    """
    catalogue: Final = _catalogue_entries()
    catalogue_counts: dict[str, int] = {}
    for entry in catalogue.values():
        provider = str(entry["litellm_provider"])
        catalogue_counts[provider] = catalogue_counts.get(provider, 0) + 1

    configured: Final = _configured_by_provider(model_list)

    usage_by_provider: dict[str, dict[str, object]] = {}
    for row in usage_rows:
        provider = row.get("custom_llm_provider")
        if not isinstance(provider, str) or not provider:
            # Rows with no provider are failed calls that never reached one. Counting
            # them would inflate requests while contributing nothing to spend.
            continue
        bucket = usage_by_provider.setdefault(provider, {"requests": 0, "spend": 0.0, "last_used": None})
        bucket["requests"] = int(bucket["requests"]) + int(row.get("api_requests") or 0)
        bucket["spend"] = float(bucket["spend"]) + float(row.get("spend") or 0.0)
        date = row.get("date")
        if isinstance(date, str) and (bucket["last_used"] is None or date > str(bucket["last_used"])):
            bucket["last_used"] = date

    rows: Final = tuple(
        ProviderRow(
            provider=provider,
            models_configured=len(deployments),
            models_in_catalogue=catalogue_counts.get(provider, 0),
            has_credentials=any(
                isinstance(d.get("litellm_params"), dict) and bool(d["litellm_params"].get("api_key"))
                for d in deployments
            ),
            requests=int(usage_by_provider.get(provider, {}).get("requests", 0)),
            spend=round(float(usage_by_provider.get(provider, {}).get("spend", 0.0)), 8),
            last_used=usage_by_provider.get(provider, {}).get("last_used"),  # type: ignore[arg-type]
        )
        for provider, deployments in sorted(configured.items())
    )

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
    """Group daily rows by model group.

    Rows carrying no model group are dropped rather than bucketed under a blank key:
    they are failed calls that never resolved to a model, and a row of zeros against an
    unnamed model would read as a real model that costs nothing.
    """
    totals: dict[str, dict[str, float]] = {}
    for row in usage_rows:
        group = row.get("model_group") or row.get("model")
        if not isinstance(group, str) or not group:
            continue
        bucket = totals.setdefault(group, {"requests": 0.0, "tokens": 0.0, "spend": 0.0})
        bucket["requests"] += float(row.get("api_requests") or 0)
        bucket["tokens"] += float(row.get("prompt_tokens") or 0) + float(row.get("completion_tokens") or 0)
        bucket["spend"] += float(row.get("spend") or 0.0)

    return ModelUsageResponse(
        range=range_key if range_key in USAGE_RANGE_DAYS else DEFAULT_USAGE_RANGE,
        days=days,
        start_date=start_date,
        usage=[
            ModelUsageRow(
                model_group=group,
                requests=int(values["requests"]),
                tokens=int(values["tokens"]),
                spend=round(values["spend"], 8),
            )
            for group, values in sorted(totals.items())
        ],
    )
