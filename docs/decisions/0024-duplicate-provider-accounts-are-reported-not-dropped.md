# 0024: a figure two provider accounts both report is reported, never dropped

**Date:** 12 Oct 2026
**Status:** accepted
**Context:** build step 3 task 2, `docs/plans/2026-10-12-blueprint-step-3-truth-layer.md`

## The problem

A customer can hold two connections to one provider that cover the same spend. Three ways it
happens, all ordinary:

- an AWS management account and one of its member accounts, where the management account's Cost
  Explorer already includes the member's costs;
- an organisation-wide provider key and a project-scoped key from the same organisation;
- a key rotated by connecting the new one and never removing the old.

In each case the same dollars arrive twice and every total that adds provider facts reads double.
Nothing in the product stopped this. The other three de-duplication rules were already covered: a
re-fetched fact by a unique `fact_key` in the database, tool spend already on a provider bill by the
cost line's type, and a gateway figure against a provider's by the same type.

## Why it cannot be detected properly

No connector learns the provider's own account identifier. Bedrock's Cost Explorer answers with
amounts by service and usage type, not by linked account, unless it is asked to group by account;
OpenAI and Anthropic answer for whichever organisation the key belongs to without naming it. So
Token IQ knows the name a customer typed for a credential and nothing about the account behind it.

Two credentials reading one account and two credentials reading two separate accounts are therefore
indistinguishable from the credentials alone. A great many customers legitimately hold two accounts
on one provider, development and production being the obvious pair.

## The decision

**Detect the one signal that is nearly unambiguous, report it, and drop nothing.**

The signal is the figure. Two accounts reporting the same amount, to every digit, for the same day,
model, meter and currency is one account read twice. Two genuinely separate accounts billing the
identical fraction of a cent on the same model and day is not an event that happens. Zero is
excluded, because two accounts reporting nothing against a model is the commonest figure a provider
publishes and pairing those would put a row on the list for every unused model in an estate.

It surfaces as a data-quality issue on Data Sources > Overview, "Figures two accounts both
reported", counted and pointing at the Accounts tab. The rule lives in `token_iq/truth/dedup.py`
with every rule named beside it, and the count is one SQL `GROUP BY` with a `HAVING COUNT(DISTINCT
credential_name) > 1`.

## Why not drop the duplicate

Because the cost of being wrong is asymmetric and only one direction is visible.

A wrong suspicion costs a reader one look at their provider console, and they can dismiss it. A
wrong deletion halves a bill, and nothing downstream can tell that it was halved: reconciliation
would report the provider's invoice as larger than the ledger and blame the provider, the Overview
total would read half, and every figure would still add up internally. Halving a customer's reported
spend is exactly as wrong as doubling it and considerably harder to notice, because nobody questions
a number that went down.

It is also not ours to decide. Which of two accounts covers the other is a fact about the customer's
own AWS or OpenAI organisation, which they can answer in a minute and we cannot answer at all.

## What would change this

An account identifier on the fact. If a connector learns the provider's own account id, by asking
Cost Explorer to group by linked account for instance, then overlap becomes computable rather than
inferred, and a connection whose scope contains another's can be resolved without a person. The
rule above then becomes the fallback for providers that still do not say.

Recording the scope per connection in the connect dialog, organisation or account or project, would
get most of the way there without a provider's help. It is a dialog field, a column and a rule, and
it belongs with Cost Allocation rather than inside the truth layer.
