# Data privacy and security

Token IQ is installed one copy per customer company, on that company's own infrastructure. There is
no Token IQ cloud, no shared database and no telemetry: nothing leaves an installation except the
calls it makes to the AI providers its own administrator connected.

## Reporting a vulnerability

Open a private security advisory on this repository, under Security then Advisories then "Report a
vulnerability". That channel is private until a fix ships, which is why it is the one to use rather
than a public issue.

Please include:

- what an attacker can do, and what they need before they can do it
- the steps to reproduce it, against an installation you own
- the version or commit you tested

A recording helps and is not required. What a report cannot do without is reproduction steps:
a plausible description that does not reproduce takes review time away from one that does.

Do not test against an installation you do not own. Reports that involve somebody else's
installation, or somebody else's provider account, cannot be accepted.

## What counts as a vulnerability here

**P0, the supply chain.** Anything that lets a third party change what an installation runs: the
build, the published image, the migration package, or a dependency's resolution.

**P1, unauthenticated access.** Reading or changing anything on an installation without a valid
key: spend data, virtual keys, provider credentials, or the request log.

**P2, authenticated actions beyond a role.** A key or a signed-in person doing something their role
is not allowed to do, including reading another team's spend or another person's requests.

**P3, the observer-only guarantee.** Token IQ reads provider bills and records gateway traffic. It
must never change which endpoint serves a call, what a response contains, or whether the provider is
reached at all. Anything that makes it do so is a vulnerability in the product's central promise,
not a feature request.

### Not vulnerabilities

- A misconfiguration an administrator has to make for the attack to work, such as running without a
  master key, or granting a credential more provider permissions than the connector asks for
- Anything that requires access the attacker already has, such as the database or the host

## How credentials are held

Two kinds of credential, deliberately kept apart because they carry different risk. A **billing**
credential is read-only access to a provider's cost figures. A **forwarding** credential is what the
gateway sends traffic with. Both are encrypted with the installation's own master key, which the
customer sets and holds; neither is ever shown back once stored.

For AWS, the recommended connection is an IAM role the customer creates in their own account, with
one permission, `ce:GetCostAndUsage`, and a trust policy naming an external ID minted for that one
connection. No long-lived AWS key is stored, and deleting the stack ends Token IQ's access
immediately.

## Keeping the dependencies honest

Every image, package and action is pinned, and updates arrive as pull requests through Dependabot
rather than as a floating tag. Nothing is piped from a remote script into a shell: an artefact is
downloaded, its checksum verified, and then installed.
