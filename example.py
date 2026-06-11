import asyncio
import logging

from guru.app import GlueApp
from example_mappings import MAPPINGS
from guru import observer


async def main():
    app = GlueApp(mappings=MAPPINGS, log_level=logging.DEBUG)

    # You MUST initialize the app first!
    await app.initialize()

    # Now you can do stuff
    await observer.emit("PrintToMockDisplay", "Hello NAMM!")

    # And finally start the event loops
    return await app.run()


if __name__ == "__main__":
    exit(asyncio.run(main()))
