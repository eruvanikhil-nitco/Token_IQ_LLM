# Ledger and Bill Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take a month's provider bill, set it against every cost line the product holds, and account for the difference or say plainly that it is unexplained.

**Architecture:** An invoice is a figure a human enters from a real bill, because almost no provider publishes invoices through an API. The ledger is one read over the cost lines that already exist: provider facts carry a source, an evidence level and, through the attribution rules, an owner. Reconciliation subtracts the two and splits the difference into the reasons a bill legitimately differs from usage, leaving whatever nobody can name as an unexplained remainder that is shown rather than absorbed.

**Tech Stack:** Python 3.12, FastAPI, Prisma with Postgres, `prisma-client-py` raw queries, pytest. Dashboard is Next.js with shadcn/Base UI, TanStack Query and vitest.

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "Key screens / Ledger", "What the product must handle" and "Phases" (Phase 3)

This plan is what closes Phase 3, whose completion test is exactly its goal sentence.

## Global Constraints

- Money is `Decimal` end to end and must never pass through `float`. Every summed money column leaves Postgres cast `::text`, because `prisma-client-py` decodes a bare `numeric` as a float
- Every cost keeps its original currency alongside any converted figure. An invoice entered in euros is never silently compared against a dollar total
- The unexplained remainder is always shown, never absorbed into another category to make a total balance
- Every figure carries its source and evidence level (`reconciled`, `priced`, `allocated`)
- A day the provider has not finished billing is labelled, never counted as a gap
- The hierarchy is teams, projects and users. Never "employees"
- Never remove, merge or rename an existing UI tab. Adding one is fine
- Prisma migrations change schema only. No `UPDATE`, `DELETE`, `MERGE` or `INSERT ... SELECT`
- All three prisma schema copies stay byte-identical; `.github/workflows/check-schema-sync.yml` diffs them and fails the build
- No `Any` or coarse types, every parameter strongly typed, `: Final` on every variable (LIT010), `ReadOnly[...]` on TypedDict fields (LIT012), no parameter rebinding (LIT011), immutable collections. `# mutable-ok: <reason>` only as a genuine last resort with a true reason
- Every lint or type suppression names its exact rule in brackets and carries a real reason. `# type: ignore` is banned
- No comments except genuinely complex business logic, tool-read suppressions, or TODO/FIXME with a strong reason. A test must not open with a docstring restating its own name. Never add a constant or export whose only purpose is to carry a comment
- Tests must test function, never structure, and must fail when the behaviour is mutated
- No customer-visible LiteLLM branding, no company or customer names, no secrets in code, no `eval`, no `shell=True`
- Python max line length 120. TypeScript has no `any`, and no tokens in `localStorage`
- Never run the full dashboard vitest suite with no path. Never run `python -m pytest`; invoke it as `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main([...]))"`, because the harness refuses the module form intermittently
- Python is always `C:\Users\NikhilEruva\litellm\.venv\Scripts\python.exe`. The proxy starts only with `bash ~/.claude/scripts/litellm-dev-up.sh` (port 4001, dev key `sk-1234`)
- `npm run gen:api` needs the venv on PATH, because it shells out to `python3`: `PATH="/c/Users/NikhilEruva/litellm/.venv/Scripts:$PATH" npm run gen:api`
- Conventional-commits messages, no Claude attribution or `Co-Authored-By` trailer

## Scope, decided before any code

The spec's Ledger has five tabs. This plan builds three and defers two, and Task 7 records why.

- **Built: Cost Ledger, Invoices, Bill Reconciliation.** These three are exactly what Phase 3's completion test needs.
- **Deferred: Seats & Commitments.** Seats are flat per-person fees for user tools, and user tools are Phase 4 with no data and no connector. Building a table for them now would be a screen that can only ever show what someone typed into it. Commitments still get accounted for, as a named adjustment on an invoice, which is where a customer reads them off the bill anyway.
- **Deferred: Pricing Adjustments.** It is a move of the existing Cost Tracking settings into a new group, not new capability, and it touches an inherited page. It belongs with the sidebar reorganisation, not with reconciliation.
- **Currency is carried, not converted.** Every invoice records the currency its bill was written in, and reconciliation refuses to compare two currencies rather than applying a rate nobody chose. A conversion needs a rate source, a date convention and someone's sign-off; inventing one would produce a number that looks authoritative and is not.

