# Project Spend Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a project's spend a real number, so project budgets enforce and project cost screens read a rollup instead of scanning raw spend logs.

**Architecture:** Projects already exist as a first-class entity: keys carry a `project_id` column, `LiteLLM_ProjectTable` has `spend` and `budget_id`, `Litellm_EntityType.PROJECT` is in the enum, and `auth_checks` already refuses a project that is over budget. The one missing piece is the write path. Nothing increments `LiteLLM_ProjectTable.spend`, so the budget check reads a value frozen at zero, and there is no `LiteLLM_DailyProjectSpend` to answer what a project cost last week. Both gaps close by threading `project_id` from the auth object into the existing spend write path and registering the project as one more entity in two dispatch maps that are already generic.

**Tech Stack:** FastAPI, Prisma/Postgres, pytest

**Spec:** the org hierarchy design, organisation -> teams -> {projects, employees}, where a project is machine usage (chats, embeddings, bots) and an employee is human usage

## Global Constraints

Terminology throughout code, endpoints, docs and UI copy: **organisation**, **team**, **project**, **employee**. A project belongs to exactly one team; a team belongs to one organisation. Never say "sub-team" or "workspace" for a project.

Prisma migrations may only change schema, never rewrite rows. No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`, enforced by `tests/code_coverage_tests/check_migrations_no_data_rewrites.py`.

Python max line length 120. All work runs in `C:\Users\NikhilEruva\litellm\.venv`, never system Python.

Every new variable annotated `: Final` (LIT010). Every new TypedDict field qualified `ReadOnly[...]` (LIT012) unless a writable field is genuinely unavoidable.

No comments unless they explain genuinely complex business logic.

---

### Task 1: Cumulative project spend, so project budgets actually enforce

The bug: `auth_checks._project_max_budget_check` (`litellm/proxy/auth/auth_checks.py:5309`) compares `project_object.spend` against the budget, and `LiteLLM_ProjectTable.spend` is never written by anything. A project with a $10 budget can spend unbounded.

**Files:**
- Modify: `litellm/proxy/_types.py` (add `project_list_transactions` to `DBSpendUpdateTransactions`, around line 5002)
- Modify: `litellm/proxy/db/db_transaction_queue/spend_update_queue.py` (register `PROJECT` in `entity_type_to_dict_key` around line 146, and in the empty-dict seed around line 140)
- Modify: `litellm/proxy/db/db_spend_update_writer.py` (add `_update_project_db`, the flush block, and thread `project_id` through `update_database`)
- Modify: `litellm/proxy/hooks/proxy_track_cost_callback.py` (pass `project_id` at both call sites)
- Test: `tests/test_litellm/proxy/db/test_db_spend_update_writer.py`

**Interfaces:**
- Consumes: `UserAPIKeyAuth.project_id` (already populated at auth time), `Litellm_EntityType.PROJECT`, and the existing generic `DBSpendUpdateWriter._update_entity_spend_in_db(entity_name, transactions, table_accessor, where_field, n_retry_times, prisma_client, proxy_logging_obj)`
- Produces: `DBSpendUpdateWriter._update_project_db(response_cost: float | None, project_id: str | None, prisma_client: PrismaClient | None) -> None`, and `update_database(..., project_id: str | None = None)`

- [ ] **Step 1: Write the failing test**

Two things to prove: a project id enqueues a PROJECT update, and a request on a project key reaches the ledger the budget check reads.

```python
async def test_project_spend_is_enqueued_against_the_project_ledger():
    writer = DBSpendUpdateWriter()
    await writer._update_project_db(
        response_cost=0.25,
        project_id="proj-alpha",
        prisma_client=_FakePrismaClient(),
    )
    transactions = await writer.spend_update_queue.flush_and_get_aggregated_db_spend_update_transactions()
    assert transactions["project_list_transactions"] == {"proj-alpha": 0.25}


