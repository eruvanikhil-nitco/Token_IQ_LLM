"""What AWS charges for Bedrock.

There is no Bedrock usage API. Model spend is a line on the AWS bill, so this reads Cost
Explorer, which is the same place the customer's finance team looks.

Three things to know. Cost Explorer is only served from us-east-1, whatever region the
models run in. It lags roughly 34 hours for Bedrock, so a recent day is partial and is
skipped rather than compared. And the service filter is configurable, because a filter
matching nothing returns an empty result rather than an error: a customer whose bill names
the service differently would otherwise see a confident zero.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from litellm.provider_billing.cloud_rows import day_from_iso, decimal_or_none, settling_cutoff
from litellm.types.proxy.provider_billing import (
    Fetched,
    FetchFailed,
    FetchResult,
    NotConfigured,
    ProviderUsageFact,
)

COST_EXPLORER_REGION: Final = "us-east-1"
"""Cost Explorer is only served here, whatever region the models run in."""

DEFAULT_SERVICE_NAME: Final = "Amazon Bedrock"

METRIC: Final = "UnblendedCost"
"""What the account was actually charged, as opposed to an amortised or blended view."""

SETTLING_HOURS: Final = 48
"""Cost Explorer lags roughly 34 hours for Bedrock; 48 leaves margin."""

MAX_PAGES_PER_RUN: Final = 12

UNGROUPED: Final = "all"

_PERMANENT: Final = ("AccessDenied", "UnrecognizedClient", "InvalidClientTokenId", "SignatureDoesNotMatch")


def _amounts_in(period: Mapping[str, object]) -> tuple[tuple[str, object, Mapping[str, object]], ...]:
    """Every charge in one day, labelled by usage type.

    A period with no Groups but a Total is a real charge Cost Explorer could not break
    down, and dropping it would understate the bill.
    """
    groups: Final = period.get("Groups")
    if isinstance(groups, Sequence) and not isinstance(groups, (str, bytes)) and groups:
        return tuple(
            (
                keys[0] if isinstance(keys := group.get("Keys"), Sequence) and keys and isinstance(keys[0], str)
                else UNGROUPED,
                metric.get("Amount"),
                dict(group),
            )
            for group in groups
            if isinstance(group, Mapping)
            and isinstance(metrics := group.get("Metrics"), Mapping)
            and isinstance(metric := metrics.get(METRIC), Mapping)
        )

    total: Final = period.get("Total")
    if isinstance(total, Mapping) and isinstance(metric := total.get(METRIC), Mapping):
        return ((UNGROUPED, metric.get("Amount"), dict(total)),)
    return ()


def _facts_from(
    periods: Sequence[object], credential_name: str, cutoff: datetime
) -> tuple[ProviderUsageFact, ...]:
    facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across periods
    for period in periods:
        if not isinstance(period, Mapping):
            continue
        window = period.get("TimePeriod")
        day = day_from_iso(window.get("Start")) if isinstance(window, Mapping) else None
        if day is None or day >= cutoff:
            continue

        facts.extend(
            ProviderUsageFact(
                fact_key=f"bedrock:{day.date().isoformat()}:{usage_type}",
                provider="bedrock",
                credential_name=credential_name,
                grain="day",
                bucket_start=day,
                evidence="reconciled",
                billed_cost=amount,
                model=None if usage_type == UNGROUPED else usage_type,
                raw=group,
            )
            for usage_type, raw, group in _amounts_in(period)
            if (amount := decimal_or_none(raw)) is not None
        )
    return tuple(facts)


class BedrockBillingConnector:
    def __init__(self, cost_explorer_factory: Callable[[Mapping[str, str]], Any]) -> None:  # any-ok: boto3 client
        self._cost_explorer_factory = cost_explorer_factory

    @property
    def provider(self) -> str:
        return "bedrock"

    async def fetch(
        self,
        *,
        since: datetime,
        until: datetime,
        credential_name: str,
        credential_values: Mapping[str, str],
    ) -> FetchResult:
        if not credential_values.get("aws_access_key_id") or not credential_values.get("aws_secret_access_key"):
            return NotConfigured(reason=f"credential {credential_name} carries no AWS access key")

        client: Final = self._cost_explorer_factory(credential_values)
        cutoff: Final = settling_cutoff(until, SETTLING_HOURS)
        request: dict[str, object] = {  # mutable-ok: the page token advances across requests
            "TimePeriod": {"Start": since.date().isoformat(), "End": until.date().isoformat()},
            "Granularity": "DAILY",
            "Metrics": [METRIC],
            "Filter": {
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": [credential_values.get("service_name") or DEFAULT_SERVICE_NAME],
                }
            },
            "GroupBy": [{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        }

        facts: list[ProviderUsageFact] = []  # mutable-ok: accumulated across pages
        for _ in range(MAX_PAGES_PER_RUN):
            try:
                page = await asyncio.to_thread(client.get_cost_and_usage, **request)
            except Exception as exc:  # noqa: BLE001  # boto3 raises a generated class this module must not import
                text = str(exc)
                return FetchFailed(
                    reason=f"cost explorer: {text}",
                    retryable=not any(marker in text for marker in _PERMANENT),
                )

            if not isinstance(page, Mapping):
                return FetchFailed(reason="cost explorer returned an unexpected shape", retryable=True)

            periods = page.get("ResultsByTime")
            if isinstance(periods, Sequence) and not isinstance(periods, (str, bytes)):
                facts.extend(_facts_from(periods, credential_name, cutoff))

            token = page.get("NextPageToken")
            if not isinstance(token, str) or not token:
                break
            request["NextPageToken"] = token

        return Fetched(facts=tuple(facts), watermark=until)


def build_cost_explorer(credential_values: Mapping[str, str]) -> Any:  # any-ok: the boto3 client is untyped
    """A Cost Explorer client from the credential's own AWS keys."""
    import boto3

    return boto3.client(
        "ce",
        region_name=credential_values.get("aws_region_name") or COST_EXPLORER_REGION,
        aws_access_key_id=credential_values.get("aws_access_key_id"),
        aws_secret_access_key=credential_values.get("aws_secret_access_key"),
        aws_session_token=credential_values.get("aws_session_token") or None,
    )
