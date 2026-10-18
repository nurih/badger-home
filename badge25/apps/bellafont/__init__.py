import os
import random
from badgeware import screen, PixelFont, brushes, io, run

""" Show all available fonts """

FONT_DIR = "/system/assets/fonts/"
BUNDLED_FONTS = (
    "absolute",
    "ark",
    "awesome",
    "bacteria",
    "compass",
    "corset",
    "curse",
    "desert",
    "fear",
    "futile",
    "holotype",
    "hungry",
    "ignore",
    "kobold",
    "lookout",
    "loser",
    "manticore",
    "match",
    "memo",
    "nope",
    "outflank",
    "saga",
    "salty",
    "sins",
    "smart",
    "teatime",
    "torch",
    "troll",
    "unfair",
    "vest",
    "winds",
    "yesterday",
    "yolk",
    "ziplock",
)


def available_fonts():
    try:
        names = [
            entry[0]
            for entry in os.ilistdir(FONT_DIR.rstrip("/"))
            if not entry[0].startswith(".") and entry[0].endswith(".ppf")
        ]
        names.sort()
        if names:
            print(f"Found {len(names)} fonts on disk.")
            return names
    except (OSError, AttributeError) as error:
        print("Font scan failed:", error)
    # Firmware assets can be loadable even when directory enumeration fails.
    return [name + ".ppf" for name in BUNDLED_FONTS]


font_files = []
label_font = PixelFont.load(FONT_DIR + "nope.ppf")
font_name = "nope"
current_font = label_font
painted_font = None
screen.font = current_font
background_color = brushes.color(0, 0, 0)
text_color = brushes.color(0, 255, 100)

demo_text = (
    """Lorem ipsum dolor sit amet. 1234567890-+ !@#4%^&*()_+ []\\\{\}|;':",./<>?"""
)
status = "Starting"
font_index = -1


def init():
    global font_files
    print("Init")
    font_files = available_fonts()

    print("FONTS: ", font_files)


def wrap_text(text):
    lines = []
    line = ""
    for word in text.split():
        candidate = line + (" " if line else "") + word
        if screen.measure_text(candidate)[0] <= screen.width - 6:
            line = candidate
        else:
            if line:
                lines.append(line)
            # Split words that are wider than the display.
            line = ""
            for char in word:
                if line and screen.measure_text(line + char)[0] > screen.width - 6:
                    lines.append(line)
                    line = ""
                line += char
    if line:
        lines.append(line)
    return lines


def advance(step):
    global font_files, font_index, font_name, current_font
    print(f"Font was {font_name} ")

    font_index = (font_index + step) % len(font_files)
    filename = font_files[font_index]
    try:
        font = (
            label_font
            if filename == "nope.ppf"
            else PixelFont.load(FONT_DIR + filename)
        )
    except Exception as error:
        print("Font load failed:", filename, error)
        return
    current_font = font
    font_name = filename[:-4]
    screen.font = current_font

    print(f"Font now {font_name}.")
    return font_name


def update():
    global painted_font

    if io.BUTTON_B in io.pressed:
        clear_screen()
        text = "Buttons [A] or[UP]: prev. Buttons [C] or [DOWN] next."
        paint_footer(text)

    if any([button in io.pressed for button in (io.BUTTON_A, io.BUTTON_UP)]):
        advance(-1)

    if any([button in io.pressed for button in (io.BUTTON_C, io.BUTTON_DOWN)]):
        advance(1)

    if font_name == painted_font:
        return

    clear_screen()

    screen.font = current_font
    line_height = screen.measure_text("Ag")[1] + 1
    screen.font = label_font
    _, label_height = screen.measure_text(font_name)
    label_y = screen.height - label_height - 3
    screen.font = current_font
    y = 3

    for line in wrap_text(demo_text):
        if y + line_height <= label_y - 3:
            screen.text(line, 3, y)
        y += line_height

    paint_footer(font_name)

    painted_font = font_name


def paint_footer(text):
    screen.font = label_font
    _, text_height = screen.measure_text(text)
    lines = wrap_text(text)
    line_height = text_height + 1
    y = screen.height - text_height - (len(lines) - 1) * line_height - 3

    for line in lines:
        screen.text(line, 3, y)
        y += line_height

    screen.font = current_font


def clear_screen():
    screen.brush = background_color
    screen.clear()
    screen.brush = text_color


if __name__ == "__main__":
    init()
    run(update)
