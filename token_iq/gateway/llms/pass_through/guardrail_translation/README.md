# Pass-Through Endpoint Guardrail Translation

## Why This Exists Here

This module is located under `token_iq/gateway/llms/` (instead of with the main passthrough code) because:

1. **Auto-discovery**: The `load_guardrail_translation_mappings()` function in `token_iq/gateway/llms/__init__.py` scans for `guardrail_translation/` directories under `token_iq/gateway/llms/`
2. **Consistency**: All other guardrail translation handlers follow this pattern (e.g., `openai/chat/guardrail_translation/`, `anthropic/chat/guardrail_translation/`)

## Main Passthrough Implementation

The main passthrough endpoint implementation is in:

```
token_iq/gateway/proxy/pass_through_endpoints/
├── pass_through_endpoints.py      # Core passthrough routing logic
├── passthrough_guardrails.py      # Guardrail collection and field targeting
├── jsonpath_extractor.py          # JSONPath field extraction utility
└── ...
```

## What This Handler Does

The `PassThroughEndpointHandler` enables guardrails to run on passthrough endpoint requests by:

1. **Field Targeting**: Extracts specific fields from the request/response using JSONPath expressions configured in `request_fields` / `response_fields`
2. **Full Payload Fallback**: If no field targeting is configured, processes the entire payload
3. **Config Access**: Uses `get_passthrough_guardrails_config()` / `set_passthrough_guardrails_config()` helpers to access the passthrough guardrails configuration stored in request metadata

## Example Config

```yaml
passthrough_endpoints:
  - path: "/v1/rerank"
    target: "https://api.cohere.com/v1/rerank"
    guardrails:
      bedrock-pre-guard:
        request_fields: ["query", "documents[*].text"]
        response_fields: ["results[*].text"]
```

