from functools import partial
from glue_app.presets import Preset
from glue_app.mappings import PluginParameterMapping, SwitchMapping, Control
from glue_app import observer


preset_01 = Preset(
    "Short",
    initial_state=[
        {
            "processor": "Reverb",
            "parameters": {"dry": 0.0, "wet": 0.2, "width": 0.25, "damp": 0.75},
        },
        {"processor": "Send_rev", "parameters": {"gain": 1.0}},
    ],
    mappings=[
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
        Control(controller_name="SW4", cb=partial(observer.emit, "LoadNextPreset")),
    ],
)

preset_02 = Preset(
    "Medium",
    initial_state=[
        {
            "processor": "Reverb",
            "parameters": {
                "dry": 0.0,
                "wet": 0.5,
                "room_size": 0.5,
                "width": 0.6,
                "damp": 0.88,
            },
        }
    ],
    mappings=[
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="room_size",
            controller_name="POT2",
        ),
        SwitchMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="freeze",
            controller_name="SW2",
            pressed_value=1.0,
            released_value=0.0,
        ),
        Control(controller_name="SW4", cb=partial(observer.emit, "LoadNextPreset")),
    ],
)

preset_03 = Preset(
    "Long",
    initial_state=[
        {
            "processor": "Reverb",
            "bypassed": True,
            "parameters": {
                "dry": 0.0,
                "wet": 1.0,
                "room_size": 1.0,
                "width": 1.0,
                "damp": 0.1,
            },
        },
    ],
    mappings=[
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="room_size",
            controller_name="POT2",
        ),
        PluginParameterMapping(
            track_name="AUX",
            plugin_name="Reverb",
            parameter_name="damp",
            controller_name="POT3",
        ),
        Control(controller_name="SW4", cb=partial(observer.emit, "LoadNextPreset")),
    ],
)
