"""The bundled tokenizer files have to be where the code says they are.

`default_encoding` points `TIKTOKEN_CACHE_DIR` at a directory inside the package so tiktoken never
reaches the network. The path is a relative string, so moving the package in phase 6 left it naming
`litellm_core_utils/tokenizers`, which no longer existed. Nothing failed: the import succeeded, the
directory was created empty on first use, and tiktoken would have gone to the network for files that
were sitting in the tree all along. An air-gapped installation would have found that out first.
"""

import os
import pathlib
from typing import Final

import pytest


@pytest.fixture(scope="module")
def cache_dir() -> pathlib.Path:
    """Where the engine tells tiktoken to look, read after importing it as any caller would."""
    import token_iq.gateway  # noqa: F401  # imported for the side effect of setting the variable

    where = os.environ.get("TIKTOKEN_CACHE_DIR")
    assert where, "importing the engine did not set TIKTOKEN_CACHE_DIR"
    return pathlib.Path(where)


def test_the_tokenizer_cache_points_at_a_directory_that_exists(cache_dir: pathlib.Path) -> None:
    assert cache_dir.is_dir(), f"{cache_dir} is not there, so tiktoken would create it empty and download"


# The BPE ranks tiktoken looks up by hash, committed so the engine never has to fetch them.
BUNDLED: Final = frozenset(
    {
        "9b5ad71b2ce5302211f9c61530b329a4922fc6a4",
        "ec7223a39ce59f226a68acc30dc1af2788490e15",
        "fb374d419588a4632f3f557e76b4b70aebbca790",
        "anthropic_tokenizer.json",
    }
)


def test_the_tokenizer_cache_holds_the_bundled_files(cache_dir: pathlib.Path) -> None:
    """Named files, not merely a non-empty directory. A wrong path still answers `is_dir()` because it
    gets created on first use, and tiktoken then writes one downloaded file into it, so "exists" and
    "not empty" are both true of the failure this test is for."""
    present: Final = {path.name for path in cache_dir.glob("*")}
    assert BUNDLED <= present, f"{cache_dir} is missing {sorted(BUNDLED - present)}"


def test_the_cache_is_inside_the_package_rather_than_beside_it(cache_dir: pathlib.Path) -> None:
    """It ships with the package, so it has to resolve under the package wherever that is installed."""
    import token_iq.gateway

    package = pathlib.Path(token_iq.gateway.__file__).resolve().parent
    assert cache_dir.resolve().is_relative_to(package)
