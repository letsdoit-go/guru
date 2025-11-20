from typing import Callable
from elkpy.sushicontroller import SushiController




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
