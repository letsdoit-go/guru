"""
User configuration file for mapping hardware controllers to Sushi parameters.

Define your mappings here using the Mapping and SwitchMapping classes from presets.py.
The controller_name should match the name field from PotState or SwitchState
returned by RefreshAllStates().
"""

from presets import Mapping, SwitchMapping

# Example mappings - replace with your actual configuration
MAPPINGS = [
    # Example: Map a pot to a plugin parameter
    # Mapping(
    #     track_name="guitar",
    #     plugin_name="distortion",
    #     parameter_name="gain",
    #     controller_name="pot_1",
    #     preprocessor=lambda x: x * 100  # Optional: transform 0-1 to 0-100
    # ),

    # Example: Map a switch to bypass parameter
    # SwitchMapping(
    #     track_name="guitar",
    #     plugin_name="reverb",
    #     parameter_name="bypass",
    #     controller_name="switch_1",
    #     pressed_value=1.0,
    #     released_value=0.0
    # ),
]
