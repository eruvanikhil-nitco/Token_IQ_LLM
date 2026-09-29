# Seats and Total Cost Per User Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show what one person costs the company, counting the gateway traffic they drove and the flat subscriptions assigned to them, and say plainly which part is still missing.

**Architecture:** A seat is a flat per-person fee an admin enters, the same way an invoice is, because seat pricing lives on a contract rather than behind an API. Gateway spend per user already exists in `LiteLLM_DailyUserSpend`. A pure function adds the two into one total per person, keeping each part separately visible so nobody has to trust a single blended number. Tool usage, the third part, is deliberately absent and named as absent.

**Tech Stack:** Python 3.12, FastAPI, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, Phase 4, plus `docs/superpowers/specs/2026-09-14-user-tools-data-research.md`

## Why this slice, and not the connectors

Phase 4 as written is the user tool connectors, the User Directory, seats, and the Tools and Seats tabs. This plan builds the part that can be proven correct on this machine and defers the part that cannot.

**There is no real account for any user tool, and none for five of the six providers.** Everything this branch has learned says that matters. Running against real infrastructure found five defects that fully green test suites had missed: a query that could not execute because a column was text, a filter that reported zero for the only provider with data, an endpoint that failed because a client was never regenerated, a reader that rejected every real row because timestamps arrive as strings, and a cursor that broke only on the second page. Writing four more vendor connectors from documentation would add four more integrations in that same unproven state, and their defects would be invisible until a customer's numbers were wrong.

Seats need no vendor API at all. An admin reads the subscription off a contract and types it in, exactly as they do with an invoice. That makes this slice fully verifiable today, and it delivers half of Phase 4's completion test on its own.

**Built here:** seat storage, seat assignment to a user, per-user total cost combining gateway spend and seats, the Seats tab on a user, and the Ledger's deferred Seats & Commitments tab.

**Deferred until an account exists:** the Claude Code, Copilot, Cursor and Codex connectors, the User Tools data-source page, the User Directory identity linking, and the Tools tab on a user. Task 7 records each, so nobody reads their absence as an oversight.

## Global Constraints

- Money is `Decimal` end to end and must never pass through `float`. Every summed money column leaves Postgres cast `::text`, because `prisma-client-py` decodes a bare `numeric` as a float
- A person's total is always shown with its parts, never as one blended figure. A reader must be able to see how much is gateway traffic and how much is a subscription
- The missing third part, tool usage, is named on the screen. A total that silently excludes it would be read as complete
- Every cost keeps the currency it was written in. A seat priced in euros is never silently added to dollars
- The hierarchy is teams, projects and users. Never "employees"
- Users see only their own cost and team admins see their team, per the spec's privacy rule. Enforce it in the endpoint, not only in the UI
- Never remove, merge or rename an existing UI tab. Adding one is fine
- Prisma migrations change schema only. No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`. All three schema copies stay byte-identical; CI diffs them
- Repositories use raw parameterised SQL, like every other new billing table here, because the generated client needs `prisma generate`, which is blocked on this machine
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), `ReadOnly[...]` on TypedDict fields (LIT012), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a genuine last resort with a true reason
- Every lint or type suppression names its exact rule in brackets and carries a real reason. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME with a strong reason. Never add a constant or export whose only purpose is to carry a comment
- Tests must test function, never structure, and must fail when the behaviour is mutated
- No customer-visible LiteLLM branding, no company or customer names, no secrets, no `eval`, no `shell=True`
- Python max line length 120. TypeScript has no `any`, no tokens in `localStorage`
- Never run the full dashboard vitest suite with no path. Never run `python -m pytest`; use `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main([...]))"`
- Python is always `C:\Users\NikhilEruva\litellm\.venv\Scripts\python.exe`. The proxy starts only with `bash ~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234`)
- `npm run gen:api` needs the venv on PATH: `PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" npm run gen:api`
- A new sidebar entry, its route in `migratedPages.ts`, and the expected group list in `leftnav.test.tsx` all change in the same commit. A menu entry without a route renders and leads nowhere, and that test exists because it already happened once
- Conventional-commits messages, no Claude attribution or `Co-Authored-By` trailer

## The rule this plan must not break

