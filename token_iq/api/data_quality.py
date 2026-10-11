"""The Data Sources > Overview tab's issues list, gathered once for one period.

Composed on the server so every issue covers the same period and the rule about what counts as a
problem is applied in one place. That rule lives in `token_iq/overview/data_quality.py` and is
tested without a database; the two counts it cannot work out for itself come from
`DataQualityRepository`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, status

from token_iq.api.provider_connections import build_provider_connections
from token_iq.api.types.data_quality import (
    CoveredInvoices,
    DataQualityResponse,
    InvoiceCoverageResponse,
    IssueResponse,
    MeasuredIssue,
    NothingBilledYet,
    UnmeasurableIssue,
)
from token_iq.connectors.billing.credential_purpose import BILLING_PROVIDERS
from token_iq.connectors.billing.scheduled import build_billing_credentials_lookup
from token_iq.gateway.proxy._types import CommonProxyErrors, GatewayUserRoles, UserAPIKeyAuth
from token_iq.gateway.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.overview.data_quality import (
    DataQualityIssue,
    InvoiceCoverage,
    InvoicesCovered,
    Measured,
    NothingBilled,
    Unmeasurable,
    data_quality_issues,
    invoice_coverage,
    issues_to_fix,
)
from token_iq.repositories.data_quality_repository import DataQualityRepository
from token_iq.repositories.provider_sync_run_repository import ProviderSyncRunRepository
from token_iq.repositories.provider_usage_fact_repository import ProviderUsageFactRepository

router: Final = APIRouter(
    tags=["data quality"],  # mutable-ok: fixed single-element tag list, never grown after this line
    dependencies=(Depends(user_api_key_auth),),
)

DEFAULT_DAYS: Final = 30
"""The window the tab asks about. Long enough that a monthly invoice has had a chance to arrive."""

RUNS_FOR_STATE: Final = 200
"""How many recent sync runs decide a connection's state. The same number the connections
endpoint uses, because a different one would disagree with the Accounts tab about the same
connection."""


def _proxy_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=MappingProxyType({"error": message}),
    )


def _admin_or_403(user_api_key_dict: UserAPIKeyAuth) -> None:
    if user_api_key_dict.user_role != GatewayUserRoles.PROXY_ADMIN:
        raise _proxy_error(status.HTTP_403_FORBIDDEN, CommonProxyErrors.not_allowed_access.value)


def to_wire(issue: DataQualityIssue) -> IssueResponse:
    """One issue in the shape a client reads.

    Exhaustive over the union rather than defaulting, so adding a third state is a type error here
    instead of an issue that silently stops being reported.
    """
    match issue.state:
        case Measured(count=count):
            return MeasuredIssue(key=issue.key, title=issue.title, fix_on=issue.fix_on, count=count)
        case Unmeasurable(reason=reason):
            return UnmeasurableIssue(key=issue.key, title=issue.title, fix_on=issue.fix_on, reason=reason)


def coverage_to_wire(coverage: InvoiceCoverage) -> InvoiceCoverageResponse:
    """Invoice coverage in the shape a client reads, exhaustive for the same reason `to_wire` is."""
    match coverage:
        case InvoicesCovered(providers_billed=billed, providers_invoiced=invoiced):
            return CoveredInvoices(providers_billed=billed, providers_invoiced=invoiced)
        case NothingBilled():
            return NothingBilledYet()


@router.get("/data-quality", response_model=DataQualityResponse)
async def data_quality(
    # `Annotated` rather than a `Depends()` default: the call then sits inside the annotation
    # instead of being evaluated as a default argument, which is what B008 objects to, and it is
    # the form FastAPI now documents. A parameter with no default has to come first.
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
    days: int = DEFAULT_DAYS,
) -> DataQualityResponse:
    """What is wrong with the incoming data, and where each one is fixed."""
    from token_iq.gateway.proxy.proxy_server import prisma_client

    _admin_or_403(user_api_key_dict)
    if prisma_client is None:
        raise _proxy_error(status.HTTP_500_INTERNAL_SERVER_ERROR, CommonProxyErrors.db_not_connected_error.value)

    end: Final = datetime.now(timezone.utc)
    start: Final = end - timedelta(days=days)

    repository: Final = DataQualityRepository(prisma_client)

    # Gathered here rather than left to the browser. Passing no states would report
    # "failing connections: 0", and a measured zero on a tab asking whether the data can be
    # trusted reads as reassurance; the whole point of the unmeasurable state is that "I did not
    # look" must never borrow that number. The same builder and the same run window as the
    # connections endpoint, so the two cannot disagree about one connection.
    facts: Final = ProviderUsageFactRepository(prisma_client)
    counts: Final = MappingProxyType(
        {provider: await facts.counts_by_credential(provider) for provider in sorted(BILLING_PROVIDERS)}
    )
    connections: Final = await build_provider_connections(
        providers=sorted(BILLING_PROVIDERS),
        credentials_for=build_billing_credentials_lookup(prisma_client=prisma_client),
        recent_runs=await ProviderSyncRunRepository(prisma_client).recent(limit=RUNS_FOR_STATE),
        fact_counts_for=lambda provider: counts[provider],
    )

    missing_invoices: Final = await repository.providers_missing_invoice(start, end)
    issues: Final = data_quality_issues(
        connection_states=tuple(
            account.state for connection in connections.providers for account in connection.accounts
        ),
        missing_invoices=missing_invoices,
        keys_without_project=await repository.keys_without_project(),
    )
    coverage: Final = invoice_coverage(
        providers_billed=await repository.providers_billing(start, end),
        providers_missing_invoice=missing_invoices,
    )

    return DataQualityResponse(
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        invoice_coverage=coverage_to_wire(coverage),
        issues=tuple(to_wire(issue) for issue in issues),
        issues_to_fix=issues_to_fix(issues),
    )
