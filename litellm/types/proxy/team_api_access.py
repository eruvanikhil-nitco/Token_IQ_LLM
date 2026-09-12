"""Which addresses a team may send model requests to.

A leaf module on purpose: the team model and the auth check both need these two names,
and anything heavier here would close a circular import between them.
"""

from __future__ import annotations

from typing import Final, Literal

TeamApiAccessMode = Literal["courier", "translator", "both"]

DEFAULT_API_ACCESS_MODE: Final[TeamApiAccessMode] = "both"