A seat is a fee for a period, not for a day. Spreading a monthly subscription across days to make it add up alongside daily gateway spend would invent a daily figure the company was never charged. Seats are held and reported per period, and a total that mixes them says which period it covers.

---

### Task 1: Store a seat

**Files:**
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260930000000_user_seat/migration.sql`
- Modify: `schema.prisma`, `litellm/proxy/schema.prisma`, `litellm-proxy-extras/litellm_proxy_extras/schema.prisma`
- Create: `litellm/types/proxy/seat.py`
- Create: `litellm/repositories/seat_repository.py`
- Test: `tests/test_litellm/repositories/test_seat_repository.py`

**Interfaces:**
- Produces:
  - `SeatCadence = Literal["monthly", "annual"]`
  - `@dataclass(frozen=True, slots=True) class Seat: seat_id: str; tool: str; user_id: str; cadence: SeatCadence; currency: str; amount: Decimal; period_start: datetime; period_end: datetime; note: str | None`
  - `SeatRepository(db)` with `async def upsert(self, seat: Seat) -> Seat | None`, `async def for_period(self, *, period_start: datetime, period_end: datetime) -> tuple[Seat, ...]`, `async def all(self) -> tuple[Seat, ...]`, `async def delete(self, seat_id: str) -> bool`

```prisma
// One flat per-person subscription for one period, entered by an admin because seat pricing
// lives on a contract rather than behind an API.
model LiteLLM_UserSeat {
    seat_id      String   @id @default(uuid())
    tool         String
    user_id      String
    cadence      String   // monthly | annual
    currency     String   @default("USD")
    amount       String   // exact digits as text; prisma-client-py gates Decimal behind an experimental flag
    period_start DateTime
    period_end   DateTime
    note         String?
    created_at   DateTime @default(now())
    updated_at   DateTime @updatedAt

    @@unique([tool, user_id, period_start, period_end])
    @@index([user_id, period_start])
}
```

The unique constraint makes re-entering a corrected seat an update rather than a second charge for the same person, tool and period. That is the same shape the invoice table uses and for the same reason.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_a_seat_round_trips_with_its_tool_and_person() -> None:
    repo, _ = _repo([_stored()])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.tool == "claude-code"
    assert saved.user_id == "u-1"
    assert saved.amount == Decimal("30.00")


@pytest.mark.asyncio
async def test_the_amount_is_exact_to_the_last_digit_the_contract_showed() -> None:
    repo, _ = _repo([_stored(amount="30.123456789012345")])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.amount == Decimal("30.123456789012345")


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_stored(amount=30.0)])
    assert await repo.upsert(SEAT) is None


@pytest.mark.asyncio
async def test_a_cadence_we_do_not_know_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(cadence="fortnightly")])
    assert await repo.all() == ()


@pytest.mark.asyncio
async def test_a_timestamp_returned_as_an_iso_string_is_read_not_rejected() -> None:
    repo, _ = _repo([_stored(period_start="2026-09-01T00:00:00+00:00")])
    saved: Final = await repo.upsert(SEAT)
    assert saved is not None
    assert saved.period_start == START


@pytest.mark.asyncio
async def test_re_entering_a_persons_seat_corrects_it_rather_than_charging_twice() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(SEAT)
    assert "ON CONFLICT (tool, user_id, period_start, period_end)" in db.last_sql


@pytest.mark.asyncio
async def test_the_note_is_bound_as_a_parameter_never_interpolated() -> None:
    hostile: Final = "x'; DROP TABLE \"LiteLLM_UserSeat\"; --"
    repo, db = _repo([_stored()])
    await repo.upsert(replace(SEAT, note=hostile))
    assert hostile not in db.last_sql
    assert hostile in db.last_args
```

The ISO-string test is not optional. Raw queries hand Postgres timestamps back as strings, and the invoice repository passed fifteen unit tests while rejecting every real row because it required a `datetime`.

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/repositories/test_seat_repository.py']))"`
Expected: FAIL with "No module named 'litellm.repositories.seat_repository'"

- [ ] **Step 3: Write the types, the schema, the migration and the repository**

Follow `litellm/repositories/invoice_repository.py` closely: it is the same shape, including the `_datetime_or_none` helper and the float refusal.

