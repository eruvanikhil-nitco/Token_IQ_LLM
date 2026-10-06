"""The deployment image check must catch what it claims and exclude only what it names.

Its exclusions decide whether it polices anything at all, so they get tests of their own.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO / "tests" / "code_coverage_tests") not in sys.path:
    sys.path.insert(0, str(REPO / "tests" / "code_coverage_tests"))

from check_deployment_images_are_ours import offenders  # noqa: E402  # path set above


def _file(tmp_path: Path, name: str, body: str) -> Path:
    path: Final = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_a_terraform_default_pointing_at_another_registry_is_caught(tmp_path: Path, monkeypatch) -> None:
    import check_deployment_images_are_ours as gate

    monkeypatch.setattr(gate, "REPO", tmp_path)
    path: Final = _file(tmp_path, "main.tf", 'default = "ghcr.io/berriai/litellm-gateway:v1"\n')

    assert len(offenders((path,))) == 1


def test_our_own_image_is_allowed_wherever_it_is_published(tmp_path: Path, monkeypatch) -> None:
    import check_deployment_images_are_ours as gate

    monkeypatch.setattr(gate, "REPO", tmp_path)
    path: Final = _file(tmp_path, "main.tf", 'default = "ghcr.io/tokeniq/gateway:v1"\n')

    assert offenders((path,)) == ()


def test_a_base_image_we_build_on_is_not_an_image_we_ship(tmp_path: Path, monkeypatch) -> None:
    """Every image is built on someone else's base. Naming one in a FROM line is not shipping
    their product, and a check that conflated the two would be unusable."""
    import check_deployment_images_are_ours as gate

    monkeypatch.setattr(gate, "REPO", tmp_path)
    path: Final = _file(tmp_path, "Dockerfile.x", "FROM docker.io/library/python:3.12-slim\n")

    assert offenders((path,)) == ()


def test_a_foreign_image_below_a_from_line_is_still_caught(tmp_path: Path, monkeypatch) -> None:
    """The exclusion is for the FROM line itself, not for the rest of the file."""
    import check_deployment_images_are_ours as gate

    monkeypatch.setattr(gate, "REPO", tmp_path)
    body: Final = "FROM docker.io/library/python:3.12-slim\nRUN echo ghcr.io/berriai/litellm:v1\n"
    path: Final = _file(tmp_path, "Dockerfile.y", body)

    assert len(offenders((path,))) == 1


def test_a_compose_file_shipping_another_companys_image_is_caught(tmp_path: Path, monkeypatch) -> None:
    import check_deployment_images_are_ours as gate

    monkeypatch.setattr(gate, "REPO", tmp_path)
    path: Final = _file(tmp_path, "docker-compose.yml", "services:\n  app:\n    image: ghcr.io/berriai/litellm:v1\n")

    assert len(offenders((path,))) == 1


def test_the_real_tree_is_clean() -> None:
    """The check is only worth having if it currently passes on the repository it polices."""
    import check_deployment_images_are_ours as gate

    assert gate.offenders(tuple(gate._candidates())) == ()
