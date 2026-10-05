"""The isolation the Token IQ tests had before they moved here.

pytest finds fixtures and hook implementations by name in the conftest files along a test's own
directory path. Moving a test out from under a conftest removes every autouse fixture and every
hook in it, with no error and nothing missing from the run: the moved test still passes. What
breaks is the next test in the same xdist worker, which is why these are re-exported rather than
left to be inherited, and why removing one of them has to make a sibling fail.

Re-exported, never copied. One definition means one place to fix, and a copy that drifts gives
two tests different isolation while looking like it gives them the same.

Hook functions are looked up by name in this module's namespace exactly as fixtures are, so
importing one is enough to register it here. All three session hooks below are idempotent, which
matters because a run covering both this tree and `tests/test_litellm` loads both conftests and
calls each hook twice.
"""

from tests.test_litellm.conftest import (  # noqa: F401  # re-exported for pytest to find by name
    isolate_host_aws_config,
    isolate_host_os_keychain,
    isolate_host_proxy_base_url,
    isolate_litellm_state,
    isolated_aws_credentials_dir,
    local_model_cost_map,
    pytest_collection_modifyitems,
    pytest_configure,
    pytest_sessionfinish,
    secret_vault_factory,
    setup_and_teardown,
    strict_isolation,
)
