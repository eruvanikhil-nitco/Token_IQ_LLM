"""The one module allowed to name what Token IQ used to be called.

A customer upgrading to this release keeps their configuration. Their environment says `LITELLM_…`,
their `config.yaml` says `litellm_settings`, and both go on working, with a warning saying what to
change. The release after next deletes this file, and `tests/repo/test_no_litellm_name.py` is what
makes everywhere else stay clean in the meantime.

Reading an environment variable goes through `env` rather than `os.getenv`, so the fallback exists in
one place instead of once per call site. The new name wins when both are set, because an operator who
has already migrated should not be overridden by a variable they forgot to delete.

The warning fires once per name, not once per read. `LITELLM_LOG` is read four times while the proxy
starts, and four identical lines teach a reader nothing the first one did not.
"""

from __future__ import annotations

import functools
import os
import warnings
from collections.abc import Callable, Mapping
from typing import Final

OLD_PREFIX: Final = "LITELLM_"
NEW_PREFIX: Final = "TOKEN_IQ_"


def old_name_for(name: str) -> str | None:
    """What this variable used to be called, or None when it was never renamed.

    Every one of the 80 the engine reads starts with the new prefix, so the mapping is the prefix and
    nothing else. A name that does not start with it is some other project's variable, and guessing an
    old spelling for `AWS_REGION_NAME` would invent a fallback nobody asked for.
    """
    return f"{OLD_PREFIX}{name[len(NEW_PREFIX) :]}" if name.startswith(NEW_PREFIX) else None


def _say(message: str) -> None:
    """Say it through the engine's logger, or through `warnings` when that is not ready yet.

    Imported here rather than at module scope, for two reasons that both matter. `_logging` pulls in the
    logging stack, and this module is read while the proxy is still working out how to log. And
    `_logging` itself reads two of these variables, so the very first warning can fire part-way through
    importing it, when the module object exists but `verbose_logger` does not. Letting that raise would
    turn a deprecation notice into a failure to start.
    """
    try:
        from token_iq.gateway._logging import verbose_logger
    except ImportError:
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        return
    logger: Final = getattr(verbose_logger, "warning", None)
    if logger is None:
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        return
    logger(message)


@functools.cache
def _warn_once(old: str, new: str, say: Callable[[str], None]) -> None:
    """Say it the first time this name is read by its old spelling, and not again.

    `functools.cache` rather than a set of names already seen: the requirement is one line per name per
    process, which is what a cache keyed on the name already means, and it leaves no mutable collection
    for anything to grow. `cache_clear` is the seam a test uses to see the first warning again.
    """
    say(
        f"{old} is the name Token IQ used before it was renamed. It still works in this release and is "
        f"removed in the one after next. Set {new} instead."
    )


def env(
    name: str,
    default: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    warn: Callable[[str], None] | None = None,
) -> str | None:
    """The value of `name`, falling back to what it used to be called.

    `environ` and `warn` are parameters so a test can set an environment and read the warning without
    touching the process it runs in, which is what makes the fallback testable at all.
    """
    source: Final = os.environ if environ is None else environ
    found: Final = source.get(name)
    if found is not None:
        return found

    old: Final = old_name_for(name)
    if old is None:
        return default
    legacy: Final = source.get(old)
    if legacy is None:
        return default

    _warn_once(old, name, warn or _say)
    return legacy


def forget_warnings() -> None:
    """Let a test see the first warning again. Nothing in the engine calls this."""
    _warn_once.cache_clear()
