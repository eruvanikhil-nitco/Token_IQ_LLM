# Token IQ documentation

## Where things are

**`decisions/`** holds every decision that shaped this codebase, numbered and dated. Most of
them record something that was removed and why, because Token IQ is a fork that deletes more
than it adds. A decision is never rewritten when it changes; a later record supersedes it and
says so, since the reasoning behind a reversal is worth more than a tidy file.

**`plans/`** holds implementation plans, one per piece of work, written before the work
starts and checked off as it proceeds. They are historical once finished and are kept rather
than deleted. The programme turning Token IQ into an independent codebase is
`2026-10-04-independent-codebase.md`.

**`specs/`** holds designs: what something should do, decided before anyone works out how.

**`product/`** holds what the product is meant to become. The blueprint is the page-by-page
reference; the product design document is the agreed direction behind it.

**`status.md`** is where each session records what changed, what was left and why. Read it
first when picking work up.

**`runbooks/`** holds the procedures for operations that need care, such as renaming database
tables in a live installation.

## Glossary

These terms appear in the product's own screens and in the code, and none of them explains
itself.

**Observer-only.** Token IQ watches traffic and accounts for it. It never decides where a
request goes or what comes back: the provider and model are the ones the caller named, the
answer is the one that provider produced, and nothing is served from a cache or retried
somewhere else. Routing, load balancing, fallbacks and response caching are all deliberately
removed or switched off.

**Pass-through mode.** A request forwarded to a provider exactly as the caller wrote it,
with Token IQ recording what it cost rather than reshaping it. Called "courier mode" in some
older code.

**Virtual key.** A key Token IQ issues to a team, project or person, which stands in front of
the real provider key. It is what makes spend attributable to someone, because the provider
only ever sees one account.

**Provider usage fact.** One row of cost as a provider's own billing API reported it: an
amount, a day, an account, and what it was for. Facts come from the provider, not from
Token IQ's own measurements, which is what makes them the authority on how much was spent.

**Evidence level.** How a figure was arrived at, and therefore how much weight it carries.
*Reconciled* means the provider asserted this amount. *Priced* means Token IQ calculated it
from usage and a price list. *Allocated* means it was divided out from a larger figure by a
rule. The three are never silently mixed.

**Attribution.** Deciding whose spend a cost was. The gateway knows who made a request, so
gateway records answer "who", while provider bills answer "how much". A cost nobody can be
attributed to is unallocated, and the product says so rather than hiding it.

**Seat.** A flat per-person subscription read off a contract rather than an API, such as a
Copilot or Cursor licence. It counts toward that person's cost for the period it covers and
is never spread across days, because a daily share of a monthly fee is a number nobody was
charged.

## The counting rule

The one rule worth knowing before reading any figure in this product.

**A provider figure says how much was spent. A gateway figure says who spent it. They are
never added together.**

The headline total is what the providers billed, plus tool spend that appears on no provider
bill, plus seats. The gateway's own figure never enters it, and appears only as attribution:
how much of the provider total the product can say who spent.

Breaking this is silent. Every screen keeps working and the one number a customer repeats to
their finance team is roughly double what they actually spent.
