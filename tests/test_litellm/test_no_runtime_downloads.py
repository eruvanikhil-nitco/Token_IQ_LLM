"""Nothing is fetched from upstream while a proxy is running.

Phase 2's whole point. An installation behind a firewall must price, route headers and serve
its pages exactly as one with open egress does, and the only way to be sure is to check that
no code path can reach out, rather than that no code path currently does.
"""

from __future__ import annotations

import pathlib
import socket
from typing import Final

import pytest

REPO: Final = pathlib.Path(__file__).resolve().parents[2]

# The one file allowed to name an upstream host: it runs in CI and opens a pull request, and
# never executes inside an installation.
ALLOWED: Final[frozenset[str]] = frozenset(
    {"scripts/update_model_prices.py", ".github/workflows/update-model-prices.yml"}
)


@pytest.fixture
def no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a socket was opened; nothing may be fetched at runtime")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class TestNothingFetchesAtRuntime:
    def test_importing_litellm_opens_no_socket(self, no_sockets: None) -> None:
        import importlib

        import litellm

        importlib.reload(litellm)

    def test_the_anthropic_beta_headers_load_without_a_network(self, no_sockets: None) -> None:
        from litellm.anthropic_beta_headers_manager import get_beta_headers_config

        assert get_beta_headers_config()

    def test_no_upstream_url_is_configured_in_the_package_root(self) -> None:
        source: Final = (REPO / "litellm" / "__init__.py").read_text(encoding="utf-8")
        for forbidden in ("raw.githubusercontent.com", "docs.litellm.ai", "BerriAI"):
            assert forbidden not in source, f"{forbidden} is still reachable from litellm/__init__.py"


class TestOnlyTheUpdateJobNamesUpstream:
    def test_no_module_under_litellm_fetches_from_upstream(self) -> None:
        """A grep is the right test here: the failure is a URL existing at all, and a
        behavioural test can only prove the paths it happens to walk."""
        offenders: Final = [
            path.relative_to(REPO).as_posix()
            for path in (REPO / "litellm").rglob("*.py")
            if "_experimental" not in path.parts
            and any(
                host in path.read_text(encoding="utf-8", errors="ignore")
                for host in ("raw.githubusercontent.com/BerriAI", "docs.litellm.ai/blog")
            )
        ]
        assert not offenders, f"these still fetch from upstream: {offenders}"
