"""
Pedal Glue App - Bridge between hardware controllers and Sushi audio engine.

This application subscribes to gRPC events from hardware controllers and
routes them to Sushi parameters based on user-defined mappings.
"""

import logging
import signal
import sys
import time
from typing import Optional

from sensei_client import PinProxyClient
from sushi_client import MappingError, SushiClient
from dispatcher import EventDispatcher
from mappings import MAPPINGS, MappingManager


# Configuration
PIN_PROXY_ADDRESS = "localhost:50051"
SUSHI_ADDRESS = "localhost:51051"
LOG_LEVEL = logging.DEBUG


# Global flag for graceful shutdown
running = True


def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) for graceful shutdown."""
    global running
    logging.info("Shutdown signal received, stopping...")
    running = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """Main application entry point."""
    setup_logging(LOG_LEVEL)
    logger = logging.getLogger(__name__)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Starting Pedal Glue App")

    # Check if mappings are defined
    if not MAPPINGS:
        logger.warning(
            "No mappings defined in mappings.py. "
            "The app will run but won't control any parameters."
        )

    pin_client: Optional[PinProxyClient] = None
    sushi_client: Optional[SushiClient] = None

    try:
        # Initialize Pin Proxy client
        logger.info("Initializing Pin Proxy client")
        pin_client = PinProxyClient(PIN_PROXY_ADDRESS)
        mapping_manager = MappingManager()

        pin_client.connect()

        # Get controller name->ID mapping
        logger.info("Fetching controller states")
        while True:
            try:
                controller_map = pin_client.refresh_all_states()
                break
            except Exception:
                if not running:
                    return 1
                logger.info("Pin proxy unavailable. Retrying in 5s...")
                time.sleep(5)

        # Initialize Sushi client
        logger.info("Initializing Sushi client")
        pin_client.start()

        sushi_client = SushiClient(SUSHI_ADDRESS)
        if not sushi_client.connect():
            sys.exit(1)
        # If Sushi is unavailable, this will wait forever and retry every 5s.
        #
        # Initialize mappings with Sushi
        #
        if MAPPINGS:
            logger.info("Initializing mappings")
            mapping_manager.initialize_mappings(MAPPINGS)
            mapping_manager.register_mappings(MAPPINGS)
        #     # Create dispatcher and register mappings
        #     dispatcher = EventDispatcher(sushi_client)
        #     dispatcher.register_mappings(MAPPINGS, controller_map)
        # else:
        #     dispatcher = EventDispatcher(sushi_client)
        #     logger.info("No mappings to register")
        #
        # # Subscribe to events and start processing
        # logger.info("Starting event subscription")
        # logger.info("Press Ctrl+C to stop")
        #
        # for event in pin_client.subscribe_to_events():
        #     if not running:
        #         logger.info("Stopping event processing")
        #         break
        #
        #     # Dispatch event to Sushi
        #     dispatcher.dispatch_event(event)
        while running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except MappingError:
        logger.info("Exiting because of a fatal error.")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        logger.info("Cleaning up connections")
        if pin_client:
            pin_client.disconnect()
        if sushi_client:
            sushi_client.disconnect()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
