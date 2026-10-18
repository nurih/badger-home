import os
import sys
import gc
import json
import hashlib
import binascii
import network
from urllib.urequest import urlopen
from badgeware import screen, PixelFont, Image, brushes, io, run

APP_DIR = "/system/apps/fishface"
CACHE_DIR = "/fishface-cache"
CACHE_BYTES = 512 * 1024
REFRESH_MS = 600000
FISHFACE_API_URL = ""
FISHFACE_SITE_URL = ""
SLIDE_MS = 4000
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)
screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
logo = Image.load("logo.png")
black = brushes.color(0, 0, 0)
white = brushes.color(255, 255, 255)

wlan = None
entries = []
next_before = None
index = -1
view = 0
pair_step = 0
batch_times = {}
photo = None
paused = False
last_slide = 0
retry_at = 0
status = "Connecting Wi-Fi"


def init():
    global wlan, status, FISHFACE_API_URL, FISHFACE_SITE_URL
    sys.path.insert(0, "/")
    try:
        import secrets
        FISHFACE_API_URL = secrets.FISHFACE_API_URL.rstrip("/")
        FISHFACE_SITE_URL = secrets.FISHFACE_SITE_URL.rstrip("/")
        try:
            os.mkdir(CACHE_DIR)
        except OSError as error:
            if error.args[0] != 17:
                raise
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    except Exception as error:
        print("FishFace config:", error)
        status = "Check secrets.py"
        wlan = None
    finally:
        sys.path.pop(0)


def cache_path(key, suffix):
    key = FISHFACE_API_URL + "|" + FISHFACE_SITE_URL + "|" + key
    digest = binascii.hexlify(hashlib.sha256(key.encode()).digest()).decode()
    return CACHE_DIR + "/" + digest + suffix


def trim_cache(reserve=0, keep=()):
    files = []
    total = 0
    for name in os.listdir(CACHE_DIR):
        path = CACHE_DIR + "/" + name
        info = os.stat(path)
        total += info[6]
        files.append((info[8], path, info[6]))
    for _, path, size in sorted(files):
        if total + reserve <= CACHE_BYTES:
            break
        if path in keep:
            continue
        os.remove(path)
        total -= size
        batch_times.pop(path, None)


def fetch_batch():
    global entries, next_before, index
    url = FISHFACE_API_URL + "/api/booth/gallery"
    if next_before:
        url += "?before=" + next_before
    path = cache_path(url, ".json")
    batch = None
    try:
        with open(path) as source:
            batch = json.load(source)
    except (OSError, ValueError):
        pass
    if batch is not None and path not in batch_times:
        batch_times[path] = io.ticks
    if batch is None or io.ticks - batch_times[path] >= REFRESH_MS:
        try:
            print("FishFace batch: fetching", url)
            response = urlopen(url)
            try:
                fresh = json.loads(response.read())
            finally:
                response.close()
            trim_cache(16384)
            with open(path + ".tmp", "w") as output:
                json.dump(fresh, output)
            os.rename(path + ".tmp", path)
            batch = fresh
            batch_times[path] = io.ticks
        except Exception as error:
            print("FishFace batch: fetch failed", repr(error))
            if batch is None:
                raise
            print("FishFace batch: using stale cache")
            # Use stale results when offline; retry refresh in 30 seconds.
            batch_times[path] = io.ticks - REFRESH_MS + 30000
    else:
        print("FishFace batch: using cache")
    entries = batch["entries"]
    next_before = batch.get("nextBefore")
    print("FishFace batch: loaded", len(entries), "entries; next cursor:", next_before)
    index = 0


def image_url(entry, view):
    path = entry["selfieUrl"] if view == 0 else entry["match"]["imageUrl"]
    if path.startswith("/api/media/fish/"):
        path = path.replace("/api/media/fish/", "/fish/", 1)
    if path.startswith("/fish/"):
        path = FISHFACE_SITE_URL + path
    elif path.startswith("/"):
        path = FISHFACE_API_URL + path
    encoded = "".join(chr(c) if (65 <= c <= 90 or 97 <= c <= 122 or
                               48 <= c <= 57 or c in b"-._~") else "%%%02X" % c
                      for c in path.encode("utf-8"))
    return "https://wsrv.nl/?url=" + encoded + "&w=160&h=76&fit=inside&output=png"


def load_photo():
    global photo
    entry = entries[index]
    paths = []
    for pair_view in (0, 1):
        url = image_url(entry, pair_view)
        path = cache_path(url, ".png")
        paths.append(path)
        try:
            os.stat(path)
        except OSError:
            trim_cache(65536, paths)
            response = urlopen(url)
            try:
                with open(path + ".tmp", "wb") as output:
                    while True:
                        chunk = response.read(1024)
                        if not chunk:
                            break
                        output.write(chunk)
            finally:
                response.close()
            os.rename(path + ".tmp", path)
    photo = None
    gc.collect()
    try:
        photo = Image.load(paths[view])
    except Exception:
        os.remove(paths[view])
        raise


def advance(next_entry=False):
    global index, view, pair_step, last_slide, retry_at, status
    try:
        if not entries or (next_entry and index + 1 >= len(entries)):
            fetch_batch()
            view = 0
            pair_step = 0
        elif next_entry:
            index += 1
            view = 0
            pair_step = 0
        if entries:
            load_photo()
            status = ""
        else:
            status = "No FishFaces yet"
    except Exception as error:
        print("FishFace fetch:", repr(error))
        status = "Fetch: " + str(error)[:24]
    last_slide = io.ticks
    retry_at = io.ticks + 30000


def update():
    global view, pair_step, paused, last_slide
    if wlan:
        if index < 0 or not entries:
            if io.ticks >= retry_at:
                advance()
        else:
            if io.BUTTON_B in io.pressed:
                paused = not paused
                last_slide = io.ticks
            if io.BUTTON_C in io.pressed:
                advance(True)
            elif io.BUTTON_A in io.pressed:
                view = 1 - view
                pair_step = view
                advance()
            elif not paused and io.ticks - last_slide >= SLIDE_MS:
                pair_step += 1
                if pair_step == 6:
                    advance(True)
                else:
                    view = pair_step % 2
                    advance()

    screen.brush = black
    screen.clear()
    if photo:
        screen.blit(photo, (160 - photo.width) // 2, 13 + (76 - photo.height) // 2)
    screen.brush = white
    if status:
        label = status
    elif entries:
        label = (entries[index].get("fullName") or "Player") if view == 0 else "Best match"
        if paused:
            label += " (paused)"
    else:
        label = "Connecting Wi-Fi"
    screen.text(label, 3, 1)
    screen.blit(logo, (160 - logo.width) // 2, 92)


if __name__ == "__main__":
    init()
    run(update)
