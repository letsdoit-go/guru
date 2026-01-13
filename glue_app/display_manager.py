from luma.core.interface.serial import spi
from luma.core.render import canvas
from luma.oled.device import sh1106
import gpiod

from . import observer


# Create a GPIO adapter for luma using gpiod
class GpiodAdapter:
    OUT=1
    IN=0
    LOW=0
    HIGH=1

    def __init__(self, chip_name="/dev/gpiochip0"):
        self.chip = gpiod.Chip(chip_name)
        self.lines = {}
    
    def setup(self, pin, mode):
        """Setup a GPIO pin as input or output"""
        if pin not in self.lines:
            if mode == "OUT" or mode == 1:  # luma might use 1 for OUT
                line_settings = gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)
            else:
                line_settings = gpiod.LineSettings(direction=gpiod.line.Direction.INPUT)
            line = self.chip.request_lines(consumer="luma", config={pin: line_settings})
            self.lines[pin] = { "line":line, "offset":pin }

    def output(self, pin, value):
        """Set output value on a GPIO pin"""
        if pin in self.lines:
            self.lines[pin]["line"].set_value(self.lines[pin]["offset"], gpiod.line.Value(int(value)))
    
    def cleanup(self):
        """Release all GPIO lines"""
        for line in self.lines.values():
            line["line"].release()
        self.chip.close()


class DisplayManager:
    """Writes to displays with LUMA.
    Its draw() method is a callback for the DrawText event.
    """
    def __init__(self, chip_name: str = "/dev/gpiochip0"):
        self.gpio = GpiodAdapter(chip_name=chip_name)  # Adjust chip name if needed
        self.serial = spi(port=1, device=0, gpio_DC=14, gpio_RST=12, gpio=self.gpio)
        self.device = sh1106(self.serial)
        observer.subscribe(event="DrawText", cb=self.draw)

    def draw(self, position: tuple[int, int], text: str, fill: str = "white") -> None:
        with canvas(self.device) as draw:
            draw.text(position, text, fill)
        self.gpio.cleanup()


# draw.text((0, 0), "STM-SOM dev board", fill="white")
# draw.text((0, 24), "by ELK & AUT", fill="white")
#
# Initialize SPI interface with GPIO control
# DC and RST pin numbers depend on your hardware - these are examples

# Draw text on the display

# Cleanup GPIO when done

