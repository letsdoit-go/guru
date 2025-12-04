import sys
import logging
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from glue_app.app import GlueApp
from param_mappings import MAPPINGS


app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)

app.run()