async def test_a_request_on_a_project_key_moves_that_projects_spend():
    """The point of the whole task: the budget check in auth_checks reads exactly this
    column, so a request that does not move it is a budget that never fires."""
    writer = DBSpendUpdateWriter()
    await writer.update_database(
        token="sk-test",
        user_id="u1",
        end_user_id=None,
        team_id="team-1",
        org_id=None,
        project_id="proj-alpha",
        kwargs={},
        completion_response=None,
        start_time=None,
        end_time=None,
        response_cost=0.4,
    )
    transactions = await writer.spend_update_queue.flush_and_get_aggregated_db_spend_update_transactions()
    assert transactions["project_list_transactions"] == {"proj-alpha": 0.4}
```

Read the existing tests in that file first and reuse their fixtures for the fake prisma client rather than inventing a new one.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/db/test_db_spend_update_writer.py -k project -v`

Expected: FAIL, with `AttributeError` on `_update_project_db` and `TypeError: unexpected keyword argument 'project_id'`

- [ ] **Step 3: Register the project as a spend entity**

In `litellm/proxy/_types.py`, `DBSpendUpdateTransactions`:

```python
    project_list_transactions: ReadOnly[dict[str, float] | None]
```

In `spend_update_queue.py`, add to the empty-dict seed and to the dispatch map:

```python
            project_list_transactions={},
```

```python
            Litellm_EntityType.PROJECT: "project_list_transactions",
```

- [ ] **Step 4: Enqueue and flush**

In `db_spend_update_writer.py`, mirroring `_update_org_db`:

```python
    async def _update_project_db(
        self,
        response_cost: float | None,
        project_id: str | None,
        prisma_client: PrismaClient | None,
    ) -> None:
        if project_id is None or prisma_client is None:
            return
        try:
            await self.spend_update_queue.add_update(
                update=SpendUpdateQueueItem(
                    entity_type=Litellm_EntityType.PROJECT,
                    entity_id=project_id,
                    response_cost=response_cost,
                )
            )
        except Exception as e:
            spend_log_error(
                "Spend tracking - failed to enqueue project spend update. project_id=%s, response_cost=%s - %s",
                project_id,
                response_cost,
                str(e),
                exc=e,
            )
```

In the flush, next to the tag block, using the generic helper that is already there:

```python
        ### UPDATE PROJECT TABLE ###
        project_list_transactions: Final = db_spend_update_transactions["project_list_transactions"]
        await DBSpendUpdateWriter._update_entity_spend_in_db(
            entity_name="Project",
            transactions=project_list_transactions,
            table_accessor="litellm_projecttable",
            where_field="project_id",
            n_retry_times=n_retry_times,
            prisma_client=prisma_client,
            proxy_logging_obj=proxy_logging_obj,
        )
```

- [ ] **Step 5: Thread project_id from the request**

Add `project_id: str | None = None` to `update_database`, and call `await self._update_project_db(response_cost=response_cost, project_id=project_id, prisma_client=prisma_client)` alongside the existing `_update_team_db` call.

At both `proxy_track_cost_callback.py` call sites, pass `project_id=user_api_key_dict.project_id`. The second site goes through `_update_database_and_spend_counters`, so add `project_id: str | None` to that signature too and pass it from its caller near line 295.

