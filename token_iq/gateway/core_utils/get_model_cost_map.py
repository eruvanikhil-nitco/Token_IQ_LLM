"""The cost, context window and provider route for every model Token IQ can price.

Read from the file bundled with this package and from nowhere else. Nothing is fetched at
runtime, so an installation behind a firewall prices exactly as one with open egress does.

A stale price is the failure this guards against, and it is a silent one: nothing crashes,
no test goes red, the ledger keeps reconciling, and every figure the product reports is
wrong for any model whose price moved. Freshness is therefore a build-time concern, handled
by the daily update job in `scripts/update_model_prices.py`, which proposes upstream's
changes as a reviewed pull request rather than letting a running process decide.
"""

import json
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from token_iq.gateway import verbose_logger
from token_iq.gateway.constants import (
    MODEL_COST_MAP_MAX_SHRINK_RATIO,
    MODEL_COST_MAP_MIN_MODEL_COUNT,
)
from token_iq.gateway.core_utils.fallback_generalizations import (
    set_fallback_generalizations,
)

FALLBACK_GENERALIZATIONS_KEY: Final = "fallback_generalizations"

def _repo_root() -> pathlib.Path:
    """The directory holding the `token_iq` package, found by name rather than by counting parents.

    This used to count: `parents[2]` was the repository root while this module lived two directories
    down. Moving the engine into `token_iq/gateway/` made it three, and the only sign was the proxy
    failing to start on a missing price file. Looking the package up by name cannot go stale the next
    time something moves.
    """
    here: Final = pathlib.Path(__file__).resolve()
    package: Final = next((parent for parent in here.parents if parent.name == "token_iq"), None)
    return package.parent if package is not None else here.parents[2]


# The single source of prices. One copy on purpose: there were two byte-identical 2.1MB
# files kept in step by convention, and two copies of anything eventually disagree.
PRICES_PATH: Final = _repo_root() / "data" / "pricing" / "model_prices.json"


def load_bundled_prices() -> dict:
    """The bundled price list, as written. No network, no fallback, no second copy."""
    return json.loads(PRICES_PATH.read_text(encoding="utf-8"))

# Reserved top-level keys that are not model entries. They must be excluded
# from the model-count integrity check so a real upstream shrink can't be masked.
RESERVED_TOP_LEVEL_KEYS: Final = frozenset({"sample_spec", FALLBACK_GENERALIZATIONS_KEY})


def _count_model_entries(model_cost: dict) -> int:
    """Count actual model entries, excluding reserved meta keys."""
    return sum(1 for key in model_cost if key not in RESERVED_TOP_LEVEL_KEYS)


class GetModelCostMap:
    """
    Handles fetching, validating, and loading the model cost map.

    Only the backup model *count* is cached (a single int). The full
    backup dict is never held in memory — it is only parsed when it
    needs to be *returned* as a fallback.
    """

    _backup_model_count: int = -1  # -1 = not yet loaded

    @staticmethod
    def load_local_model_cost_map() -> dict:
        """Kept as the name the rest of the codebase already calls. Reads the bundled file."""
        content: Final = json.loads(
            PRICES_PATH.read_text(encoding="utf-8")
        )
        return content

    @classmethod
    def _get_backup_model_count(cls) -> int:
        """Return the number of models in the local backup (cached int)."""
        if cls._backup_model_count < 0:
            backup: Final = cls.load_local_model_cost_map()
            cls._backup_model_count = _count_model_entries(backup)
        return cls._backup_model_count

    @staticmethod
    def _check_is_valid_dict(fetched_map: dict) -> bool:
        """Check 1: fetched map is a non-empty dict."""
        if not isinstance(fetched_map, dict):
            verbose_logger.warning(
                "LiteLLM: Fetched model cost map is not a dict (type=%s). Falling back to local backup.",
                type(fetched_map).__name__,
            )
            return False

        if len(fetched_map) == 0:
            verbose_logger.warning(
                "LiteLLM: Fetched model cost map is empty. Falling back to local backup.",
            )
            return False

        return True

    @classmethod
    def _check_model_count_not_reduced(
        cls,
        fetched_map: dict,
        backup_model_count: int,
        min_model_count: int = MODEL_COST_MAP_MIN_MODEL_COUNT,
        max_shrink_ratio: float = MODEL_COST_MAP_MAX_SHRINK_RATIO,
    ) -> bool:
        """Check 2: model count has not reduced significantly vs backup."""
        fetched_count: Final = _count_model_entries(fetched_map)

        if fetched_count < min_model_count:
            verbose_logger.warning(
                "LiteLLM: Fetched model cost map has only %d models (minimum=%d). "
                "This may indicate a corrupted upstream file. "
                "Falling back to local backup.",
                fetched_count,
                min_model_count,
            )
            return False

        if backup_model_count > 0 and fetched_count < backup_model_count * max_shrink_ratio:
            verbose_logger.warning(
                "LiteLLM: Fetched model cost map shrank significantly "
                "(fetched=%d, backup=%d, threshold=%.0f%%). "
                "This may indicate a corrupted upstream file. "
                "Falling back to local backup.",
                fetched_count,
                backup_model_count,
                max_shrink_ratio * 100,
            )
            return False

        return True

    @classmethod
    def validate_model_cost_map(
        cls,
        fetched_map: dict,
        backup_model_count: int,
        min_model_count: int = MODEL_COST_MAP_MIN_MODEL_COUNT,
        max_shrink_ratio: float = MODEL_COST_MAP_MAX_SHRINK_RATIO,
    ) -> bool:
        """
        Validate the integrity of a fetched model cost map.

        Runs each check in order and returns False on the first failure.

        Checks:
        1. ``_check_is_valid_dict`` -- fetched map is a non-empty dict.
        2. ``_check_model_count_not_reduced`` -- model count meets minimum
           and has not shrunk >``max_shrink_ratio`` vs backup.

        Returns True if all checks pass, False otherwise.
        """
        if not cls._check_is_valid_dict(fetched_map):
            return False

        if not cls._check_model_count_not_reduced(
            fetched_map=fetched_map,
            backup_model_count=backup_model_count,
            min_model_count=min_model_count,
            max_shrink_ratio=max_shrink_ratio,
        ):
            return False

        return True