- [ ] **Step 4: Sync the three schema copies and confirm both diffs are empty**

```bash
cp schema.prisma litellm/proxy/schema.prisma
cp schema.prisma litellm-proxy-extras/litellm_proxy_extras/schema.prisma
diff schema.prisma litellm/proxy/schema.prisma && diff schema.prisma litellm-proxy-extras/litellm_proxy_extras/schema.prisma
```

- [ ] **Step 5: Run the tests, then mutate each behaviour and confirm a test dies**

Assert each search string occurs exactly once before mutating.

- [ ] **Step 6: Apply the migration and prove the repository against real Postgres**

```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm -v ON_ERROR_STOP=1 --single-transaction \
  < litellm-proxy-extras/litellm_proxy_extras/migrations/20260930000000_user_seat/migration.sql
```

Then drive the repository directly against the database: store a seat, correct it and confirm one row with the same id, read it back by period, and put a hostile string in the note and confirm the table survives. A fake database has now hidden five defects on this branch; this step is where they surface.

- [ ] **Step 7: Commit**

```bash
git add schema.prisma litellm/proxy/schema.prisma litellm-proxy-extras/litellm_proxy_extras litellm/types/proxy/seat.py litellm/repositories/seat_repository.py tests/test_litellm/repositories/test_seat_repository.py
git commit -m "feat(seats): store a flat per-person subscription for a period"
```

---

### Task 2: Read gateway spend per person

**Files:**
- Modify: `litellm/repositories/gateway_spend_repository.py`
- Test: `tests/test_litellm/repositories/test_gateway_spend_repository.py`

**Interfaces:**
- Produces: `GatewaySpendRepository.by_user_for_period(self, *, period_start: datetime, period_end: datetime) -> Mapping[str, Decimal]`, keyed by user id

The existing `by_dimension` groups by a fixed window in days. A person's cost is asked for over a period with a start and an end, because a seat covers a period. Add the period-shaped read rather than bending the day-count one.

`LiteLLM_DailyUserSpend.date` is TEXT holding `YYYY-MM-DD`, not a date. Compare it as text with `to_char`, exactly as the existing statements do: casting the column to `date` makes Postgres refuse the comparison outright, which is a defect a fake database cannot show.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_spend_comes_back_per_person_and_exact() -> None:
    repo, db = _repo([{"key": "u-1", "gateway_cost": "0.30000000000000004"}])
    spend: Final = await repo.by_user_for_period(period_start=START, period_end=END)
    assert spend["u-1"] == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_the_period_is_bound_as_text_because_the_date_column_is_text() -> None:
    repo, db = _repo([{"key": "u-1", "gateway_cost": "1"}])
    await repo.by_user_for_period(period_start=START, period_end=END)
    assert db.last_args == ("2026-09-01", "2026-09-30")
    assert "d.date::date" not in db.last_sql


@pytest.mark.asyncio
async def test_a_row_with_no_person_is_left_out_rather_than_grouped_under_blank() -> None:
    repo, _ = _repo([{"key": "", "gateway_cost": "5"}, {"key": "u-1", "gateway_cost": "5"}])
    assert tuple(await repo.by_user_for_period(period_start=START, period_end=END)) == ("u-1",)
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Write the query, then run the tests**

- [ ] **Step 4: Prove it against real Postgres, printing the per-person totals**

The live database has two users in `LiteLLM_DailyUserSpend`. Cross-check that the per-person figures sum to the same total the existing `by_dimension(dimension="user")` reports for the same window, and say so in your report. Two independent reads agreeing is the evidence; either alone is not.

- [ ] **Step 5: Commit**

---

### Task 3: Add a person's parts into one total

**Files:**
- Create: `litellm/seats/user_cost.py`
- Create: `litellm/seats/__init__.py`
- Test: `tests/test_litellm/seats/test_user_cost.py`