- [ ] **Step 6: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/db/test_db_spend_update_writer.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix(spend): increment project spend so project budgets enforce"
```

---

### Task 2: The LiteLLM_DailyProjectSpend table

Every other entity has a daily rollup. Without one, a project cost screen scans raw spend logs.

**Files:**
- Modify: `schema.prisma` (new model after `LiteLLM_DailyTeamSpend`, around line 976)
- Create: `litellm/proxy/db/migrations/<timestamp>_add_daily_project_spend/migration.sql`

**Interfaces:**
- Produces: table `LiteLLM_DailyProjectSpend`, unique constraint on `[project_id, date, api_key, model, custom_llm_provider, mcp_namespaced_tool_name, endpoint]`, matching the team table's constraint with `team_id` swapped out

- [ ] **Step 1: Copy the team model, swap the entity column**

Read `LiteLLM_DailyTeamSpend` in `schema.prisma` in full and reproduce it exactly with `team_id` replaced by `project_id`, including every counter column, every savings column, and every index. A column the team table has and this one lacks will silently drop data at upsert time, because `daily_spend_bulk_upsert` builds its statement from the transaction's keys, not from a fixed list.

- [ ] **Step 2: Generate the migration**

```bash
.venv/Scripts/python -m prisma migrate dev --name add_daily_project_spend --create-only --schema schema.prisma
```

- [ ] **Step 3: Verify the migration only creates**

Run: `.venv/Scripts/python tests/code_coverage_tests/check_migrations_no_data_rewrites.py`

Expected: PASS. The generated SQL must be `CREATE TABLE` plus `CREATE INDEX` only, with no `UPDATE` and no `INSERT ... SELECT`.

- [ ] **Step 4: Apply and confirm against the live database**

```bash
.venv/Scripts/python -m prisma migrate deploy --schema schema.prisma
docker exec tokeniq_db psql -U llmproxy -d litellm -c '\d "LiteLLM_DailyProjectSpend"'
```

Expected: the table exists with the same columns as `LiteLLM_DailyTeamSpend` and a `project_id` where `team_id` was.

- [ ] **Step 5: Commit**

```bash
git add schema.prisma litellm/proxy/db/migrations
git commit -m "feat(schema): add LiteLLM_DailyProjectSpend"
```

---

### Task 3: Write the daily project rollup

**Files:**
- Modify: `litellm/proxy/_types.py` (`DailyProjectSpendTransaction`)
- Modify: `litellm/proxy/db/daily_spend_bulk_upsert.py` (the `DailySpendEntity` literal and `DAILY_SPEND_TABLES`)
- Modify: `litellm/proxy/db/db_spend_update_writer.py` (queue, enqueue, flush)
- Modify: `litellm/proxy/db/db_transaction_queue/redis_update_buffer.py` (carry the new queue across pods)
- Test: `tests/test_litellm/proxy/db/test_daily_spend_bulk_upsert.py`

**Interfaces:**
- Consumes: `DailySpendTable(name, entity_id_column, carries_request_id)` and the table from Task 2, plus `Litellm_EntityType.PROJECT` from Task 1
- Produces: `DBSpendUpdateWriter.daily_project_spend_update_queue: DailySpendUpdateQueue`, `DBSpendUpdateWriter.update_daily_project_spend(...)`, and `DailyProjectSpendTransaction(BaseDailySpendTransaction)` carrying `project_id: str`

- [ ] **Step 1: Write the failing test**

```python
def test_the_project_rollup_upserts_against_the_project_table():
    statement = build_daily_spend_upsert(
        entity="project",
        rows=[
            {
                "project_id": "proj-alpha",
                "date": "2026-09-13",
                "api_key": "hk",
                "model": "gpt-4o",
                "spend": 0.5,
                "api_requests": 1,
                "successful_requests": 1,
            }
        ],
    )
    assert '"LiteLLM_DailyProjectSpend"' in statement.sql
    assert '"project_id"' in statement.sql
```

Match the call shape to whatever the builder in `daily_spend_bulk_upsert.py` is actually named and actually takes: read the existing team test in that file and mirror it rather than trusting the sketch above.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/db/test_daily_spend_bulk_upsert.py -k project -v`

Expected: FAIL on the unknown entity `"project"`

- [ ] **Step 3: Register the table**

```python
DailySpendEntity = Literal["user", "team", "project", "org", "tag", "end_user", "agent"]
```

```python
        "project": DailySpendTable(name="LiteLLM_DailyProjectSpend", entity_id_column="project_id"),
```

- [ ] **Step 4: Add the transaction type**

In `_types.py`, next to `DailyTeamSpendTransaction`:

```python
class DailyProjectSpendTransaction(BaseDailySpendTransaction):
    project_id: str
```

- [ ] **Step 5: Wire the queue**

In `DBSpendUpdateWriter.__init__`, alongside `self.daily_team_spend_update_queue`:

