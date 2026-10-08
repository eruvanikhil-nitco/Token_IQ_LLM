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
from collections.abc import Callable, Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Final, TypeVar

_V = TypeVar("_V")

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
        # Part-way through importing `_logging`: the module object is in sys.modules but the name is not
        # bound yet, which `from ... import` reports as an ImportError rather than an AttributeError.
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        return
    verbose_logger.warning(message)


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


CONFIG_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # What a config.yaml may now say, and the spelling the engine reads it as. Normalising towards
        # the old name rather than the new one is deliberate: 1,647 places in the engine read
        # `litellm_params` as a Python keyword argument or attribute, and renaming those is a separate
        # piece of work from accepting both spellings in a customer's file. A reader of this release sees
        # the new names in their config and the old ones in the code, which is what a transition means.
        "gateway_settings": "litellm_settings",
        "model_params": "litellm_params",
    }
)

RENAMED_CONFIG_KEYS: Final[Mapping[str, str]] = MappingProxyType({old: new for new, old in CONFIG_KEYS.items()})
"""The other way round, for saying what to change."""


def _config_value(value: object, say: Callable[[str], None]) -> object:
    """One value from a config, with every renamed key inside it normalised."""
    if isinstance(value, Mapping):
        mapping: Final[Mapping[object, object]] = value  # pyright: ignore[reportUnknownVariableType]  # YAML data
        # A dict, for the same reason the list below stays a list: this is a customer's own data on its
        # way through, and the proxy edits the config it is handed.
        return {  # mutable-ok: see above
            _config_key(key, say) if isinstance(key, str) else key: _config_value(inner, say)
            for key, inner in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        items: Final[Sequence[object]] = value  # pyright: ignore[reportUnknownVariableType]  # YAML data
        # A list, not a tuple: a customer's `model_list` is a list in their file and the proxy treats it
        # as one. Freezing it here would change the type of their own data on the way through.
        # The suppressions below are on the element type, not the call: narrowing YAML data with
        # `isinstance` leaves the elements unknown, and the parameter is already as wide as `object` gets.
        return [  # mutable-ok: see above
            _config_value(item, say)  # pyright: ignore[reportUnknownArgumentType]  # YAML elements
            for item in items  # pyright: ignore[reportUnknownVariableType]  # same
        ]
    return value


def _config_key(key: str, say: Callable[[str], None]) -> str:
    """The spelling the engine reads, and a word about it the first time an old one is seen."""
    if key in CONFIG_KEYS:
        return CONFIG_KEYS[key]
    if key in RENAMED_CONFIG_KEYS:
        _warn_once(key, RENAMED_CONFIG_KEYS[key], say)
    return key


def config(
    loaded: Mapping[str, object], *, warn: Callable[[str], None] | None = None
) -> dict[str, object]:  # mutable-ok: the loaded config is a document the proxy edits in place
    """A loaded config with both spellings of every renamed key accepted.

    Applied where a config comes out of `ProxyConfig.get_config`, which is the one place every source
    passes through: a file, the database, GCS and S3 all end up there. Doing it per reader instead would
    mean finding all of them, and the ones under `model_list` are nested inside a customer's own data.

    Walks the whole structure rather than only the top level, because `litellm_params` sits inside each
    entry of `model_list` and a customer may have a hundred of those.

    Returns a plain dict because that is what every caller already has: `get_config` is annotated to
    return one, `_check_for_os_environ_vars` rebinds it, and the printed copy has a key popped out of it.
    A read-only view here would be a change to all of them rather than a compatibility shim.
    """
    said: Final = warn or _say
    return {  # mutable-ok: see the return type
        _config_key(key, said): _config_value(value, said) for key, value in loaded.items()
    }


OLD_HEADER_PREFIX: Final = "x-litellm-"
NEW_HEADER_PREFIX: Final = "x-token-iq-"

HEADER_PREFIXES: Final = (NEW_HEADER_PREFIX, OLD_HEADER_PREFIX)
"""Both spellings, for the two places that have to recognise a Token IQ header without knowing its name.

One strips them off a request before forwarding it to an agent, so a caller cannot claim to be the proxy.
The other decides whether a response header is the engine's own or a provider's. Both are about trust, so
both have to know the old prefix for as long as the old prefix still authenticates anything.
"""

OLD_API_KEY_HEADER: Final = f"{OLD_HEADER_PREFIX}api-key"
NEW_API_KEY_HEADER: Final = f"{NEW_HEADER_PREFIX}api-key"
API_KEY_HEADERS: Final = frozenset({NEW_API_KEY_HEADER, OLD_API_KEY_HEADER})
"""Named, unlike the other 90, because FastAPI wants a header name at import time rather than a lookup.

`APIKeyHeader(name=...)` builds a security dependency per name, so accepting both spellings of the key
header means two dependencies, and each needs its literal. The set is for the places that ask whether
a header authenticates the caller, which decide whether to forward it to a provider or an agent.
"""


def old_header_for(name: str) -> str | None:
    """What this header used to be called, or None when it was never renamed.

    Lowercased on the way out because that is the form every call site asks for and the form HTTP/2 puts
    on the wire. Header names are case-insensitive, so `X-LiteLLM-Trace-Id` and `x-litellm-trace-id` are
    one header, and treating them as two would mean a fallback that fires for one casing and not the other.
    """
    lowered: Final = name.lower()
    if not lowered.startswith(NEW_HEADER_PREFIX):
        return None
    return f"{OLD_HEADER_PREFIX}{lowered[len(NEW_HEADER_PREFIX) :]}"


def header(
    headers: Mapping[str, _V],
    name: str,
    default: _V | None = None,
    *,
    warn: Callable[[str], None] | None = None,
) -> _V | None:
    """The value of a request header, falling back to what the header used to be called.

    Every read of a `x-token-iq-…` header goes through here, including the ones that read a dict the
    engine filled in itself. Sorting reads into "could be a caller's" and "could only be ours" would be a
    judgement per call site, and getting it wrong in the first direction 401s a customer whose client has
    not been updated. Getting it wrong the other way costs a dictionary lookup that misses.

    Tries the name as given before the lowercase form, and nothing else. `Headers` from Starlette and
    httpx are both case-insensitive, and the plain dicts that reach a read here are either `dict(
    request.headers)`, whose keys Starlette has already lowercased, or built by a reader that lowercases
    them itself. Guessing a mixed-case spelling instead would be wrong anyway, since `str.title()` turns
    `x-litellm-trace-id` into `X-Litellm-Trace-Id` and the engine used to write `X-LiteLLM-Trace-Id`.
    """
    found: Final = headers.get(name, headers.get(name.lower()))
    if found is not None:
        return found

    old: Final = old_header_for(name)
    if old is None:
        return default
    legacy: Final = headers.get(old)
    if legacy is None:
        return default

    _warn_once(old, name.lower(), warn or _say)
    return legacy


PROVIDER_PREFIX: Final = "llm_provider-"
PROVIDER_COST_KEY: Final = f"{PROVIDER_PREFIX}{NEW_HEADER_PREFIX}response-cost"
PROVIDER_COST_KEYS: Final = (PROVIDER_COST_KEY, f"{PROVIDER_PREFIX}{OLD_HEADER_PREFIX}response-cost")
"""Where a cost an upstream reported lands once `process_response_headers` has prefixed it.

A hop to another Token IQ proxy arrives as a raw provider response, so its `…-response-cost` header is
prefixed rather than kept bare, and the key depends on which release that proxy is running. The engine
writes the first and reads both, so a fleet part-way through an upgrade still counts the cost its
upstream reported instead of silently falling back to its own estimate.
"""


def both_spellings(names: Iterable[str]) -> tuple[str, ...]:
    """Every name given, each followed by what it used to be called.

    For the lists of header names the engine matches a request against. A list of headers it *sends* does
    not go through here: a response carries the new name only, which is what makes the old one droppable.
    """
    return tuple(spelling for name in names for spelling in (name, old_header_for(name)) if spelling is not None)


def is_gateway_header(name: str) -> bool:
    """Whether this is one of the engine's own headers, under either spelling of the prefix."""
    return name.lower().startswith(HEADER_PREFIXES)


OLD_ID_PREFIX: Final = "litellm:"
NEW_ID_PREFIX: Final = "token_iq:"
ID_PREFIXES: Final = (NEW_ID_PREFIX, OLD_ID_PREFIX)
"""The prefix inside an identifier the engine hands a caller and later reads back.

A file id, a batch id, a response item id and a container id are all base64 of a string that starts with
this. The caller stores the result and sends it back whenever it likes, so an id issued before the rename
has to keep decoding for as long as anything a customer saved is still in use. New ones carry the new
spelling; both are accepted on the way in.
"""


def strip_id_prefix(decoded: str) -> str | None:
    """What follows the prefix in a decoded identifier, or None when it carries neither spelling."""
    for prefix in ID_PREFIXES:
        if decoded.startswith(prefix):
            return decoded[len(prefix) :]
    return None


def has_id_prefix(decoded: str) -> bool:
    """Whether this decoded identifier is one the engine issued, under either spelling."""
    return decoded.startswith(ID_PREFIXES)


OLD_WRAPPED_CONTENT_PREFIX: Final = "litellm_enc:"
NEW_WRAPPED_CONTENT_PREFIX: Final = "token_iq_enc:"
WRAPPED_CONTENT_PREFIXES: Final = (NEW_WRAPPED_CONTENT_PREFIX, OLD_WRAPPED_CONTENT_PREFIX)
"""The prefix on encrypted content the engine wraps a model id into and a client sends back verbatim.

The same situation as an identifier, one layer in: a Codex client holds the wrapped content and replays it,
so content wrapped before the rename has to keep unwrapping.
"""


def strip_wrapped_content_prefix(wrapped: str) -> str | None:
    """What follows the prefix in wrapped content, or None when it carries neither spelling."""
    for prefix in WRAPPED_CONTENT_PREFIXES:
        if wrapped.startswith(prefix):
            return wrapped[len(prefix) :]
    return None


def both_claim_sources(sources: Iterable[str]) -> tuple[str, ...]:
    """Each claim source a guardrail accepts, followed by the spelling it had before the rename.

    A customer writes these in their config, so the old ones keep working. Unlike a header, the engine never
    sends one back, so there is nothing to stop emitting.
    """
    return tuple(
        spelling
        for source in sources
        for spelling in (
            source,
            source.replace(NEW_ID_PREFIX, OLD_ID_PREFIX, 1) if source.startswith(NEW_ID_PREFIX) else None,
        )
        if spelling is not None
    )


OLD_MASTER_KEY_ALIAS: Final = "litellm_proxy_master_key"
NEW_MASTER_KEY_ALIAS: Final = "token_iq_proxy_master_key"
MASTER_KEY_ALIASES: Final = (NEW_MASTER_KEY_ALIAS, OLD_MASTER_KEY_ALIAS)
"""What stands in for the master key everywhere it would otherwise be written down.

Spend logs, audit rows and metrics already hold the old spelling, and two checks ask whether a key is this
alias rather than a secret worth redacting. Those read both, or every row written before the rename starts
failing the check that keeps a real key out of a log.
"""

OLD_HEALTH_CHECK_ACCOUNT: Final = "litellm-internal-health-check"
NEW_HEALTH_CHECK_ACCOUNT: Final = "token-iq-internal-health-check"
HEALTH_CHECK_ACCOUNTS: Final = (NEW_HEALTH_CHECK_ACCOUNT, OLD_HEALTH_CHECK_ACCOUNT)
"""The service account the background health check bills its own calls to.

It is the key, the team, both aliases and a tag on every row the health check writes, so a customer's spend
history is full of the old spelling and their Tag Management page lists it.
"""

OLD_UI_SESSION_TEAM_ID: Final = "litellm-dashboard"
NEW_UI_SESSION_TEAM_ID: Final = "token-iq-dashboard"
UI_SESSION_TEAM_IDS: Final = (NEW_UI_SESSION_TEAM_ID, OLD_UI_SESSION_TEAM_ID)
"""The team a dashboard login's key belongs to, which is how a session token is told from a real key.

Sessions outlive an upgrade. Reading only the new spelling would leave every key issued before it looking
like an ordinary virtual key: listed on the Virtual Keys page, counted in Prometheus, and never cleaned up
when it expires.
"""


def is_master_key_alias(value: str) -> bool:
    return value in MASTER_KEY_ALIASES


def is_ui_session_team(team_id: str | None) -> bool:
    return team_id in UI_SESSION_TEAM_IDS


def ui_session_spellings(team_id: str) -> tuple[str, ...]:
    """Both spellings when the id names the dashboard's session team, otherwise the one given.

    Lets a filter that excludes a single team keep its signature while still excluding sessions minted
    before the rename.
    """
    return UI_SESSION_TEAM_IDS if team_id in UI_SESSION_TEAM_IDS else (team_id,)
