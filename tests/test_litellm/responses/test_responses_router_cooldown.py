"""
Regression: Responses API router must register cooldowns on deployment
failures. Previously the Responses API path built ``litellm_params`` without
``model_info``, so ``Router.deployment_callback_on_failure`` exited early via
the "No model_info found" branch and the failing deployment was never added
to the cooldown set.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest


from token_iq import gateway as litellm
from token_iq.gateway.router_utils.cooldown_handlers import _async_get_cooldown_deployments


