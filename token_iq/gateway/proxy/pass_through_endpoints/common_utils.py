from __future__ import annotations

from typing import TYPE_CHECKING, Final

from fastapi import Request
from token_iq.gateway import compat

if TYPE_CHECKING:
    from token_iq.gateway.integrations.custom_logger import CustomLogger


def get_gateway_virtual_key(request: Request) -> str:
    """
    Extract and format API key from request headers.
    Prioritizes x-litellm-api-key over Authorization header.


    Vertex JS SDK uses `Authorization` header, we use `x-litellm-api-key` to pass litellm virtual key

    """
    litellm_api_key: Final = compat.header(request.headers, "x-token-iq-api-key")
    if litellm_api_key:
        return f"Bearer {litellm_api_key}"
    return request.headers.get("Authorization", "")


def assert_passthrough_body_fidelity(managed_files_hook: CustomLogger | None) -> None:
    """
    Fail startup when the managed-files hook is registered.

    Both managed-id rewrite sites in `pass_through_endpoints.py` are gated on
    this hook being present. When it is, the gateway swaps provider IDs for its
    own in the response body before the client sees it, and rejects inbound IDs
    it did not mint with a 404 or 403. That breaks byte-for-byte forwarding in
    both directions, so this build refuses to run with it registered rather than
    relying on the hook happening to be unavailable.

    See docs/decisions/0009-passthrough-body-fidelity.md
    """
    if managed_files_hook is None:
        return
    raise ValueError(
        "The 'managed_files' proxy hook is registered, but this gateway forwards "
        "request and response bodies unchanged. That hook enables the managed-id "
        "rewriter, which swaps provider IDs out of response bodies on files, batches "
        "and responses routes, and rejects inbound IDs it did not mint. "
        "Remove the hook. See docs/decisions/0009-passthrough-body-fidelity.md"
    )
