from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import pytest

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from deploy.installations.manifest import Installation, ManifestError, read_manifest  # noqa: E402


def _write(tmp_path: Path, body: str) -> Path:
    path: Final = tmp_path / "manifest.yaml"
    path.write_text(body, encoding="utf-8")
    return path


ONE: Final = """
installations:
  acme:
    hostname: acme.tokeniq.example
    version: v1.2.3
"""


def test_a_customer_becomes_its_own_database_and_role(tmp_path: Path) -> None:
    """Sharing one Postgres server is what makes a small customer profitable, and it only
    works because each one owns a database and a role of its own."""
    entry: Final = read_manifest(_write(tmp_path, ONE))[0]

    assert entry.database == "tokeniq_acme"
    assert entry.role == "tokeniq_acme"
    assert entry.database != entry.hostname


def test_a_size_becomes_a_cpu_and_memory_pair_fargate_accepts(tmp_path: Path) -> None:
    """Fargate refuses arbitrary combinations, so a size is a name rather than two numbers a
    manifest could get wrong in a way only an apply would reveal."""
    entry: Final = read_manifest(_write(tmp_path, ONE))[0]

    assert (entry.cpu, entry.memory) == (512, 1024)


def test_a_customer_key_that_is_not_a_safe_identifier_is_refused(tmp_path: Path) -> None:
    """The key becomes a database and role name. A bad one fails halfway through creating an
    installation, which is a far worse place to find out than reading the file."""
    for bad in ("Acme", "1acme", "acme-corp", "ac", "a" * 32, "acme;drop"):
        body = f"installations:\n  {bad}:\n    hostname: x.tokeniq.example\n    version: v1.0.0\n"
        with pytest.raises(ManifestError, match="customer key"):
            read_manifest(_write(tmp_path, body))


def test_a_moving_tag_is_refused_as_a_version(tmp_path: Path) -> None:
    """An installation whose version cannot be named cannot be rolled back to a known build."""
    for bad in ("latest", "main", "stable", "v1.2", ""):
        body = f"installations:\n  acme:\n    hostname: a.tokeniq.example\n    version: {bad!r}\n"
        with pytest.raises(ManifestError, match="version"):
            read_manifest(_write(tmp_path, body))


def test_a_commit_hash_is_accepted_as_a_version(tmp_path: Path) -> None:
    body: Final = "installations:\n  acme:\n    hostname: a.tokeniq.example\n    version: 5fbe0136d4a\n"

    assert read_manifest(_write(tmp_path, body))[0].version == "5fbe0136d4a"


def test_two_customers_cannot_share_a_hostname(tmp_path: Path) -> None:
    """The shared load balancer routes by hostname, so a duplicate would send one customer's
    traffic to another customer's installation."""
    body: Final = (
        "installations:\n"
        "  acme:\n    hostname: same.tokeniq.example\n    version: v1.0.0\n"
        "  other:\n    hostname: same.tokeniq.example\n    version: v1.0.0\n"
    )
    with pytest.raises(ManifestError, match="hostname"):
        read_manifest(_write(tmp_path, body))


def test_an_unknown_size_is_refused(tmp_path: Path) -> None:
    body: Final = "installations:\n  acme:\n    hostname: a.tokeniq.example\n    version: v1.0.0\n    size: huge\n"

    with pytest.raises(ManifestError, match="size"):
        read_manifest(_write(tmp_path, body))


def test_an_empty_manifest_is_refused_rather_than_read_as_no_customers(tmp_path: Path) -> None:
    """Reading an empty file as a fleet of zero would make an upgrade report success while
    touching nobody."""
    with pytest.raises(ManifestError, match="lists no installations"):
        read_manifest(_write(tmp_path, "installations: {}\n"))


def test_a_file_that_is_not_yaml_is_refused_with_its_path(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not valid YAML"):
        read_manifest(_write(tmp_path, "installations:\n  acme:\n   - broken: ["))


def test_every_installation_in_the_file_is_returned(tmp_path: Path) -> None:
    body: Final = (
        "installations:\n"
        "  acme:\n    hostname: acme.tokeniq.example\n    version: v1.0.0\n    size: large\n"
        "  globex:\n    hostname: globex.tokeniq.example\n    version: v1.0.0\n"
    )
    entries: Final = read_manifest(_write(tmp_path, body))

    assert tuple(entry.key for entry in entries) == ("acme", "globex")
    assert entries[0].cpu == 2048


def test_an_installation_is_frozen_so_a_caller_cannot_retarget_it() -> None:
    """Provisioning and upgrading share these objects. One mutating another's copy is the kind
    of bug that points an upgrade at the wrong customer's database."""
    entry: Final = Installation(key="acme", hostname="a.tokeniq.example", version="v1.0.0")

    with pytest.raises((AttributeError, TypeError)):
        entry.key = "other"  # pyright: ignore[reportAttributeAccessIssue]  # frozen by design
