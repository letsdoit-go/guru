"""
User configuration file for mapping hardware controllers to Sushi parameters.

Define your mappings here using the Mapping and SwitchMapping classes from presets.py.
The controller_name should match the name field from PotState or SwitchState
returned by RefreshAllStates().
"""

from typing import Callable
from elkpy.sushicontroller import SushiController
import pin_events_pb2
import observer
import logging

logger = logging.getLogger(__name__)


class Control:
    def __init__(self, controller_name: str, cb: Callable | None):
        self.controller_name = controller_name
        self.callback = cb

    def init(self, sc) -> None: ...


class TrackParameterMapping:
    def __init__(
        self,
        track_name: str,
        parameter_name: str,
        controller_name: str,
        preprocessor: Callable | None = None,
    ) -> None:
        self.track_name = track_name
        self.parameter_name = parameter_name
        self.controller_name = controller_name
        self.preprocessor = preprocessor

    def init(self, sc: SushiController) -> None:
        self.track_id = sc.audio_graph.get_track_id(self.track_name)
        self.param_id = sc.parameters.get_parameter_id(
            self.track_id, self.parameter_name
        )


class PluginParameterMapping:
    def __init__(
        self,
        track_name: str,
        plugin_name: str | None,
        parameter_name: str,
        controller_name: str | None = None,
        preprocessor: Callable | None = None,
    ):
        self.track_name = track_name
        self.plugin_name = plugin_name
        self.parameter_name = parameter_name
        self.controller_name = controller_name
        self.preprocessor = preprocessor

    def init(self, sc: SushiController) -> None:
        self.track_id = sc.audio_graph.get_track_id(self.track_name)
        self.plugin_id = sc.audio_graph.get_processor_id(self.plugin_name)
        self.param_id = sc.parameters.get_parameter_id(
            self.plugin_id, self.parameter_name
        )


class SwitchMapping(PluginParameterMapping):
    def __init__(
        self,
        track_name: str,
        plugin_name: str,
        parameter_name: str,
        controller_name: str,
        pressed_value: float,
        released_value: float,
        preprocessor: Callable | None = None,
    ):
        super().__init__(
            track_name, plugin_name, parameter_name, controller_name, preprocessor
        )
        self.pressed_value = pressed_value
        self.released_value = released_value