---

### Task 1: Store an invoice

**Files:**
- Create: `litellm-proxy-extras/litellm_proxy_extras/migrations/20260929000000_provider_invoice/migration.sql`
- Modify: `schema.prisma`, `litellm/proxy/schema.prisma`, `litellm-proxy-extras/litellm_proxy_extras/schema.prisma`
- Create: `litellm/types/proxy/invoice.py`
- Create: `litellm/repositories/invoice_repository.py`
- Test: `tests/test_litellm/repositories/test_invoice_repository.py`

**Interfaces:**
- Produces:
  - `AdjustmentKind = Literal["credit", "discount", "tax", "commitment"]`
  - `@dataclass(frozen=True, slots=True) class InvoiceAdjustment: kind: AdjustmentKind; amount: Decimal; note: str | None`
  - `@dataclass(frozen=True, slots=True) class ProviderInvoice: invoice_id: str; provider: str; period_start: datetime; period_end: datetime; currency: str; total: Decimal; adjustments: tuple[InvoiceAdjustment, ...]; note: str | None`
  - `InvoiceRepository(db)` with `async def upsert(self, invoice: ProviderInvoice) -> ProviderInvoice | None`, `async def for_period(self, *, provider: str, period_start: datetime, period_end: datetime) -> ProviderInvoice | None`, `async def all(self) -> tuple[ProviderInvoice, ...]`, `async def delete(self, invoice_id: str) -> bool`

Use raw parameterised SQL, not the generated Prisma model, exactly as
`litellm/repositories/attribution_rule_repository.py` does and for the reason written at the top
of that file: the generated client only knows a table after `prisma generate`, which is blocked
on some machines, and every other new billing table here is read the same way.

Adjustments are stored as a JSON column on the invoice rather than their own table. They are only
ever read back with their invoice, never queried across invoices, so a second table would buy a
join and nothing else.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_an_invoice_round_trips_with_its_adjustments() -> None:
    repo, _ = _repo([_stored()])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.total == Decimal("1234.56")
    assert saved.adjustments[0].kind == "credit"


@pytest.mark.asyncio
async def test_the_amount_is_exact_to_the_last_digit_the_bill_showed() -> None:
    repo, _ = _repo([_stored(total="1234.567890123456789")])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.total == Decimal("1234.567890123456789")


@pytest.mark.asyncio
async def test_an_amount_the_driver_decoded_as_a_float_is_refused() -> None:
    repo, _ = _repo([_stored(total=1234.56)])
    assert await repo.upsert(INVOICE) is None


@pytest.mark.asyncio
async def test_an_adjustment_of_an_unknown_kind_is_dropped_rather_than_guessed() -> None:
    repo, _ = _repo([_stored(adjustments=[{"kind": "vibes", "amount": "1", "note": None}])])
    saved: Final = await repo.upsert(INVOICE)
    assert saved is not None
    assert saved.adjustments == ()


@pytest.mark.asyncio
async def test_re_entering_a_period_corrects_it_rather_than_storing_two_bills() -> None:
    repo, db = _repo([_stored()])
    await repo.upsert(INVOICE)
    assert "ON CONFLICT (provider, period_start, period_end)" in db.last_sql


@pytest.mark.asyncio
async def test_the_note_is_bound_as_a_parameter_never_interpolated() -> None:
    hostile: Final = "note'; DROP TABLE \"LiteLLM_ProviderInvoice\"; --"
    repo, db = _repo([_stored()])
    await repo.upsert(replace(INVOICE, note=hostile))
    assert hostile not in db.last_sql
    assert hostile in db.last_args
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/Scripts/python.exe -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_litellm/repositories/test_invoice_repository.py']))"`
Expected: FAIL with "No module named 'litellm.repositories.invoice_repository'"

- [ ] **Step 3: Add the model to all three prisma schemas**

```prisma
// One provider bill for one period, entered by an admin because almost no provider publishes
// invoices through an API. Bill Reconciliation compares this against the ledger.
model LiteLLM_ProviderInvoice {
    invoice_id   String   @id @default(uuid())
    provider     String
    period_start DateTime
    period_end   DateTime
    currency     String   @default("USD")
    total        String   // exact digits as text; prisma-client-py gates Decimal behind an experimental flag
    adjustments  Json?
    note         String?
    created_at   DateTime @default(now())
    updated_at   DateTime @updatedAt

    @@unique([provider, period_start, period_end])
    @@index([provider, period_start])
}
```

