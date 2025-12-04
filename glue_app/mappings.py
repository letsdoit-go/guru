"""
User configuration file for mapping hardware controllers to Sushi parameters.

Define your mappings here using the Mapping and SwitchMapping classes from presets.py.
The controller_name should match the name field from PotState or SwitchState
returned by RefreshAllStates().
"""

from typing import Callable
from elkpy.sushicontroller import SushiController
from functools import partial
import pin_events_pb2
from . import observer
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
        controller_name: str | None = None,
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

    def __repr__(self) -> str:
        return f"TrackParameterMapping: track={self.track_name}, parameter={self.parameter_name}{f', controller={self.controller_name}' if self.controller_name else ''}"


class PluginParameterMapping:
    def __init__(
        self,
        track_name: str,
        plugin_name: str,
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

    def __repr__(self) -> str:
        return f"PluginParameterMapping: plugin={self.plugin_name}, parameter={self.parameter_name}{f', controller={self.controller_name}' if self.controller_name else ''}"


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


class BypassMapping(PluginParameterMapping):
    def __init__(
        self,
        plugin_name: str,
        controller_name: str,
        preprocessor: Callable | None = None,
    ):
        self.plugin_name = plugin_name
        self.controller_name = controller_name
        self.preprocessor = preprocessor

    def init(self, sc: SushiController) -> None:
        self.plugin_id = sc.audio_graph.get_processor_id(self.plugin_name)


class ComboMapping:
    """This holds a list of Mappings"""

    def __init__(
        self,
        mappings: list[TrackParameterMapping | PluginParameterMapping | SwitchMapping],
        controller_name: str,
    ) -> None:
        self.mappings = mappings
        self.controller_name = controller_name

    def __repr__(self) -> str:
        return f"ComboMapping - [{self.mappings}]"


class MappingManager:
    """This class consumes UiEvents and maps them to Sushi controls or other internal settings."""

    def __init__(self) -> None:
        observer.subscribe(event="UiEvent", cb=self._dispatch_ui_event)
        observer.subscribe(event="NewControllerMap", cb=self._update_controller_map)
        observer.subscribe(event="NewMappings", cb=self._setup_new_mappings)
        observer.subscribe(
            event="MappingsInitialized", cb=self._handle_mappings_initialized
        )
        self._mappings_initialized: bool = False
        self.mappings_by_controller_id: dict[
            int,
            PluginParameterMapping
            | TrackParameterMapping
            | SwitchMapping
            | BypassMapping
            | Control
            | ComboMapping,
        ] = {}
        self.controller_map = None

    def initialize_mappings(self, mappings: list) -> None:
        map = [m for m in mappings if not isinstance(m, Control)]
        if map == []:
            logger.warning("There are no mappings specified.")
        observer.emit(signal="InitMapping", mappings=map)

    def _update_controller_map(self, controller_map):
        self.controller_map = controller_map
        logger.debug("Updated contoller map")

    def _handle_mappings_initialized(self):
        self._mappings_initialized = True

    def _setup_new_mappings(self, mappings: list) -> None:
        self.register_mappings(mappings)
        self.initialize_mappings(mappings)

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

        # Clearing existing mappings
        self.mappings_by_controller_id = {}

        for mapping in mappings:
            self._register_single_mapping(mapping)

        logger.info("all mappings registered successfully")
        return True

    def _register_single_mapping(
        self,
        mapping: PluginParameterMapping
        | SwitchMapping
        | TrackParameterMapping
        | Control
        | ComboMapping
        | BypassMapping,
    ) -> None:
        assert self.controller_map is not None
        controller_id = self.controller_map.get(mapping.controller_name)
        if controller_id is None:
            raise ValueError(
                f"Controller '{mapping.controller_name}' not found in available controllers. "
                f"Available: {list(self.controller_map.keys())}"
            )

        self.mappings_by_controller_id[controller_id] = mapping

        match mapping:
            case Control():
                logger.info(
                    f"Registered: controller '{mapping.controller_name}' -> control -> cb = {mapping.callback}"
                )
            case ComboMapping():
                logger.info(
                    f"Registered: controller '{mapping.controller_name}' (ID {controller_id}) -> ComboMapping: {mapping.mappings}"
                )
            case _:
                logger.info(
                    f"Registered: controller '{mapping.controller_name}' (ID {controller_id}) -> "
                    f"{getattr(mapping, 'track_name', '')}/{getattr(mapping, 'plugin_name', '-')}/{getattr(mapping, 'parameter_name', 'BYPASS')}"
                )

    def _dispatch_ui_event(self, event: pin_events_pb2.Event) -> None:
        """
        process an incoming event and route it to the appropriate sushi parameter.

        args:
            event: event message from pin proxy
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
            logger.warning(f"unknown event type: {event_type}")

    def _handle_analog_event(self, event: pin_events_pb2.AnalogEvent) -> None:
        """handle analog controller events (pots, faders)."""
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"no mapping for controller id {event.controller_id}")
            return

        match mapping:
            case Control():
                self._handle_control_event(mapping, event)
            case ComboMapping():
                for m in mapping.mappings:
                    self._create_sushi_event(event, m)
            case _:
                self._create_sushi_event(event, mapping)

    def _create_sushi_event(self, event, mapping) -> None:
        # apply preprocessor if defined
        value = event.value
        if mapping.preprocessor:
            value = mapping.preprocessor(value)

        logger.debug(
            f"analog event: controller={event.controller_id}, "
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
        """handle toggle/switch events."""
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"no mapping for controller id {event.controller_id}")
            return

        match mapping:
            case Control():
                self._handle_control_event(mapping, event)
                return
            case BypassMapping():
                self._handle_bypass_event(mapping, event)
                return
            case ComboMapping():
                for m in mapping.mappings:
                    self._create_sushi_event(event, m)
                return
            case _:
                # determine value based on switch state
                if isinstance(mapping, SwitchMapping):
                    value = (
                        mapping.pressed_value if event.value else mapping.released_value
                    )
                else:
                    # for regular mappings, treat as binary 1.0/0.0
                    value = 1.0 if event.value else 0.0

                self._create_sushi_event(event, mapping)

        logger.debug(
            f"toggle event: controller={event.controller_id}, "
            f"pressed={event.value} -> {value}"
        )

    def _handle_relative_event(self, event: pin_events_pb2.RelativeEvent) -> None:
        """
        handle relative events (encoders).

        note: this is a basic implementation. for production use, you may want to:
        - track current parameter values
        - apply scaling/acceleration
        - clamp values to parameter ranges
        """
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"no mapping for controller id {event.controller_id}")
            return

        match mapping:
            case Control():
                self._handle_control_event(mapping, event)
            case BypassMapping():
                self._handle_bypass_event(mapping, event)
        # for relative events, we'd need to get the current value and increment/decrement
        # this requires additional state tracking and parameter info
        logger.warning(
            f"relative event handling not fully implemented for controller {event.controller_id}. "
            f"delta: {event.value}"
        )

        # todo: implement relative value changes
        # current_value = get_current_parameter_value(...)
        # new_value = current_value + (event.value * step_size)
        # new_value = clamp(new_value, param_min, param_max)
        # self.sushi_client.set_parameter_value(...)

    def _handle_range_event(self, event: pin_events_pb2.RangeEvent) -> None:
        """
        handle range events (discrete position controllers).

        maps discrete range values to parameter values.
        """
        mapping = self.mappings_by_controller_id.get(event.controller_id)
        if not mapping:
            logger.debug(f"no mapping for controller id {event.controller_id}")
            return
        if isinstance(mapping, Control):
            self._handle_control_event(mapping, event)
            return

        # basic implementation: use the range value directly
        value = float(event.value)

        # apply preprocessor if defined
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
            f"Range={event.value} -> {value}"
        )

    def _handle_control_event(self, mapping, event) -> None:
        logger.debug(f"Received control event: {event} -> cb: {mapping.callback}")
        mapping.callback()

    def _handle_bypass_event(self, mapping, event) -> None:
        logger.debug(f"Toggling bypass state for plugin {mapping.controller_name}")
        self._emit_sushi_bypass_event(mapping.plugin_id)

    def _emit_sushi_plugin_event(
        self, track_id: int, plugin_id: int, param_id: int, value: float
    ) -> None:
        # send to sushi
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
        # send to sushi
        observer.emit(
            "SushiTrackEvent",
            {
                "track_id": track_id,
                "param_id": param_id,
                "value": value,
            },
        )

    def _emit_sushi_bypass_event(self, plugin_id: int) -> None:
        observer.emit("PluginBypassEvent", {"plugin_id": plugin_id})


# example mappings - replace with your actual configuration
# mappings = []
MAPPINGS = [
    # Example: Map a pot to a plugin parameter
    Control(controller_name="SW2", cb=None),
    BypassMapping(plugin_name="bitcrusher", controller_name="SW1"),
    ComboMapping(
        mappings=[
            PluginParameterMapping(
                track_name="TRACK",
                plugin_name="chorus",
                parameter_name="amount",
                preprocessor=lambda x: 0.2 + x * 0.6,
            ),
            PluginParameterMapping(
                track_name="TRACK", plugin_name="bitcrusher", parameter_name="sr_ratio"
            ),
            PluginParameterMapping(
                track_name="TRACK",
                plugin_name="tremolo",
                parameter_name="rate",
                preprocessor=lambda x: 0.1 + x * 0.8,
            ),
        ],
        controller_name="POT1",
    ),
]
