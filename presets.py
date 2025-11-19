from typing import Callable
from elkpy.sushicontroller import SushiController


class Control:
    def __init__(self):
        self.controller_name: str
        self.callback: Callable

    def init(self, sc: SushiController) -> None:
        self.sc = sc


class Mapping:
    def __init__(
        self,
        track_name: str,
        plugin_name: str,
        parameter_name: str,
        controller_name: str,
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


class SwitchMapping(Mapping):
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


class Preset:
    def __init__(
        self,
        name: str,
        initial_state: list | None = None,
        mappings: list | None = None,
    ) -> None:
        self.name = name
        self.initial_state = initial_state if initial_state else []
        self.mappings = mappings if mappings else []

    def add_mapping(self, mapping: Mapping) -> None:
        self.mappings.append(mapping)
