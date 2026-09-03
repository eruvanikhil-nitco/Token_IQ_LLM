# LiteLLM branding in the Admin UI shell

> **Status: REPLACED, not deleted.** The old branding is swapped for "Token IQ" rather
> than removed. Everything below is a one-line revert.

## What changed

The top-left corner of the sidebar and the account menu now read "Token IQ".

- `leftnav.tsx`, the header `<Link>` renders the new `BrandLogo` instead of the two
  `/get_image` `<img>` tags, and its `aria-label` is now `Token IQ home`
- `SidebarAccountMenu.tsx`, the popover heading and the palm-tree tooltip
- `app/layout.tsx`, the page `<title>` and description
- `components/BrandLogo.tsx`, new, exports `BRAND_NAME` and the mark

## Why it was done this way

The default logo used to be fetched from the proxy's `/get_image` endpoint, which serves
`litellm/proxy/logo.jpg`. Replacing that file would have meant authoring a raster asset in
two theme variants and would have left `alt="LiteLLM"` and the page title untouched.

`BrandLogo` draws the mark as inline SVG using `currentColor`, so one definition covers
light and dark, it is crisp at any size, there is no asset fetch, and there is no font
dependency for the wordmark, which is plain HTML text next to the mark.

## What was deliberately preserved

A custom logo configured through UI settings still wins. `leftnav.tsx` renders the original
`<img>` pair whenever `logoUrl` is set, so `UI_LOGO_PATH`, `UI_LOGO_PATH_DARK` and the
dark-logo `onError` fallback all behave exactly as before. Only the *default* changed.

The `/get_image` endpoint in `proxy_server.py` is untouched, as is `logo.jpg`.

## Scope

Five files plus one new component, all under `ui/litellm-dashboard/src`. No Python changed.
Feature-level strings that legitimately name the upstream project, "LiteLLM Parameters",
"LiteLLM LLM as a Judge", "LiteLLM Content Filter", were left alone: they name a provider
or a parameter group, not the company in the corner.

## How to restore

```bash
git checkout litellm_internal_staging -- ui/litellm-dashboard/src/components/leftnav.tsx   ui/litellm-dashboard/src/components/leftnav.test.tsx   ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.tsx   ui/litellm-dashboard/src/components/SidebarAccountMenu/SidebarAccountMenu.test.tsx   ui/litellm-dashboard/src/app/layout.tsx
rm ui/litellm-dashboard/src/components/BrandLogo.tsx
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```

To keep the code but change only the displayed name, edit `BRAND_NAME` in
`components/BrandLogo.tsx`; `leftnav.tsx` and `SidebarAccountMenu.tsx` both read it.
