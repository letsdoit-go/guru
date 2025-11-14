"""
Sushi client wrapper for controlling audio engine parameters via elkpy.
"""

import logging
from typing import List
from elkpy import sushicontroller as sc

from presets import Mapping


logger = logging.getLogger(__name__)


class SushiClient:
    """Wrapper for elkpy SushiController with mapping management."""

    def __init__(self, sushi_address: str = "localhost:51051"):
        """
        Initialize the Sushi client.

        Args:
            sushi_address: Address of the Sushi gRPC server (host:port)
        """
        self.sushi_address = sushi_address
        self.controller = None

    def connect(self) -> None:
        """Establish connection to Sushi."""
        logger.info(f"Connecting to Sushi at {self.sushi_address}")
        self.controller = sc.SushiController(self.sushi_address)
        logger.info("Connected to Sushi")

    def disconnect(self) -> None:
        """Close the connection to Sushi."""
        if self.controller:
            logger.info("Disconnecting from Sushi")
            self.controller = None

    def initialize_mappings(self, mappings: List[Mapping]) -> None:
        """
        Initialize all mappings by resolving track/plugin/parameter IDs.

        Args:
            mappings: List of Mapping objects to initialize

        Raises:
            RuntimeError: If not connected to Sushi
            Exception: If any mapping fails to initialize (invalid track/plugin/parameter names)
        """
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        logger.info(f"Initializing {len(mappings)} mappings")
        for i, mapping in enumerate(mappings):
            try:
                mapping.init(self.controller)
                logger.info(
                    f"Mapping {i+1}: {mapping.controller_name} -> "
                    f"{mapping.track_name}/{mapping.plugin_name}/{mapping.parameter_name}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize mapping {i+1}: {e}")
                raise

        logger.info("All mappings initialized successfully")

    def set_parameter_value(
        self, track_id: int, processor_id: int, parameter_id: int, value: float
    ) -> None:
        """
        Set a parameter value in Sushi.

        Args:
            track_id: ID of the track
            processor_id: ID of the processor/plugin
            parameter_id: ID of the parameter
            value: New parameter value
        """
        if not self.controller:
            raise RuntimeError("Not connected to Sushi. Call connect() first.")

        self.controller.parameters.set_parameter_value(
            processor_id, parameter_id, value
        )
        logger.debug(
            f"Set parameter: track={track_id}, processor={processor_id}, "
            f"param={parameter_id}, value={value}"
        )

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