`total` is `String` for the same reason `LiteLLM_ProviderUsageFact.billed_cost` is: the driver
turns a `numeric` into a float and the digits are gone before any Python sees them.

The unique constraint is what makes re-entering a corrected bill an update rather than a second
invoice for the same month.

- [ ] **Step 4: Write the migration, schema only**

```sql
CREATE TABLE "LiteLLM_ProviderInvoice" (
    "invoice_id" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "period_start" TIMESTAMP(3) NOT NULL,
    "period_end" TIMESTAMP(3) NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "total" TEXT NOT NULL,
    "adjustments" JSONB,
    "note" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "LiteLLM_ProviderInvoice_pkey" PRIMARY KEY ("invoice_id")
);

CREATE UNIQUE INDEX "LiteLLM_ProviderInvoice_provider_period_start_period_end_key"
    ON "LiteLLM_ProviderInvoice"("provider", "period_start", "period_end");

CREATE INDEX "LiteLLM_ProviderInvoice_provider_period_start_idx"
    ON "LiteLLM_ProviderInvoice"("provider", "period_start");
```

After writing it, copy the root schema over the other two and confirm both diffs are empty:
`cp schema.prisma litellm/proxy/schema.prisma && cp schema.prisma litellm-proxy-extras/litellm_proxy_extras/schema.prisma`

- [ ] **Step 5: Write the types and the repository**

An adjustment whose `kind` is not one of the four literals is dropped, the way an unreadable
attribution rule is dropped: an adjustment nobody can name would otherwise subtract money from a
customer's unexplained remainder for a reason the screen cannot state.

- [ ] **Step 6: Run the tests, then prove each behaviour by mutation**

Assert each search string occurs exactly once before mutating. A replace that matches nothing
looks identical to a missing test, and that has happened twice on this branch.

- [ ] **Step 7: Apply the migration to the dev database and commit**

The startup script refuses to boot when a model has no table and prints the command to run.

```bash
docker exec -i tokeniq_db psql -U llmproxy -d litellm -v ON_ERROR_STOP=1 --single-transaction \
  < litellm-proxy-extras/litellm_proxy_extras/migrations/20260929000000_provider_invoice/migration.sql
git add schema.prisma litellm/proxy/schema.prisma litellm-proxy-extras/litellm_proxy_extras litellm/types/proxy/invoice.py litellm/repositories/invoice_repository.py tests/test_litellm/repositories/test_invoice_repository.py
git commit -m "feat(ledger): store a provider invoice and its adjustments"
```

---

### Task 2: Read the cost ledger

**Files:**
- Create: `litellm/repositories/ledger_repository.py`
- Test: `tests/test_litellm/repositories/test_ledger_repository.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class LedgerLine: day: datetime; provider: str; credential_name: str; model: str | None; evidence: EvidenceLevel; currency: str; amount: Decimal`
  - `LedgerRepository(db)` with `async def lines(self, *, provider: str | None, period_start: datetime, period_end: datetime, limit: int, cursor: tuple[datetime, str] | None) -> LedgerPage`
  - `@dataclass(frozen=True, slots=True) class LedgerPage: lines: tuple[LedgerLine, ...]; next_cursor: tuple[datetime, str] | None`
  - `async def total(self, *, provider: str, period_start: datetime, period_end: datetime) -> Mapping[str, Decimal]`, keyed by currency

The ledger is the provider facts, which already carry a source, an evidence level and a currency.
Do not union gateway spend into it: the gateway's figure and the provider's figure describe the
same money, and a ledger that listed both would double count, which is the one thing the counting
rule forbids. The owner comes from the attribution rules at the endpoint, not here.

`total` returns a mapping keyed by currency rather than one number, so a provider billing in two
currencies is visible as two totals instead of one meaningless sum. Read
`litellm/repositories/provider_usage_fact_repository.py` for the keyset pagination pattern: the
cursor is `(bucket_start, fact_key)`, and page fullness is decided from the raw row count and not
from how many rows survived parsing, because one unreadable row would otherwise truncate all the
history behind it.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_a_line_keeps_its_source_evidence_and_currency() -> None:
    repo, _ = _repo([_row(evidence="reconciled", currency="EUR")])
    page: Final = await repo.lines(provider=None, period_start=START, period_end=END, limit=50, cursor=None)
    assert page.lines[0].evidence == "reconciled"
    assert page.lines[0].currency == "EUR"


