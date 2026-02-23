try:
    from luma.core.interface.serial import spi
    from luma.core.render import canvas
    from luma.oled.device import sh1106
    import gpiod

    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False

import asyncio
import io
import base64
from functools import cache
from PIL import Image, ImageDraw
from . import observer
import time

if LUMA_AVAILABLE:
    class GpiodAdapter:
        """GPIO adapter for luma using gpiod."""
        OUT = 1
        IN = 0
        LOW = 0
        HIGH = 1

        def __init__(self, chip_name):
            self.chip = gpiod.Chip(chip_name)  # type: ignore[name-defined]
            self.lines = {}

        def setup(self, pin, mode):
            """Setup a GPIO pin as input or output"""
            if pin not in self.lines:
                if mode == "OUT" or mode == 1:  # luma might use 1 for OUT
                    line_settings = gpiod.LineSettings(  # type: ignore[name-defined]
                        direction=gpiod.line.Direction.OUTPUT  # type: ignore[name-defined]
                    )
                else:
                    line_settings = gpiod.LineSettings(  # type: ignore[name-defined]
                        direction=gpiod.line.Direction.INPUT  # type: ignore[name-defined]
                    )
                line = self.chip.request_lines(
                    consumer="luma", config={pin: line_settings}
                )
                self.lines[pin] = {"line": line, "offset": pin}

        def output(self, pin, value):
            """Set output value on a GPIO pin"""
            if pin in self.lines:
                self.lines[pin]["line"].set_value(
                    self.lines[pin]["offset"], gpiod.line.Value(int(value))  # type: ignore[name-defined]
                )

        def cleanup(self):
            """Release all GPIO lines"""
            for line in self.lines.values():
                line["line"].release()
            self.chip.close()


class DisplayManagerBase:
    """Shared event subscription, throttle logic, and text rendering."""

    def __init__(self, app=None, chip_name: str = "/dev/gpiochip0"):
        if app:
            self._sm = app.sushi_client.controller
            observer.subscribe(
                "SushiPluginEvent", cb=self._handle_sushi_plugin_event
            )
        observer.subscribe(event="DrawText", cb=self.render_text)
        self.last_write = 0
        self._init_display(chip_name)

    def _init_display(self, chip_name: str) -> None:
        pass

    async def render_text(
        self, text: str, position: tuple[int, int] = (0, 0), fill: str = "white"
    ) -> None:
        def draw_fn(draw):
            draw.text(position, text, fill)
        await self.render_frame(draw_fn)

    async def render_frame(self, draw_fn) -> None:
        raise NotImplementedError

    async def _handle_sushi_plugin_event(self, event) -> None:
        name = self._get_param_name_by_event(event["plugin_id"], event["param_id"])
        return await self.render_text(f"{name}: {event['value']:.2f}")

    @cache
    def _get_param_name_by_event(self, proc_id: int, param_id: int) -> str:
        info = self._sm.parameters.get_parameter_info(
            processor_identifier=proc_id,
            parameter_identifier=param_id,
        )
        return info.name


class LumaDisplayManager(DisplayManagerBase):
    """DisplayManager backed by a real SH1106 OLED over SPI with luma.oled."""

    def _init_display(self, chip_name: str) -> None:
        gpio = GpiodAdapter(chip_name=chip_name)  # type: ignore[name-defined]
        serial = spi(port=1, device=0, gpio_DC=14, gpio_RST=12, gpio=gpio)  # type: ignore[name-defined]
        self.device = sh1106(serial)  # type: ignore[name-defined]

    async def render_frame(self, draw_fn) -> None:
        now = time.time()
        if now - self.last_write < 0.2:
            return
        self.last_write = now
        await asyncio.to_thread(self._draw_sync, draw_fn)

    def _draw_sync(self, draw_fn) -> None:
        """Runs GPIO operations in a thread pool."""
        with canvas(self.device) as draw:  # type: ignore[name-defined]
            draw_fn(draw)


class MockDisplayManager(DisplayManagerBase):
    """DisplayManager that renders to a PIL image and emits it as base64 PNG."""

    async def render_frame(self, draw_fn) -> None:
        img = Image.new("RGB", (128, 64), "black")
        draw = ImageDraw.Draw(img)
        draw_fn(draw)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        await observer.emit("PrintToMockDisplay", png_b64)


def DisplayManager(app=None, chip_name: str = "/dev/gpiochip0") -> DisplayManagerBase:
    """Factory: returns LumaDisplayManager on hardware, MockDisplayManager otherwise."""
    cls = LumaDisplayManager if LUMA_AVAILABLE else MockDisplayManager
    return cls(app=app, chip_name=chip_name)
