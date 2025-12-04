from glue_app.presets import Preset
from glue_app.mappings import PluginParameterMapping, SwitchMapping


preset_01 = Preset(
    "Short",
    initial_state=[
        {
            "processor": "Reverb",
            "parameters": {
                "dry": 1.0,
                "wet": 0.1,
                "width": 0.25,
                "damp": 0.75
            },
        },
        {
            "processor": "Send_rev",
            "parameters": {
                "gain": 1.0
            }
        }
    ],
    mappings=[
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
    ],
)

preset_02 = Preset(
    "Medium",
    initial_state=[
        {
            "processor": "Reverb",
            "parameters": {
                "dry": 0.5,
                "wet": 0.15,
                "room_size": 0.5,
                "width": 0.6,
                "damp": 0.88,
            },
        }
    ],
    mappings=[
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="room_size",
            controller_name="POT2",
        ),
        SwitchMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="freeze",
            controller_name="SW2",
            pressed_value=1.0,
            released_value=0.0,
        ),
    ],
)

preset_03 = Preset(
    "Long",
    initial_state=[
        {
            "processor": "Reverb",
            "bypassed": True,
            "parameters": {
                "dry": 0.5,
                "wet": 0.6,
                "room_size": 1.0,
                "width": 1.0,
                "damp": 0.1,
            },
        },
    ],
    mappings=[
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="wet",
            controller_name="POT1",
        ),
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="room_size",
            controller_name="POT2",
        ),
        PluginParameterMapping(
            track_name="TRACK",
            plugin_name="Reverb",
            parameter_name="damp",
            controller_name="POT3",
        ),
    ],
)

