# Changelog

This file records what changes between releases, and names the settings an upgrade has to know about.
It keeps the name Token IQ was forked from, which is one of the four places that do; see
`docs/decisions/0023-remove-litellm-names.md`.

## Unreleased

The transition release of the rename. Everything a customer configures now has a Token IQ name, and
every old name still works for one more release.

<!-- begin generated: scripts/rename/write_upgrading_notes.py -->

### Upgrading to this release

Nothing to do. Every name below was renamed, and this release reads both spellings, so a running
installation keeps working with the configuration it already has. The release after next stops accepting
the old ones, so treat this as the window to migrate.

The proxy logs a deprecation warning the first time it reads each old name, once per name rather than
once per read, which is also the shortest list of what a particular installation still has to change.

Two things do not move. `model: litellm_proxy/gpt-4o` still names the provider that way, because that is
a value a customer writes rather than a setting. And the names kept for legal and historical reasons stay
put: `LICENSE`, `NOTICE`, this file, and the decision records and plans under `docs/`.

#### Environment variables, 101 of them

The rule is the prefix and nothing else: `LITELLM_` becomes `TOKEN_IQ_`. The new name wins when both are
set, so an operator who has migrated is not overridden by a variable they forgot to delete.

| Before | Now |
| --- | --- |
| `LITELLM_AGENT_HEALTH_CHECK_GATHER_TIMEOUT` | `TOKEN_IQ_AGENT_HEALTH_CHECK_GATHER_TIMEOUT` |
| `LITELLM_AGENT_HEALTH_CHECK_TIMEOUT` | `TOKEN_IQ_AGENT_HEALTH_CHECK_TIMEOUT` |
| `LITELLM_ANTHROPIC_DISABLE_URL_SUFFIX` | `TOKEN_IQ_ANTHROPIC_DISABLE_URL_SUFFIX` |
| `LITELLM_ANTHROPIC_PROMPT_CACHING_TTL` | `TOKEN_IQ_ANTHROPIC_PROMPT_CACHING_TTL` |
| `LITELLM_ASSETS_PATH` | `TOKEN_IQ_ASSETS_PATH` |
| `LITELLM_ASYNCIO_QUEUE_MAXSIZE` | `TOKEN_IQ_ASYNCIO_QUEUE_MAXSIZE` |
| `LITELLM_AZURE_REALTIME_PROTOCOL` | `TOKEN_IQ_AZURE_REALTIME_PROTOCOL` |
| `LITELLM_CLI_DISABLE_KEYRING` | `TOKEN_IQ_CLI_DISABLE_KEYRING` |
| `LITELLM_CLI_JWT_EXPIRATION_HOURS` | `TOKEN_IQ_CLI_JWT_EXPIRATION_HOURS` |
| `LITELLM_CLI_SSO_CLAIM_MAP` | `TOKEN_IQ_CLI_SSO_CLAIM_MAP` |
| `LITELLM_CONFIG_BUCKET_NAME` | `TOKEN_IQ_CONFIG_BUCKET_NAME` |
| `LITELLM_CONFIG_BUCKET_OBJECT_KEY` | `TOKEN_IQ_CONFIG_BUCKET_OBJECT_KEY` |
| `LITELLM_CONFIG_BUCKET_TYPE` | `TOKEN_IQ_CONFIG_BUCKET_TYPE` |
| `LITELLM_CONFIG_PARAM_CACHE_TTL_SECONDS` | `TOKEN_IQ_CONFIG_PARAM_CACHE_TTL_SECONDS` |
| `LITELLM_CONTENT_FILTER_ALLOW_EXTERNAL_PATHS` | `TOKEN_IQ_CONTENT_FILTER_ALLOW_EXTERNAL_PATHS` |
| `LITELLM_CORS_ALLOW_CREDENTIALS` | `TOKEN_IQ_CORS_ALLOW_CREDENTIALS` |
| `LITELLM_CORS_ORIGINS` | `TOKEN_IQ_CORS_ORIGINS` |
| `LITELLM_DD_AGENT_HOST` | `TOKEN_IQ_DD_AGENT_HOST` |
| `LITELLM_DD_AGENT_PORT` | `TOKEN_IQ_DD_AGENT_PORT` |
| `LITELLM_DD_LLM_OBS_PORT` | `TOKEN_IQ_DD_LLM_OBS_PORT` |
| `LITELLM_DEFAULT_EMBEDDING_ENCODING_FORMAT` | `TOKEN_IQ_DEFAULT_EMBEDDING_ENCODING_FORMAT` |
| `LITELLM_DEPLOYMENT_ENVIRONMENT` | `TOKEN_IQ_DEPLOYMENT_ENVIRONMENT` |
| `LITELLM_DETAILED_TIMING` | `TOKEN_IQ_DETAILED_TIMING` |
| `LITELLM_DEV_ENV_HOT_RELOAD` | `TOKEN_IQ_DEV_ENV_HOT_RELOAD` |
| `LITELLM_DISABLE_LAZY_LOADING` | `TOKEN_IQ_DISABLE_LAZY_LOADING` |
| `LITELLM_DISABLE_NO_REDIS_WARNING` | `TOKEN_IQ_DISABLE_NO_REDIS_WARNING` |
| `LITELLM_DISABLE_REDACT_SECRETS` | `TOKEN_IQ_DISABLE_REDACT_SECRETS` |
| `LITELLM_DONT_SHOW_FEEDBACK_BOX` | `TOKEN_IQ_DONT_SHOW_FEEDBACK_BOX` |
| `LITELLM_DROP_PARAMS` | `TOKEN_IQ_DROP_PARAMS` |
| `LITELLM_ENABLE_ANTHROPIC_PROMPT_CACHING` | `TOKEN_IQ_ENABLE_ANTHROPIC_PROMPT_CACHING` |
| `LITELLM_ENABLE_HSTS` | `TOKEN_IQ_ENABLE_HSTS` |
| `LITELLM_ENABLE_PTU_COST_ATTRIBUTION` | `TOKEN_IQ_ENABLE_PTU_COST_ATTRIBUTION` |
| `LITELLM_ENABLE_PYROSCOPE` | `TOKEN_IQ_ENABLE_PYROSCOPE` |
| `LITELLM_ENABLE_TEAM_STALE_ALIAS_BYPASS` | `TOKEN_IQ_ENABLE_TEAM_STALE_ALIAS_BYPASS` |
| `LITELLM_ENVIRONMENT` | `TOKEN_IQ_ENVIRONMENT` |
| `LITELLM_EXPIRED_UI_SESSION_KEY_CLEANUP_BATCH_SIZE` | `TOKEN_IQ_EXPIRED_UI_SESSION_KEY_CLEANUP_BATCH_SIZE` |
| `LITELLM_EXPIRED_UI_SESSION_KEY_CLEANUP_ENABLED` | `TOKEN_IQ_EXPIRED_UI_SESSION_KEY_CLEANUP_ENABLED` |
| `LITELLM_EXPIRED_UI_SESSION_KEY_CLEANUP_INTERVAL_SECONDS` | `TOKEN_IQ_EXPIRED_UI_SESSION_KEY_CLEANUP_INTERVAL_SECONDS` |
| `LITELLM_EXTERNAL_URL` | `TOKEN_IQ_EXTERNAL_URL` |
| `LITELLM_FAVICON_URL` | `TOKEN_IQ_FAVICON_URL` |
| `LITELLM_GEMINI_LIVE_DEFER_SETUP` | `TOKEN_IQ_GEMINI_LIVE_DEFER_SETUP` |
| `LITELLM_GLOBAL_MAX_PARALLEL_REQUEST_RETRIES` | `TOKEN_IQ_GLOBAL_MAX_PARALLEL_REQUEST_RETRIES` |
| `LITELLM_GLOBAL_MAX_PARALLEL_REQUEST_RETRY_TIMEOUT` | `TOKEN_IQ_GLOBAL_MAX_PARALLEL_REQUEST_RETRY_TIMEOUT` |
| `LITELLM_HIDE_DEFAULT_CREDENTIALS_HINT` | `TOKEN_IQ_HIDE_DEFAULT_CREDENTIALS_HINT` |
| `LITELLM_KEY_ROTATION_CHECK_INTERVAL_SECONDS` | `TOKEN_IQ_KEY_ROTATION_CHECK_INTERVAL_SECONDS` |
| `LITELLM_KEY_ROTATION_ENABLED` | `TOKEN_IQ_KEY_ROTATION_ENABLED` |
| `LITELLM_KEY_ROTATION_GRACE_PERIOD` | `TOKEN_IQ_KEY_ROTATION_GRACE_PERIOD` |
| `LITELLM_KEY_ROTATION_LOCK_TTL_SECONDS` | `TOKEN_IQ_KEY_ROTATION_LOCK_TTL_SECONDS` |
| `LITELLM_LOG` | `TOKEN_IQ_LOG` |
| `LITELLM_LOGGER_NAME` | `TOKEN_IQ_LOGGER_NAME` |
| `LITELLM_MASTER_KEY` | `TOKEN_IQ_MASTER_KEY` |
| `LITELLM_MAX_BUDGET_PER_SESSION_TTL` | `TOKEN_IQ_MAX_BUDGET_PER_SESSION_TTL` |
| `LITELLM_MAX_CALLBACKS` | `TOKEN_IQ_MAX_CALLBACKS` |
| `LITELLM_MAX_ITERATIONS_TTL` | `TOKEN_IQ_MAX_ITERATIONS_TTL` |
| `LITELLM_MAX_STREAMING_DURATION_SECONDS` | `TOKEN_IQ_MAX_STREAMING_DURATION_SECONDS` |
| `LITELLM_MCP_CLIENT_SIDE_AUTH_HEADER_NAME` | `TOKEN_IQ_MCP_CLIENT_SIDE_AUTH_HEADER_NAME` |
| `LITELLM_MCP_CLIENT_TIMEOUT` | `TOKEN_IQ_MCP_CLIENT_TIMEOUT` |
| `LITELLM_MCP_HEALTH_CHECK_TIMEOUT` | `TOKEN_IQ_MCP_HEALTH_CHECK_TIMEOUT` |
| `LITELLM_MCP_METADATA_TIMEOUT` | `TOKEN_IQ_MCP_METADATA_TIMEOUT` |
| `LITELLM_MCP_OAUTH_DISCOVERY_ON_STARTUP` | `TOKEN_IQ_MCP_OAUTH_DISCOVERY_ON_STARTUP` |
| `LITELLM_MCP_SERVER_DESCRIPTION` | `TOKEN_IQ_MCP_SERVER_DESCRIPTION` |
| `LITELLM_MCP_SERVER_NAME` | `TOKEN_IQ_MCP_SERVER_NAME` |
| `LITELLM_MCP_STDIO_EXTRA_COMMANDS` | `TOKEN_IQ_MCP_STDIO_EXTRA_COMMANDS` |
| `LITELLM_MCP_TOOL_LISTING_TIMEOUT` | `TOKEN_IQ_MCP_TOOL_LISTING_TIMEOUT` |
| `LITELLM_METER_NAME` | `TOKEN_IQ_METER_NAME` |
| `LITELLM_MIGRATION_DIR` | `TOKEN_IQ_MIGRATION_DIR` |
| `LITELLM_MODE` | `TOKEN_IQ_MODE` |
| `LITELLM_MODIFY_PARAMS` | `TOKEN_IQ_MODIFY_PARAMS` |
| `LITELLM_NON_ROOT` | `TOKEN_IQ_NON_ROOT` |
| `LITELLM_OIDC_ALLOWED_CREDENTIAL_DIRS` | `TOKEN_IQ_OIDC_ALLOWED_CREDENTIAL_DIRS` |
| `LITELLM_OTEL_BAGGAGE_METADATA_KEYS` | `TOKEN_IQ_OTEL_BAGGAGE_METADATA_KEYS` |
| `LITELLM_OTEL_BAGGAGE_PROMOTED_KEYS` | `TOKEN_IQ_OTEL_BAGGAGE_PROMOTED_KEYS` |
| `LITELLM_OTEL_BAGGAGE_TEAM_METADATA_KEYS` | `TOKEN_IQ_OTEL_BAGGAGE_TEAM_METADATA_KEYS` |
| `LITELLM_OTEL_INTEGRATION_ENABLE_EVENTS` | `TOKEN_IQ_OTEL_INTEGRATION_ENABLE_EVENTS` |
| `LITELLM_OTEL_INTEGRATION_ENABLE_METRICS` | `TOKEN_IQ_OTEL_INTEGRATION_ENABLE_METRICS` |
| `LITELLM_OTEL_LEGACY_COMPAT` | `TOKEN_IQ_OTEL_LEGACY_COMPAT` |
| `LITELLM_OTEL_V2` | `TOKEN_IQ_OTEL_V2` |
| `LITELLM_PRINT_STANDARD_LOGGING_PAYLOAD` | `TOKEN_IQ_PRINT_STANDARD_LOGGING_PAYLOAD` |
| `LITELLM_PROFILE` | `TOKEN_IQ_PROFILE` |
| `LITELLM_PROXY_API_BASE` | `TOKEN_IQ_PROXY_API_BASE` |
| `LITELLM_PROXY_API_KEY` | `TOKEN_IQ_PROXY_API_KEY` |
| `LITELLM_PROXY_URL` | `TOKEN_IQ_PROXY_URL` |
| `LITELLM_RATE_LIMIT_WINDOW_SIZE` | `TOKEN_IQ_RATE_LIMIT_WINDOW_SIZE` |
| `LITELLM_REASONING_AUTO_SUMMARY` | `TOKEN_IQ_REASONING_AUTO_SUMMARY` |
| `LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES` | `TOKEN_IQ_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES` |
| `LITELLM_RUST` | `TOKEN_IQ_RUST` |
| `LITELLM_SALT_KEY` | `TOKEN_IQ_SALT_KEY` |
| `LITELLM_SENSITIVE_ROUTING_TTL` | `TOKEN_IQ_SENSITIVE_ROUTING_TTL` |
| `LITELLM_SSL_CIPHERS` | `TOKEN_IQ_SSL_CIPHERS` |
| `LITELLM_STORE_AUDIT_LOGS` | `TOKEN_IQ_STORE_AUDIT_LOGS` |
| `LITELLM_STRICT_GUARDRAIL_MODES` | `TOKEN_IQ_STRICT_GUARDRAIL_MODES` |
| `LITELLM_SUPPRESS_SPEND_LOG_TRACEBACKS` | `TOKEN_IQ_SUPPRESS_SPEND_LOG_TRACEBACKS` |
| `LITELLM_TPM_TOKEN_RESERVATION_ENABLED` | `TOKEN_IQ_TPM_TOKEN_RESERVATION_ENABLED` |
| `LITELLM_UI_API_DOC_BASE_URL` | `TOKEN_IQ_UI_API_DOC_BASE_URL` |
| `LITELLM_UI_PATH` | `TOKEN_IQ_UI_PATH` |
| `LITELLM_UI_SESSION_DURATION` | `TOKEN_IQ_UI_SESSION_DURATION` |
| `LITELLM_USER_AGENT` | `TOKEN_IQ_USER_AGENT` |
| `LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES` | `TOKEN_IQ_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES` |
| `LITELLM_USE_LEGACY_INTERACTIONS_SCHEMA` | `TOKEN_IQ_USE_LEGACY_INTERACTIONS_SCHEMA` |
| `LITELLM_USE_SHORT_MCP_TOOL_PREFIX` | `TOKEN_IQ_USE_SHORT_MCP_TOOL_PREFIX` |
| `LITELLM_WORKER_STARTUP_HOOKS` | `TOKEN_IQ_WORKER_STARTUP_HOOKS` |

