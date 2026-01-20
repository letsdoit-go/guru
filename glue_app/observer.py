from typing import Callable
import logging


logger = logging.getLogger("OBSERVER")

events = {}
current_session = None


def subscribe(event: str, cb: Callable) -> None:
    if not events.get(event):
        events[event] = []
    events[event].append(cb)
    logger.debug(f"Registering subscription to {event}")


def emit(signal: str, *args, **kwargs) -> None:
    if not events.get(signal):
        return
    for cb in list(events.get(signal, [])):
        try:
            cb(*args, **kwargs)
        except Exception:
            logger.exception(f"Error in callback {cb} for signal {signal}")


def get_event_list():
    return events
