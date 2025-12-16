import sys
import logging
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from glue_app.app import GlueApp
from param_mappings import MAPPINGS
from glue_app.presets import PresetManager


app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)

# Adding a PresetManager
# Thanks to the event-signal system, that's all we need to do!
pm = PresetManager()
from sushi_presets import preset_01, preset_02, preset_03

pm.add_preset(preset_01)
pm.add_preset(preset_02)
pm.add_preset(preset_03)
pm.initialize_presets()
pm.load_preset(0)

app.run()
