import logging

from glue_app.app import GlueApp
from old_param_mappings import MAPPINGS
from glue_app import observer


app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)
observer.emit("DrawText", "Hello NAMM!")

app.run()