@pytest.mark.asyncio
async def test_amounts_stay_exact() -> None:
    repo, db = _repo([_row(amount="0.30000000000000004")])
    page: Final = await repo.lines(provider=None, period_start=START, period_end=END, limit=50, cursor=None)
    assert page.lines[0].amount == Decimal("0.30000000000000004")
    assert "::text" in db.last_sql


@pytest.mark.asyncio
async def test_two_currencies_total_separately_rather_than_being_summed() -> None:
    repo, _ = _repo([{"currency": "USD", "total": "10"}, {"currency": "EUR", "total": "5"}])
    totals: Final = await repo.total(provider="openai", period_start=START, period_end=END)
    assert totals == {"USD": Decimal("10"), "EUR": Decimal("5")}


@pytest.mark.asyncio
async def test_a_full_page_is_decided_from_the_rows_the_database_returned() -> None:
    repo, _ = _repo([_row(fact_key=f"k{n}") for n in range(50)] + [_row(amount="bad", fact_key="k50")])
    page: Final = await repo.lines(provider=None, period_start=START, period_end=END, limit=50, cursor=None)
    assert len(page.lines) < 51
    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_the_gateway_is_not_in_the_ledger_at_all() -> None:
    repo, db = _repo([_row()])
    await repo.lines(provider=None, period_start=START, period_end=END, limit=50, cursor=None)
    assert "LiteLLM_SpendLogs" not in db.last_sql
    assert "LiteLLM_DailyTeamSpend" not in db.last_sql
```

The last test is the counting rule made mechanical: it fails the moment someone unions gateway
spend into the ledger.

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, the module does not exist

- [ ] **Step 3: Write the repository**

- [ ] **Step 4: Run the tests, then mutate each behaviour and confirm a test dies**

- [ ] **Step 5: Prove it against the real database**

Run the repository directly against Postgres, as the gap repository was proven, and print the
lines and the per-currency totals. A fake database cannot catch a SQL type error: Task 3 of the
Combined plan shipped a query that could never run because the `date` column was text, and only
a live run found it.

- [ ] **Step 6: Commit**

```bash
git add litellm/repositories/ledger_repository.py tests/test_litellm/repositories/test_ledger_repository.py
git commit -m "feat(ledger): read every cost line with its source, evidence and currency"
```

---

### Task 3: Reconcile a bill against the ledger

**Files:**
- Create: `litellm/ledger/reconciliation.py`
- Create: `litellm/ledger/__init__.py`
- Test: `tests/test_litellm/ledger/test_reconciliation.py`

**Interfaces:**
- Consumes: `ProviderInvoice`, `InvoiceAdjustment` from Task 1
- Produces:
  - `ReconciliationOutcome = Literal["balanced", "unexplained_difference", "currency_mismatch", "no_invoice"]`
  - `@dataclass(frozen=True, slots=True) class Reconciliation: outcome: ReconciliationOutcome; currency: str | None; invoice_total: Decimal | None; ledger_total: Decimal | None; explained: tuple[InvoiceAdjustment, ...]; explained_total: Decimal; unexplained: Decimal`
  - `def reconcile(*, invoice: ProviderInvoice | None, ledger_totals: Mapping[str, Decimal]) -> Reconciliation`

A pure function. No database, no clock.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_bill_that_matches_the_ledger_once_credits_are_applied_is_balanced() -> None:
    invoice = _invoice(total="90", adjustments=(InvoiceAdjustment("credit", Decimal("-10"), None),))
    result = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "balanced"
    assert result.unexplained == Decimal(0)


def test_whatever_no_adjustment_explains_is_reported_not_absorbed() -> None:
    invoice = _invoice(total="80", adjustments=(InvoiceAdjustment("credit", Decimal("-10"), None),))
    result = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "unexplained_difference"
    assert result.unexplained == Decimal("-10")


def test_a_bill_in_another_currency_is_refused_rather_than_converted() -> None:
    invoice = _invoice(total="90", currency="EUR")
    result = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "currency_mismatch"
    assert result.unexplained == Decimal(0)


def test_no_invoice_says_so_rather_than_reporting_the_whole_ledger_as_unexplained() -> None:
    result = reconcile(invoice=None, ledger_totals={"USD": Decimal("100")})
    assert result.outcome == "no_invoice"
    assert result.unexplained == Decimal(0)


def test_a_ledger_with_nothing_in_it_still_reconciles_against_a_bill() -> None:
    invoice = _invoice(total="50")
    result = reconcile(invoice=invoice, ledger_totals={})
    assert result.outcome == "unexplained_difference"
    assert result.unexplained == Decimal("50")


def test_money_never_passes_through_a_float() -> None:
    invoice = _invoice(total="0.1")
    result = reconcile(invoice=invoice, ledger_totals={"USD": Decimal("0.30000000000000004")})
    assert result.unexplained == Decimal("-0.20000000000000004")
```

