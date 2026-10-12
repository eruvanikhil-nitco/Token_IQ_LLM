# Runbook: rename the database tables

**What this does:** renames the 87 `LiteLLM_*` tables to snake_case, with their indexes,
constraints and sequence, and then removes the `@@map` lines that are currently holding the old
physical names in place.

**Why it is a runbook and not a migration anybody can run:** every other migration in this
repository changes schema only, and the proxy applies them at boot before it serves traffic. This
one is also schema-only, which is what makes it safe to apply that way, but it renames every table
the product reads at once. A failure part-way through leaves an installation whose code and
database disagree about every name, and the only sane recovery is the rename back. That is worth a
window and a backup rather than a deploy.

**Who decides:** the repository owner, as phase 8 of
`docs/plans/2026-10-04-independent-codebase.md` says. Nothing here runs without that.

## What it touches, measured

Counted on a development database on 12 Oct 2026, which carries every table the schema declares:

| Thing | Count |
|---|---|
| Tables named `LiteLLM_*` | 87 |
| Indexes on them, primary keys included | 250 |
| Foreign key constraints between them | 29 |
| Sequences in the schema | 1 |

Postgres renames the dependent objects with the table for a `RENAME TO`, so indexes, constraints
and the sequence follow automatically. They are counted here because the verification step has to
confirm that they did, and because an installation that has run for a while may carry extras: an
index somebody added by hand is renamed too, and an index named after the old table keeps that name
until it is renamed explicitly.

## Before the window

1. **Take a backup and prove it restores.** `pg_dump` of the whole database, then restore it into a
   scratch database and run the rehearsal below against that copy. A backup nobody restored is a
   hope.
2. **Rehearse on the restored copy.** Apply the migration, start the proxy against the copy, and
   check the three things under Verification. Record how long the migration took: on a
   spend-log-sized table a rename is fast because no data moves, but the lock is exclusive, so the
   number to tell the customer is the lock time, not the data size.
3. **Check for anything outside this repository that names a table.** A customer's own BI tool, a
   Grafana dashboard, a scheduled export or a database user with grants on specific tables will
   break. Ask before the window rather than finding out after it.
4. **Agree the window.** The proxy must not serve traffic while the rename runs, because its running
   process holds the old names in its prepared statements.

## The window

1. Stop the proxy. Confirm nothing else holds a connection:
   `select pid, usename, application_name from pg_stat_activity where datname = current_database();`
2. Apply the rename migration. It is one migration, every statement inside one transaction, so a
   failure rolls the whole thing back rather than leaving half the names changed.
3. Deploy the release that has the `@@map` lines removed. The order matters: the old release cannot
   read the new names, and the new release cannot read the old ones.
4. Start the proxy and watch the migration log line it prints at boot.

## Verification

Three checks, in this order, because each one would pass while the next fails:

1. **The names moved.**
   `select count(*) from information_schema.tables where table_schema = 'public' and table_name like 'LiteLLM%';`
   must return 0, and the snake_case count must be 87.
2. **The data is the same.** For the tables that carry figures, compare a row count and a sum taken
   before the window against the same query after it: `LiteLLM_SpendLogs`,
   `LiteLLM_ProviderUsageFact`, `LiteLLM_ProviderInvoice`, `LiteLLM_UserSeat`. A rename moves no
   rows, so any difference means something other than the rename happened.
3. **The product reads it.** Not a status endpoint: the Overview page shows a total, the Ledger
   lists its lines with owners, and one request through the gateway appears in the request log. A
   migration that renamed everything and a product that cannot read any of it both report healthy.

## Rollback

Rename back and deploy the previous release, in that order. The rollback migration is the same
statements with the names swapped, and it is written and applied the same way: one transaction,
proxy stopped.

Rollback is only this simple while the two releases differ by nothing but the names. If anything
else ships in the same release, the rollback is no longer a rename.

## What this does not do

It does not rename the migration folders. Prisma tracks applied migrations by folder name in
`_prisma_migrations`, so renaming one makes every installation think it has an unapplied migration.

It does not touch column names. The schema renames models and keeps field names, so only the 87
table names and whatever Postgres renames with them are in scope.
