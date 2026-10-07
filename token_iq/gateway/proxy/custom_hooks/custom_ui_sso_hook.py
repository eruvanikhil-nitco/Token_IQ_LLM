from typing import Final

from fastapi import Request
from fastapi_sso.sso.base import OpenID

from token_iq.gateway._logging import verbose_logger
from token_iq.gateway.integrations.custom_logger import CustomLogger
from token_iq.gateway.proxy.common_utils.http_parsing_utils import _safe_get_request_headers
from token_iq.gateway import compat


class CustomSSOLoginHandler(CustomLogger):
    """
    Custom logger for the UI SSO sign in

    Use this to parse the request headers and return a OpenID object

    Useful when you have an OAuth proxy in front of LiteLLM
    and you want to use the headers from the proxy to sign in the user
    """

    async def handle_custom_ui_sso_sign_in(
        self,
        request: Request,
    ) -> OpenID:
        request_headers_dict: Final = _safe_get_request_headers(request)
        verbose_logger.debug("inside custom ui sso sign in hook...")
        return OpenID(
            id=compat.header(request_headers_dict, "x-token-iq-user-id") or "123",
            email=compat.header(request_headers_dict, "x-token-iq-user-email") or "test@test.com",
            first_name="Test",
            last_name="Test",
            display_name="Test",
            picture="https://test.com/test.png",
            provider="test",
        )


custom_ui_sso_sign_in_handler: Final = CustomSSOLoginHandler()