Variables nothing in this repository reads are not renamed, `LITELLM_LICENSE` among them: the enterprise
package reads that one.

#### Config keys, 2 of them

Both spellings are accepted anywhere in `config.yaml`, including inside each entry of `model_list`, and
in a config stored in the database or fetched from S3 or GCS.

| Before | Now |
| --- | --- |
| `litellm_params` | `model_params` |
| `litellm_settings` | `gateway_settings` |

#### Request and response headers, 83 of them

A request is understood under either spelling. A response carries only the new one, which is what makes
the old one droppable later, so anything reading a response header has to be updated in this window
rather than the next.

| Before | Now |
| --- | --- |
| `x-litellm-adaptive-router-model` | `x-token-iq-adaptive-router-model` |
| `x-litellm-agent-id` | `x-token-iq-agent-id` |
| `x-litellm-api-key` | `x-token-iq-api-key` |
| `x-litellm-applied-guardrails` | `x-token-iq-applied-guardrails` |
| `x-litellm-applied-policies` | `x-token-iq-applied-policies` |
| `x-litellm-attempted-fallbacks` | `x-token-iq-attempted-fallbacks` |
| `x-litellm-attempted-retries` | `x-token-iq-attempted-retries` |
| `x-litellm-cache-key` | `x-token-iq-cache-key` |
| `x-litellm-call-id` | `x-token-iq-call-id` |
| `x-litellm-callback-duration-ms` | `x-token-iq-callback-duration-ms` |
| `x-litellm-classifier-cost` | `x-token-iq-classifier-cost` |
| `x-litellm-cli-poll-secret` | `x-token-iq-cli-poll-secret` |
| `x-litellm-customer-id` | `x-token-iq-customer-id` |
| `x-litellm-disable-callbacks` | `x-token-iq-disable-callbacks` |
| `x-litellm-enable-message-redaction` | `x-token-iq-enable-message-redaction` |
| `x-litellm-end-user-id` | `x-token-iq-end-user-id` |
| `x-litellm-fallback-errors` | `x-token-iq-fallback-errors` |
| `x-litellm-guardrail-scan-id` | `x-token-iq-guardrail-scan-id` |
| `x-litellm-keepalive-seconds` | `x-token-iq-keepalive-seconds` |
| `x-litellm-key-alias` | `x-token-iq-key-alias` |
| `x-litellm-key-max-budget` | `x-token-iq-key-max-budget` |
| `x-litellm-key-name` | `x-token-iq-key-name` |
| `x-litellm-key-remaining-requests-*` | `x-token-iq-key-remaining-requests-*` |
| `x-litellm-key-remaining-tokens-*` | `x-token-iq-key-remaining-tokens-*` |
| `x-litellm-key-rpm-limit` | `x-token-iq-key-rpm-limit` |
| `x-litellm-key-spend` | `x-token-iq-key-spend` |
| `x-litellm-key-tpm-limit` | `x-token-iq-key-tpm-limit` |
| `x-litellm-max-retries` | `x-token-iq-max-retries` |
| `x-litellm-mcp-debug` | `x-token-iq-mcp-debug` |
| `x-litellm-min-quality-tier` | `x-token-iq-min-quality-tier` |
| `x-litellm-model` | `x-token-iq-model` |
| `x-litellm-model-api-base` | `x-token-iq-model-api-base` |
| `x-litellm-model-group` | `x-token-iq-model-group` |
| `x-litellm-model-id` | `x-token-iq-model-id` |
| `x-litellm-model-name` | `x-token-iq-model-name` |
| `x-litellm-model-region` | `x-token-iq-model-region` |
| `x-litellm-num-retries` | `x-token-iq-num-retries` |
| `x-litellm-org-id` | `x-token-iq-org-id` |
| `x-litellm-overhead-duration-ms` | `x-token-iq-overhead-duration-ms` |
| `x-litellm-policy-sources` | `x-token-iq-policy-sources` |
| `x-litellm-priority` | `x-token-iq-priority` |
| `x-litellm-quality-router-complexity` | `x-token-iq-quality-router-complexity` |
| `x-litellm-quality-router-keyword` | `x-token-iq-quality-router-keyword` |
| `x-litellm-quality-router-model` | `x-token-iq-quality-router-model` |
| `x-litellm-quality-router-tier` | `x-token-iq-quality-router-tier` |
| `x-litellm-quality-router-via` | `x-token-iq-quality-router-via` |
| `x-litellm-rate-limiter-version` | `x-token-iq-rate-limiter-version` |
| `x-litellm-request-prioritization-used` | `x-token-iq-request-prioritization-used` |
| `x-litellm-response-cost` | `x-token-iq-response-cost` |
| `x-litellm-response-cost-cache-creation` | `x-token-iq-response-cost-cache-creation` |
| `x-litellm-response-cost-cache-read` | `x-token-iq-response-cost-cache-read` |
| `x-litellm-response-cost-discount-amount` | `x-token-iq-response-cost-discount-amount` |
| `x-litellm-response-cost-input` | `x-token-iq-response-cost-input` |
| `x-litellm-response-cost-margin-amount` | `x-token-iq-response-cost-margin-amount` |
| `x-litellm-response-cost-margin-percent` | `x-token-iq-response-cost-margin-percent` |
| `x-litellm-response-cost-original` | `x-token-iq-response-cost-original` |
| `x-litellm-response-cost-output` | `x-token-iq-response-cost-output` |
| `x-litellm-response-cost-reasoning` | `x-token-iq-response-cost-reasoning` |
| `x-litellm-response-cost-tool-usage` | `x-token-iq-response-cost-tool-usage` |
| `x-litellm-response-duration-ms` | `x-token-iq-response-duration-ms` |
| `x-litellm-rust` | `x-token-iq-rust` |
| `x-litellm-saturation` | `x-token-iq-saturation` |
| `x-litellm-semantic-filter` | `x-token-iq-semantic-filter` |
| `x-litellm-semantic-filter-tools` | `x-token-iq-semantic-filter-tools` |
| `x-litellm-semantic-similarity` | `x-token-iq-semantic-similarity` |
| `x-litellm-session-id` | `x-token-iq-session-id` |
| `x-litellm-spend-logs-metadata` | `x-token-iq-spend-logs-metadata` |
| `x-litellm-spend-logs-truncated` | `x-token-iq-spend-logs-truncated` |
| `x-litellm-stream-timeout` | `x-token-iq-stream-timeout` |
| `x-litellm-tags` | `x-token-iq-tags` |
| `x-litellm-team-id` | `x-token-iq-team-id` |
| `x-litellm-team-name` | `x-token-iq-team-name` |
| `x-litellm-timeout` | `x-token-iq-timeout` |
| `x-litellm-timing-llm-api-ms` | `x-token-iq-timing-llm-api-ms` |
| `x-litellm-timing-message-copy-ms` | `x-token-iq-timing-message-copy-ms` |
| `x-litellm-timing-post-processing-ms` | `x-token-iq-timing-post-processing-ms` |
| `x-litellm-timing-pre-processing-ms` | `x-token-iq-timing-pre-processing-ms` |
| `x-litellm-total-tokens` | `x-token-iq-total-tokens` |
| `x-litellm-trace-id` | `x-token-iq-trace-id` |
| `x-litellm-user-email` | `x-token-iq-user-email` |
| `x-litellm-user-id` | `x-token-iq-user-id` |
| `x-litellm-user-role` | `x-token-iq-user-role` |
| `x-litellm-version` | `x-token-iq-version` |

