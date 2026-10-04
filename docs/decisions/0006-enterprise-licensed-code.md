# Enterprise-licensed code

## Why this was removed

You asked for a local OSS-only build. `enterprise/` is a separate uv workspace member
carrying its own commercial licence, `enterprise/LICENSE.md`, which is not the repo's MIT
licence. It held the SSO handler, SCIM, audit-log endpoints, project management, managed
files and vector stores, the llama-guard / llm-guard guardrails, PagerDuty alerting and the
Resend / SendGrid / SMTP senders.

Nothing in `litellm/` needed patching. All 37 `litellm_enterprise` import sites across 16
files were already guarded, so the proxy boots, serves traffic, writes spend logs and signs
in to the Admin UI with the package absent. Two import misses remain and log at DEBUG,
`proxy_server.py:9645` and `:9674`, both for cost checking that was enterprise-gated anyway.

## What was removed

Commit `728daee2d8`, 243 files, 11,766 deletions:

- `enterprise/` (211 tracked files, 5.0 MB), the workspace member
- `tests/enterprise/` and `tests/test_litellm/enterprise/` (31 files)
- `litellm/proxy/enterprise`, a symlink to `../../enterprise`
- The `litellm-enterprise==0.1.63` dependency, its `[tool.uv.sources]` entry and
  `"enterprise"` from `[tool.uv.workspace] members` in `pyproject.toml`

## Why the code is not inlined here

Unlike the other documents in this folder, the source is deliberately not pasted in.
`enterprise/LICENSE.md` permits modification for development and testing but forbids
copying, publishing and distributing the software. Duplicating it into a second location in
the working tree serves no purpose when git already holds every byte, and it would put a
commercially licensed copy somewhere easy to publish by accident.

Nothing is lost: the commit is intact and the restore below is exact.

## How to restore

```bash
git checkout 728daee2d8^ -- enterprise tests/enterprise tests/test_litellm/enterprise litellm/proxy/enterprise pyproject.toml
uv sync --extra proxy --extra extra_proxy --no-install-project
```

Or drop the whole commit, if it is still the tip:

```bash
git revert --no-commit 728daee2d8
```

## Full file list

