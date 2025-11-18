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

    def dispatch_event(self, event: pin_events_pb2.Event) -> None:
        """
        Process an incoming event and route it to the appropriate Sushi parameter.

        Args:
            event: Event message from Pin Proxy
        """
        event_type = event.WhichOneof("event")
        logger.info(event)

        if event_type == "analog_ev":
            self._handle_analog_event(event.analog_ev)
        elif event_type == "toggle_ev":
            self._handle_toggle_event(event.toggle_ev)
        elif event_type == "relative_ev":
            self._handle_relative_event(event.relative_ev)
        elif event_type == "range_ev":
            self._handle_range_event(event.range_ev)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def _handle_analog_event(self, event: pin_events_pb2.AnalogEvent) -> None:
        """Handle analog controller events (pots, faders)."""
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"No mapping for controller ID {event.controller_id}")
            return

        # Apply preprocessor if defined
        value = event.value
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        # Send to Sushi
        self.sushi_client.set_parameter_value(
            mapping.track_id, mapping.plugin_id, mapping.param_id, value
        )

        logger.debug(
            f"Analog event: controller={event.controller_id}, "
            f"value={event.value} -> {value}"
        )

    def _handle_toggle_event(self, event: pin_events_pb2.ToggleEvent) -> None:
        """Handle toggle/switch events."""
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"No mapping for controller ID {event.controller_id}")
            return

        # Determine value based on switch state
        if isinstance(mapping, SwitchMapping):
            value = mapping.pressed_value if event.value else mapping.released_value
        else:
            # For regular mappings, treat as binary 1.0/0.0
            value = 1.0 if event.value else 0.0

        # Apply preprocessor if defined
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        # Send to Sushi
        self.sushi_client.set_parameter_value(
            mapping.track_id, mapping.plugin_id, mapping.param_id, value
        )

        logger.debug(
            f"Toggle event: controller={event.controller_id}, "
            f"pressed={event.value} -> {value}"
        )

    def _handle_relative_event(self, event: pin_events_pb2.RelativeEvent) -> None:
        """
        Handle relative events (encoders).

        Note: This is a basic implementation. For production use, you may want to:
        - Track current parameter values
        - Apply scaling/acceleration
        - Clamp values to parameter ranges
        """
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"No mapping for controller ID {event.controller_id}")
            return

        # For relative events, we'd need to get the current value and increment/decrement
        # This requires additional state tracking and parameter info
        logger.warning(
            f"Relative event handling not fully implemented for controller {event.controller_id}. "
            f"Delta: {event.value}"
        )

        # TODO: Implement relative value changes
        # current_value = get_current_parameter_value(...)
        # new_value = current_value + (event.value * step_size)
        # new_value = clamp(new_value, param_min, param_max)
        # self.sushi_client.set_parameter_value(...)

    def _handle_range_event(self, event: pin_events_pb2.RangeEvent) -> None:
        """
        Handle range events (discrete position controllers).

        Maps discrete range values to parameter values.
        """
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"No mapping for controller ID {event.controller_id}")
            return

        # Basic implementation: use the range value directly
        value = float(event.value)

        # Apply preprocessor if defined
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        # Send to Sushi
        self.sushi_client.set_parameter_value(
            mapping.track_id, mapping.plugin_id, mapping.param_id, value
        )

        logger.debug(
            f"Range event: controller={event.controller_id}, "
            f"range={event.value} -> {value}"
        )