The third test is the one that matters most. A rate nobody chose, applied silently, produces a
number that looks authoritative and is not.

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, the module does not exist

- [ ] **Step 3: Write `reconcile`**

The order of the checks is the behaviour: no invoice first, then a currency the ledger does not
hold, then the arithmetic. `unexplained` is `invoice_total - adjustments - ledger_total`, and it
is reported with its sign, because a bill smaller than the ledger and a bill larger than it are
different problems for a customer.

- [ ] **Step 4: Run the tests, then mutate each branch and confirm a test dies**

- [ ] **Step 5: Commit**

```bash
git add litellm/ledger tests/test_litellm/ledger
git commit -m "feat(ledger): reconcile a bill against the ledger without hiding the remainder"
```

---

### Task 4: Serve the ledger, the invoices and the reconciliation

**Files:**
- Create: `litellm/proxy/management_endpoints/ledger.py`
- Create: `litellm/types/proxy/management_endpoints/ledger_endpoints.py`
- Modify: `litellm/proxy/proxy_server.py`
- Test: `tests/test_litellm/proxy/management_endpoints/test_ledger.py`

**Interfaces:**
- Produces, all admin only, guarded exactly as `combined_usage.py` guards:
  - `GET /ledger/lines?provider=&period_start=&period_end=&limit=&cursor=`
  - `GET /ledger/invoices`
  - `POST /ledger/invoices`
  - `DELETE /ledger/invoices/{invoice_id}`
  - `GET /ledger/reconciliation?provider=&period_start=&period_end=`

- [ ] **Step 1: Write the failing tests**

```python
def test_every_amount_crosses_as_a_string() -> None:
    body: Final = reconciliation_response(provider="openai", reconciliation=BALANCED)
    assert isinstance(body.invoice_total, str)
    assert isinstance(body.unexplained, str)


def test_the_unexplained_remainder_is_always_present_even_when_zero() -> None:
    body: Final = reconciliation_response(provider="openai", reconciliation=BALANCED)
    assert body.unexplained == "0"


def test_a_currency_mismatch_reports_both_currencies_rather_than_one_number() -> None:
    body: Final = reconciliation_response(provider="openai", reconciliation=MISMATCH)
    assert body.outcome == "currency_mismatch"
    assert "EUR" in body.note and "USD" in body.note


@pytest.mark.asyncio
async def test_a_non_admin_cannot_read_another_team_s_ledger() -> None:
    with pytest.raises(HTTPException) as caught:
        await ledger_lines(provider=None, period_start=START, period_end=END, limit=50,
                           cursor=None, user_api_key_dict=MEMBER)
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_an_invoice_with_an_unknown_adjustment_kind_is_refused_by_validation() -> None:
    with pytest.raises(ValidationError):
        InvoiceBody(provider="openai", period_start="2026-09-01", period_end="2026-09-30",
                    currency="USD", total="100",
                    adjustments=[{"kind": "vibes", "amount": "1"}])  # pyright: ignore[reportArgumentType]  # the point of the test
```

- [ ] **Step 2: Run them and watch them fail**

Expected: FAIL, the module does not exist

- [ ] **Step 3: Write the response models and routes**

Validate the POST body with Pydantic using the `AdjustmentKind` literal, so an adjustment nobody
can name is a 400 before anything is written rather than a stored row silently skipped on read.

- [ ] **Step 4: Register the router beside `combined_usage_router`**

- [ ] **Step 5: Run the tests**

