"""Check a built wheel actually contains the packages and data the product needs.

Everything passes from a source checkout, because the files sit right there next to the code.
A wheel contains only what the build backend was told to include, and maturin builds the one
Python package `module-name` points at. The price list has gone missing from a wheel twice: once
when it moved out of the package with nothing adding it back, and once when `tool.maturin.include`
named it at the repository root and the wheel shipped without it anyway, so the published image
could not import its own engine.

Run against the real wheel, in the job that already builds one:

    python .github/scripts/verify_wheel_contents.py dist/*.whl
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable
from typing import Final

# Every top-level path a wheel must carry something under. Checked separately from the files
# below so that a package missing altogether reads differently from one that arrived empty.
TREES: Final[tuple[str, ...]] = ("token_iq/", "token_iq/pricing/data/")

# One file from each subpackage, because an include glob can match a directory and still bring
# none of its contents.
FILES: Final[tuple[str, ...]] = (
    "token_iq/gateway/__init__.py",
    "token_iq/__init__.py",
    "token_iq/api/overview.py",
    "token_iq/api/types/overview.py",
    "token_iq/attribution/gap_owner.py",
    "token_iq/connectors/billing/openai.py",
    "token_iq/connectors/tools/claude_code.py",
    "token_iq/ledger/reconciliation.py",
    "token_iq/overview/totals.py",
    "token_iq/policy/team_api_access.py",
    "token_iq/pricing/history.py",
    "token_iq/recommendations/rules/price_drift.py",
    "token_iq/repositories/ledger_repository.py",
    "token_iq/seats/user_cost.py",
    "token_iq/types/provider_billing.py",
    "token_iq/pricing/data/model_prices.json",
    "token_iq/pricing/data/price_history.jsonl",
)

# Imported from a directory that is not the checkout, so a module that only resolves because the
# repository happens to be on `sys.path` fails here. One per subpackage, and only modules that
# import nothing but the standard library: the install is deliberately `--no-deps`, so a router
# pulling in FastAPI would fail for a reason that has nothing to do with packaging. The zip
# check above covers the routers instead.
IMPORTS: Final[tuple[str, ...]] = (
    "token_iq",
    "token_iq.api.types",
    "token_iq.attribution.gap_owner",
    "token_iq.connectors.billing.openai",
    "token_iq.connectors.tools.claude_code",
    "token_iq.ledger.reconciliation",
    "token_iq.overview.totals",
    "token_iq.policy.plan",
    "token_iq.pricing.history",
    "token_iq.recommendations.registry",
    "token_iq.repositories.ledger_repository",
    "token_iq.seats.user_cost",
    "token_iq.types.provider_billing",
)

# The price data is found relative to a module's own `__file__`, so being inside the zip is not
# the same as being reachable: a wheel that puts it somewhere else still installs. This reads the
# path the code will really use.
#
# The probe goes through `token_iq.pricing.history` rather than the engine's own price loader,
# which resolves the same directory but cannot be imported at all under `--no-deps`: reaching it
# means importing `token_iq/gateway/__init__.py`, and that wants the whole dependency tree.
# Both files are checked from the one path the probe does resolve.
PRICE_DATA: Final[tuple[str, str, tuple[str, ...]]] = (
    "token_iq.pricing.history",
    "HISTORY_PATH",
    ("price_history.jsonl", "model_prices.json"),
)

REACHED: Final = "reached"

PROBE: Final = """
from {module} import {name} as path
missing = [n for n in {siblings!r} if not (path.parent / n).is_file()]
print({reached!r} if not missing else "{{}} resolved to {{}}, which holds none of {{}}".format(
    {name!r}, path.parent, missing))
"""


def complaints(names: Iterable[str]) -> tuple[str, ...]:
    """What is wrong with this wheel, said once per cause rather than once per file."""
    held: Final = frozenset(names)
    empty: Final = tuple(tree for tree in TREES if not any(name.startswith(tree) for name in held))
    return (
        *(f"nothing at all under {tree}" for tree in empty),
        # A file under a tree already reported as empty would only repeat that finding.
        *(name for name in FILES if name not in held and not name.startswith(empty)),
    )


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {pathlib.Path(sys.argv[0]).name} WHEEL\n")
        return 2

    wheel: Final = pathlib.Path(sys.argv[1])
    if not wheel.is_file():
        sys.stderr.write(f"no such wheel: {wheel}\n")
        return 2

    with zipfile.ZipFile(wheel) as archive:
        missing: Final = complaints(archive.namelist())

    if missing:
        sys.stderr.write(f"{wheel.name} is missing:\n")
        for name in missing:
            sys.stderr.write(f"  {name}\n")
        return 1

    sys.stdout.write(f"{wheel.name} holds all {len(FILES)} required files\n")
    return _check_an_install(wheel)


def _check_an_install(wheel: pathlib.Path) -> int:
    """Install into a throwaway environment and use it, from a directory that is not the repo."""
    with tempfile.TemporaryDirectory() as workspace:
        root: Final = pathlib.Path(workspace)
        venv: Final = root / "venv"
        created: Final = subprocess.run(
            (sys.executable, "-m", "venv", str(venv)), capture_output=True, text=True, check=False
        )
        if created.returncode != 0:
            sys.stderr.write(f"could not create a virtual environment:\n{created.stderr}\n")
            return 1

        python: Final = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

        # --no-deps: this proves the wheel's own contents, not that its dependency tree resolves.
        installed: Final = subprocess.run(
            (str(python), "-m", "pip", "install", "--no-deps", "--quiet", str(wheel.resolve())),
            capture_output=True,
            text=True,
            cwd=root,
            check=False,
        )
        if installed.returncode != 0:
            sys.stderr.write(f"could not install the wheel:\n{installed.stdout}{installed.stderr}\n")
            return 1

        failures: Final = _failed_imports(python, root)
        unreachable: Final = () if failures else _unreachable_data(python, root)

    if failures:
        sys.stderr.write(f"an install of {wheel.name} cannot import:\n")
        for module, error in failures:
            sys.stderr.write(f"  {module}: {error}\n")
        return 1

    if unreachable:
        sys.stderr.write(f"an install of {wheel.name} cannot reach its own data:\n")
        for line in unreachable:
            sys.stderr.write(f"  {line}\n")
        return 1

    sys.stdout.write(
        f"an install of {wheel.name} imports all {len(IMPORTS)} modules and reaches its price data\n"
    )
    return 0


def _run(python: pathlib.Path, cwd: pathlib.Path, source: str) -> subprocess.CompletedProcess[str]:
    # cwd is the temporary directory, so nothing resolves via the checkout.
    return subprocess.run(
        (str(python), "-c", source), capture_output=True, text=True, cwd=cwd, check=False
    )


def _last_line(text: str) -> str:
    return next(reversed(text.strip().splitlines()), "")


def _failed_imports(python: pathlib.Path, cwd: pathlib.Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        (module, _last_line(result.stderr))
        for module, result in ((name, _run(python, cwd, f"import {name}")) for name in IMPORTS)
        if result.returncode != 0
    )


def _unreachable_data(python: pathlib.Path, cwd: pathlib.Path) -> tuple[str, ...]:
    """Ask the installed code where its price data is, then check it is really there."""
    module, name, siblings = PRICE_DATA
    result: Final = _run(
        python, cwd, PROBE.format(module=module, name=name, siblings=siblings, reached=REACHED)
    )
    if result.returncode == 0 and result.stdout.strip() == REACHED:
        return ()
    return (f"{module}.{name}: {result.stdout.strip() or _last_line(result.stderr)}",)


if __name__ == "__main__":
    sys.exit(main())
