import os
import sys
import json
import random
import network
from urllib.urequest import urlopen
from badgeware import screen, PixelFont, brushes, io, run


JOKES_URL = "https://official-joke-api.appspot.com/jokes/programming/ten"
SLIDE_MS = 5000
RETRY_MS = 30000
FONT_DIR = "/system/assets/fonts/"
BUNDLED_FONTS = (
    "absolute", "ark", "awesome", "bacteria", "compass", "corset", "curse",
    "desert", "fear", "futile", "holotype", "hungry", "ignore", "kobold",
    "lookout", "loser", "manticore", "match", "memo", "nope", "outflank",
    "saga", "salty", "sins", "smart", "teatime", "torch", "troll", "unfair",
    "vest", "winds", "yesterday", "yolk", "ziplock",
)


def available_fonts():
    try:
        names = [
            name for name in os.listdir(FONT_DIR)
            if not name.startswith(".") and name.endswith(".ppf")
        ]
        names.sort()
        if len(names) > 1:
            return names
    except (OSError, AttributeError) as error:
        print("JK font scan failed:", error)
    # Firmware assets can be loadable even when directory enumeration fails.
    return [name + ".ppf" for name in BUNDLED_FONTS]


font_files = []
label_font = PixelFont.load(FONT_DIR + "nope.ppf")
joke_font = label_font
screen.font = joke_font
black = brushes.color(0, 0, 0)
green = brushes.color(0, 255, 100)

wlan = None
entries = []
setup_lines = []
punch_lines = []
show_punch = False
last_slide = 0
retry_at = 0
status = "Connecting Wi-Fi"
font_index = -1
font_name = ""
first_frame = True


def init():
    global wlan, status
    sys.path.insert(0, "/")
    try:
        import secrets

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    except Exception as error:
        print("JK Wi-Fi failed:", error)
        status = "Check secrets.py"
        wlan = None
    finally:
        sys.path.pop(0)


def fetch_jokes():
    response = urlopen(JOKES_URL)
    try:
        batch = json.loads(response.read())
    finally:
        response.close()
    jokes = [
        joke for joke in batch
        if isinstance(joke, dict)
        and isinstance(joke.get("setup"), str) and joke["setup"].strip()
        and isinstance(joke.get("punchline"), str) and joke["punchline"].strip()
    ]
    if not jokes:
        raise ValueError("No jokes returned")
    return jokes


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


def next_font():
    global font_files, font_index, font_name, joke_font
    if not font_files:
        font_files = available_fonts()
    for _ in range(len(font_files)):
        font_index = (font_index + 1) % len(font_files)
        filename = font_files[font_index]
        try:
            font = label_font if filename == "nope.ppf" else PixelFont.load(FONT_DIR + filename)
        except Exception as error:
            print("JK font failed:", filename, error)
            continue
        joke_font = font
        font_name = filename[:-4]
        screen.font = joke_font
        return
    joke_font = label_font
    font_name = "nope"
    screen.font = joke_font


def advance():
    global entries, setup_lines, punch_lines, show_punch, last_slide, retry_at, status
    try:
        if not entries:
            entries = fetch_jokes()
        joke = entries.pop(random.randrange(len(entries)))
        next_font()
        setup_lines = wrap_text(joke["setup"])
        punch_lines = wrap_text(joke["punchline"])
        show_punch = False
        last_slide = io.ticks
        status = ""
    except Exception as error:
        print("JK fetch failed:", error)
        setup_lines = []
        punch_lines = []
        status = "Jokes unavailable"
        retry_at = io.ticks + RETRY_MS


def update():
    global show_punch, last_slide, first_frame
    # Return one drawn frame before any blocking network or font discovery work.
    if first_frame:
        first_frame = False
    elif wlan:
        if not setup_lines:
            if wlan.isconnected() and io.ticks >= retry_at:
                advance()
        elif io.ticks - last_slide >= SLIDE_MS:
            if show_punch:
                advance()
            else:
                show_punch = True
                last_slide = io.ticks

    screen.brush = black
    screen.clear()
    screen.brush = green
    if not setup_lines:
        screen.text("Connecting Wi-Fi" if wlan and not wlan.isconnected() else status, 3, 3)
        return

    screen.font = joke_font
    line_height = screen.measure_text("Ag")[1] + 1
    screen.font = label_font
    label_width, label_height = screen.measure_text(font_name)
    label_y = screen.height - label_height - 3
    screen.font = joke_font
    y = 3
    for line in setup_lines:
        if y + line_height <= label_y - 3:
            screen.text(line, 3, y)
        y += line_height
    if show_punch:
        y += 4
        for line in punch_lines:
            if y + line_height <= label_y - 3:
                screen.text(line, 3, y)
            y += line_height
    screen.font = label_font
    screen.text(font_name, screen.width - label_width - 3, label_y)
    screen.font = joke_font


if __name__ == "__main__":
    init()
    run(update)
