import logging

from glue_app.app import GlueApp
from param_mappings import MAPPINGS


app = GlueApp(mappings=MAPPINGS, log_level=logging.INFO)

app.run()

