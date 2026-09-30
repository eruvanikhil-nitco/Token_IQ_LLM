# Customer Installations on AWS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new customer's installation, and roll every existing installation to a new version, each with one command, on AWS, from images we build.

**Architecture:** One shared VPC, one shared Postgres server and one shared load balancer carry every customer. Per customer we create only what must be separate: a container running the product, a database with its own role on the shared server, its own secrets, and a hostname on the shared load balancer. A manifest lists the installations, so provisioning and upgrading both read the same file and neither needs a human to remember who exists.

**Tech Stack:** Terraform, AWS (ECS Fargate, RDS Postgres, ECR, Application Load Balancer, Secrets Manager), Docker, Python 3.12 for the provisioning and upgrade tooling, pytest

**Spec:** `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, sections "How Token IQ is sold and delivered" and Phase 0

## The decisions this plan writes down

Taken on 2026-09-30, because a plan that leaves these open produces infrastructure nobody can price.

**AWS, with plain containers on ECS Fargate.** Chosen over Google Cloud Run, which is less work
to operate, because an enterprise buyer's procurement team never argues about AWS and that
friction is real money at this stage. Plain containers rather than a provider-specific hosting
service, so installing inside a customer's own cloud later stays possible.

**The expensive things are shared; only what must be separate is separate.** One VPC, one
Postgres server, one load balancer. Per customer: a container, a database and role of its own,
its own secrets, its own hostname. A Postgres server per customer is roughly ten times the
cost and is the right answer only when a customer's security review demands it, which is a
decision to take per customer rather than for all of them in advance.

**One container per installation, not three.** The inherited module splits the product into
gateway, backend and UI services, which is right for a large customer and wasteful for a small
one: three tasks and a load balancer each. The product already runs as a single process today,
which is how every developer runs it. The inherited componentized module stays in the tree
unused, as the path for a customer who outgrows one container.

**Our own images, never anyone else's.** The inherited variables default to
`ghcr.io/berriai/litellm-*`. A deployment that forgets to override them would run another
company's published images inside our customer's installation, which is both a branding and a
supply-chain problem. Task 1 makes that impossible rather than discouraged.

## The rule this plan must not break

**One customer must never be able to read another customer's data.**

Sharing a Postgres server is what makes a small customer profitable, and it is also the one
decision that could expose one company's spend and provider credentials to another. The
guarantee cannot rest on the application behaving, because the application is a fork of a
codebase with no tenant boundary, which is exactly why the product ships one installation per
customer in the first place.

So it rests on the database: each installation connects as its own role, which owns its own
database and is granted nothing on any other. A connection string leaked from one installation
must be able to reach that customer's data and nothing else. Task 5 proves this against a real
Postgres server rather than asserting it.

## What this plan can prove without an AWS account, and what it cannot

| Question | Provable now |
|---|---|
| Do our images build from a clean checkout and run | Yes, locally |
| Does a customer's configuration come out complete and valid | Yes, `terraform validate` and unit tests |
| Does provisioning create a database and role with the right privileges | Yes, against real Postgres |
| Can one installation read another's data | Yes, and it is the point of Task 5 |
| Does the upgrade roll every installation and stop on the first failure | Yes, against a local fleet |
| Does Terraform actually apply against AWS | **No. Only an account settles this** |
| Do the AWS costs match the estimate | **No** |
| Does the load balancer route real traffic to the right installation | **No** |

## Global Constraints

- No secrets in the repository, in Terraform state committed anywhere, or in a log. Each
  installation's master key and database password are generated at provisioning and stored in
  Secrets Manager
- No deployment artefact may reference a container registry belonging to another company
- CI supply chain: never pipe a remote script into a shell, pin every external tool to a
  version with a full URL, and verify a SHA-256 checksum before using a downloaded binary
- A customer's database role is granted what it needs and nothing on any other database
- Prisma migrations already run at boot and change schema only, so provisioning does not run
  them separately
- Nothing is copied or adapted from LiteLLM enterprise code
- New Python annotates variables `Final`, uses frozen slotted dataclasses and tagged unions,
  and carries no comments beyond genuinely complex logic. Line length 120
- Tests check behaviour, not structure, and must fail when the behaviour is mutated
- No customer-visible LiteLLM branding anywhere in the deployment artefacts

---

## Task 1: An image reference can only be one of ours

**Files:**
- Create: `tests/code_coverage_tests/check_deployment_images_are_ours.py`
- Modify: `terraform/litellm/aws/variables.tf`

- [x] **Step 1: Write the failing check**

It reads every Terraform variable default, Compose file and workflow, and fails on a container
image belonging to another company. It starts red on the four inherited defaults.

- [x] **Step 2: Make the image variables required rather than defaulted**

A variable with no default fails at plan time when nobody passes one, which is the behaviour
we want: an installation that cannot say which image it runs must not be created at all.

- [x] **Step 3: Run the check, and `terraform validate`, then commit**

---

## Task 2: Our images build and run

**Files:**
- Create: `deploy/images/build.py`, `deploy/images/README.md`
- Create: `tests/test_litellm/deploy/test_image_build.py`

- [ ] **Step 1: Write the failing tests**

The build names every image under our own registry, tags each with the same immutable version
rather than a moving tag, and refuses to build when the working tree is dirty, because an
image nobody can trace back to a commit cannot be rolled back with confidence.

- [ ] **Step 2: Build the all-in-one image locally and run it**

Against the local Postgres, proving the container serves the API and the dashboard and applies
its migrations at boot. This is the step that catches a Dockerfile that only builds on the
machine it was written on.

- [ ] **Step 3: Record what publishing to ECR needs, without an account to publish to**

- [ ] **Step 4: Commit**

---

## Task 3: One customer's installation, described as data

**Files:**
- Create: `deploy/installations/manifest.py`, `deploy/installations/example-manifest.yaml`
- Create: `terraform/tokeniq/installation/` (a lean per-customer module)
- Create: `tests/test_litellm/deploy/test_manifest.py`

- [x] **Step 1: Write the failing tests**

A manifest entry names the customer, its hostname, its image version and its size. Two
installations cannot share a hostname or a database name. A customer name that is not a safe
database identifier is refused at read time, not at apply time.

- [x] **Step 2: Write the module**

Per customer: one ECS service, one target group and listener rule on the shared load
balancer, one Secrets Manager entry, one log group. Shared networking, database server and
load balancer arrive as inputs.

- [x] **Step 3: `terraform validate` and `terraform fmt`, then commit**

---

## Task 4: Creating a customer, and the privileges that keep them apart

**Files:**
- Create: `deploy/installations/provision.py`
- Create: `tests/test_litellm/deploy/test_provision.py`

- [x] **Step 1: Write the failing tests**

Provisioning creates a database, a role that owns only that database, and a generated password
of real length. It is idempotent: running it twice on an existing customer changes nothing and
never resets a password, because resetting one would take a live customer offline.

- [x] **Step 2: Build it**

- [x] **Step 3: Prove it against real Postgres**

- [x] **Step 4: Commit**

---

## Task 5: Prove one customer cannot read another

**Files:**
- Create: `tests/test_litellm/deploy/test_installation_isolation.py`

- [x] **Step 1: Write the failing test**

Provision two customers on one real Postgres server. Write a row for each. Then, connected as
the first customer's role, attempt to read the second's database and the second's tables, and
require every attempt to be refused. Also attempt it after the first role has been granted
everything it legitimately needs, so the test proves isolation rather than proving that a role
with no privileges can do nothing.

- [x] **Step 2: Make it pass**

- [x] **Step 3: Mutate the grants and confirm the test dies**

Grant the first role `CONNECT` on the second database. If the test still passes it is not
testing what it claims, and the whole shared-server decision rests on it.

- [x] **Step 4: Commit**

---

## Task 6: Upgrading every installation with one command

**Files:**
- Create: `deploy/installations/upgrade.py`
- Create: `tests/test_litellm/deploy/test_upgrade.py`

- [x] **Step 1: Write the failing tests**

An upgrade rolls each installation in the manifest to a named version, reports what it did per
customer, and stops on the first failure rather than continuing, because a half-upgraded fleet
where nobody knows which half is worse than a stopped one. A dry run changes nothing and says
what it would do.

- [x] **Step 2: Build it**

- [x] **Step 3: Rehearse against a local fleet of two, then commit**

---

## Task 7: Say what is ready and what an account will settle

**Files:**
- Modify: `docs/superpowers/specs/2026-09-14-token-iq-product-design.md`, `PROJECT.md`
- Create: `deploy/README.md`

- [x] **Step 1: Record the decisions from the top of this plan as decisions, with their dates**

- [x] **Step 2: Write the runbook: create a customer, upgrade the fleet, roll one back**

- [x] **Step 3: Record the estimated cost per customer, and say it is an estimate**

- [x] **Step 4: State what only an AWS account can settle, and what the first one should be used to check**

- [x] **Step 5: Commit**

---

## Self-Review

**1. Spec coverage**

| Spec requirement | Task |
|---|---|
| Working Docker images | Task 2 |
| A deployment pipeline | Tasks 2 and 6 |
| Automated provisioning of a new customer installation | Tasks 3 and 4 |
| One-step upgrades across all installations | Task 6 |
| Each customer has its own proxy, database and settings | Tasks 3, 4 and 5 |
| Migrations apply at boot | Already true, unchanged |
| A staff console showing version, health and subscription | Out of scope, the spec says later |

**2. Placeholder scan**

No "TBD". The cost figure in Task 7 is labelled an estimate because it is one.

**3. Type consistency**

The manifest is the one shared type: read once in Task 3, consumed by provisioning in Task 4
and by the upgrade in Task 6, so neither can invent a customer the other does not know about.

**4. The thing a reviewer should check hardest**

Task 5, and specifically that it would fail if the grants were wrong. Every customer sharing a
Postgres server rests on it, the failure is silent, and the consequence is one company reading
another's spend and provider credentials. A test that passes because a role has no privileges
at all proves nothing, which is why Task 5 grants the role everything it legitimately needs
before trying to cross the boundary.

---

## Whole-plan review, 2026-09-30

Six of seven tasks are done. Task 2, building and publishing our own images, is the one left,
and it is deliberately last: nothing else depends on it, and it is the only task whose value
comes mostly from a registry we do not have yet.

The plan's own Self-Review said a reviewer should check Task 5 hardest, and it was right to.
Mutating the grants found two things, one of them mine.

The real defect was that Postgres rejects a bound parameter in `CREATE ROLE ... PASSWORD`, so
provisioning failed with a syntax error the first time it met a server. No fake cursor would
ever have shown it.

The worse one was a test that passed for the wrong reason. The crossed connection string was
built by substituting the database name across the whole URL, and because a role is named
after its database it changed the username too, so the server refused the connection for a
wrong password. That looks exactly like isolation working. Both grant mutations survived until
it was fixed; both kill their tests now. Without the mutation pass this plan would have
shipped an unproven isolation guarantee that read as proven, which is the worst possible
outcome for the one decision the cost model rests on.

A third mutation still survives and is left surviving on purpose: granting the public schema
back to its owner is redundant on Postgres 15 and later, so nothing kills it on this server.
It stays for 13 and 14, and the code says exactly that rather than looking covered.

One incidental improvement: the deploy tests were first written under `tests/test_litellm/`,
where its conftest made five database tests take twenty-one minutes. They mirror a top-level
package, so they belong in `tests/deploy/`, where they run in two seconds.

Nothing here has touched AWS. `deploy/README.md` says what the first account should be used to
check, in order, and gives a cost estimate from list prices while saying plainly that it is
not a bill.
