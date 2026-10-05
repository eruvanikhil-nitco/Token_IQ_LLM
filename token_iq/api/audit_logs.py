"""Reading the audit trail.

`LiteLLM_AuditLog` records who created, changed or deleted a key, team, model or user, with a
full snapshot either side of the change. Writing it is in the MIT core; nothing here reads it,
so the rows accumulate where only someone with database access can see them.

This is a fresh implementation against that table. The upstream reader was enterprise-licensed
and is not the basis for any of it.

What it deliberately returns is the *diff* rather than the raw snapshots: see `audit_log_diff`
for why two forty-field blobs answer nobody's question.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

import fastapi
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from token_iq.api.audit_log_diff import FieldChange, diff_snapshots, summarise

router: Final = fastapi.APIRouter(tags=["audit"])

MAX_PAGE_SIZE: Final = 200


class AuditEntry(BaseModel):
    """One recorded change, as the table renders it."""

    id: str
    changed_at: datetime
    action: str = Field(description="created, updated or deleted")
    table_name: str = Field(description="Which kind of object changed")
    object_id: str = Field(description="The id of the object that changed")
    changed_by: str = Field(description="Who made the change")
    summary: str = Field(description="One line naming the fields that moved")
    changes: list[FieldChange] = Field(  # writable-ok: FastAPI serialises the response model directly
        default_factory=list,
        description="Field level before and after, with secrets redacted",
    )


class AuditListResponse(BaseModel):
    entries: list[AuditEntry]  # writable-ok: FastAPI serialises the response model directly
    total: int = Field(description="Rows matching the filters, before paging")
    page: int
    size: int


def build_where(
    table_name: str | None = None,
    action: str | None = None,
    object_id: str | None = None,
    changed_by: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, object]:
    """The Prisma filter for a query.

    Absent filters are omitted rather than passed as None, because a None in a Prisma where
    clause matches rows whose column is null instead of matching everything.
    """
    updated_at: Final = {
        **({"gte": start_date} if start_date is not None else {}),
        **({"lte": end_date} if end_date is not None else {}),
    }
    return {
        **({"table_name": table_name} if table_name else {}),
        **({"action": action} if action else {}),
        **({"object_id": object_id} if object_id else {}),
        **({"changed_by": changed_by} if changed_by else {}),
        **({"updated_at": updated_at} if updated_at else {}),
    }


def to_entry(row: object, include_noise: bool = False) -> AuditEntry:
    """One database row as an API entry, with the diff computed and secrets stripped."""
    changes: Final = diff_snapshots(
        getattr(row, "before_value", None),
        getattr(row, "updated_values", None),
        include_noise=include_noise,
    )
    return AuditEntry(
        id=str(getattr(row, "id", "")),
        changed_at=getattr(row, "updated_at", None) or datetime.min,
        action=str(getattr(row, "action", "") or ""),
        table_name=str(getattr(row, "table_name", "") or ""),
        object_id=str(getattr(row, "object_id", "") or ""),
        changed_by=str(getattr(row, "changed_by", "") or ""),
        summary=summarise(changes),
        changes=changes,
    )


@router.get(
    "/audit/list",
    description="Recorded changes to keys, teams, models and users, newest first",
    dependencies=[Depends(user_api_key_auth)],  # mutable-ok: fastapi's decorator types dependencies as a list
    response_model=AuditListResponse,
)
async def list_audit_logs(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
    table_name: str | None = fastapi.Query(None, description="Only changes to this kind of object"),
    action: Literal["created", "updated", "deleted"] | None = fastapi.Query(None),
    object_id: str | None = fastapi.Query(None, description="Only changes to this object"),
    changed_by: str | None = fastapi.Query(None, description="Only changes made by this user"),
    start_date: datetime | None = fastapi.Query(None),
    end_date: datetime | None = fastapi.Query(None),
    page: int = fastapi.Query(1, ge=1),
    size: int = fastapi.Query(50, ge=1, le=MAX_PAGE_SIZE),
    include_noise: bool = fastapi.Query(
        False, description="Include fields that move on every write, such as updated_at"
    ),
) -> AuditListResponse:
    """
    The audit trail, newest first.

    Requires `store_audit_logs` to be enabled; without it the table is simply empty rather
    than an error, because "nothing has been recorded yet" and "recording is off" look the
    same from here and the settings page is the place that knows the difference.
    """
    if user_api_key_dict.user_role not in (LitellmUserRoles.PROXY_ADMIN, LitellmUserRoles.PROXY_ADMIN_VIEW_ONLY):
        raise HTTPException(status_code=403, detail={"error": "Only proxy admins can read the audit trail"})
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(status_code=500, detail={"error": "No database connected"})

    where: Final = build_where(table_name, action, object_id, changed_by, start_date, end_date)

    total: Final = await prisma_client.db.litellm_auditlog.count(where=where)
    rows: Final = await prisma_client.db.litellm_auditlog.find_many(
        where=where,
        order={"updated_at": "desc"},
        skip=(page - 1) * size,
        take=size,
    )

    return AuditListResponse(
        entries=[to_entry(row, include_noise=include_noise) for row in rows],
        total=total,
        page=page,
        size=size,
    )
