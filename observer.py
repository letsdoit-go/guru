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
    logger.debug(f"Emitting {signal}")
    if not events.get(signal):
        events[signal] = []
        logger.warning(f"Emitting a signal with NO listeners: {signal}")
    try:
        for cb in events[signal]:
            cb(*args, **kwargs)
            logger.debug(f"Calling {cb} for signal {signal}")
    except KeyError as e:
        print(e)
        logger.info(f"No signal called {signal} exists.")


def get_event_list():
    return events
