try:
    from luma.core.interface.serial import spi
    from luma.core.render import canvas
    from luma.oled.device import sh1106
    import gpiod

    LUMA_AVAILABLE = True
except ImportError:
    LUMA_AVAILABLE = False

from functools import cache
from . import observer

if LUMA_AVAILABLE:
    # Create a GPIO adapter for luma using gpiod
    class GpiodAdapter:
        OUT = 1
        IN = 0
        LOW = 0
        HIGH = 1

        def __init__(self, chip_name="/dev/gpiochip0"):
            self.chip = gpiod.Chip(chip_name)
            self.lines = {}

        def setup(self, pin, mode):
            """Setup a GPIO pin as input or output"""
            if pin not in self.lines:
                if mode == "OUT" or mode == 1:  # luma might use 1 for OUT
                    line_settings = gpiod.LineSettings(
                        direction=gpiod.line.Direction.OUTPUT
                    )
                else:
                    line_settings = gpiod.LineSettings(
                        direction=gpiod.line.Direction.INPUT
                    )
                line = self.chip.request_lines(
                    consumer="luma", config={pin: line_settings}
                )
                self.lines[pin] = {"line": line, "offset": pin}

        def output(self, pin, value):
            """Set output value on a GPIO pin"""
            if pin in self.lines:
                self.lines[pin]["line"].set_value(
                    self.lines[pin]["offset"], gpiod.line.Value(int(value))
                )

        def cleanup(self):
            """Release all GPIO lines"""
            for line in self.lines.values():
                line["line"].release()
            self.chip.close()

    class DisplayManager:
        """Writes to displays with LUMA.
        Its draw() method is a callback for the DrawText event.
        """

        def __init__(self, app=None, chip_name: str = "/dev/gpiochip0"):
            self.gpio = GpiodAdapter(chip_name=chip_name)  # Adjust chip name if needed
            self.serial = spi(port=1, device=0, gpio_DC=14, gpio_RST=12, gpio=self.gpio)
            self.device = sh1106(self.serial)
            if app:
                self._sm = app.sushi_client.controller
                observer.subscribe(
                    "SushiPluginEvent", cb=self._handle_sushi_plugin_event
                )
            observer.subscribe(event="DrawText", cb=self.draw)

        def draw(
            self, text: str, position: tuple[int, int] = (0, 0), fill: str = "white"
        ) -> None:
            with canvas(self.device) as draw:
                draw.text(position, text, fill)

        def _handle_sushi_plugin_event(self, event) -> None:
            name = self._get_param_name_by_event(event["plugin_id"], event["param_id"])
            self.draw(f"{name}: {event['value']:.2f}")

        @cache
        def _get_param_name_by_event(self, proc_id: int, param_id: int) -> str:
            info = self._sm.parameters.get_parameter_info(
                processor_identifier=proc_id,
                parameter_identifier=param_id,
            )
            return info.name

else:

    class DisplayManager:
        """Writes to the mocked display in board-ui when LUMA is not available on the current machine"""

        def __init__(self, app=None, chip_name: str = "/dev/gpiochip0"):
            observer.subscribe(event="DrawText", cb=self.draw)
            if app:
                observer.subscribe(
                    "SushiPluginEvent", cb=self._handle_sushi_plugin_event
                )
                self._sm = app.sushi_client.controller

        def draw(
            self, text: str, position: tuple[int, int] = (0, 0), fill: str = "white"
        ) -> None:
            observer.emit("PrintToMockDisplay", text)

        def _handle_sushi_plugin_event(self, event) -> None:
            name = self._get_param_name_by_event(event["plugin_id"], event["param_id"])
            self.draw(f"{name}: {event['value']:.2f}")

        @cache
        def _get_param_name_by_event(self, proc_id: int, param_id: int) -> str:
            info = self._sm.parameters.get_parameter_info(
                processor_identifier=proc_id,
                parameter_identifier=param_id,
            )
            return info.name
