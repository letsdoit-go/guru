import asyncio
import logging

from glue_app.app import GlueApp
from old_param_mappings import MAPPINGS
from glue_app import observer


async def main():
    app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)
    await observer.emit("PrintToMockDisplay", "Hello NAMM!")
    return await app.run()


if __name__ == "__main__":
    exit(asyncio.run(main()))
