"""Reconciliation: a daily-activity summary must describe the query, not the page.

The existing daily-activity tests pin response *shape*, so a totals field can be
wrong by any factor and still pass. These cases pin the *values*.

`metadata.total_spend` and its sibling totals feed the Usage dashboard's summary
tiles directly (`entityUsageSummary.ts` -> `buildSummaryTiles`), so whatever the
gateway reports there is the number a customer reads first. `get_daily_activity`
builds those totals by aggregating `daily_spend_data`, which is one page of rows
(`skip=(page - 1) * page_size, take=page_size`), while `total_pages` is derived
from the unpaginated `total_count`. A summary computed over one page but labelled
as the total is wrong whenever the query spans more than one page, and wrong by a
different amount for every page size. When page one happens to hold a zero-spend
row, the dashboard reports no spend at all against a tenant that has spent money.

The totals are read at two page sizes over the same window rather than by walking
every page, so the cost is three requests whether the tenant has five rows or five
million.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

import pytest
from pydantic import BaseModel
from spend_e2e_client import SpendClient, unique_marker, unwrap

pytestmark = pytest.mark.e2e

DRIVER_MODEL: Final = "gemini-2.5-flash"
NARROW_PAGE: Final = 1
WIDE_PAGE: Final = 1000
WINDOW_DAYS: Final = 30
SPEND_TOLERANCE: Final = 1e-9

ROUTES: Final = ("/tag/daily/activity", "/user/daily/activity", "/team/daily/activity")


class DailyActivityParams(BaseModel):
    start_date: str
    end_date: str
    page: int
    page_size: int


class DailyActivityMetadata(BaseModel):
    total_spend: float
    total_api_requests: int
    page: int
    total_pages: int
    has_more: bool


class DailyActivityResponse(BaseModel):
    metadata: DailyActivityMetadata


def _totals(client: SpendClient, route: str, *, page: int, page_size: int) -> DailyActivityMetadata:
    end: Final = datetime.now(timezone.utc).date()
    result: Final = client.proxy.transport.probe(
        route,
        params=DailyActivityParams(
            start_date=(end - timedelta(days=WINDOW_DAYS)).isoformat(),
            end_date=end.isoformat(),
            page=page,
            page_size=page_size,
        ),
    )
    assert result.status_code == 200, f"{route} page={page} must be 200, got {result.status_code}: {result.body[:600]}"
    return DailyActivityResponse.model_validate_json(result.body).metadata


def _whole_window(client: SpendClient, route: str) -> DailyActivityMetadata:
    """The authoritative totals: one page wide enough to hold the window."""
    totals: Final = _totals(client, route, page=1, page_size=WIDE_PAGE)
    assert totals.total_pages == 1, (
        f"{route} needs more than {WIDE_PAGE} rows for a {WINDOW_DAYS}-day window "
        f"({totals.total_pages} pages), so no single page holds the true total; narrow WINDOW_DAYS"
    )
    return totals


@pytest.fixture
def recorded_traffic(client: SpendClient, scoped_key: str) -> str:
    """Two priced calls on one key, so every route below spans more than one page."""
    marker: Final = unique_marker()
    for _ in range(2):
        unwrap(client.chat(scoped_key, DRIVER_MODEL, f"reply with the single word {marker}", max_tokens=16))
    rows: Final = client.poll_logs_for_key(scoped_key, min_rows=2)
    assert len(rows) >= 2, f"expected 2 spend rows for the reconciliation key, saw {len(rows)}"
    return marker


@pytest.mark.usefixtures("recorded_traffic")
class TestDailyActivityTotalsReconcile:
    @pytest.mark.covers("quota_management.spend_tracking.daily_activity.totals_cover_every_page")
    @pytest.mark.parametrize("route", ROUTES)
    def test_paged_totals_match_the_whole_window(self, client: SpendClient, route: str) -> None:
        whole: Final = _whole_window(client, route)
        paged: Final = _totals(client, route, page=1, page_size=NARROW_PAGE)
        assert paged.total_pages > 1, (
            f"{route} fits in one page at page_size={NARROW_PAGE}, so this invariant is not exercised"
        )

        assert abs(paged.total_spend - whole.total_spend) < SPEND_TOLERANCE, (
            f"{route} reports total_spend={paged.total_spend} when served {NARROW_PAGE} row per page, "
            f"but {whole.total_spend} for the same window in one page. The summary describes the page "
            "it arrived on rather than the query, so the Usage dashboard's total moves with page size"
        )
        assert paged.total_api_requests == whole.total_api_requests, (
            f"{route} reports total_api_requests={paged.total_api_requests} at page_size={NARROW_PAGE} "
            f"but {whole.total_api_requests} for the same window in one page"
        )