**Interfaces:**
- Consumes: `Seat` from Task 1
- Produces:
  - `@dataclass(frozen=True, slots=True) class SeatLine: tool: str; currency: str; amount: Decimal`
  - `@dataclass(frozen=True, slots=True) class UserCost: user_id: str; currency: str; gateway: Decimal; seats: Decimal; total: Decimal; seat_lines: tuple[SeatLine, ...]; tool_usage_known: bool`
  - `def user_costs(*, gateway_by_user: Mapping[str, Decimal], seats: Sequence[Seat], currency: str) -> tuple[UserCost, ...]`

A pure function. No database, no clock.

`tool_usage_known` is always `False` in this plan and exists so the screen can say the total is incomplete rather than imply it is whole. It is not speculative plumbing: the screen reads it in Task 5, and a test asserts it.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_persons_total_is_their_gateway_spend_plus_their_seats() -> None:
    result = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(SEAT_30,), currency="USD")
    assert result[0].gateway == Decimal("10")
    assert result[0].seats == Decimal("30")
    assert result[0].total == Decimal("40")


def test_the_parts_stay_visible_so_nobody_has_to_trust_one_blended_number() -> None:
    result = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(SEAT_30,), currency="USD")
    assert result[0].seat_lines[0].tool == "claude-code"
    assert result[0].seat_lines[0].amount == Decimal("30")


def test_a_person_with_a_seat_and_no_gateway_traffic_still_costs_money() -> None:
    result = user_costs(gateway_by_user={}, seats=(SEAT_30,), currency="USD")
    assert result[0].gateway == Decimal(0)
    assert result[0].total == Decimal("30")


def test_a_person_with_traffic_and_no_seat_is_not_given_one() -> None:
    result = user_costs(gateway_by_user={"u-2": Decimal("5")}, seats=(), currency="USD")
    assert result[0].seats == Decimal(0)
    assert result[0].seat_lines == ()


def test_a_seat_in_another_currency_is_left_out_rather_than_added_to_dollars() -> None:
    euro_seat = replace(SEAT_30, currency="EUR")
    result = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(euro_seat,), currency="USD")
    assert result[0].seats == Decimal(0)
    assert result[0].total == Decimal("10")


def test_every_total_says_tool_usage_is_not_counted_yet() -> None:
    result = user_costs(gateway_by_user={"u-1": Decimal("10")}, seats=(), currency="USD")
    assert result[0].tool_usage_known is False


def test_money_never_passes_through_a_float() -> None:
    result = user_costs(
        gateway_by_user={"u-1": Decimal("0.30000000000000004")},
        seats=(replace(SEAT_30, amount=Decimal("0.1")),),
        currency="USD",
    )
    assert result[0].total == Decimal("0.40000000000000004")


def test_people_come_back_in_a_stable_order_so_a_screen_does_not_jump() -> None:
    result = user_costs(gateway_by_user={"u-2": Decimal("5"), "u-1": Decimal("10")}, seats=(), currency="USD")
    assert tuple(c.user_id for c in result) == ("u-1", "u-2")
