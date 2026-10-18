import sys
import json
import random
import network
from urllib.urequest import urlopen
from badgeware import screen, PixelFont, brushes, io, run


JOKES_URL = "https://official-joke-api.appspot.com/jokes/programming/ten"
SLIDE_MS = 5000
RETRY_MS = 30000
screen.font = PixelFont.load("/system/assets/fonts/smart.ppf")
background_color = brushes.color(0, 0, 0)
punch_color = brushes.color(0, 255, 255)
setup_color = brushes.color(0, 255, 0)

wlan = None
entries = []
setup_lines = []
punch_lines = []
show_punch = False
last_slide = 0
retry_at = 0
status = "Connecting Wi-Fi"
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


def advance():
    global entries, setup_lines, punch_lines, show_punch, last_slide, retry_at, status
    try:
        if not entries:
            entries = fetch_jokes()
        joke = entries.pop(random.randrange(len(entries)))
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
    # Return one drawn frame before any blocking network work.
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

    screen.brush = background_color
    screen.clear()
    screen.brush = setup_color

    if not setup_lines:
        screen.text("Connecting Wi-Fi" if wlan and not wlan.isconnected() else status, 3, 3)
        return

    line_height = screen.measure_text("Ag")[1] + 1
    y = 3
    for line in setup_lines:
        if y + line_height <= screen.height - 3:
            screen.text(line, 3, y)
        y += line_height
    if show_punch:
        screen.brush = punch_color
        y += 4
        for line in punch_lines:
            if y + line_height <= screen.height - 3:
                screen.text(line, 3, y)
            y += line_height


if __name__ == "__main__":
    init()
    run(update)
