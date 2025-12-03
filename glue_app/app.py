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


class GlueApp:

    def __init__(self):
        """Main application entry point."""
        setup_logging(LOG_LEVEL)
        self.logger = logging.getLogger(__name__)

        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)

        self.logger.info("Starting Pedal Glue App")

        self.running = True

        # Check if mappings are defined
        if MAPPINGS == []:
            self.logger.warning(
                "No mappings defined in mappings.py. "
                "The app will run but won't control any parameters."
            )

        try:
            # Initialize Sensei client
            self.logger.info("Initializing Sensei client")
            self.sensei_client = SenseiClient(SENSEI_ADDRESS)
            self.sensei_client.connect()
            self.sensei_client.start() # Starts the listening thread

            # MappingManager must exist before SenseiClient.refresh_all_states
            self.mapping_manager = MappingManager()

            # Get controller name->ID
            self.logger.info("Fetching controller states")
            while True:
                try:
                    self.sensei_client.refresh_all_states()
                    break
                except Exception:
                    if not self.running:
                        return 1
                    self.logger.info("Pin proxy unavailable. Retrying in 5s...")
                    time.sleep(5)


            # Initialize Sushi client
            self.logger.info("Initializing Sushi client")
            self.sushi_client = SushiClient(SUSHI_ADDRESS)
            if not self.sushi_client.connect():
                self.logger.error("Sushi does not seem to be running. Exiting now.")
                sys.exit(1)

            # If the app needs to get notifications from Sushi, it should subscribe to those here.
            self.sushi_client.subscribe_to_parameter_updates()
            
            # Initialize mappings with Sushi
            if MAPPINGS:
                self.logger.info("Initializing mappings")
                self.mapping_manager.initialize_mappings(MAPPINGS)
                self.mapping_manager.register_mappings(MAPPINGS)
            # while self.running:
            #     time.sleep(1)
        except MappingError:
            self.logger.info("Exiting because of a fatal error.")
            return 0
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

        finally:
            # Cleanup
            self.logger.info("Cleaning up connections")
            if self.sensei_client:
                self.sensei_client.disconnect()
            if self.sushi_client:
                self.sushi_client.disconnect()
            self.logger.info("Shutdown complete")

        return 0

    def run(self) -> None:
        while self.running:
            time.sleep(1)

    def stop(self) -> None:
        self.running = False
        # Cleanup
        self.logger.info("Cleaning up connections")
        if self.sensei_client:
            self.sensei_client.disconnect()
        if self.sushi_client:
            self.sushi_client.disconnect()
        self.logger.info("Shutdown complete")



if __name__ == "__main__":
    app = GlueApp()
    sys.exit(app.run())
