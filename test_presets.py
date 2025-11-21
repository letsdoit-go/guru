"""
Unit tests for presets.py (Mapping, SwitchMapping, Control, Preset classes).

Tests focus on initialization and ID resolution with mocked SushiController.
"""

import pytest
from unittest.mock import MagicMock, Mock


class TestMapping:
    """Tests for the Mapping class."""

    def test_mapping_initialization(self):
        """Test that Mapping initializes with correct attributes."""
        from presets import PluginParameterMapping

        preprocessor = lambda x: x * 2
        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name="POT1",
            preprocessor=preprocessor,
        )

        assert mapping.track_name == "main"
        assert mapping.plugin_name == "gain"
        assert mapping.parameter_name == "volume"
        assert mapping.controller_name == "POT1"
        assert mapping.preprocessor == preprocessor

    def test_mapping_initialization_without_preprocessor(self):
        """Test that Mapping can be initialized without preprocessor."""
        from presets import PluginParameterMapping

        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name="POT1",
        )

        assert mapping.preprocessor is None

    def test_mapping_init_resolves_ids(self):
        """Test that init() resolves track/plugin/parameter names to IDs."""
        from presets import PluginParameterMapping

        # Create mock SushiController
        mock_sc = MagicMock()
        mock_sc.audio_graph.get_track_id.return_value = 10
        mock_sc.audio_graph.get_processor_id.return_value = 20
        mock_sc.parameters.get_parameter_id.return_value = 30

        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name="POT1",
        )

        # Call init to resolve IDs
        mapping.init(mock_sc)

        # Verify IDs were resolved
        assert mapping.track_id == 10
        assert mapping.plugin_id == 20
        assert mapping.param_id == 30

        # Verify correct methods were called
        mock_sc.audio_graph.get_track_id.assert_called_once_with("main")
        mock_sc.audio_graph.get_processor_id.assert_called_once_with("gain")
        mock_sc.parameters.get_parameter_id.assert_called_once_with(20, "volume")

    def test_mapping_preprocessor_is_callable(self):
        """Test that preprocessor function works correctly."""
        from presets import PluginParameterMapping

        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name="POT1",
            preprocessor=lambda x: x * 100,
        )

        # Test preprocessor
        assert mapping.preprocessor(0.5) == 50.0
        assert mapping.preprocessor(1.0) == 100.0


class TestSwitchMapping:
    """Tests for the SwitchMapping class."""

    def test_switch_mapping_initialization(self):
        """Test that SwitchMapping initializes with correct attributes."""
        from presets import SwitchMapping

        preprocessor = lambda x: x
        mapping = SwitchMapping(
            track_name="main",
            plugin_name="reverb",
            parameter_name="bypass",
            controller_name="SW1",
            pressed_value=1.0,
            released_value=0.0,
            preprocessor=preprocessor,
        )

        # Check base Mapping attributes
        assert mapping.track_name == "main"
        assert mapping.plugin_name == "reverb"
        assert mapping.parameter_name == "bypass"
        assert mapping.controller_name == "SW1"
        assert mapping.preprocessor == preprocessor

        # Check SwitchMapping-specific attributes
        assert mapping.pressed_value == 1.0
        assert mapping.released_value == 0.0

    def test_switch_mapping_inherits_from_mapping(self):
        """Test that SwitchMapping is a subclass of Mapping."""
        from presets import SwitchMapping, PluginParameterMapping

        assert issubclass(SwitchMapping, PluginParameterMapping)

    def test_switch_mapping_init_resolves_ids(self):
        """Test that init() resolves IDs correctly for SwitchMapping."""
        from presets import SwitchMapping

        # Create mock SushiController
        mock_sc = MagicMock()
        mock_sc.audio_graph.get_track_id.return_value = 15
        mock_sc.audio_graph.get_processor_id.return_value = 25
        mock_sc.parameters.get_parameter_id.return_value = 35

        mapping = SwitchMapping(
            track_name="guitar",
            plugin_name="distortion",
            parameter_name="bypass",
            controller_name="SW2",
            pressed_value=1.0,
            released_value=0.0,
        )

        # Call init to resolve IDs
        mapping.init(mock_sc)

        # Verify IDs were resolved
        assert mapping.track_id == 15
        assert mapping.plugin_id == 25
        assert mapping.param_id == 35

    def test_switch_mapping_without_preprocessor(self):
        """Test that SwitchMapping works without preprocessor."""
        from presets import SwitchMapping

        mapping = SwitchMapping(
            track_name="main",
            plugin_name="reverb",
            parameter_name="bypass",
            controller_name="SW1",
            pressed_value=1.0,
            released_value=0.0,
        )

        assert mapping.preprocessor is None


