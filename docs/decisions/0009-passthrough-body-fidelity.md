# Pass-through body fidelity: the managed-id rewriter

> **Status: ASSERTED, nothing removed.** The rewriter was already unreachable on this
> build. This entry adds a startup check so that stays true on purpose rather than by
> accident, and records why the feature conflicts with a forwarding gateway.

## What the managed-id rewriter does

LiteLLM can hand clients its own IDs instead of the provider's. `managed_id_rewriter.py`
does this in both directions.

On the response path, `rewrite_response_ids()` looks up `(provider, method, path)` in
`BUILTIN_OUTPUT_ID_FIELD_MAP`, mints a managed ID for each listed field, stores a DB row
mapping it to the raw value, and swaps it into the body before the client sees it.

On the request path, `rewrite_path_ids()`, `rewrite_query_ids()` and `rewrite_body_ids()`
walk the URL path, query string and body, and `_resolve_one()` turns any managed ID back
into the raw provider ID. It raises 404 when the provider embedded in the ID does not match
the route, 404 for IDs absent from the DB, and 403 when the caller does not own the
resource.

The map is narrow: OpenAI and Azure only, on files, batches and responses. It covers `id`
on `/v1/files`, `id` plus `input_file_id` / `output_file_id` / `error_file_id` on
`/v1/batches`, and `id` on `/v1/responses`. Chat completions are untouched.

## Why the response rewrite exists

It is easy to read the outbound swap as gratuitous. It is not: it is the enrollment step
that makes the inbound check possible at all.

`_resolve_one()` decodes every inbound value first, and returns it unchanged when it does
not decode as a managed ID, the "deliberate opt-out for raw OpenAI IDs" in the docstring.
So the three enforcement rules only ever apply to IDs the gateway itself issued.

Leave the response body alone and the loop never closes: the client receives
`file-abc123`, sends it back, `decode()` returns None, and it is forwarded with no
ownership check. Anyone holding that string gets the same free pass. You can only validate
IDs you minted, and rewriting the response is how you mint them.

Two things ride along. The DB row also stores a snapshot of the file object, so a list-files
call can be served from LiteLLM's table instead of the provider. And the managed ID embeds
the provider name, so an ID minted on the `azure` route 404s when replayed against
`openai`, which a raw provider ID cannot express.

## Why it conflicts with a forwarding gateway

It rewrites the provider's response body, and it can reject with 404 or 403 a request the
provider would have accepted. Both break byte-for-byte forwarding.

There is a second cost specific to an observability product: the ID the client sees never
existed at the provider, so gateway logs and the provider's own console cannot be joined on
ID. The isolation it buys is real, but it is available more cheaply by scoping credentials
per tenant and leaving the provider's IDs intact.

## Why nothing was removed

Both call sites, the input rewrite at `pass_through_endpoints.py:1089` and the output
rewrite at `:1501`, are gated on `proxy_logging_obj.get_proxy_hook("managed_files")` being
non-None. That hook ships in `enterprise/litellm_enterprise/proxy/hooks/managed_files.py`,
which left with the enterprise package in `728daee2d8`. The hook cannot be registered, the
gate is always None, and neither rewriter runs.

So byte fidelity here was already true, but only as a side effect of an unrelated deletion.

## What was added

`assert_passthrough_body_fidelity()` in `pass_through_endpoints/common_utils.py`, called
from `ProxyLogging.startup_event` immediately after `_init_litellm_callbacks` populates
`proxy_hook_mapping`. If the hook is ever registered again, the proxy refuses to start
instead of silently resuming body rewrites.

It takes the hook as a parameter rather than reaching for global state, so the tests inject
one instead of patching module internals.

## Verification

Four tests in
`tests/test_litellm/proxy/pass_through_endpoints/test_passthrough_endpoints_common_utils.py`:
the helper accepts None, the helper rejects a registered hook, `startup_event` aborts when
one is registered, and `startup_event` still completes when none is.

The wiring test drives `startup_event` rather than inspecting source. Confirmed it has
teeth by deleting the call and re-running: `test_proxy_startup_refuses_a_registered_managed_files_hook`
fails, 1 failed / 8 passed. With the call restored, 20 passed across this file and
`test_managed_id_rewriter.py`.

## How to restore the old behaviour

Delete the `assert_passthrough_body_fidelity(...)` line from `ProxyLogging.startup_event`.
Re-enabling the rewriter itself additionally needs the enterprise `managed_files` hook back,
see `06-enterprise-licensed-code.md`.
