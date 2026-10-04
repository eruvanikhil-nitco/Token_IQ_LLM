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

## Shown on the page, not just in a dialog

The address does not depend on the key, so withholding it until the key is created was
arbitrary. `components/shared/GatewayBaseUrl.tsx` renders it as a compact line using the
existing shared `CopyButton` rather than a second copy implementation, and returns `null`
when the address is unknown.

It sits in the Virtual Keys page header, right-anchored opposite the "+ Create New Key"
button, so it is readable without opening anything. `PageHeader` already has a `utilities`
slot that renders with `ml-auto` next to `primaryAction`, so this needed no layout changes:
the CTA stays where it was and the URL takes the other end of the same control row.

It first went inside the create dialog's header, which was worse. You had to open a modal to
read a value that never changes, and it was invisible to anyone browsing existing keys.

The save dialog keeps its own copy, deliberately. The page header answers "where does this
gateway live" while you are working; the save dialog is what gets copied and handed to
whoever will use the key, so it has to carry both facts on its own.

Not added to the Add Agent wizard's key step, which creates a key through the same shared
display. Worth doing if that flow is used to hand keys to other people.

## Tests

Five added to `CreatedKeyDisplay.test.tsx`, taking it from 7 to 12. Both of the ones that
matter were mutation-checked:

- dropping `/v1` from the snippet kills "should build an example request carrying both the
  base URL and the key"
- rendering the base URL block unconditionally kills "should omit the base URL and example
  when no base URL is known"

Three more for `GatewayBaseUrl`, and two in `VirtualKeysTable.test.tsx`: one that the header
shows the address, one that it is anchored opposite the CTA rather than next to it. Deleting
the `utilities` prop from `PageHeader` kills both.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
