"""
Pedal Glue App - Bridge between hardware controllers and Sushi audio engine.

This application subscribes to gRPC events from hardware controllers and
routes them to Sushi parameters based on user-defined mappings.
"""

import asyncio
import logging
import signal
import sys

from .sensei_client import SenseiClient
from .sushi_client import MappingError, SushiClient
from .mappings import MappingManager

DEFAULT_SUSHI_ADDRESS = 'localhost:51051'
if sys.platform == 'win32':
    DEFAULT_SUSHI_ADDRESS = 'localhost:510'


class ShutdownSignalException(Exception):
    """Exception raised by the shutdown signal monitoring Task"""
    pass


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class GlueApp:
    def __init__(
        self,
        mappings: list | None = None,
        sensei_address: str = "localhost:50051",
        sushi_address: str = DEFAULT_SUSHI_ADDRESS,
        log_level: int = logging.INFO,
    ):
        """
        Initialize the Pedal Glue App.

        Args:
            mappings: List of mapping objects (PluginParameterMapping, etc.)
            sensei_address: Address of the Pin Proxy gRPC server
            sushi_address: Address of the Sushi gRPC server
            log_level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        self.mappings = mappings or []
        self.sensei_address = sensei_address
        self.sushi_address = sushi_address

        setup_logging(log_level)
        self.logger = logging.getLogger('APP')
        self._shutdown_event = asyncio.Event()

        # Check if mappings are defined
        if not self.mappings:
            self.logger.warning(
                "No mappings defined. "
                "The app will run but won't control any parameters."
            )

        # Initialize clients (but don't connect yet)
        self.sensei_client = SenseiClient(self.sensei_address)
        self.mapping_manager = MappingManager()
        self.sushi_client = SushiClient(self.sushi_address)

    def _setup_signal_handlers(self):
        """Setup asyncio-compatible signal handlers."""
        loop = asyncio.get_running_loop()

        def signal_handler():
            self.logger.info("Shutdown signal received, stopping...")
            self._shutdown_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    async def initialize(self) -> bool:
        """
        Initialize connections to Sensei and Sushi.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        self.logger.info("Starting Pedal Glue App")

        # Connect to Sensei client with retry
        self.logger.info("Initializing Sensei client")
        await self.sensei_client.connect()

        # Get controller name->ID mapping with retry
        self.logger.info("Fetching controller states")
        while not self._shutdown_event.is_set():
            try:
                await self.sensei_client.get_controller_map()
                break
            except Exception:
                self.logger.info("Pin proxy unavailable. Retrying in 5s...")
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=5.0
                    )
                    return False  # Shutdown requested during retry
                except asyncio.TimeoutError:
                    pass  # Continue retry

        # Connect to Sushi client
        self.logger.info("Initializing Sushi client")
        if not await self.sushi_client.connect():
            self.logger.error("Sushi does not seem to be running. Exiting now.")
            return False

        # Initialize mappings with Sushi
        if self.mappings:
            try:
                self.logger.info("Initializing mappings")
                await self.mapping_manager.initialize_mappings(self.mappings)
                self.mapping_manager.register_mappings(self.mappings)
            except MappingError:
                self.logger.error("Mapping initialization failed.")
                return False

        return True

    async def run(self) -> int:
        """
        Run the application with async event loop and TaskGroup.

        Returns:
            Exit code (0 for success, 1 for failure).
        """
        self._setup_signal_handlers()

        try:
            # Run concurrent tasks
            self.sensei_client._streaming = True
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.sensei_client.stream_events())
                tg.create_task(self._wait_for_shutdown())
        except* Exception as eg:
            # TaskGroup wraps exceptions in ExceptionGroup
            for exc in eg.exceptions:
                self.logger.error(f"Task error: {exc}", exc_info=exc)
        finally:
            await self.stop()

        return 0

    async def _wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
        self.logger.info("Shutdown event triggered")
        raise ShutdownSignalException

    async def stop(self) -> None:
        """Cleanup connections."""
        self.logger.info("Cleaning up connections")
        if self.sensei_client:
            await self.sensei_client.disconnect()
        if self.sushi_client:
            self.sushi_client.disconnect()
        self.logger.info("Shutdown complete")


if __name__ == "__main__":
    app = GlueApp()
    sys.exit(app.run())