- [ ] **Step 6: Prove the whole thing against the live proxy**

```bash
bash ~/.claude/scripts/litellm-dev-up.sh
curl -s -H "Authorization: Bearer sk-1234" \
  "http://localhost:4001/ledger/reconciliation?provider=openrouter&period_start=2026-09-01&period_end=2026-09-30"

curl -s -X POST -H "Authorization: Bearer sk-1234" -H "Content-Type: application/json" \
  http://localhost:4001/ledger/invoices \
  -d '{"provider":"openrouter","period_start":"2026-09-01","period_end":"2026-09-30","currency":"USD","total":"0.00780515","adjustments":[]}'

curl -s -H "Authorization: Bearer sk-1234" \
  "http://localhost:4001/ledger/reconciliation?provider=openrouter&period_start=2026-09-01&period_end=2026-09-30"
```

Expected: `no_invoice` first, then `balanced` with an unexplained remainder of `0`, because the
real OpenRouter ledger for September totals `0.00780515`. Then enter a wrong total and confirm
the difference is reported rather than absorbed. Delete the invoice afterwards and put the output
in your report.

- [ ] **Step 7: Commit**

---

### Task 5: The Ledger screen, Cost Ledger and Invoices

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/page.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/LedgerTabs.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/CostLedgerView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/InvoicesView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/ledgerDisplay.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/ledger/useLedger.ts`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/ledger/useInvoices.ts`
- Modify: `ui/litellm-dashboard/src/components/networking.tsx`
- Modify: `ui/litellm-dashboard/src/components/leftnav.tsx`, `ui/litellm-dashboard/src/components/leftnav.test.tsx`
- Modify: `ui/litellm-dashboard/src/utils/migratedPages.ts`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/LedgerTabs.integration.test.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/ledgerDisplay.test.ts`

Add `Ledger` to the sidebar under ANALYTICS, after `Usage`. Register its route in
`migratedPages.ts` in the same commit: `leftnav.test.tsx` asserts every sidebar page has an
address, and a menu entry without one renders and leads nowhere. Update the expected group list
in that test too.

Internal links use `migratedHref("ledger")`, never a hardcoded `/ui/?page=...`, which breaks on
any installation served under a different root path.

- [ ] **Step 1: Write the failing display tests**

```ts
it("keeps every digit rather than rounding a ledger line for display", () => {
  expect(formatAmount("0.00774700", "USD")).toBe("$0.00774700");
});

it("names a currency it has no symbol for rather than dropping it", () => {
  expect(formatAmount("10", "SEK")).toBe("SEK 10");
});

it("says what each evidence level means, in words a customer reads", () => {
  expect(EVIDENCE_LABEL.reconciled).toMatch(/provider/i);
  expect(EVIDENCE_LABEL.allocated).not.toMatch(/provider asserted/i);
});
```

- [ ] **Step 2: Write the failing integration tests**

```tsx
it("shows a ledger line with its source, evidence and owner", async () => {
  render(<LedgerTabs />);
  expect(await screen.findByText("$0.00774700")).toBeInTheDocument();
  expect(screen.getByText("OpenRouter")).toBeInTheDocument();
});

it("lets an admin enter a bill and shows it in the list", async () => {
  const user = userEvent.setup();
  render(<LedgerTabs />);
  await user.click(screen.getByRole("tab", { name: "Invoices" }));
  fireEvent.change(await screen.findByLabelText("Invoice total"), { target: { value: "1234.56" } });
  await user.click(screen.getByRole("button", { name: "Save invoice" }));
  expect(upsertCall).toHaveBeenCalledWith("sk-test", expect.objectContaining({ total: "1234.56" }));
});

it("will not save an invoice with no total", async () => {
  render(<LedgerTabs />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "Invoices" }));
  expect(await screen.findByRole("button", { name: "Save invoice" })).toBeDisabled();
});
```

- [ ] **Step 3: Run both and watch them fail**

- [ ] **Step 4: Build the screen**

Base UI unmounts an inactive panel unless `keepMounted` is set, which silently discards a
half-typed invoice on a tab round-trip.

- [ ] **Step 5: Run the touched tests only, then `PATH=... npm run gen:api` and commit the result**

---

### Task 6: The Bill Reconciliation view

**Files:**
- Create: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/BillReconciliationView.tsx`
- Create: `ui/litellm-dashboard/src/app/(dashboard)/hooks/ledger/useReconciliation.ts`
- Modify: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/LedgerTabs.tsx`
- Test: `ui/litellm-dashboard/src/app/(dashboard)/ledger/_components/BillReconciliationView.integration.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it("shows the unexplained remainder even when it is zero", async () => {
  server.use(reconciliationHandler(BALANCED));
  render(<BillReconciliationView provider="openrouter" />);
  expect(await screen.findByText(/unexplained/i)).toBeInTheDocument();
  expect(screen.getByText("$0")).toBeInTheDocument();
});