class TestControl:
    """Tests for the Control class."""

    def test_control_initialization(self):
        """Test that Control initializes with correct attributes."""
        from presets import Control

        callback = lambda x: print(x)
        control = Control()
        control.controller_name = "SW1"
        control.callback = callback

        assert control.controller_name == "SW1"
        assert control.callback == callback

    def test_control_callback_is_callable(self):
        """Test that Control callback can be invoked."""
        from presets import Control

        mock_callback = MagicMock()
        control = Control()
        control.callback = mock_callback

        # Call the callback
        control.callback("test_event")

        # Verify it was called
        mock_callback.assert_called_once_with("test_event")

    def test_control_init_method_exists(self):
        """Test that Control has an init method."""
        from presets import Control

        control = Control()
        mock_sc = MagicMock()

        # Should not raise
        control.init(mock_sc)


class TestPreset:
    """Tests for the Preset class."""

    def test_preset_initialization_with_defaults(self):
        """Test that Preset initializes with default empty lists."""
        from presets import Preset

        preset = Preset(name="Clean")

        assert preset.name == "Clean"
        assert preset.initial_state == []
        assert preset.mappings == []

    def test_preset_initialization_with_data(self):
        """Test that Preset initializes with provided data."""
        from presets import Preset, PluginParameterMapping

        mapping1 = PluginParameterMapping("main", "gain", "volume", "POT1")
        mapping2 = PluginParameterMapping("main", "eq", "bass", "POT2")
        initial_state = [{"param": "value1"}, {"param": "value2"}]

        preset = Preset(
            name="Rock", initial_state=initial_state, mappings=[mapping1, mapping2]
        )

        assert preset.name == "Rock"
        assert preset.initial_state == initial_state
        assert len(preset.mappings) == 2
        assert preset.mappings[0] == mapping1
        assert preset.mappings[1] == mapping2

    def test_preset_add_mapping(self):
        """Test that add_mapping() adds a mapping to the preset."""
        from presets import Preset, PluginParameterMapping

        preset = Preset(name="Blues")
        mapping = PluginParameterMapping("main", "reverb", "mix", "POT3")

        preset.add_mapping(mapping)

        assert len(preset.mappings) == 1
        assert preset.mappings[0] == mapping

    def test_preset_add_multiple_mappings(self):
        """Test that multiple mappings can be added."""
        from presets import Preset, PluginParameterMapping, SwitchMapping

        preset = Preset(name="Jazz")
        mapping1 = PluginParameterMapping("main", "compressor", "threshold", "POT1")
        mapping2 = SwitchMapping(
            "main", "chorus", "bypass", "SW1", pressed_value=1.0, released_value=0.0
        )

        preset.add_mapping(mapping1)
        preset.add_mapping(mapping2)

        assert len(preset.mappings) == 2
        assert preset.mappings[0] == mapping1
        assert preset.mappings[1] == mapping2


class TestMappingIntegration:
    """Integration tests for mapping workflows."""

    def test_mapping_workflow_with_preprocessor(self):
        """Test complete mapping workflow with preprocessing."""
        from presets import PluginParameterMapping

        # Create mapping with preprocessor that scales 0-1 to 0-100
        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name="POT1",
            preprocessor=lambda x: x * 100,
        )

        # Mock SushiController
        mock_sc = MagicMock()
        mock_sc.audio_graph.get_track_id.return_value = 1
        mock_sc.audio_graph.get_processor_id.return_value = 2
        mock_sc.parameters.get_parameter_id.return_value = 3

        # Initialize mapping
        mapping.init(mock_sc)

        # Verify IDs are set
        assert mapping.track_id == 1
        assert mapping.plugin_id == 2
        assert mapping.param_id == 3

        # Test preprocessor
        raw_value = 0.75
        processed_value = mapping.preprocessor(raw_value)
        assert processed_value == 75.0

    def test_switch_mapping_workflow(self):
        """Test complete switch mapping workflow."""
        from presets import SwitchMapping

        # Create switch mapping for bypass
        mapping = SwitchMapping(
            track_name="guitar",
            plugin_name="delay",
            parameter_name="bypass",
            controller_name="SW_DELAY",
            pressed_value=1.0,
            released_value=0.0,
        )

        # Mock SushiController
        mock_sc = MagicMock()
        mock_sc.audio_graph.get_track_id.return_value = 10
        mock_sc.audio_graph.get_processor_id.return_value = 20
        mock_sc.parameters.get_parameter_id.return_value = 30

        # Initialize mapping
        mapping.init(mock_sc)

        # Verify IDs and values
        assert mapping.track_id == 10
        assert mapping.plugin_id == 20
        assert mapping.param_id == 30
        assert mapping.pressed_value == 1.0
        assert mapping.released_value == 0.0

    @pytest.mark.parametrize(
        "controller_name,expected",
        [
            ("POT1", "POT1"),
            ("SW_MASTER", "SW_MASTER"),
            ("ENC_TEMPO", "ENC_TEMPO"),
        ],
    )
    def test_mapping_with_various_controller_names(self, controller_name, expected):
        """Test that mappings work with various controller name formats."""
        from presets import PluginParameterMapping

        mapping = PluginParameterMapping(
            track_name="main",
            plugin_name="gain",
            parameter_name="volume",
            controller_name=controller_name,
        )

        assert mapping.controller_name == expected
