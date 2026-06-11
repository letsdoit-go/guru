"""
Disk-backed cache for Sushi name→ID lookups (track IDs, processor IDs, parameter IDs).
These IDs are stable for a given sushi config, so we resolve once and reuse on every
subsequent startup. Delete the cache file manually when the sushi config changes.
"""

import inspect
import json
import logging
from pathlib import Path

logger = logging.getLogger("ID_CACHE")

_CACHEABLE = frozenset({"get_track_id", "get_processor_id", "get_parameter_id"})


class _Proxy:
    """Wraps one sub-controller (audio_graph or parameters) and caches whitelisted calls."""

    def __init__(self, wrapped, cache: dict):
        object.__setattr__(self, "_w", wrapped)
        object.__setattr__(self, "_c", cache)

    def __getattr__(self, name):
        attr = getattr(object.__getattribute__(self, "_w"), name)
        if name not in _CACHEABLE or not callable(attr):
            return attr
        c = object.__getattribute__(self, "_c")

        if inspect.iscoroutinefunction(attr):
            async def _cached(*args):
                key = f"{name}:{args}"
                if key in c:
                    return c[key]
                result = await attr(*args)
                c[key] = result
                return result
        else:
            def _cached(*args):
                key = f"{name}:{args}"
                if key in c:
                    return c[key]
                result = attr(*args)
                c[key] = result
                return result

        return _cached


def wrap_controller(controller, cache: dict) -> None:
    """Replace audio_graph and parameters on controller with caching proxies."""
    controller.audio_graph = _Proxy(controller.audio_graph, cache)
    controller.parameters = _Proxy(controller.parameters, cache)


def load(cache_path: Path) -> dict:
    try:
        ids = json.loads(cache_path.read_text())
        logger.info("ID cache loaded (%d entries)", len(ids))
        return ids
    except Exception:
        pass
    logger.info("ID cache cold start")
    return {}


def save(cache_path: Path, cache: dict) -> None:
    try:
        cache_path.write_text(json.dumps(cache))
        logger.info("ID cache saved (%d entries)", len(cache))
    except Exception as e:
        logger.warning("Failed to save ID cache: %s", e)
