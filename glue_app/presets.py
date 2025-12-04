"""
Preset management system for the topo-pedal controller.

This module handles loading, switching, and managing audio effect presets,
including parameter mappings and plugin bypass states.
"""

from typing import Optional, Any
import logging
import time

from elkpy.sushicontroller import SushiController

from . import observer
from .mappings import TrackParameterMapping, PluginParameterMapping

PRESET_LOADING_MIN_WAIT_S = 2


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
        self.parameter_states: list = []
        self.bypass_states: list = []


    def add_mapping(self, mapping: TrackParameterMapping | PluginParameterMapping) -> None:
        self.mappings.append(mapping)

    def init(self, sc: SushiController) -> None:
        for state in self.initial_state:
            proc_id = sc.audio_graph.get_processor_id(state["processor"])
            for param_name, value in state["parameters"].items():
                param_id = sc.parameters.get_parameter_id(proc_id, param_name)
                self.parameter_states.append((proc_id, param_id, value))
            if "bypassed" in state.keys():
                self.bypass_states.append((proc_id, state["bypassed"]))

    def __repr__(self) -> str:
        return f"{self.name}: {self.initial_state} => {'Initialized' if self.parameter_states else 'Not Initialized'}" 



class PresetManager:
    """
    Manages audio effect presets and handles dynamic switching.

    Coordinates with the Sushi audio host to apply preset configurations
    including plugin bypass states and parameter mappings.
    """

    def __init__(self) -> None:
        """
        Initialize preset manager.

        Args:
            event_bus: Event bus for listening to preset switch events
            sushi_controller: Sushi controller for audio graph manipulation
        """
        self._logger = logging.getLogger(__name__)

        self.preset_list: list[Preset] = []
        self.current_preset_index: int = 0
        self.current_mappings: dict[str, TrackParameterMapping | PluginParameterMapping] = {}
        self._last_preset_loading = time.time()
        observer.subscribe('LoadPreset', self._handle_load_preset)
        observer.subscribe('LoadNextPreset', self.load_next_preset)

    def _handle_load_preset(self, preset: int) -> None:
        self.load_preset(preset)

    def add_preset(self, preset: Preset) -> None:
        """
        Add a preset to the preset list.

        Args:
            preset: Preset instance to add
        """
        self.preset_list.append(preset)
        self._logger.info(
            f"Added preset '{preset.name}' (total: {len(self.preset_list)})"
        )

    def initialize_presets(self) -> None:
        for preset in self.preset_list:
            observer.emit("InitPreset", preset)

    def remove_preset(self, index: int) -> bool:
        """
        Remove a preset by index.

        Args:
            index: Index of preset to remove

        Returns:
            True if preset was removed, False if index invalid
        """
        if 0 <= index < len(self.preset_list):
            preset = self.preset_list.pop(index)
            self._logger.info(f"Removed preset '{preset.name}'")

            # Adjust current preset index if needed
            if self.current_preset_index >= len(self.preset_list):
                self.current_preset_index = max(0, len(self.preset_list) - 1)

            return True
        else:
            self._logger.warning(f"Invalid preset index: {index}")
            return False

    def load_preset(self, index: int) -> bool:
        """
        Load a specific preset by index.

        Args:
            index: Index of preset to load

        Returns:
            True if preset loaded successfully, False otherwise
        """
        if not (0 <= index < len(self.preset_list)):
            self._logger.error(f"Invalid preset index: {index}")
            return False

        self._last_preset_loading = time.time()
        preset = self.preset_list[index]
        old_preset_name = self.get_current_preset_name()

        try:
            self._logger.info(f"Loading preset '{preset.name}' (index {index})")

            # Set plugin bypass states
            self._apply_initial_state(preset)

            # Update parameter mappings
            self._update_parameter_mappings(preset)

            # Update current preset index
            old_index = self.current_preset_index
            self.current_preset_index = index

            self._logger.info(
                f"Successfully loaded preset '{preset.name}' "
                f"(switched from '{old_preset_name}' at index {old_index})"
            )
            return True

        except Exception as e:
            self._logger.error(f"Failed to load preset '{preset.name}': {e}")
            return False

    def load_next_preset(self) -> bool:
        """
        Load the next preset in the list (cycles back to first).

        Returns:
            True if preset loaded successfully, False otherwise
        """
        if not self.preset_list:
            self._logger.warning("No presets available")
            return False

        if (time.time() - self._last_preset_loading) <= PRESET_LOADING_MIN_WAIT_S:
            self._logger.debug("Preset switch pressed - ignoring because too early")
            return False

        self._logger.debug("Preset switch pressed - switching to next preset")
        next_index = (self.current_preset_index + 1) % len(self.preset_list)
        return self.load_preset(next_index)

    def load_previous_preset(self) -> bool:
        """
        Load the previous preset in the list (cycles to last).

        Returns:
            True if preset loaded successfully, False otherwise
        """
        if not self.preset_list:
            self._logger.warning("No presets available")
            return False

        prev_index = (self.current_preset_index - 1) % len(self.preset_list)
        return self.load_preset(prev_index)

    def get_current_preset(self) -> Optional[Preset]:
        """
        Get the currently active preset.

        Returns:
            Current preset instance, or None if no presets available
        """
        if 0 <= self.current_preset_index < len(self.preset_list):
            return self.preset_list[self.current_preset_index]
        return None

    def get_current_preset_name(self) -> str:
        """
        Get the name of the currently active preset.

        Returns:
            Name of current preset, or "No preset" if none available
        """
        current = self.get_current_preset()
        return current.name if current else "No preset"

    def get_preset_names(self) -> list[str]:
        """
        Get list of all preset names.

        Returns:
            List of preset names
        """
        return [preset.name for preset in self.preset_list]

    def get_status(self) -> dict[str, Any]:
        """
        Get current status of the preset manager.

        Returns:
            Dictionary containing preset manager status
        """
        current_preset = self.get_current_preset()

        return {
            "total_presets": len(self.preset_list),
            "current_preset_index": self.current_preset_index,
            "current_preset_name": self.get_current_preset_name(),
            "preset_names": self.get_preset_names(),
            "active_mappings": len(self.current_mappings),
            "current_preset_details": {
                "active_plugins": current_preset.active_plugins
                if current_preset
                else [],
                "inactive_plugins": current_preset.inactive_plugins
                if current_preset
                else [],
                "mapping_count": len(current_preset.mappings) if current_preset else 0,
            }
            if current_preset
            else None,
        }

    def _handle_switch_event(self, event) -> None:
        """
        Handle switch press events for preset switching.

        Args:
            event: Switch pressed event
        """
        # Only respond to preset switch presses (not releases)
        if event.switch_name == "SW1" and event.pressed:
            self.load_next_preset()

    def _apply_initial_state(self, preset: Preset) -> None:
        """
        Apply plugin bypass states for the given preset.

        Args:
            preset: Preset to apply bypass states for
        """
        for state in preset.bypass_states:
            observer.emit("SetBypassStateOnPlugin", state)
        for state in preset.parameter_states:
            observer.emit("SetInitialStateOnPlugin", state)
            
    def _update_parameter_mappings(self, preset: Preset) -> None:
        """
        Update parameter mappings for the given preset.

        Args:
            preset: Preset to update mappings for
        """
        observer.emit("NewMappings", preset.mappings)
        # # Clear existing mappings
        # self.current_mappings.clear()
        #
        # # Initialize new mappings
        # for mapping in preset.mappings:
        #     try:
        #         # Initialize the mapping with Sushi controller
        #         mapping.init(sc=self.sushi_controller)
        #
        #         # Store mapping by controller name for event handling
        #         self.current_mappings[mapping.controller_name] = mapping
        #
        #         self._logger.debug(
        #             f"Initialized mapping: {mapping.controller_name} -> "
        #             f"{mapping.track_name}.{mapping.plugin_name}.{mapping.parameter_name}"
        #         )
        #
        #     except Exception as e:
        #         self._logger.error(
        #             f"Failed to initialize mapping for {mapping.controller_name}: {e}"
        #         )
        #
        # self._logger.info(
        #     f"Updated parameter mappings: {len(self.current_mappings)} active"
        # )

    def get_mapping_for_controller(
        self, controller_name: str
    ) -> None:
        """
        Get the parameter mapping for a specific controller.

        Args:
            controller_name: Name of the controller (e.g., "POT1")

        Returns:
            Mapping instance if found, None otherwise
        """
        return self.current_mappings.get(controller_name)

    def clear_presets(self) -> None:
        """Clear all presets from the manager."""
        self.preset_list.clear()
        self.current_preset_index = 0
        self.current_mappings.clear()
        self._logger.info("Cleared all presets")
