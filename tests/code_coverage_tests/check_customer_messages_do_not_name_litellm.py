"""Messages the proxy returns to callers must not name LiteLLM.

A message is a string literal assigned to detail, message, exceeded_message, event_message or an
"error" key. Files listed in ALLOWED are exempt, each for the reason given.
"""

import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

REPO: Final = Path(__file__).resolve().parents[2]
MESSAGE: Final = re.compile(
    r"""(?:\bdetail|\bmessage|\bexceeded_message|\bevent_message|["']error["'])\s*[:=]\s*f?"""
    r"""(?:"(?P<double>[^"\n]*LiteLLM[^"\n]*)"|'(?P<single>[^'\n]*LiteLLM[^'\n]*)')"""
)
ALLOWED: Final[Mapping[str, str]] = MappingProxyType(
    {
        "litellm/proxy/example_config_yaml/custom_auth.py": "sample code a customer copies and edits",
        "litellm/proxy/post_call_rules.py": "sample rule a customer copies and edits",
    }
)


def offending_messages() -> tuple[str, ...]:
    return tuple(
        f"{path.relative_to(REPO).as_posix()}:{number}  {(match.group('double') or match.group('single'))[:100]}"
        for path in sorted((REPO / "litellm" / "proxy").rglob("*.py"))
        if path.relative_to(REPO).as_posix() not in ALLOWED
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        for match in MESSAGE.finditer(line)
    )


def main() -> int:
    found: Final = offending_messages()
    for line in found:
        print(f"customer-facing message names LiteLLM  {line}")
    if found:
        return 1
    print("No customer-facing proxy message names LiteLLM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
