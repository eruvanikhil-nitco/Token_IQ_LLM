"""Generate the Upgrading section of CHANGELOG.md from the rename map.

Phase 7 asks for a changelog that lists every renamed variable, key and header, generated from the map
rather than typed out. Typed out it would go stale the first time a name moved and nobody would know,
and the thing a customer reads before upgrading is the worst place for a list that has drifted.

    python scripts/rename/write_upgrading_notes.py --check
    python scripts/rename/write_upgrading_notes.py --apply

The section sits between two markers so it can be regenerated in place. `--check` says whether the file
on disk matches the map, which is what a test asserts.
"""

from __future__ import annotations

import argparse
import csv
import io
import pathlib
import sys
from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
MAP: Final = REPO / "docs" / "plans" / "rename-map.csv"
CHANGELOG: Final = REPO / "CHANGELOG.md"

BEGIN: Final = "<!-- begin generated: scripts/rename/write_upgrading_notes.py -->"
END: Final = "<!-- end generated -->"


class Options(BaseModel):
    """The command line, typed. `parse_args` hands back `Any` for every flag."""

    apply: bool = False
    check: bool = False


def renamed(kind: str) -> tuple[tuple[str, str], ...]:
    with MAP.open(newline="", encoding="utf-8") as handle:
        return tuple((row["old"], row["new"]) for row in csv.DictReader(handle) if row["kind"] == kind and row["new"])


def table(pairs: Sequence[tuple[str, str]], old_heading: str, new_heading: str) -> str:
    rows: Final = "\n".join(f"| `{old}` | `{new}` |" for old, new in sorted(pairs))
    return f"| {old_heading} | {new_heading} |\n| --- | --- |\n{rows}"


