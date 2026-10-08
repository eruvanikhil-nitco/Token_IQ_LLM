# Rebranding what a client actually sees

> **Status: CHANGED (copy only).** No identifiers renamed. Both passes.

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

## Update, 8 Oct 2026: omitted rather than invented

The reasoning above weighed two options, keep the upstream defaults or invent Token IQ ones, and chose to
keep them because inventing is not a decision to make on someone's behalf. There is a third: render
neither.

An unset logo now produces no `<img>` and an unset support address no "any questions" line, through
`email_tag` and `email_support_line` beside the footer. Nothing is invented and nothing leaves for a third
party, which also closes the definition-of-done line "no runtime call leaves for upstream": every opened
alert email used to fetch an image from another company's S3 bucket. The override advice stands unchanged,
and setting `EMAIL_LOGO_URL` or `SMTP_SENDER_LOGO` and `EMAIL_SUPPORT_CONTACT` is still the way to put a
logo and an address in.

The email footer went the same way. It carried a Token IQ copyright line above links to another company's
Twitter and website, and a GitHub link with an empty href.

## Pass two: the admin dashboard

86 replacements across 24 files, all of them copy where LiteLLM meant *this gateway*: the
login page, the MCP connect tab and its cURL examples, the transform-request explainer, the
model-name hints on Add Model, the agent card discovery text, the cache-control hints, the
UI theme page, and the pricing calculator export footer.

**The login page was missed in pass one.** `OnboardingFormBody.tsx` is the invitation-accept
screen; `app/login/LoginPage.tsx` is the actual sign-in page, and it still showed `🚅 LiteLLM`
twice plus "Access your LiteLLM Admin UI". Two files, similar names, and only one of them is
what a person sees when they log in.

### What was deliberately left alone

**LiteLLM's own product names.** "LiteLLM Content Filter", "LiteLLM LLM as a Judge",
"LiteLLM Built-in", "a native LiteLLM guardrail", "a LiteLLM Enterprise feature". Renaming
these would claim authorship of someone else's work, and the guardrail garden genuinely lists
LiteLLM's built-in guardrails alongside partner ones.

**Links to `docs.litellm.ai`** and their link text, 189 of them. They point at real, working
documentation. Rebranding the words while the link still goes to LiteLLM reads worse than
leaving it honest.

**"LiteLLM Params" and "LiteLLM Parameters"** as field labels. They label the `litellm_params`
config key, which is not being renamed. A label that no longer matches the key the user has to
type in `config.yaml` would be actively misleading.

**`LiteLLM_TableName` type names**, which mirror the database tables, and every identifier.

### Grammar the sweep broke, and the fix

Replacing "LiteLLM proxy" with "Token IQ" leaves the article dangling: "used by the Token IQ
itself", "an API call to the Token IQ with", "emitted by the Token IQ during". Three of those
were caught by reading the diff rather than trusting the replacement. A blind sweep would have
shipped them.

`schema.d.ts` also picked up 24 replacements before being reverted: it is generated from the
OpenAPI spec and must never be hand-edited, and those descriptions come from backend docstrings
that regeneration will carry across properly.

### Tests that pinned the old copy

Three failed, all of them correct failures rather than breakage: two asserting the cache-control
role hint verbatim, one selecting a tab by the accessible name "LiteLLM Proxy". Updated to the
new strings. `TeamGuardrailsTab.test.tsx` was already in sync because the sweep covered test
files too, which is right for assertions on visible labels.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
