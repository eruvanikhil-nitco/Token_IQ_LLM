"""The `proxy_server` module-global isolation these tests had under `tests/gateway/proxy/`.

The hook pair is the load-bearing part. It snapshots `litellm.proxy.proxy_server`'s module
globals before any fixture runs and restores them after every finalizer has run. Without it a
leaked `master_key` flips the auth short-circuit in `user_api_key_auth` and unrelated tests in
the same worker return 401 instead of 200, and a leaked `llm_router` makes the PTU rollup count
another test's deployments as the proxy's own.

It must stay a hook pair. Its docstring in the original conftest explains why an autouse fixture
cannot do this job: such a fixture requests `monkeypatch`, so `monkeypatch`'s undo stack unwinds
after every other finalizer, and a test that patches a global while a fixture holds it patched
records the fixture's mock as the original.
"""

from tests.gateway.proxy.conftest import (  # noqa: F401  # re-exported for pytest to find by name
    _reset_graceful_shutdown_state,
    disconnected_prisma,
    pytest_runtest_setup,
    pytest_runtest_teardown,
)
