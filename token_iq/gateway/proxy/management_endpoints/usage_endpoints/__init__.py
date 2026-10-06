"""
Usage endpoints package.

Re-exports the router from endpoints module.
"""

from token_iq.gateway.proxy.management_endpoints.usage_endpoints.endpoints import (  # noqa: F401
    router,
)