@dataclass(frozen=True, slots=True)
class ModelCostMapReloaded:
    model_cost_map: dict  # mutable-ok: adopted as litellm.model_cost, whose consumer contract is a plain mutable dict


@dataclass(frozen=True, slots=True)
class ModelCostMapReloadUnavailable:
    reason: str


ModelCostMapReloadResult = ModelCostMapReloaded | ModelCostMapReloadUnavailable


async def refetch_model_cost_map() -> ModelCostMapReloadResult:
    """Re-read the bundled price file.

    Kept for the admin reload endpoints, whose purpose changes rather than disappearing:
    they used to pull a fresh copy from upstream, and now they pick up a file that a deploy
    swapped underneath a running process. There is nothing to fetch and nothing to fall back
    to, so the only failure left is a file that will not parse.
    """
    try:
        return ModelCostMapReloaded(model_cost_map=_finalize_model_cost_map(load_bundled_prices()))
    except (OSError, json.JSONDecodeError) as error:
        return ModelCostMapReloadUnavailable(reason=f"bundled price file could not be read: {error}")

class ModelCostMapSourceInfo:
    """Where the price list in this process came from."""

    source: str = "bundled"
    url: str | None = None
    is_env_forced: bool = False
    fallback_reason: str | None = None
    loaded_at: "datetime | None" = None


_cost_map_source_info: Final = ModelCostMapSourceInfo()


def get_model_cost_map_source_info() -> dict:
    """
    Return metadata about where the current model cost map was loaded from.

    Returns a dict with:
    - source: always "bundled"
    - url, is_env_forced, fallback_reason: retained so the admin endpoint's response shape
      does not change; there is no remote source left for them to describe
    """
    return {
        "source": _cost_map_source_info.source,
        "url": _cost_map_source_info.url,
        "is_env_forced": _cost_map_source_info.is_env_forced,
        "fallback_reason": _cost_map_source_info.fallback_reason,
    }


def get_model_cost_map_loaded_at() -> "datetime | None":
    """When this process last loaded its cost map, stamped at the start of every load"""
    return _cost_map_source_info.loaded_at


def _expand_model_aliases(model_cost: dict) -> dict:
    """
    Expand ``aliases`` lists in model cost entries into top-level entries.

    Each alias gets a reference to the **same** dict object as the canonical
    entry (zero memory overhead).  The ``aliases`` key is removed from the
    entry so downstream code never sees it.

    If an alias collides with an existing canonical entry the alias is
    skipped and a warning is logged.
    """
    aliases_to_add: Final[dict[str, dict]] = {}
    keys_with_aliases: Final[list[str]] = []

    for model_name, model_info in model_cost.items():
        aliases: list | None = model_info.get("aliases")
        if aliases is None:
            continue
        keys_with_aliases.append(model_name)
        if not isinstance(aliases, list):
            verbose_logger.warning(
                "LiteLLM model alias field for '%s' is not a list (got %s) — skipping.",
                model_name,
                type(aliases).__name__,
            )
            continue
        if not aliases:
            continue
        for alias in aliases:
            if alias in model_cost:
                verbose_logger.warning(
                    "LiteLLM model alias conflict: alias '%s' (from '%s') "
                    "already exists as a canonical entry — skipping.",
                    alias,
                    model_name,
                )
                continue
            if alias in aliases_to_add:
                verbose_logger.warning(
                    "LiteLLM model alias conflict: alias '%s' (from '%s') "
                    "was already claimed by another entry — skipping.",
                    alias,
                    model_name,
                )
                continue
            aliases_to_add[alias] = model_info  # same dict reference

    # Remove the ``aliases`` key from entries so it doesn't pollute model info
    for key in keys_with_aliases:
        model_cost[key].pop("aliases", None)

    model_cost.update(aliases_to_add)
    return model_cost


def _finalize_model_cost_map(model_cost: dict) -> dict:
    """Extract fallback generalizations out of the raw map, then expand aliases.

    The ``fallback_generalizations`` block is installed into the generalizations
    module and removed from the map so it is never treated as a model entry.
    """
    raw: Final = model_cost.pop(FALLBACK_GENERALIZATIONS_KEY, None)
    rules: Final = raw.get("rules") if isinstance(raw, dict) else None
    set_fallback_generalizations(rules)
    return _expand_model_aliases(model_cost)


def get_model_cost_map() -> dict:
    """The price list this process will use.

    Reads the bundled file and nothing else. There is no url, no retry and no fallback,
    because there is only one source and it ships with the code.
    """
    _cost_map_source_info.loaded_at = datetime.now(timezone.utc)
    _cost_map_source_info.source = "bundled"
    _cost_map_source_info.url = None
    _cost_map_source_info.is_env_forced = False
    _cost_map_source_info.fallback_reason = None
    return _finalize_model_cost_map(load_bundled_prices())

