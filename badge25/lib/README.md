# Shared Universe 2025 modules

Copy this directory to `/system/lib` and use `badge25/main.py` to add it to
the import path. These modules are for the 2025 Badgeware runtime.

## ColorPicker

`bgcolor` is the initial RGB tuple, with each channel from 0 to 255.
Each initial channel is rounded down to a multiple of five.
Each instance owns its color, selected channel, and drawing state.
The picker uses `smart` without changing the caller's screen font or brush.

- A / C: previous / next channel, wrapping through R, G, B.
- UP / DOWN: add / subtract five.
  UP wraps 255 to 0; DOWN wraps 0 to 255.
- B: confirm, set `busy` to `False`, and return a `brushes.color` brush.

Call `pick()` once per app update while `busy` is true. It draws the picker
and returns the current brush on every call. Check `busy` for confirmation.
The `complement` property returns a background brush with RGB channels
`(255 - R, 255 - G, 255 - B)` for the current selection.
It does not start a separate run loop. After confirmation, further calls return
the selected brush without drawing or processing input. HOME retains the launcher's normal behavior.

```python
from colorpicker import ColorPicker
from badgeware import screen, brushes

colorpicker = ColorPicker((0, 128, 0))
background_color = brushes.color(0, 128, 0)

def update():
    global background_color
    if colorpicker.busy:
        background_color = colorpicker.pick()
        return
    screen.brush = background_color
    screen.clear()
```

For a caller outside the standard launcher, add `/system/lib` to `sys.path`
before importing. Call `colorpicker.start()` to reopen it with the last selected color. RGB state
stays inside the picker; the caller stores only a brush. The 2025 brush API
does not expose RGB getters, so the initial constructor input remains an RGB
tuple.
