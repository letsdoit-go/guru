from functools import partial
from glue_app.mappings import Control, PluginParameterMapping, BypassMapping
from glue_app import observer


MAPPINGS = [
    # Example: Map a pot to a plugin parameter
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
    BypassMapping(plugin_name="Guvnor", controller_name="SW1")
]

