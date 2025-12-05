from typing import Mapping
from glue_app.mappings import PluginParameterMapping, BypassMapping


MAPPINGS = [
    # Example: Map a pot to a plugin parameter
    PluginParameterMapping(
        track_name="TRACK",
        plugin_name="gain",
        parameter_name="gain",
        controller_name="POT1",
        preprocessor=lambda x: x,  # Optional: transform 0-1 to 0-100
    )
]

