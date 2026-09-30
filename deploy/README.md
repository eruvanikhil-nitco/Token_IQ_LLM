# Running customer installations

Every customer company gets its own installation. This is how one is created, upgraded and
rolled back, and what it costs.

## The shape

One shared VPC, one shared Postgres server, one shared load balancer and one shared ECS
cluster carry every customer. Per customer we create only what must not be shared: one
container, one database and role, its own secrets, and a hostname on the shared load balancer.

`deploy/installations/example-manifest.yaml` is the shape of the file that lists them. Both
provisioning and upgrades read it, so neither can act on a customer the other does not know
about.

A version is a commit hash or a semantic version, never a moving tag. An installation whose
version cannot be named cannot be rolled back to a known build.

## Creating a customer

1. Add them to the manifest: key, hostname, version, size. The key becomes their Postgres
   database and role, so it is lower case letters, digits and underscores.
2. Run provisioning against the shared Postgres server. It creates the database and role,
   generates a password, and hands back the connection string. It is safe to run twice: an
   existing customer is left alone and their password is never rotated, because rotating one
   takes a live installation offline.
3. Put the connection string and a generated master key into Secrets Manager.
4. Apply `terraform/tokeniq/installation` with the customer's values and the shared
   infrastructure's identifiers.
5. Point their hostname at the shared load balancer.

Migrations need no step of their own: they run at boot, before the installation serves traffic.

## Upgrading every installation

Roll the fleet to one version with the upgrade tool. It skips anyone already on the target, so
running it twice is safe, and it stops at the first failure rather than carrying on. A
half-upgraded fleet is survivable; a half-upgraded fleet where nobody can say which half is
not. The report names who moved, who failed and why, and who was never attempted.

Run it as a dry run first. That changes nothing and prints the same list.

## Rolling one customer back

Set that customer's version in the manifest to the previous one and apply. This works only
because versions are immutable: the old image is still there under its own name.

Rolling back the application does not roll back the database. A migration that has run stays
run, which is safe because migrations here only ever add to the schema and never rewrite rows.

## What it costs

Estimated from AWS list prices in a single region on 2026-09-30. **Not validated against a
real bill**, because there is no account yet. Treat the shape as reliable and the figures as
approximate.

Shared, the same whether you have one customer or fifty:

| Item | Monthly |
|---|---|
| Application Load Balancer | ~$25 |
| NAT gateway | ~$35 plus data |
| Postgres, one small instance with a standby | ~$50 |
| Registry, logs, secrets overhead | ~$5 |
| **Fixed total** | **~$115** |

Per customer:

| Item | Monthly |
|---|---|
| One always-on container, half a vCPU and 1 GB | ~$18 |
| Two secrets | ~$1 |
| Logs | ~$1 to $3 |
| **Per customer** | **~$20 to $22** |

So roughly $135 a month for the first customer, and about $22 for each one after. At ten
customers that is around $335, or $34 each. At fifty it is around $1,225, or $25 each, though
the Postgres instance would need to grow before then.

**The figure most likely to surprise you is data transfer.** This is a gateway: every token of
every request and response your customers send flows out through the NAT gateway and then to
the internet, at roughly $0.13 per gigabyte combined. A customer moving a terabyte a month
adds about $135 on their own, which is more than the entire fixed cost. Two things reduce it
when it starts to matter: putting the tasks in public subnets with no NAT, or a VPC endpoint
arrangement. Neither is worth doing before the first bill shows it.

The other lever is the always-on container. Fargate bills whether a customer is using the
product or not, so an idle customer still costs about $20. That is the price of a gateway that
must answer at any hour and run its own scheduled collection.

## What only a real account can settle

Everything above is built and tested, but nothing here has run against AWS. Specifically
unproven: that Terraform applies cleanly, that the load balancer routes a real hostname to the
right installation, that a task starts and passes its health check, and that the costs match.

The first account should be used to create one throwaway installation end to end, in this
order: apply the shared infrastructure, provision one customer, apply their installation,
reach it over its hostname, then upgrade it to a second version and roll it back. That
sequence exercises every piece in this directory.
