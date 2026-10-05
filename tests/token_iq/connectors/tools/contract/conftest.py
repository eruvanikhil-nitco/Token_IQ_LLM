"""The tool contract tests use the same stand-in server as the provider contract tests.

Re-exported rather than copied: one harness means one place to fix when a connector needs to
assert something new about the request it sent.
"""

from tests.token_iq.connectors.billing.contract.conftest import (  # noqa: F401  # re-exported fixture and helpers
    Recorded,
    Reply,
    Vendor,
    vendor,
)