```

The currency test matters most. Adding a euro subscription to a dollar total would produce a figure in no currency at all, and it would look right.

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Write `user_costs`, then run the tests**

- [ ] **Step 4: Mutate each behaviour and confirm a test dies**

Include a mutation that adds the euro seat anyway, and one that sets `tool_usage_known` to `True`.

- [ ] **Step 5: Commit**

---

### Task 4: Serve the seats and the per-person cost

**Files:**
- Create: `litellm/proxy/management_endpoints/seats.py`
- Create: `litellm/types/proxy/management_endpoints/seat_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_seats.py`

**Interfaces:**
- `GET /seats` and `POST /seats` and `DELETE /seats/{seat_id}`, admin only
- `GET /users/cost?period_start=&period_end=&currency=` returning every person an admin may see
- `GET /users/{user_id}/cost?period_start=&period_end=&currency=` returning one person

**The privacy rule is a requirement of this task, not a nicety.** The spec says a user sees only their own cost and a team admin sees their team. Enforce it in the endpoint. A test must prove that an internal user asking for another person's cost is refused, and that the same user asking for their own is answered.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_a_person_may_read_their_own_cost() -> None:
    body: Final = await user_cost(user_id="u-1", period_start="2026-09-01", period_end="2026-09-30",
                                  currency="USD", user_api_key_dict=_member("u-1"))
    assert body.user_id == "u-1"


@pytest.mark.asyncio
async def test_a_person_may_not_read_someone_else_s_cost() -> None:
    with pytest.raises(HTTPException) as caught:
        await user_cost(user_id="u-2", period_start="2026-09-01", period_end="2026-09-30",
                        currency="USD", user_api_key_dict=_member("u-1"))
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_a_non_admin_cannot_list_everyone_s_cost() -> None:
    with pytest.raises(HTTPException) as caught:
        await all_user_costs(period_start="2026-09-01", period_end="2026-09-30",
                             currency="USD", user_api_key_dict=_member("u-1"))
    assert caught.value.status_code == 403


def test_every_amount_crosses_as_a_string_and_the_parts_are_separate() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.gateway == "10"
    assert body.seats == "30"
    assert body.total == "40"
    assert isinstance(body.total, str)


def test_the_response_says_tool_usage_is_not_included() -> None:
    body: Final = user_cost_response(cost=COST_40, period_start=START, period_end=END)
    assert body.tool_usage_known is False
    assert "tool" in body.note.lower()


@pytest.mark.asyncio
async def test_a_seat_with_an_unknown_cadence_is_refused_by_validation() -> None:
    with pytest.raises(ValidationError):
        SeatBody(tool="claude-code", user_id="u-1", cadence="fortnightly", currency="USD",
                 amount="30", period_start="2026-09-01", period_end="2026-09-30")  # pyright: ignore[reportArgumentType]  # the point of the test
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Write the routes**

Follow `litellm/proxy/management_endpoints/ledger.py` for the guards, the `_plain` helper and the error envelope, and carry across its period handling: `_period_end_or_400` exists because a period ending on a date must cover that whole day, and reusing the day-start helper for the end silently drops the final day.

- [ ] **Step 4: Register the router, run the tests**

- [ ] **Step 5: Prove it against the live proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/users/cost?period_start=2026-09-01&period_end=2026-09-30&currency=USD"
curl -s -X POST -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" http://localhost:4001/seats \
  -d '{"tool":"claude-code","user_id":"default_user_id","cadence":"monthly","currency":"USD","amount":"30.00","period_start":"2026-09-01","period_end":"2026-09-30"}'
curl -s -H "Authorization: Bearer sk-1234" "http://localhost:4001/users/cost?period_start=2026-09-01&period_end=2026-09-30&currency=USD"
```

Expected: the person's gateway figure appears first with no seat, then the same figure with a seat of 30.00 and a total exactly 30.00 higher. Delete the seat and confirm the total returns. Put the output in your report.

- [ ] **Step 6: Commit**

---

### Task 5: The Seats tab on a user, and Seats & Commitments on the Ledger

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/SeatsView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/seatsDisplay.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/seats/useSeats.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/seats/useUserCosts.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/LedgerTabs.tsx`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/SeatsView.integration.test.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/seatsDisplay.test.ts`

This adds the Seats & Commitments tab the Ledger plan deferred, so that gap closes here.

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows a person's cost with its parts, not one blended number", async () => {
  render(<SeatsView periodStart="2026-09-01" periodEnd="2026-09-30" />);
  expect(await screen.findByText("$40")).toBeInTheDocument();
  expect(screen.getByText("$10")).toBeInTheDocument();
  expect(screen.getByText("$30")).toBeInTheDocument();
});

it("says the total does not yet include tool usage", async () => {
  render(<SeatsView periodStart="2026-09-01" periodEnd="2026-09-30" />);
  expect(await screen.findByText(/does not include.*tool/i)).toBeInTheDocument();
});

it("will not save a seat with no amount", async () => {
  render(<SeatsView periodStart="2026-09-01" periodEnd="2026-09-30" />);
  expect(await screen.findByRole("button", { name: "Save seat" })).toBeDisabled();
});

it("sends the seat an admin typed, for the period they chose", async () => {
  const user = userEvent.setup();
  render(<SeatsView periodStart="2026-09-01" periodEnd="2026-09-30" />);
  fireEvent.change(await screen.findByLabelText("Person"), { target: { value: "u-1" } });
  fireEvent.change(screen.getByLabelText("Seat amount"), { target: { value: "30.00" } });
  await user.click(screen.getByRole("button", { name: "Save seat" }));
  expect(upsertCall).toHaveBeenCalledWith("sk-test", expect.objectContaining({ user_id: "u-1", amount: "30.00" }));
});
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Build the view and add the tab to `LedgerTabs`**