class MappingManager:
    """This class consumes UiEvents and maps them to Sushi controls or other internal settings."""

    def __init__(self) -> None:
        observer.subscribe(event="UiEvent", cb=self._dispatch_ui_event)
        observer.subscribe(event="NEW_CTRL_MAP", cb=self._update_controller_map)
        observer.subscribe(
            event="MAPPINGS_INITIALIZED", cb=self._handle_mappings_initialized
        )
        self._mappings_initialized: bool = False
        self.mappings_by_controller_id: dict[int, PluginParameterMapping] = {}
        self.controller_map = None

    def initialize_mappings(self, mappings: list) -> None:
        map = [m for m in mappings if not isinstance(m, Control)]
        if map == []:
            logger.warning("There are no mappings specified.")
        observer.emit(signal="INIT_MAPPING", mappings=map)

    def _update_controller_map(self, controller_map):
        self.controller_map = controller_map
        logger.debug("Updated contoller map")

    def _handle_mappings_initialized(self):
        self._mappings_initialized = True

    def register_mappings(self, mappings: list[PluginParameterMapping]) -> bool:
        """
        Register mappings and resolve controller names to IDs.

        Args:
            mappings: List of Mapping objects
            controller_name_map: Dictionary mapping controller names to IDs

        Raises:
            ValueError: If a controller_name is not found in the map
        """
        if not self.controller_map:
            logger.error("Controller map not yet initialized!")
            return False

        logger.info(f"Registering {len(mappings)} mappings")

        for mapping in mappings:
            controller_id = self.controller_map.get(mapping.controller_name)
            if controller_id is None:
                raise ValueError(
                    f"Controller '{mapping.controller_name}' not found in available controllers. "
                    f"Available: {list(self.controller_map.keys())}"
                )

            self.mappings_by_controller_id[controller_id] = mapping
            if not isinstance(mapping, Control):
                logger.info(
                    f"Registered: controller '{mapping.controller_name}' (ID {controller_id}) -> "
                    f"{mapping.track_name}/{getattr(mapping, 'plugin_name', '-')}/{mapping.parameter_name}"
                )
            else:
                logger.info(
                    f"Registered: controller '{mapping.controller_name}' -> Control -> cb = {mapping.callback}"
                )

        logger.info("All mappings registered successfully")
        return True

    def _dispatch_ui_event(self, event: pin_events_pb2.Event) -> None:
        """
        Process an incoming event and route it to the appropriate Sushi parameter.

        Args:
            event: Event message from Pin Proxy
        """
        event_type = event.WhichOneof("event")

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
        if isinstance(mapping, Control):
            self._handle_control_event(mapping, event)
            return

        # Apply preprocessor if defined
        value = event.value
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        logger.debug(
            f"Analog event: controller={event.controller_id}, "
            f"value={event.value} -> {value}"
        )

        if isinstance(mapping, PluginParameterMapping):
            self._emit_sushi_plugin_event(
                track_id=mapping.track_id,
                plugin_id=mapping.plugin_id,
                param_id=mapping.param_id,
                value=value,
            )
        elif isinstance(mapping, TrackParameterMapping):
            self._emit_sushi_track_event(
                track_id=mapping.track_id,
                param_id=mapping.param_id,
                value=value,
            )

    def _handle_toggle_event(self, event: pin_events_pb2.ToggleEvent) -> None:
        """Handle toggle/switch events."""
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"No mapping for controller ID {event.controller_id}")
            return

        if isinstance(mapping, Control):
            self._handle_control_event(mapping, event)
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

        self._emit_sushi_plugin_event(
            track_id=mapping.track_id,
            plugin_id=mapping.plugin_id,
            param_id=mapping.param_id,
            value=value,
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
        if isinstance(mapping, Control):
            self._handle_control_event(mapping, event)
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
        if isinstance(mapping, Control):
            self._handle_control_event(mapping, event)
            return

        # Basic implementation: use the range value directly
        value = float(event.value)

        # Apply preprocessor if defined
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        self._emit_sushi_plugin_event(
            track_id=mapping.track_id,
            plugin_id=mapping.plugin_id,
            param_id=mapping.param_id,
            value=value,
        )

        logger.debug(
            f"Range event: controller={event.controller_id}, "
            f"range={event.value} -> {value}"
        )

    def _handle_control_event(self, mapping, event) -> None:
        logger.debug(f"Received Control event: {event} -> cb: {mapping.callback}")
        # TODO: implementation

    def _emit_sushi_plugin_event(
        self, track_id: int, plugin_id: int, param_id: int, value: float
    ) -> None:
        # Send to Sushi
        observer.emit(
            "SushiPluginEvent",
            {
                "track_id": track_id,
                "plugin_id": plugin_id,
                "param_id": param_id,
                "value": value,
            },
        )

    def _emit_sushi_track_event(
        self, track_id: int, param_id: int, value: float
    ) -> None:
        # Send to Sushi
        observer.emit(
            "SushiTrackEvent",
            {
                "track_id": track_id,
                "param_id": param_id,
                "value": value,
            },
        )

# Example mappings - replace with your actual configuration
# MAPPINGS = []
MAPPINGS = [
    # Example: Map a pot to a plugin parameter
    PluginParameterMapping(
        track_name="main",
        plugin_name="gain",
        parameter_name="gain",
        controller_name="POT1",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    TrackParameterMapping(
        track_name="main",
        parameter_name="gain",
        controller_name="POT2",
        preprocessor=lambda x: x * x
    ),
    Control(controller_name="SW1", cb=None),
]


