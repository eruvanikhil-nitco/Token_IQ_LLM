"""Where each Token IQ test file goes, and what has to change when it gets there.

The map is the record of the move, the same as `move_token_iq_modules.py` holds for the modules.
It is kept because phase 4 compares against a baseline keyed on the old paths: without a map from
old nodeid to new, every moved case reads as `disappeared` and every arrival as `appeared`, which
is also what a deleted test file looks like.

Two things this deliberately does not decide.

A test's subject is not its filename. `test_daily_reconciliation.py` exercises
`token_iq.api.provider_reconciliation` but is named after the endpoint, so a rule built on
filenames leaves it behind. It is listed explicitly below. Eight other files that import
`token_iq` stay where they are, because they exercise engine endpoints under plan gating and only
use Token IQ policy as a collaborator.

Nothing here moves a conftest's contents. Fixtures and hooks reach the new tree by being
re-exported from `tests/token_iq/conftest.py` and the two beside it, which is checked by
`tests/code_coverage_tests/test_token_iq_test_isolation.py`.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

REPO: Final = pathlib.Path(__file__).resolve().parents[1]

OLD: Final = "tests/test_litellm"
NEW: Final = "tests/token_iq"

# Whole directories, mirroring where phase 3 put the modules they test.
DIRECTORIES: Final[Mapping[str, str]] = MappingProxyType(
    {
        f"{OLD}/provider_billing/contract": f"{NEW}/connectors/billing/contract",
        f"{OLD}/provider_billing": f"{NEW}/connectors/billing",
        f"{OLD}/tool_usage/contract": f"{NEW}/connectors/tools/contract",
        f"{OLD}/tool_usage": f"{NEW}/connectors/tools",
        f"{OLD}/ledger": f"{NEW}/ledger",
        f"{OLD}/attribution": f"{NEW}/attribution",
        f"{OLD}/overview": f"{NEW}/overview",
        f"{OLD}/seats": f"{NEW}/seats",
        f"{OLD}/recommendations": f"{NEW}/recommendations",
        f"{OLD}/pricing": f"{NEW}/pricing",
    }
)

# The router tests, out of a directory that keeps 42 engine tests. Four are renamed to follow the
# modules phase 3 renamed, so the test file and its subject still share a name.
ROUTERS: Final[Mapping[str, str]] = MappingProxyType(
    {
        f"{OLD}/proxy/management_endpoints/{old}": f"{NEW}/api/{new}"
        for old, new in (
            ("test_audit_log_endpoints.py", "test_audit_logs.py"),
            ("test_project_endpoints.py", "test_projects.py"),
            *(
                (f"test_{name}.py", f"test_{name}.py")
                for name in (
                    "attribution",
                    "audit_log_diff",
                    "combined_usage",
                    "courier_coverage",
                    "daily_reconciliation",
                    "ledger",
                    "model_discovery",
                    "overview",
                    "project_org_authz",
                    "provider_connections",
                    "provider_overview",
                    "provider_reconciliation",
                    "provider_usage",
                    "recommendations",
                    "seats",
                    "tool_connections",
                )
            ),
        )
    }
)

# The policy tests, from four separate proxy subdirectories. Two are renamed with their modules.
POLICY: Final[Mapping[str, str]] = MappingProxyType(
    {
        f"{OLD}/proxy/auth/test_team_api_access.py": f"{NEW}/policy/test_team_api_access.py",
        f"{OLD}/proxy/auth/test_token_iq_plan.py": f"{NEW}/policy/test_plan.py",
        f"{OLD}/proxy/spend_tracking/test_capture_policy.py": f"{NEW}/policy/test_capture.py",
        f"{OLD}/proxy/db/test_spend_log_retention.py": f"{NEW}/policy/test_spend_log_retention.py",
        f"{OLD}/proxy/credential_endpoints/test_credential_access.py": (
            f"{NEW}/policy/test_credential_access.py"
        ),
        f"{OLD}/proxy/pass_through_endpoints/test_same_target_retry.py": (
            f"{NEW}/policy/test_same_target_retry.py"
        ),
    }
)

# Ten of the eleven Token IQ repositories have a test file, out of a directory that keeps the
# engine's sixteen.
#
# `overview_repository` has none, which this found by looking for one. Nothing exercises it
# directly: `tests/test_litellm/proxy/management_endpoints/test_overview.py` injects a fake and
# tests the router's composition instead. Its methods are `provider_billed`, `tool_new_money`,
# `seats` and `gateway_recorded`, which are the four figures the counting rule governs, so a
# wrong one there is the silent failure the rule exists to prevent. Recorded here rather than
# listed as a move, because writing that test is work in its own right and not this phase's.
REPOSITORIES: Final[Mapping[str, str]] = MappingProxyType(
    {
        f"{OLD}/repositories/test_{name}_repository.py": f"{NEW}/repositories/test_{name}_repository.py"
        for name in (
            "attribution_rule",
            "gap",
            "gateway_spend",
            "invoice",
            "ledger",
            "provider_sync_run",
            "provider_usage_fact",
            "recommendation_state",
            "seat",
            "tool_usage_fact",
        )
    }
)

FILES: Final[Mapping[str, str]] = MappingProxyType(
    {
        **ROUTERS,
        **POLICY,
        **REPOSITORIES,
        f"{OLD}/types/proxy/test_provider_billing.py": f"{NEW}/types/test_provider_billing.py",
    }
)


def planned() -> Mapping[str, str]:
    """Every file that moves, old path to new, directories expanded.

    Expanded from the tree rather than listed, so a file added to one of those directories
    between writing this and running it is not silently left behind.
    """
    from_directories: Final = {
        f"{old}/{path.name}": f"{new}/{path.name}"
        for old, new in DIRECTORIES.items()
        for path in sorted((REPO / old).glob("*.py"))
        # A nested directory is handled by its own entry above, which is listed first.
        if path.is_file()
    }
    return MappingProxyType({**from_directories, **FILES})


def remap(nodeid: str) -> str:
    """An old nodeid at its new path, for comparing against a baseline captured before the move.

    Longest prefix first: `provider_billing/contract` has to win over `provider_billing`.
    """
    path, _, rest = nodeid.partition("::")
    moves: Final = planned()
    if path in moves:
        return f"{moves[path]}::{rest}" if rest else moves[path]
    for old, new in sorted(DIRECTORIES.items(), key=lambda pair: -len(pair[0])):
        if path.startswith(f"{old}/"):
            return f"{new}{path[len(old):]}" + (f"::{rest}" if rest else "")
    return nodeid


def main() -> int:
    moves: Final = planned()
    missing: Final = tuple(old for old in moves if not (REPO / old).is_file())
    if missing:
        sys.stderr.write(f"{len(missing)} file(s) in the map do not exist:\n")
        for old in missing:
            sys.stderr.write(f"  {old}\n")
        return 1

    for old, new in sorted(moves.items()):
        destination: Final = REPO / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        moved = subprocess.run(
            ("git", "mv", old, new), capture_output=True, text=True, cwd=REPO, check=False
        )
        if moved.returncode != 0:
            sys.stderr.write(f"could not move {old}:\n{moved.stderr}")
            return 1
        sys.stdout.write(f"{old} -> {new}\n")

    sys.stdout.write(f"{len(moves)} files moved\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
