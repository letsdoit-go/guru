"""
Event dispatcher for routing hardware events to Sushi parameter changes.
"""

import logging
from typing import Dict, List

import pin_events_pb2
from presets import Mapping, SwitchMapping
from sushi_client import SushiClient


logger = logging.getLogger(__name__)


class EventDispatcher:
    """Dispatches hardware events to Sushi parameter updates based on mappings."""

    def __init__(self, sushi_client: SushiClient):
        """
        Initialize the event dispatcher.

        Args:
            sushi_client: Connected SushiClient instance
        """
        self.sushi_client = sushi_client
        self.mappings_by_controller_id: Dict[int, Mapping] = {}

    def register_mappings(
        self, mappings: List[Mapping], controller_name_map: Dict[str, int]
    ) -> None:
        """
        Register mappings and resolve controller names to IDs.

        Args:
            mappings: List of Mapping objects
            controller_name_map: Dictionary mapping controller names to IDs

        Raises:
            ValueError: If a controller_name is not found in the map
        """
        logger.info(f"Registering {len(mappings)} mappings")

        for mapping in mappings:
            controller_id = controller_name_map.get(mapping.controller_name)
            if controller_id is None:
                raise ValueError(
                    f"Controller '{mapping.controller_name}' not found in available controllers. "
                    f"Available: {list(controller_name_map.keys())}"
                )

            self.mappings_by_controller_id[controller_id] = mapping
            logger.info(
                f"Registered: controller '{mapping.controller_name}' (ID {controller_id}) -> "
                f"{mapping.track_name}/{mapping.plugin_name}/{mapping.parameter_name}"
            )

        logger.info("All mappings registered successfully")