```python
        self.daily_project_spend_update_queue = DailySpendUpdateQueue()
```

Add `add_spend_log_transaction_to_daily_project_transaction` and `update_daily_project_spend` by mirroring the team pair exactly, and call the enqueue from `_batch_database_updates` next to the team call, guarding on the project id being present.

The project id at that point comes from the payload's metadata field `user_api_key_project_id`, which `get_logging_payload` already emits on every row. Prefer the explicit `project_id` threaded in Task 1 wherever it is in scope, so the daily rollup and the cumulative ledger cannot disagree about which project a request belonged to.

- [ ] **Step 6: Carry it across pods**

`redis_update_buffer.py` names each daily queue explicitly in about eight places: the constant lists near lines 69 and 81, then the flush signature, the store, and the restore. Add the project queue to every one. A queue added to the writer but missed here silently loses rollup rows whenever more than one pod is running, which is exactly the kind of bug that shows up only in production.

- [ ] **Step 7: Run the suite**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/db/ -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(spend): roll daily spend up per project"
```

---

### Task 4: GET /project/daily/activity

**Files:**
- Modify: `litellm/proxy/management_endpoints/project_endpoints.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py`

**Interfaces:**
- Consumes: `get_daily_activity(prisma_client, table_name, entity_id_field, entity_id, entity_metadata_field, start_date, end_date, model, api_key, page, page_size, exclude_entity_ids=None, ...) -> SpendAnalyticsPaginatedResponse` from `common_daily_activity.py:1198`, and `_authorised_project_or_403` already in `project_endpoints.py`
- Produces: `GET /project/daily/activity`

- [ ] **Step 1: Write the failing test**

The read obeys the same rule as the rest of the project routes: whoever administers the team administers its projects, and a caller with no relationship to the team is refused rather than shown an empty result, because an empty result hides the permissions problem from whoever has to debug it.

```python
async def test_daily_activity_refuses_a_caller_who_does_not_administer_the_team():
    with pytest.raises(HTTPException) as caught:
        await get_project_daily_activity(
            project_id="proj-alpha",
            user_api_key_dict=_a_key_on_another_team(),
        )
    assert caught.value.status_code == 403
```

Mirror the fixtures already in this file rather than inventing new ones.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -k daily -v`

Expected: FAIL, name not defined

- [ ] **Step 3: Add the route**

```python
@router.get(
    "/project/daily/activity",
    response_model=SpendAnalyticsPaginatedResponse,
    tags=["project management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_project_daily_activity(
    project_id: str = fastapi.Query(description="The project to report on"),
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """What one project spent, by day."""
    prisma_client: Final = _prisma_or_500()
    project: Final = await _authorised_project_or_403(project_id, user_api_key_dict, prisma_client, write=False)
    return await get_daily_activity(
        prisma_client=prisma_client,
        table_name="litellm_dailyprojectspend",
        entity_id_field="project_id",
        entity_id=project_id,
        entity_metadata_field={project_id: {"project_alias": project.project_alias}},
        start_date=start_date,
        end_date=end_date,
        model=model,
        api_key=api_key,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_litellm/proxy/management_endpoints/test_project_endpoints.py -v`

Expected: PASS

- [ ] **Step 5: Prove it end to end against a live proxy**

Start the proxy, create a project under a team, assign a key to it, send one real request, then read both numbers back. The gateway-measured cost on that key has to appear against the project in both places.

```bash
curl -s -X POST localhost:4000/project/new -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' -d '{"project_alias":"rollup-check","team_id":"<team>"}'
curl -s "localhost:4000/project/info?project_id=<project>" -H "Authorization: Bearer $LITELLM_MASTER_KEY"
curl -s "localhost:4000/project/daily/activity?project_id=<project>" -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

Expected: `/project/info` shows a non-zero `spend` from Task 1, and `/project/daily/activity` shows one day carrying the same figure from Task 3. If the two disagree, the daily enqueue and the cumulative enqueue are reading different project ids.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(project): report daily project spend"
```
