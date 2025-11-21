"""
Pedal Glue App - Bridge between hardware controllers and Sushi audio engine.

This application subscribes to gRPC events from hardware controllers and
routes them to Sushi parameters based on user-defined mappings.
"""

import logging
import signal
import sys
import time

from sensei_client import SenseiClient
from sushi_client import MappingError, SushiClient
from mappings import MAPPINGS, MappingManager


# Configuration
SENSEI_ADDRESS = "localhost:50051"
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
    if MAPPINGS == []:
        logger.warning(
            "No mappings defined in mappings.py. "
            "The app will run but won't control any parameters."
        )

    try:
        # Initialize Sensei client
        logger.info("Initializing Sensei client")
        sensei_client = SenseiClient(SENSEI_ADDRESS)
        sensei_client.connect()
        sensei_client.start() # Starts the listening thread

        # MappingManager must exist before SenseiClient.refresh_all_states
        mapping_manager = MappingManager()

        # Get controller name->ID
        logger.info("Fetching controller states")
        while True:
            try:
                sensei_client.refresh_all_states()
                break
            except Exception:
                if not running:
                    return 1
                logger.info("Pin proxy unavailable. Retrying in 5s...")
                time.sleep(5)


        # Initialize Sushi client
        logger.info("Initializing Sushi client")
        sushi_client = SushiClient(SUSHI_ADDRESS)
        if not sushi_client.connect():
            logger.error("Sushi does not seem to be running. Exiting now.")
            sys.exit(1)

        # If the app needs to get notifications from Sushi, it should subscribe to those here.
        sushi_client.subscribe_to_parameter_updates()
        
        # Initialize mappings with Sushi
        if MAPPINGS:
            logger.info("Initializing mappings")
            mapping_manager.initialize_mappings(MAPPINGS)
            mapping_manager.register_mappings(MAPPINGS)
        while running:
            time.sleep(1)
    except MappingError:
        logger.info("Exiting because of a fatal error.")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        logger.info("Cleaning up connections")
        if sensei_client:
            sensei_client.disconnect()
        if sushi_client:
            sushi_client.disconnect()
        logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