Base UI unmounts an inactive panel unless `keepMounted` is set, which discards a half-typed seat on a tab round-trip.

- [ ] **Step 4: Run the touched tests only, regenerate the API types, commit**

---

### Task 6: Show the total on the user's own page

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/users/_components/UserCostTab.tsx`
- Modify: the user detail tab list
- Test: `ui/litellm-dashboard/src/app/(dashboard)/users/_components/UserCostTab.integration.test.tsx`

Add a Seats tab to the user detail view. Do not remove or rename any tab that is there.

The Tools tab the spec also lists is not added, because there is no tool data and an empty tab is a control that can never have a value. Task 7 records that.

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows this person's gateway spend and seats separately", async () => {
  render(<UserCostTab userId="u-1" />);
  expect(await screen.findByText("$10")).toBeInTheDocument();
  expect(screen.getByText("$30")).toBeInTheDocument();
});

it("names the part that is missing rather than implying the total is complete", async () => {
  render(<UserCostTab userId="u-1" />);
  expect(await screen.findByText(/does not include.*tool/i)).toBeInTheDocument();
});

it("says a person with no seat has none, rather than showing a blank", async () => {
  server.use(costHandler(NO_SEATS));
  render(<UserCostTab userId="u-1" />);
  expect(await screen.findByText(/no subscriptions assigned/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run them and watch them fail, then build the tab**

- [ ] **Step 3: Run the touched tests only, then commit**

---

### Task 7: Say what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Record what exists**

Seats are entered per person per tool per period and are included in that person's total, with the parts shown separately.

- [ ] **Step 2: Record what does not, and why**

The four user tool connectors, the User Tools data-source page, the User Directory, and the Tools tab on a user are not built, because no real account of any tool exists to verify a connector against, and five of the six provider connectors are already in that unproven state. Name the consequence plainly: a person's total covers their gateway traffic and their subscriptions, and not what they spent inside Claude Code, Copilot, Cursor or Codex.

- [ ] **Step 3: Record the seat rule**

A seat is a fee for a period and is never spread across days, because a daily share of a monthly subscription is a number the company was never charged.

- [ ] **Step 4: Say what Phase 4 still needs**

Phase 4's test is that a person's total cost includes their tool usage and seats. Seats are done; tool usage is not, and cannot be until an account exists.

- [ ] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Phase 4 requirement | Task |
|---|---|
| Research report on user tool APIs | Already exists, dated 2026-09-14 |
| Seats | Tasks 1, 4, 5 |
| A person's total includes seats | Tasks 3, 4, 6 |
| Seats & Commitments tab on the Ledger | Task 5, closing the Phase 3 deferral |
| Seats tab on a user | Task 6 |
| User Directory | Deferred, recorded in Task 7 |
| Claude Code and Copilot connectors | Deferred, recorded in Task 7 |
| Tools tab on a user | Deferred, recorded in Task 7 |
| Users see only their own cost | Task 4, enforced in the endpoint with two tests |

**2. Placeholder scan**

No "TBD", no "add error handling", no "similar to Task N". Every code step carries its code.

**3. Type consistency**

- `Seat` and `SeatCadence` are defined once in Task 1 and imported by Tasks 3 and 4
- `user_costs(*, gateway_by_user, seats, currency)` has one signature, used in Tasks 3 and 4
- `by_user_for_period` returns a mapping keyed by user id in Task 2 and is consumed as one in Task 4
- `UserCost.tool_usage_known` is produced in Task 3 and read in Tasks 4, 5 and 6, so it is wired rather than speculative

**4. The thing a reviewer should check hardest**

That a total never quietly excludes something. Two ways it could: a seat in another currency silently dropped without the screen saying so, and tool usage missing while the figure is presented as a person's cost. Task 3's currency test and the `tool_usage_known` tests in Tasks 3, 4, 5 and 6 exist for exactly this, and all of them must fail if the omission stops being visible.
