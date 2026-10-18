# FishFace for Universe 2025

Shows the target fish, selfie, and best matched fish from the same API as
https://nurih.github.io/FishFace/booth/. Each image fits within 50x50 pixels.
The three images form one centered row with 1 pixel between images.
Each row stays for 30 seconds, then moves to the next entry.
The label shows the player's name.
A fish follows the name in the top-right corner: bright green and happy when
the target and best matched fish are the same, red-orange and dead when they differ. Long names are clipped
to leave room for the fish.
The supplied MongoDB.local logo stays on a black footer.

The 2025 firmware loads PNG only. The badge requests resized PNG images
directly from https://wsrv.nl/. No PC service or API key is required.
wsrv.nl fetches and caches the public gallery photos.

Set Wi-Fi credentials and FishFace URLs in the badge's root `secrets.py`:

```python
WIFI_SSID = "your network"
WIFI_PASSWORD = "your password"
FISHFACE_API_URL = ""
FISHFACE_SITE_URL = "https://nurih.github.io/FishFace"
```

Copy this app directory to the badge's `/system/apps/fishface` (the USB drive's
`apps/fishface`). Use the repository's `badge25/apps/menu/__init__.py` menu,
which discovers apps and supports multiple pages. Restart the badge.

- A: next gallery entry.
- B: pause / resume rotation.
- C: next gallery entry.
- HOME: return to menu.

After the last batch, the app returns to the first cached batch. Gallery batches
are saved locally and refreshed when used after five minutes. On restart, saved
batches are reused for five minutes before refresh. If refresh fails, the app
keeps the saved results and retries refresh after 30 seconds. Empty galleries
and failed initial loads retry after 30 seconds. Network calls can pause the UI
while they complete. The app uses the public gallery API; it needs no
MongoDB credentials.

Gallery results and images are saved in `/fishface-cache` on the writable root
filesystem. The cache survives app exits and restarts. Images are keyed by URL,
so shared fish images are reused between players. Cached rows can play offline.
The cache has a 512 KiB budget; older files are removed to make room for new
downloads. Evicted images are downloaded again when needed. `/system` is
read-only while apps run.