#### Prometheus metrics, 82 of them

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

| Before | Now |
| --- | --- |
| `litellm_active_users` | `token_iq_active_users` |
| `litellm_api_key_budget_remaining_hours_metric` | `token_iq_api_key_budget_remaining_hours_metric` |
| `litellm_api_key_max_budget_metric` | `token_iq_api_key_max_budget_metric` |
| `litellm_api_key_rate_limit_allowed_metric` | `token_iq_api_key_rate_limit_allowed_metric` |
| `litellm_api_key_rate_limit_used_metric` | `token_iq_api_key_rate_limit_used_metric` |
| `litellm_cache_hits_metric` | `token_iq_cache_hits_metric` |
| `litellm_cache_misses_metric` | `token_iq_cache_misses_metric` |
| `litellm_cached_tokens_metric` | `token_iq_cached_tokens_metric` |
| `litellm_callback_logging_failures_metric` | `token_iq_callback_logging_failures_metric` |
| `litellm_check_batch_cost_errors_total` | `token_iq_check_batch_cost_errors_total` |
| `litellm_check_batch_cost_jobs_polled` | `token_iq_check_batch_cost_jobs_polled` |
| `litellm_check_batch_cost_jobs_processed_total` | `token_iq_check_batch_cost_jobs_processed_total` |
| `litellm_check_batch_cost_last_run_timestamp` | `token_iq_check_batch_cost_last_run_timestamp` |
| `litellm_deployment_cooled_down` | `token_iq_deployment_cooled_down` |
| `litellm_deployment_failed_fallbacks` | `token_iq_deployment_failed_fallbacks` |
| `litellm_deployment_failure_responses` | `token_iq_deployment_failure_responses` |
| `litellm_deployment_latency_per_output_token` | `token_iq_deployment_latency_per_output_token` |
| `litellm_deployment_rpm_limit` | `token_iq_deployment_rpm_limit` |
| `litellm_deployment_state` | `token_iq_deployment_state` |
| `litellm_deployment_success_responses` | `token_iq_deployment_success_responses` |
| `litellm_deployment_successful_fallbacks` | `token_iq_deployment_successful_fallbacks` |
| `litellm_deployment_total_requests` | `token_iq_deployment_total_requests` |
| `litellm_deployment_tpm_limit` | `token_iq_deployment_tpm_limit` |
| `litellm_guardrail_errors_total` | `token_iq_guardrail_errors_total` |
| `litellm_guardrail_latency_seconds` | `token_iq_guardrail_latency_seconds` |
| `litellm_guardrail_requests_total` | `token_iq_guardrail_requests_total` |
| `litellm_images_generated_metric` | `token_iq_images_generated_metric` |
| `litellm_in_flight_requests` | `token_iq_in_flight_requests` |
| `litellm_input_audio_tokens_metric` | `token_iq_input_audio_tokens_metric` |
| `litellm_input_cache_creation_tokens_metric` | `token_iq_input_cache_creation_tokens_metric` |
| `litellm_input_cached_tokens_metric` | `token_iq_input_cached_tokens_metric` |
| `litellm_input_tokens_metric` | `token_iq_input_tokens_metric` |
| `litellm_llm_api_failed_requests_metric` | `token_iq_llm_api_failed_requests_metric` |
| `litellm_llm_api_latency_metric` | `token_iq_llm_api_latency_metric` |
| `litellm_llm_api_time_to_first_token_metric` | `token_iq_llm_api_time_to_first_token_metric` |
| `litellm_managed_batch_created_total` | `token_iq_managed_batch_created_total` |
| `litellm_managed_batch_duration_seconds` | `token_iq_managed_batch_duration_seconds` |
| `litellm_managed_file_created_total` | `token_iq_managed_file_created_total` |
| `litellm_managed_file_deleted_total` | `token_iq_managed_file_deleted_total` |
| `litellm_managed_file_size_bytes` | `token_iq_managed_file_size_bytes` |
| `litellm_mcp_tool_call_spend_metric` | `token_iq_mcp_tool_call_spend_metric` |
| `litellm_mcp_tool_calls_total` | `token_iq_mcp_tool_calls_total` |
| `litellm_org_budget_remaining_hours_metric` | `token_iq_org_budget_remaining_hours_metric` |
| `litellm_org_max_budget_metric` | `token_iq_org_max_budget_metric` |
| `litellm_output_audio_tokens_metric` | `token_iq_output_audio_tokens_metric` |
| `litellm_output_reasoning_tokens_metric` | `token_iq_output_reasoning_tokens_metric` |
| `litellm_output_tokens_metric` | `token_iq_output_tokens_metric` |
| `litellm_overhead_latency_metric` | `token_iq_overhead_latency_metric` |
| `litellm_overhead_with_guardrails_latency_metric` | `token_iq_overhead_with_guardrails_latency_metric` |
| `litellm_provider_cache_creation_input_tokens_metric` | `token_iq_provider_cache_creation_input_tokens_metric` |
| `litellm_provider_cache_read_input_tokens_metric` | `token_iq_provider_cache_read_input_tokens_metric` |
| `litellm_provider_remaining_budget_metric` | `token_iq_provider_remaining_budget_metric` |
| `litellm_proxy_failed_requests_metric` | `token_iq_proxy_failed_requests_metric` |
| `litellm_proxy_total_requests_metric` | `token_iq_proxy_total_requests_metric` |
| `litellm_remaining_api_key_budget_metric` | `token_iq_remaining_api_key_budget_metric` |
| `litellm_remaining_api_key_requests_for_model` | `token_iq_remaining_api_key_requests_for_model` |
| `litellm_remaining_api_key_tokens_for_model` | `token_iq_remaining_api_key_tokens_for_model` |
| `litellm_remaining_org_budget_metric` | `token_iq_remaining_org_budget_metric` |
| `litellm_remaining_requests_metric` | `token_iq_remaining_requests_metric` |
| `litellm_remaining_team_budget_metric` | `token_iq_remaining_team_budget_metric` |
| `litellm_remaining_tokens_metric` | `token_iq_remaining_tokens_metric` |
| `litellm_remaining_user_budget_metric` | `token_iq_remaining_user_budget_metric` |
| `litellm_request_queue_time_seconds` | `token_iq_request_queue_time_seconds` |
| `litellm_request_total_latency_metric` | `token_iq_request_total_latency_metric` |
| `litellm_requests_metric` | `token_iq_requests_metric` |
| `litellm_spend_log_cleanup_batch_duration_seconds` | `token_iq_spend_log_cleanup_batch_duration_seconds` |
| `litellm_spend_log_cleanup_batch_failures_total` | `token_iq_spend_log_cleanup_batch_failures_total` |
| `litellm_spend_log_cleanup_rows_deleted_total` | `token_iq_spend_log_cleanup_rows_deleted_total` |
| `litellm_spend_log_cleanup_rows_remaining` | `token_iq_spend_log_cleanup_rows_remaining` |
| `litellm_spend_log_cleanup_runs_total` | `token_iq_spend_log_cleanup_runs_total` |
| `litellm_spend_metric` | `token_iq_spend_metric` |
| `litellm_team_budget_remaining_hours_metric` | `token_iq_team_budget_remaining_hours_metric` |
| `litellm_team_max_budget_metric` | `token_iq_team_max_budget_metric` |
| `litellm_team_members_metric` | `token_iq_team_members_metric` |
| `litellm_team_rate_limit_allowed_metric` | `token_iq_team_rate_limit_allowed_metric` |
| `litellm_team_rate_limit_used_metric` | `token_iq_team_rate_limit_used_metric` |
| `litellm_teams_count` | `token_iq_teams_count` |
| `litellm_total_tokens_metric` | `token_iq_total_tokens_metric` |
| `litellm_total_users` | `token_iq_total_users` |
| `litellm_user_budget_remaining_hours_metric` | `token_iq_user_budget_remaining_hours_metric` |
| `litellm_user_max_budget_metric` | `token_iq_user_max_budget_metric` |
| `litellm_video_duration_seconds_metric` | `token_iq_video_duration_seconds_metric` |

#### What is not renamed

The Prometheus label `litellm_model_name` keeps its name. It is also a key in the engine's hidden
parameters, read in ten places, so moving it would be a change to something other than metrics. A query
grouping by that label keeps working.

<!-- end generated -->
