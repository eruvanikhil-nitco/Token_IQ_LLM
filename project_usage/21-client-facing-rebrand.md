# Rebranding what a client actually sees

> **Status: CHANGED (copy only).** No identifiers renamed. Pass one of two.

## Why not rename everything

A blanket `litellm` -> `Token IQ` rename would destroy the project. Measured:

```
occurrences (excl. build output and deps):   521,641 across 5,513 files
  python imports (import litellm):            33,271
  API/SDK calls (litellm.something):          58,350
  config keys (litellm_params/_settings):     16,061
  distinct DB tables (LiteLLM_*):              3,912
  distinct env vars (LITELLM_*):                 300
```

Almost none of that is branding. `litellm` is the name of the Python package, so renaming the
directory breaks 33,271 imports and nothing boots. The database tables really are called
`LiteLLM_VerificationToken` and `LiteLLM_TeamTable`, and the live data sits in them.
`litellm_params` and `litellm_settings` are the format of `dev_config.yaml` itself, and also
appear in API responses the dashboard parses.

`LICENSE` must keep its attribution regardless: this is a fork of an MIT-licensed project.

Branding is what a person sees. Nobody using this gateway types `import litellm`. So the
internal names stay, which is also what keeps `git fetch upstream` viable.

## Pass one: everything a client sees

**The API docs page at `/`**, which is the first thing anyone pointed at this gateway meets.
It read `LiteLLM API` and linked to LiteLLM's enterprise docs.

Worth recording: `DOCS_TITLE` and `DOCS_DESCRIPTION` were read from the environment *only for
premium users*; every other deployment got a hardcoded `"LiteLLM API"`. So the documented way
to rebrand this did not work here. The env vars are now honoured for every deployment, with
`Token IQ API` as the default, which also removes an enterprise gate.

The description dropped the "Enterprise Edition" prefix, the "Customize Swagger Docs" upsell
and the model-cost-map link, and now points at this gateway's own admin panel and model hub.

**The public model hub** defaulted its browser tab to `LiteLLM Gateway`. That is the page
shared outside the company.

**The login page** showed `🚅 LiteLLM` above the sign-in form.

**Every email a user receives**: the invitation, the key-created and key-rotated notices, the
budget and soft-budget alerts, and the alert-email subjects. Titles, headings, sign-offs,
logo alt text and the footer copyright.

## The thing that matters more than the name

Emails fall back to LiteLLM's own logo and support address when nothing is configured:

```python
LITELLM_LOGO_URL: Final = "https://litellm-listing.s3.amazonaws.com/litellm_logo.png"
LITELLM_SUPPORT_CONTACT: Final = "support@berri.ai"
```

The invitation email renders that address directly:

> Thanks for signing up. We're here to help you and your team. If you have any questions,
> contact us at {email_support_contact}

So an invited user is told to email BerriAI for support, and their mail client fetches a logo
from LiteLLM's S3 bucket. Left unchanged deliberately, because inventing a support address or
a logo URL is not a decision to make on someone's behalf. Both are overridable without code:
set `EMAIL_LOGO_URL` (or `SMTP_SENDER_LOGO`) and `EMAIL_SUPPORT_CONTACT`. Do it before
inviting anyone.

## Pass two, not done

370 mentions remain in the admin dashboard, splitting cleanly:

- **189 are links to `docs.litellm.ai`**, which are real, working documentation. Rebranding
  the surrounding text while the link still goes to LiteLLM would read worse than leaving it.
- **181 are visible copy**, mostly on features not in use here: guardrails, caching, MCP
  servers, agents, prompt compression.

Some of those should stay. "LiteLLM Content Filter" names LiteLLM's own guardrail, and
renaming it claims authorship of someone else's work.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
