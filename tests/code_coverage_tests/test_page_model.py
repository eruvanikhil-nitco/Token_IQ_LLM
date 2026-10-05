"""The committed page model still matches the blueprint it was extracted from.

`docs/product/page-model.json` is generated from the `<script>` in
`docs/product/token-iq-product-blueprint.html`. Phase 5A's acceptance comes from that model rather
than from taste, so a model that has drifted from the blueprint is worse than no model: every screen
would be checked against a specification nobody edited.

The blueprint is the source. If this fails, re-run the extractor and commit the result, or the
blueprint changed in a way the extractor cannot read and that is the thing to fix.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from typing import Final

import pytest

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
MODEL: Final = REPO / "docs" / "product" / "page-model.json"
EXTRACTOR: Final = REPO / "scripts" / "product" / "extract_page_model.mjs"


@pytest.fixture(scope="module")
def committed() -> dict[str, object]:
    return json.loads(MODEL.read_text(encoding="utf-8"))


class TestTheModelIsPresentAndWhole:
    def test_it_exists(self) -> None:
        assert MODEL.is_file(), f"{MODEL.name} is missing; run {EXTRACTOR.name}"

    @pytest.mark.parametrize("section", ["roles", "matrixRoles", "matrix", "pages", "modals"])
    def test_every_section_is_present_and_not_empty(self, section: str, committed: dict[str, object]) -> None:
        assert committed.get(section), section

    def test_every_page_has_a_key_and_a_name(self, committed: dict[str, object]) -> None:
        pages: Final = committed["pages"]
        assert isinstance(pages, list)
        nameless: Final = [p for p in pages if not p.get("k") or not p.get("name")]
        assert not nameless, nameless

    def test_page_keys_are_unique_because_they_address_a_screen(self, committed: dict[str, object]) -> None:
        keys: Final = [p["k"] for p in committed["pages"]]
        assert len(keys) == len(set(keys)), [k for k in keys if keys.count(k) > 1]

    def test_the_access_matrix_covers_all_eight_roles(self, committed: dict[str, object]) -> None:
        """Section 12 names eight. A matrix that lost one silently drops a role's restrictions."""
        assert len(committed["matrixRoles"]) == 8, committed["matrixRoles"]


class TestTheModelMatchesTheBlueprint:
    def test_re_extracting_produces_the_committed_file(self, tmp_path: pathlib.Path) -> None:
        """The blueprint is the source. This is the only test that proves the JSON is not stale."""
        node: Final = shutil.which("node")
        if node is None:
            pytest.skip("node is not installed, so the extractor cannot be run here")

        before: Final = MODEL.read_text(encoding="utf-8")
        backup: Final = tmp_path / "page-model.json"
        _ = backup.write_text(before, encoding="utf-8")
        try:
            run = subprocess.run(
                (node, str(EXTRACTOR)), cwd=REPO, capture_output=True, text=True, check=False
            )
            assert run.returncode == 0, run.stderr
            assert MODEL.read_text(encoding="utf-8") == before, (
                "page-model.json is stale: the blueprint has changed since it was extracted. "
                f"Re-run `node {EXTRACTOR.relative_to(REPO).as_posix()}` and commit the result"
            )
        finally:
            _ = MODEL.write_text(before, encoding="utf-8")