def section() -> str:
    variables: Final = renamed("env var")
    keys: Final = renamed("config key")
    headers: Final = renamed("request header")
    metrics: Final = renamed("metric name")
    return f"""{BEGIN}

### Upgrading to this release

Nothing to do about configuration. Every name below was renamed, and this release reads both spellings,
so a running installation keeps working with the settings it already has. The release after next stops
accepting the old ones, so treat this as the window to migrate.

One thing is not a name a customer writes. The database tables keep the names they have, but the Prisma
models that address them were renamed, so the generated Python client has to be rebuilt against the new
schema. An image upgrade already does that at build time. An installation running from a source checkout
or a pip install has to run `prisma generate` itself, and until it does the client still answers to the
old model names: the startup password migration is skipped with a warning and key lookups fail outright.

The proxy logs a deprecation warning the first time it reads each old name, once per name rather than
once per read, which is also the shortest list of what a particular installation still has to change.

Two things do not move. `model: litellm_proxy/gpt-4o` still names the provider that way, because that is
a value a customer writes rather than a setting. And the names kept for legal and historical reasons stay
put: `LICENSE`, `NOTICE`, this file, and the decision records and plans under `docs/`.

#### Environment variables, {len(variables)} of them

The rule is the prefix and nothing else: `LITELLM_` becomes `TOKEN_IQ_`. The new name wins when both are
set, so an operator who has migrated is not overridden by a variable they forgot to delete.

{table(variables, "Before", "Now")}

Variables nothing in this repository reads are not renamed, `LITELLM_LICENSE` among them: the enterprise
package reads that one.

#### Config keys, {len(keys)} of them

Both spellings are accepted anywhere in `config.yaml`, including inside each entry of `model_list`, and
in a config stored in the database or fetched from S3 or GCS.

{table(keys, "Before", "Now")}

#### Request and response headers, {len(headers)} of them

A request is understood under either spelling. A response carries only the new one, which is what makes
the old one droppable later, so anything reading a response header has to be updated in this window
rather than the next.

{table(headers, "Before", "Now")}

#### Prometheus metrics, {len(metrics)} of them

These are the one thing here that does break. A metric is what a dashboard panel and an alert rule query,
so every one of those has to be edited, and the old name is not emitted alongside the new one: Prometheus
would count the same event twice and no amount of compatibility makes a renamed series continue an old one.

Remember the suffixes Prometheus adds when it exposes a metric. A counter named `token_iq_spend_metric` is
queried as `token_iq_spend_metric_total`, and a histogram as `_bucket`, `_sum` and `_count`. Recording rules
and alert expressions need the same edit as the panels.

`prometheus_services` builds a family of names at runtime from the service and the kind of request, and
those move with the prefix as well: `litellm_self_latency` becomes `token_iq_self_latency`.

The Grafana dashboards under `cookbook/` have been updated, so a copy taken after this release queries the
new names.

{table(metrics, "Before", "Now")}

#### Traces and logs

The same kind of break as the metrics, and for the same reason: a trace query or a log filter naming one of
these has to be edited.

84 dotted names move, which are the OpenTelemetry span attributes the engine sets, the Datadog span names it
opens and the Datadog metrics it sends. `litellm.team.metadata` becomes `token_iq.team.metadata` and so on
throughout. Standard `gen_ai.*` attributes keep their names; they belong to a convention rather than to us.

The OpenTelemetry service name, tracer, meter and logger all defaulted to `litellm` and now default to
`token_iq`. Each was already overridable, by `OTEL_SERVICE_NAME`, `OTEL_TRACER_NAME`, `TOKEN_IQ_METER_NAME`
and `TOKEN_IQ_LOGGER_NAME`, so setting the one you want keeps whatever your dashboards already expect. The
value under `gen_ai.framework` moves too, since it names the framework.

Two Python logger names move: `LiteLLM Proxy` becomes `Token IQ Proxy` and `LiteLLM Router` becomes
`Token IQ Router`. If you filter logs by logger name, or route them by it in Datadog, that is the edit.

An A2A agent card served by the proxy now says `Token IQ Proxy` as its organization rather than
`LiteLLM Proxy`.

#### Redis and cache keys

Three cache key prefixes move: the batch read-through cache, the temporary MCP server registry and the
response polling store. Entries written under the old prefix are simply never read again, which costs one
miss each and nothing more.

**Flush any spend or rate-limit counters to the database before upgrading.** Those live in Redis under keys
this release no longer reads, and unlike a cache entry a counter that disappears resets a budget window or a
rate limit rather than causing one slow request.

If you set a Redis namespace yourself, it is untouched: the engine has never added a prefix of its own on
top of yours.

#### Identifiers you already hold

A file id, a batch id, a response id, a container id, an item id and wrapped encrypted content all carry a
prefix inside them. New ones say `token_iq`, and every one issued before this release still decodes, because
anything you saved stays valid for as long as you keep it. There is nothing to migrate and nothing to
re-upload.

The claim sources a guardrail config can name, `litellm:user_id` and its three neighbours, keep working
alongside `token_iq:user_id`.

#### The prefix on an error message

Every error the API returns begins with the exception's name, and that name now says `token_iq`:

```
token_iq.RateLimitError: AnthropicException - rate limited
```

It said `litellm.RateLimitError` before. If your own code matches on that text to decide what went wrong,
this is the release to change it. The gateway reads both, so an error that reaches it from an older
gateway in front is still understood, and `mock_response="litellm.RateLimitError"` keeps working in a test
suite you already have.

#### Names already in your database

Three names the gateway writes for itself change, and two of them you will see. Rows written before this
release keep the name they were written with, and the gateway reads both, so nothing needs correcting.

| Where you see it | Was | Is now |
| --- | --- | --- |
| The key alias on Logs for anything the master key did | `litellm_proxy_master_key` | `token_iq_proxy_master_key` |
| The tag on Tag Management and Usage for the gateway's own health probes | `litellm-internal-health-check` | `token-iq-internal-health-check` |

The third is the team a dashboard login's key belongs to, which you never see because those keys are
filtered out of the Virtual Keys page. It changes too, and sessions you already have keep working: there is
no need to sign everybody out before upgrading.

Usage reports still exclude the health probes under both names, so your own figures do not move.

#### What is not renamed

The Prometheus label `litellm_model_name` keeps its name. It is also a key in the engine's hidden
parameters, read in ten places, so moving it would be a change to something other than metrics. A query
grouping by that label keeps working.

{END}"""


def rewritten(text: str) -> str:
    """The changelog with the generated section replaced, or added under its own heading."""
    if BEGIN in text and END in text:
        before, _, rest = text.partition(BEGIN)
        _, _, after = rest.partition(END)
        return f"{before}{section()}{after}"
    return f"{text.rstrip()}\n\n{section()}\n"


def skeleton() -> str:
    return """# Changelog

This file records what changes between releases, and names the settings an upgrade has to know about.
It keeps the name Token IQ was forked from, which is one of the four places that do; see
`docs/decisions/0023-remove-litellm-names.md`.

## Unreleased

The transition release of the rename. Everything a customer configures now has a Token IQ name, and
every old name still works for one more release.
"""


def main(argv: Sequence[str] | None = None, out: io.TextIOBase | None = None) -> int:
    parser: Final = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--apply", action="store_true", help="write the section")
    _ = parser.add_argument("--check", action="store_true", help="say whether the file matches the map")
    options: Final = Options.model_validate(vars(parser.parse_args(argv)))
    say: Final = out or sys.stdout

    if options.apply == options.check:
        print("pass exactly one of --apply and --check", file=say)
        return 2

    on_disk: Final = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else skeleton()
    wanted: Final = rewritten(on_disk)

    if options.check:
        if wanted == on_disk:
            print("CHANGELOG.md matches the rename map", file=say)
            return 0
        print("CHANGELOG.md is out of step with the rename map; run with --apply", file=say)
        return 1

    _ = CHANGELOG.write_text(wanted, encoding="utf-8")
    print(f"wrote the Upgrading section to {CHANGELOG.relative_to(REPO).as_posix()}", file=say)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