it("names each thing that explains part of the difference", async () => {
  server.use(reconciliationHandler(WITH_CREDIT));
  render(<BillReconciliationView provider="openrouter" />);
  expect(await screen.findByText(/credit/i)).toBeInTheDocument();
});

it("refuses to compare two currencies and says which two", async () => {
  server.use(reconciliationHandler(MISMATCH));
  render(<BillReconciliationView provider="openrouter" />);
  expect(await screen.findByText(/EUR/)).toBeInTheDocument();
  expect(screen.getByText(/USD/)).toBeInTheDocument();
});

it("asks for a bill rather than reporting the whole ledger as unexplained", async () => {
  server.use(reconciliationHandler(NO_INVOICE));
  render(<BillReconciliationView provider="openrouter" />);
  expect(await screen.findByText(/no bill entered/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Build the view**

Read the `dataviz` skill before drawing anything. The breakdown is a small number of named parts
of one difference, so it is a list with amounts rather than a pie chart; if a chart earns its
place, validate the palette with `scripts/validate_palette.js` for both light and dark before
shipping.

- [ ] **Step 4: Run the touched tests only, then commit**

---

### Task 7: Say what is built and what is not

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`

- [ ] **Step 1: Record the three tabs that exist and what each does**

- [ ] **Step 2: Record the two that do not, with the reasons from this plan's Scope section**

Seats & Commitments waits on Phase 4 because seats are user-tool fees with no data; commitments
are captured as an invoice adjustment meanwhile. Pricing Adjustments is a move of existing
settings and belongs with the sidebar reorganisation.

- [ ] **Step 3: Record that currency is carried and never converted**

An invoice in another currency is refused for comparison rather than converted, because a rate
nobody chose produces a number that looks authoritative and is not.

- [ ] **Step 4: Mark Phase 3 complete, or say precisely what is missing**

Phase 3's test is that a month's provider bill can be reconciled against the ledger with every
gap explained or marked unexplained. Say whether that now holds, and if it holds only for a
provider with real data, say that too.

- [ ] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Cost Ledger lists every line with source, evidence level and owner | Tasks 2, 4 and 5 |
| Bill Reconciliation compares ledger to bill for a period | Tasks 3, 4 and 6 |
| The gap breaks into credits, discounts, tax, commitments and an unexplained remainder | Tasks 1 and 3 |
| Invoices accepts uploaded or entered invoices | Tasks 1, 4 and 5, entered only; file upload is not built and Task 7 says so |
| Seats & Commitments | Deferred with reasons, recorded in Task 7 |
| Pricing Adjustments | Deferred with reasons, recorded in Task 7 |
| Every cost keeps its original currency | Tasks 1, 2 and 3 |
| Phase 3 completion test | Task 4's live proof, recorded in Task 7 |

**2. Placeholder scan**

No "TBD", no "add error handling", no "similar to Task N". Every code step carries its code.

**3. Type consistency**

- `ProviderInvoice`, `InvoiceAdjustment` and `AdjustmentKind` are defined once in Task 1 and imported by Tasks 3 and 4
- `reconcile(*, invoice, ledger_totals)` has one signature, used in Tasks 3 and 4
- `LedgerRepository.total` returns a mapping keyed by currency in Task 2 and is consumed as one in Task 4
- `EvidenceLevel` is the existing literal from `litellm/types/proxy/provider_billing.py`, not a new one

**4. The thing a reviewer should check hardest**

That the unexplained remainder is never absorbed. Every other number on this screen can be
recomputed from the data; the remainder is the one figure whose whole purpose is to be awkward,
and the easiest way to make a reconciliation screen look finished is to quietly fold it into
"other". Task 3's second test and Task 6's first test exist to stop that, and both must fail if
the remainder is dropped.
