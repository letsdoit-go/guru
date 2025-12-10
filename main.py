import logging

from glue_app.app import GlueApp
from param_mappings import MAPPINGS
from glue_app import observer


app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)
observer.emit("PrintToDisplay", 'Hello NAMM!')

app.run()

