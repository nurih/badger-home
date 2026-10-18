# FishFace for Universe 2025

Shows gallery selfies and best matched fish from the same API as
https://nurih.github.io/FishFace/booth/. Each pair runs as selfie, match,
selfie, match, selfie, match, with 3 seconds per image, then moves to the next
entry. The selfie label shows the player's name.
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

- A: switch selfie / best matched fish.
- B: pause / resume rotation.
- C: next gallery entry.
- HOME: return to menu.

After the last batch, the app fetches the newest entries again. Empty galleries
and failed initial loads retry after 30 seconds. Network calls can pause the UI
while they complete. The app uses the public gallery API; it needs no
MongoDB credentials.

Both images are downloaded once per entry, then switched locally. Temporary
images are stored at `/fishface-selfie.png` and `/fishface-match.png` on the
writable root filesystem and removed on exit. `/system` is read-only while
apps run.
