"""The old product name does not spread, and never reaches a customer.

Phase 10's first bullet. The plan asks for a test that fails if `litellm` appears anywhere outside a short
allowlist. That test cannot pass yet, and not because of untidy comments: 65,743 mentions remain, and they
are data contracts rather than prose. `litellm_params` alone is 15,038, and it is a config key, a column on
`LiteLLM_ProxyModelTable`, a field in request and response bodies and a word in the UI. `litellm_provider`
is 4,414 and keys the bundled price map. `litellm_teamtable` and its siblings are Prisma table names that
step 2 of phase 8 renames behind a runbook. `litellm_call_id`, `litellm_logging_obj` and `litellm_metadata`
are threaded through every call path in the engine.

The plan already says when those go: "in the release after the transition release, delete `compat.py` and
its test, remove those allowlist entries, and ship step 2 of phase 8". So zero is the end state, not
today's, and a gate asserting zero today would be a gate nobody can run.

What this does instead is what the three budget gates beside it do. Two properties hold at zero and are
asserted at zero, because they are the ones a customer can see. The rest is counted per area against a
ceiling that only ever comes down. A new mention fails the build; removing mentions and re-recording the
count ratchets the ceiling. That stops the name spreading while the families above are retired in the order
the plan sets.

It replaces `check_customer_messages_do_not_name_litellm.py` and
`check_openapi_docs_do_not_name_litellm.py`, whose checks are the two zero-tolerance properties here.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
from collections.abc import Mapping
from typing import Final

import pytest
from pydantic import BaseModel

REPO: Final = pathlib.Path(__file__).resolve().parents[2]
BUDGET_PATH: Final = REPO / "no-litellm-name-budget.json"

NAME: Final = re.compile(r"litellm", re.I)

ALLOWED: Final[Mapping[str, str]] = {
    "no-litellm-name-budget.json": "this gate's own ceilings; one area is named litellm-rust, so counting it would count the bookkeeping",
    "LICENSE": "the MIT licence the fork was granted; removing it is a licence violation",
    "NOTICE": "the attribution the licence requires",
    "CHANGELOG.md": "releases and upgrade notes, which name what each setting used to be called",
    "docs/decisions/": "decision records say what was true when they were written",
    "docs/plans/": "historical",
    "docs/specs/": "historical",
    "docs/status.md": "historical",
    "docs/product/": "the blueprint describes removing the name, so it has to say it",
    "token_iq/gateway/compat.py": "the one module allowed to name old names, until the compat release ends",
    "tests/gateway/test_compat.py": "its test, for the same reason",
    "token_iq/gateway/proxy/_experimental/out/": "the built dashboard bundle, generated from ui/dashboard",
    "scripts/update_model_prices.py": "the upstream price source names itself",
    "scripts/rename/write_upgrading_notes.py": "it writes the upgrade notes, which name what each setting used to be called, the same reason CHANGELOG.md is here",
    ".github/workflows/update-model-prices.yml": "the same, in CI",
}
"""Each exemption with the reason it exists. The plan lists these; a new one needs a reason here."""

MESSAGE: Final = re.compile(
    r"""(?:\bdetail|\bmessage|\bexceeded_message|\bevent_message|["']error["'])\s*[:=]\s*f?"""
    r"""(?:"(?P<double>[^"\n]*LiteLLM[^"\n]*)"|'(?P<single>[^'\n]*LiteLLM[^'\n]*)')"""
)
"""A string the proxy hands back to a caller, naming the product. From the gate this test replaces."""

ERROR_PREFIX: Final = re.compile(r"""f?["']litellm\.(?:\w*(?:Error|Exception)|Timeout)\b""")
"""The exception name that opens the body of every API error, as in `litellm.RateLimitError: ...`.

Its own pattern because the one above matches `LiteLLM` and these are lowercase, so 27 of them sat in
customer-visible text unseen. Searching the whole lowercase word instead would also match advice like
"set `litellm.drop_params`", which names a Python attribute whose own rename waits on the module rename,
and a check that cannot go green teaches people to ignore it."""

MESSAGE_ALLOWED: Final[Mapping[str, str]] = {
    "token_iq/gateway/proxy/example_config_yaml/custom_auth.py": "sample code a customer copies and edits",
    "token_iq/gateway/proxy/post_call_rules.py": "sample rule a customer copies and edits",
}


class Mention(BaseModel, frozen=True):
    file: str
    line: int
    text: str


def _tracked() -> tuple[str, ...]:
    return tuple(
        line
        for line in subprocess.run(
            ("git", "ls-files"), cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        if line
    )


def _exempt(name: str) -> bool:
    return any(name == allowed or name.startswith(allowed) for allowed in ALLOWED)


def _read(name: str) -> str | None:
    try:
        return (REPO / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def area_of(name: str) -> str:
    """The bucket a file counts against, which is its top-level folder."""
    return name.split("/", 1)[0] if "/" in name else "(root)"


def counts_by_area() -> Mapping[str, int]:
    """How many mentions each area holds, outside the allowlist."""
    found: dict[str, int] = {}  # rebind-ok: the tally of a scan over files
    for name in _tracked():
        if _exempt(name):
            continue
        text = _read(name)
        if text is None:
            continue
        hits = len(NAME.findall(text))
        if hits:
            found[area_of(name)] = found.get(area_of(name), 0) + hits
    return found


class Budget(BaseModel, frozen=True):
    """The recorded ceilings, validated rather than read off an `Any` from `json.loads`."""

    areas: Mapping[str, int]


def budget() -> Mapping[str, int]:
    return Budget.model_validate_json(BUDGET_PATH.read_text(encoding="utf-8")).areas


def customer_messages() -> tuple[Mention, ...]:
    """Every string the proxy returns to a caller that names the old product."""
    return tuple(
        Mention(file=name, line=number, text=(found.group("double") or found.group("single"))[:90])
        for name in _tracked()
        if name.endswith(".py") and name not in MESSAGE_ALLOWED and not name.startswith("tests/")
        for text in (_read(name),)
        if text is not None
        for number, line in enumerate(text.splitlines(), start=1)
        for found in (MESSAGE.search(line),)
        if found is not None
    )


def test_no_message_the_proxy_returns_names_the_old_product() -> None:
    """Zero, and asserted at zero: this is what a caller reads in an error."""
    offenders: Final = customer_messages()
    assert not offenders, "these messages name the old product: " + ", ".join(
        f"{one.file}:{one.line} {one.text}" for one in offenders
    )


def test_no_api_error_opens_with_the_old_name() -> None:
    """The first thing in the body of every error a caller receives. It said `litellm.RateLimitError` until
    the engine was taught to write `token_iq.` and read both, and nothing was watching because the other
    pattern here is case-sensitive."""
    offenders: Final = tuple(
        f"{name}:{number}"
        for name in _tracked()
        # The engine only. A rename codemod names what it renames, and so does the generator for the
        # upgrade notes; neither is the proxy answering a caller.
        if name.startswith("token_iq/") and name.endswith(".py") and not _exempt(name)
        for text in (_read(name),)
        if text is not None
        for number, line in enumerate(text.splitlines(), start=1)
        if ERROR_PREFIX.search(line)
    )

    assert not offenders, f"these errors still open with the old name: {offenders}"


def test_the_error_prefix_check_can_tell() -> None:
    """Said against the exact line it exists for, since the assertion above is an absence."""
    assert ERROR_PREFIX.search('self.message = f"litellm.RateLimitError: {message}"')
    assert ERROR_PREFIX.search('self.message = f"litellm.Timeout: {message}"')
    assert not ERROR_PREFIX.search('self.message = f"token_iq.RateLimitError: {message}"')
    assert not ERROR_PREFIX.search('"set `litellm.drop_params` to ignore it"'), "advice text is not this check's job"


def test_the_message_check_can_still_tell() -> None:
    """Said against a line it must catch, because an empty result is also what a dead pattern returns."""
    assert MESSAGE.search('raise ProxyException(message="LiteLLM is not configured")') is not None
    assert MESSAGE.search('detail = "Token IQ is not configured"') is None


def test_no_area_holds_more_of_the_old_name_than_its_ceiling() -> None:
    """The ratchet. A new mention fails here; removing mentions and re-recording lowers the ceiling."""
    limits: Final = budget()
    now: Final = counts_by_area()
    over: Final = tuple(
        f"{area}: {count} over {limits.get(area, 0)}"
        for area, count in sorted(now.items())
        if count > limits.get(area, 0)
    )
    assert not over, (
        "the old name spread: " + ", ".join(over) + ". Remove them, or run "
        "`python tests/repo/test_no_litellm_name.py --update` and commit the lowered ceilings."
    )


def test_a_ceiling_nobody_needs_any_more_is_noticed() -> None:
    """An area that fell to zero should lose its entry, or the budget keeps headroom nothing uses."""
    limits: Final = budget()
    now: Final = counts_by_area()
    stale: Final = tuple(area for area, limit in sorted(limits.items()) if limit > 0 and now.get(area, 0) == 0)

    assert not stale, f"these areas are clean and their ceilings can go: {stale}"


def test_every_exemption_carries_a_reason() -> None:
    """The allowlist is the part that rots. A path with no reason is a path nobody can review."""
    assert all(reason.strip() for reason in ALLOWED.values())
    assert "LICENSE" in ALLOWED and "NOTICE" in ALLOWED, "the licence files are a legal obligation"


def test_the_allowlist_only_exempts_paths_that_exist() -> None:
    """A stale entry silently widens the gate."""
    missing: Final = tuple(path for path in ALLOWED if not (REPO / path).exists() and not path.endswith("/"))

    assert not missing, f"these exemptions name nothing: {missing}"


def test_the_scan_really_reads_the_repository() -> None:
    """Guards every count above, which an empty file list would make meaningless."""
    assert len(_tracked()) > 3000
    assert sum(counts_by_area().values()) > 0, "a scan finding nothing at all means the reader is broken"


@pytest.mark.parametrize("area", ["token_iq", "tests"])
def test_the_biggest_areas_are_counted(area: str) -> None:
    """Named so a filter that quietly stops matching them cannot pass unnoticed."""
    assert counts_by_area().get(area, 0) > 0


if __name__ == "__main__":
    import sys

    if "--update" in sys.argv:
        measured = dict(sorted(counts_by_area().items()))
        BUDGET_PATH.write_text(json.dumps({"areas": measured}, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(f"recorded {sum(measured.values())} mention(s) across {len(measured)} area(s)\n")
    else:
        sys.stdout.write(json.dumps(dict(sorted(counts_by_area().items())), indent=2) + "\n")
