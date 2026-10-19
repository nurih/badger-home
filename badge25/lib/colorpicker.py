"""Frame-based RGB picker for the Universe 2025 badge."""

from badgeware import screen, PixelFont, brushes, shapes, io

STEP = 5

class ColorPicker:
    def __init__(self, bgcolor):
        self._rgb = [value // STEP * STEP for value in bgcolor]
        self._color = brushes.color(*self._rgb)
        self._channel = 0
        self.busy = True
        self._view = screen.window(0, 0, screen.width, screen.height)
        self._view.font = PixelFont.load("/system/assets/fonts/unfair.ppf")
        self._black = brushes.color(0, 0, 0)
        self._white = brushes.color(255, 255, 255)
        self._border = brushes.color(220, 220, 255)
        self._panel = shapes.rectangle(0, 0, screen.width, 80)
        self._footer = shapes.rectangle(0, 96, screen.width, screen.height - 96)
        self._tracks = tuple(shapes.rectangle(22, 24 + i * 20, screen.width - 26, 13)
                             for i in range(3))
        self._strips = [None] * 3
        self._indicators = [None] * 3
        for channel in range(3):
            self._update_strip(channel)
        self._highlight = tuple(shapes.rectangle(21, 20 + i * 20, screen.width - 24, 18)
                                for i in range(3))

    def _update_strip(self, channel):
        width = (screen.width - 26) * self._rgb[channel] // 255
        x = 22 + width
        y = 24 + channel * 20
        self._strips[channel] = shapes.rectangle(22, y, width, 13)
        self._indicators[channel] = (
            shapes.rectangle(x - 2, y - 3, 5, 1),
            shapes.rectangle(x - 1, y - 2, 3, 1),
            shapes.rectangle(x, y - 1, 1, 1),
            shapes.rectangle(x, y, 1, 13),
        )

    @property
    def complement(self):
        """Return the RGB complement of the current color as a brush."""
        return brushes.color(*(255 - value for value in self._rgb))

    def start(self):
        """Reopen the picker with its current color."""
        self.busy = True

    def pick(self):
        """Return the current brush. B confirms and clears busy."""
        if not self.busy:
            return self._color
        if io.BUTTON_B in io.pressed:
            self.busy = False
            return self._color
        if io.BUTTON_A in io.pressed:
            self._channel = (self._channel + 1) % 3
        if io.BUTTON_C in io.pressed:
            self._channel = (self._channel - 1) % 3
        value = self._rgb[self._channel]
        direction = int(io.BUTTON_UP in io.pressed) - int(io.BUTTON_DOWN in io.pressed)
        self._rgb[self._channel] = (value + direction * STEP) % (255 + STEP)
        if self._rgb[self._channel] != value:
            self._update_strip(self._channel)

        view = self._view
        self._color = brushes.color(*self._rgb)
        view.brush = self._color
        view.clear()
        view.brush = self._black
        view.draw(self._panel)
        view.draw(self._footer)
        view.brush = self._white
        view.text("pick color", 4, 3)
        view.brush = self._border
        view.draw(self._highlight[self._channel])
        for channel, name in enumerate(("R", "G", "B")):
            view.brush = self._black
            view.draw(self._tracks[channel])
            rgb = [0, 0, 0]
            rgb[channel] = self._rgb[channel]
            view.brush = brushes.color(*rgb)
            view.draw(self._strips[channel])
            view.brush = self._white
            for indicator in self._indicators[channel]:
                view.draw(indicator)
            view.text(name + ":", 4, 23 + channel * 20)
        hex_rgb = "%%%02X%02X%02X" % tuple(self._rgb)
        hex_width, hex_height = view.measure_text(hex_rgb)
        view.brush = self.complement
        view.text(hex_rgb, (view.width - hex_width) // 2, 80 + (16 - hex_height) // 2)
        view.brush = self._white
        view.text("CH+", 4, 103)
        view.text("OK", (view.width - view.measure_text("OK")[0]) // 2, 103)
        view.text("CH-", view.width - 4 - view.measure_text("CH-")[0], 103)
        return self._color
