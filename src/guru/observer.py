from typing import Callable, Coroutine
import asyncio
import logging


logger = logging.getLogger("OBSERVER")

events = {}
current_session = None


def subscribe(event: str, cb: Callable | Coroutine) -> None:
    if not events.get(event):
        events[event] = []
    events[event].append(cb)
    logger.debug("Registering subscription to %s", event)


async def emit(signal: str, *args, **kwargs) -> None:
    if not events.get(signal):
        logger.debug("Emitting signal with no listeners: %s", signal)
        return
    for cb in list(events.get(signal, [])):
        try:
            if asyncio.iscoroutinefunction(cb):
                logger.debug("Emitting %s from %s", cb, signal)
                await cb(*args, **kwargs)
            else:
                logger.debug("Calling %s synchronously from %s", cb, signal)
                result = cb(*args, **kwargs)
        except Exception:
            logger.exception(f"Error in callback {cb} for signal {signal}")


def get_event_list():
    return events
