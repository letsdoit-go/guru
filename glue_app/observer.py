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
    logger.debug(f"Registering subscription to {event}")


async def emit(signal: str, *args, **kwargs) -> None:
    if not events.get(signal):
        return
    for cb in list(events.get(signal, [])):
        try:
            if asyncio.iscoroutinefunction(cb):
                logger.debug(f"Emitting {cb} from {signal}")
                await cb(*args, **kwargs)
            else:
                logger.debug(f"Calling {cb} synchronously from {signal}")
                result = cb(*args, **kwargs)
        except Exception:
            logger.exception(f"Error in callback {cb} for signal {signal}")


def get_event_list():
    return events
