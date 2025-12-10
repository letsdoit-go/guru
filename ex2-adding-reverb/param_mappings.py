from glue_app.mappings import PluginParameterMapping, BypassMapping


MAPPINGS = [
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Guvnor",
        parameter_name="GAIN",
        controller_name="POT1",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Guvnor",
        parameter_name="BASS",
        controller_name="POT2",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Guvnor",
        parameter_name="MID",
        controller_name="POT3",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Guvnor",
        parameter_name="TREBLE",
        controller_name="POT4",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Guvnor",
        parameter_name="LEVEL",
        controller_name="POT5",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    BypassMapping(plugin_name="Guvnor", controller_name="SW2"),
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="Send_rev",
        parameter_name="gain",
        controller_name="POT6",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
    PluginParameterMapping(
        track_name="AUX",
        plugin_name="Reverb",
        parameter_name="room_size",
        controller_name="POT7",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    ),
]
