# Base URL in the key creation flow

> **Status: ADDED.** No code removed. One shared component rewritten, one added, one test
> mock completed.

## Why

A virtual key authenticates a caller. It carries no routing information at all: the proxy
only learns which key it is holding after the request has already arrived. So a client needs
two separate facts to reach this gateway.

- the **base URL**, which decides where the request goes
- the **key**, which decides what happens once it arrives

The dashboard was handing over only the second one. `getProxyBaseUrl()` appears in AI Hub's
code samples and its share link, and nowhere in the key creation flow, so whoever received a
key had to already know the gateway's address from somewhere else.

That is fine for the person running the proxy and wrong for everyone else. When keys are
issued to other teams' applications, the person holding the key is exactly the person who
does not know the URL. Verified live earlier in this work: an app given only the key, with
no `base_url` and no `OPENAI_BASE_URL`, goes to `api.openai.com` and gets their 401. It
fails in a way that looks like a bad key rather than a missing address.

## What changed

`components/shared/CreatedKeyDisplay.tsx` now renders three things instead of one:

- the virtual key, as before
- the base URL, defaulting to `getProxyBaseUrl()`
- a ready-to-paste `curl` with both values already filled in

Each has its own copy button. The repeated label, value box, copy button and transient
"Copied!" state are factored into a local `CopyableField` so the three do not drift.

`baseUrl` is a prop with a default rather than a bare call to `getProxyBaseUrl()`, which
keeps the component injectable and lets the tests assert against a fixed URL instead of
jsdom's origin. When it is empty the base URL block and the example are omitted rather than
rendering an empty box and a broken snippet.

The component is shared, so both places that create a key get this: the Virtual Keys page
(`create_key_button.tsx`) and the Add Agent wizard (`add_agent_form.tsx`). Neither call site
changed.

## The snippet uses `/v1`

`curl <base>/v1/chat/completions`. The proxy serves the OpenAI-compatible routes under both
`/` and `/v1`, but `/v1` is what the OpenAI SDKs append themselves and what a reader is most
likely to recognise. AI Hub's Python sample passes the bare origin as `base_url` because the
SDK adds the rest; a raw `curl` has to spell it out.

## A test mock that was quietly incomplete

`add_agent_form.integration.test.tsx` mocks `@/components/networking` with an explicit
object listing seven exports. Importing `getProxyBaseUrl` into the shared component broke
it, because the factory does not include that export, and vitest turns a missing export into
an unhandled error rather than `undefined`.

Worth knowing for anything else that pulls a new function out of `networking`: every test
that mocks that module with a literal factory has to grow the same entry. The alternative is
`importOriginal`, which the file deliberately does not use.

## Shown before the key exists too

The address does not depend on the key, so withholding it until the key is created was
arbitrary. `components/shared/GatewayBaseUrl.tsx` renders it as a compact line under the
"Create New Key" dialog title, using the existing shared `CopyButton` rather than a second
copy implementation. It returns `null` when the address is unknown.

Both places still show it, and that is deliberate. The dialog header answers "where does
this thing live" while you are filling the form; the save dialog is what gets copied and
handed to whoever will use the key, so it needs to carry both facts on its own.

Not added to the Add Agent wizard's key step, which creates a key through the same shared
display. Worth doing if that flow is used to hand keys to other people.

## Tests

Five added to `CreatedKeyDisplay.test.tsx`, taking it from 7 to 12. Both of the ones that
matter were mutation-checked:

- dropping `/v1` from the snippet kills "should build an example request carrying both the
  base URL and the key"
- rendering the base URL block unconditionally kills "should omit the base URL and example
  when no base URL is known"

Three more for `GatewayBaseUrl`, and one integration case in
`create_key_button.integration.test.tsx` proving the dialog actually renders it. Deleting the
`<GatewayBaseUrl />` line from the dialog header kills that one.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