```
enterprise/LICENSE.md
enterprise/README.md
enterprise/__init__.py
enterprise/cloudformation_stack/litellm.yaml
enterprise/dist/litellm_enterprise-0.1.1-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.1.tar.gz
enterprise/dist/litellm_enterprise-0.1.10-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.10.tar.gz
enterprise/dist/litellm_enterprise-0.1.11-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.11.tar.gz
enterprise/dist/litellm_enterprise-0.1.12-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.12.tar.gz
enterprise/dist/litellm_enterprise-0.1.13-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.13.tar.gz
enterprise/dist/litellm_enterprise-0.1.15-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.15.tar.gz
enterprise/dist/litellm_enterprise-0.1.17-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.17.tar.gz
enterprise/dist/litellm_enterprise-0.1.19-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.19.tar.gz
enterprise/dist/litellm_enterprise-0.1.2-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.2.tar.gz
enterprise/dist/litellm_enterprise-0.1.21-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.21.tar.gz
enterprise/dist/litellm_enterprise-0.1.22-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.22.tar.gz
enterprise/dist/litellm_enterprise-0.1.23-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.23.tar.gz
enterprise/dist/litellm_enterprise-0.1.24-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.24.tar.gz
enterprise/dist/litellm_enterprise-0.1.25-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.25.tar.gz
enterprise/dist/litellm_enterprise-0.1.26-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.26.tar.gz
enterprise/dist/litellm_enterprise-0.1.27-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.27.tar.gz
enterprise/dist/litellm_enterprise-0.1.29-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.29.tar.gz
enterprise/dist/litellm_enterprise-0.1.3-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.3.tar.gz
enterprise/dist/litellm_enterprise-0.1.30-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.30.tar.gz
enterprise/dist/litellm_enterprise-0.1.31-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.31.tar.gz
enterprise/dist/litellm_enterprise-0.1.32-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.32.tar.gz
enterprise/dist/litellm_enterprise-0.1.4-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.4.tar.gz
enterprise/dist/litellm_enterprise-0.1.5-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.5.tar.gz
enterprise/dist/litellm_enterprise-0.1.6-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.6.tar.gz
enterprise/dist/litellm_enterprise-0.1.7-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.7.tar.gz
enterprise/dist/litellm_enterprise-0.1.8-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.8.tar.gz
enterprise/dist/litellm_enterprise-0.1.9-py3-none-any.whl
enterprise/dist/litellm_enterprise-0.1.9.tar.gz
enterprise/enterprise_hooks/__init__.py
enterprise/enterprise_hooks/aporia_ai.py
enterprise/enterprise_hooks/banned_keywords.py
enterprise/enterprise_hooks/blocked_user_list.py
enterprise/enterprise_hooks/google_text_moderation.py
enterprise/enterprise_hooks/openai_moderation.py
enterprise/enterprise_ui/README.md
enterprise/enterprise_ui/_enterprise_colors.json
enterprise/litellm_enterprise/__init__.py
enterprise/litellm_enterprise/enterprise_callbacks/__init__.py
enterprise/litellm_enterprise/enterprise_callbacks/callback_controls.py
enterprise/litellm_enterprise/enterprise_callbacks/example_logging_api.py
enterprise/litellm_enterprise/enterprise_callbacks/llama_guard.py
enterprise/litellm_enterprise/enterprise_callbacks/llm_guard.py
enterprise/litellm_enterprise/enterprise_callbacks/pagerduty/__init__.py
enterprise/litellm_enterprise/enterprise_callbacks/pagerduty/pagerduty.py
enterprise/litellm_enterprise/enterprise_callbacks/secret_detection.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/__init__.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/adafruit.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/adobe.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/age_secret_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/airtable_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/algolia_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/alibaba.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/asana.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/atlassian_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/authress_access_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/beamer_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/bitbucket.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/bittrex.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/clojars_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/codecov_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/coinbase_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/confluent.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/contentful_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/databricks_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/datadog_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/defined_networking_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/digitalocean.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/discord.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/doppler_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/droneci_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/dropbox.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/duffel_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/dynatrace_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/easypost.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/etsy_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/facebook_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/fastly_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/finicity.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/finnhub_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/flickr_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/flutterwave.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/frameio_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/freshbooks_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/gcp_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/github_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/gitlab.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/gitter_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/gocardless_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/grafana.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/hashicorp_tf_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/heroku_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/hubspot_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/huggingface.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/intercom_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/jfrog.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/jwt.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/kraken_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/kucoin.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/launchdarkly_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/linear.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/linkedin.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/lob.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/mailgun.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/mapbox_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/mattermost_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/messagebird.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/microsoft_teams_webhook.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/netlify_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/new_relic.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/nytimes_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/okta_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/openai_api_key.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/planetscale.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/postman_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/prefect_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/pulumi_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/pypi_upload_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/rapidapi_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/readme_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/rubygems_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/scalingo_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/sendbird.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/sendgrid_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/sendinblue_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/sentry_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/shippo_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/shopify.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/slack.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/snyk_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/squarespace_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/sumologic.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/telegram_bot_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/travisci_access_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/twitch_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/twitter.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/typeform_api_token.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/vault.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/yandex.py
enterprise/litellm_enterprise/enterprise_callbacks/secrets_plugins/zendesk_secret_key.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/__init__.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/base_email.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/endpoints.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/resend_email.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/sendgrid_email.py
enterprise/litellm_enterprise/enterprise_callbacks/send_emails/smtp_email.py
enterprise/litellm_enterprise/integrations/__init__.py
enterprise/litellm_enterprise/integrations/custom_guardrail.py
enterprise/litellm_enterprise/litellm_core_utils/__init__.py
enterprise/litellm_enterprise/litellm_core_utils/litellm_logging.py
enterprise/litellm_enterprise/proxy/__init__.py
enterprise/litellm_enterprise/proxy/audit_logging_endpoints.py
enterprise/litellm_enterprise/proxy/auth/__init__.py
enterprise/litellm_enterprise/proxy/auth/custom_sso_handler.py
enterprise/litellm_enterprise/proxy/auth/route_checks.py
enterprise/litellm_enterprise/proxy/auth/user_api_key_auth.py
enterprise/litellm_enterprise/proxy/common_utils/__init__.py
enterprise/litellm_enterprise/proxy/common_utils/check_batch_cost.py
enterprise/litellm_enterprise/proxy/common_utils/check_responses_cost.py
enterprise/litellm_enterprise/proxy/enterprise_routes.py
enterprise/litellm_enterprise/proxy/hooks/__init__.py
enterprise/litellm_enterprise/proxy/hooks/managed_files.py
enterprise/litellm_enterprise/proxy/hooks/managed_vector_stores.py
enterprise/litellm_enterprise/proxy/management_endpoints/__init__.py
enterprise/litellm_enterprise/proxy/management_endpoints/internal_user_endpoints.py
enterprise/litellm_enterprise/proxy/management_endpoints/key_management_endpoints.py
enterprise/litellm_enterprise/proxy/management_endpoints/project_endpoints.py
enterprise/litellm_enterprise/proxy/proxy_server.py
enterprise/litellm_enterprise/proxy/readme.md
enterprise/litellm_enterprise/proxy/ui_crud_endpoints/__init__.py
enterprise/litellm_enterprise/proxy/ui_crud_endpoints/ui_settings_extensions.py
enterprise/litellm_enterprise/proxy/utils.py
enterprise/litellm_enterprise/proxy/vector_stores/__init__.py
enterprise/litellm_enterprise/proxy/vector_stores/endpoints.py
enterprise/litellm_enterprise/py.typed
enterprise/litellm_enterprise/types/__init__.py
enterprise/litellm_enterprise/types/enterprise_callbacks/__init__.py
enterprise/litellm_enterprise/types/enterprise_callbacks/send_emails.py
enterprise/litellm_enterprise/types/proxy/__init__.py
enterprise/litellm_enterprise/types/proxy/audit_logging_endpoints.py
enterprise/litellm_enterprise/types/proxy/proxy_server.py
enterprise/pyproject.toml
litellm/proxy/enterprise
tests/enterprise/conftest.py
tests/enterprise/litellm_enterprise/enterprise_callbacks/test_prometheus_logging_callbacks.py
tests/enterprise/litellm_enterprise/integrations/test_custom_guardrail.py
tests/enterprise/litellm_enterprise/integrations/test_prometheus.py
tests/enterprise/litellm_enterprise/integrations/test_prometheus_unit_tests.py
tests/enterprise/litellm_enterprise/proxy/auth/test_route_checks.py
tests/enterprise/litellm_enterprise/proxy/auth/test_user_api_key_auth.py
tests/enterprise/litellm_enterprise/proxy/guardrails/conftest.py
tests/enterprise/litellm_enterprise/proxy/guardrails/test_apply_guardrail_endpoint.py
tests/enterprise/litellm_enterprise/proxy/guardrails/test_bedrock_apply_guardrail.py
tests/enterprise/litellm_enterprise/proxy/hooks/test_managed_files.py
tests/enterprise/litellm_enterprise/proxy/management_endpoints/test_internal_user_endpoints.py
tests/enterprise/litellm_enterprise/proxy/management_endpoints/test_project_endpoints_prisma.py
tests/enterprise/litellm_enterprise/proxy/test_audit_logging_endpoints.py
tests/test_litellm/enterprise/enterprise_callbacks/send_emails/test_base_email.py
tests/test_litellm/enterprise/enterprise_callbacks/send_emails/test_endpoints.py
tests/test_litellm/enterprise/enterprise_callbacks/send_emails/test_resend_email.py
tests/test_litellm/enterprise/enterprise_callbacks/send_emails/test_sendgrid_email.py
tests/test_litellm/enterprise/enterprise_callbacks/test_callback_controls.py
tests/test_litellm/enterprise/enterprise_callbacks/test_secret_detection.py
tests/test_litellm/enterprise/proxy/__init__.py
tests/test_litellm/enterprise/proxy/test_afile_retrieve_returns_unified_id.py
tests/test_litellm/enterprise/proxy/test_batch_retrieve_input_file_id.py
tests/test_litellm/enterprise/proxy/test_batch_retrieve_registers_missing_output_file_id.py
tests/test_litellm/enterprise/proxy/test_batch_retrieve_returns_unified_input_file_id.py
tests/test_litellm/enterprise/proxy/test_batch_update_db_managed_output_file_id.py
tests/test_litellm/enterprise/proxy/test_deleted_file_returns_403_not_404.py
tests/test_litellm/enterprise/proxy/test_enterprise_routes.py
tests/test_litellm/enterprise/proxy/test_file_deletion_blocking.py
tests/test_litellm/enterprise/proxy/test_managed_files_access_check.py
tests/test_litellm/enterprise/proxy/test_managed_files_hook.py
```
