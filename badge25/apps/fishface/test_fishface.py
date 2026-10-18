"""Run with: python -m unittest discover -s tools -p test_fishface.py"""

from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FishFaceTests(unittest.TestCase):
    def setUp(self):
        screen = SimpleNamespace(width=160, clear=lambda: None, blit=lambda *a: None,
                                 text=lambda *a: None)
        io = SimpleNamespace(ticks=0, pressed=set(), BUTTON_A="A", BUTTON_B="B", BUTTON_C="C")
        badgeware = ModuleType("badgeware")
        badgeware.screen = screen
        badgeware.io = io
        badgeware.Image = SimpleNamespace(load=lambda path: SimpleNamespace(width=150, height=27))
        badgeware.PixelFont = SimpleNamespace(load=lambda path: None)
        badgeware.brushes = SimpleNamespace(color=lambda *args: args)
        badgeware.run = lambda update: None
        http = ModuleType("urllib.urequest")
        http.urlopen = lambda url: None
        saved_path = sys.path[:]
        try:
            with patch.dict(sys.modules, {"badgeware": badgeware, "network": ModuleType("network"),
                                          "urllib.urequest": http}), patch("os.chdir"):
                spec = importlib.util.spec_from_file_location("badge_fishface", ROOT / "badge25/apps/fishface/__init__.py")
                app = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(app)
        finally:
            sys.path[:] = saved_path
        self.app = app
        self.io = io
        app.FISHFACE_API_URL = "https://api.example.test"
        app.FISHFACE_SITE_URL = "https://site.example.test/FishFace"
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        app.CACHE_DIR = cache.name.replace("\\", "/")
        # MicroPython rename replaces existing files; Windows rename does not.
        rename = patch.object(app.os, "rename", os.replace)
        rename.start()
        self.addCleanup(rename.stop)

    def test_image_urls(self):
        from urllib.parse import parse_qs, urlsplit
        app = self.app
        entry = {"selfieUrl": "/api/media/selfie/" + "a" * 24,
                 "target": {"imageUrl": "/fish/fish-999.jpg"},
                 "match": {"imageUrl": "/api/media/fish/fish-005.jpg"}}
        for path in ("/api/media/fish/fish-005.jpg", "/fish/fish-005.jpg",
                     app.FISHFACE_SITE_URL + "/fish/fish-005.jpg"):
            entry["match"]["imageUrl"] = path
            query = parse_qs(urlsplit(app.image_url(entry, 2)).query)
            self.assertEqual(query["url"], [app.FISHFACE_SITE_URL + "/fish/fish-005.jpg"])
            self.assertEqual(query["output"], ["png"])
            self.assertEqual((query["w"], query["h"]), (["50"], ["50"]))
        query = parse_qs(urlsplit(app.image_url(entry, 0)).query)
        self.assertEqual(query["url"], [app.FISHFACE_SITE_URL + "/fish/fish-999.jpg"])
        entry["selfieUrl"] += "?a=1&b=two words"
        query = parse_qs(urlsplit(app.image_url(entry, 1)).query)
        self.assertEqual(query["url"], [app.FISHFACE_API_URL + entry["selfieUrl"]])

    def test_wifi_without_pc_service_setting(self):
        app = self.app
        wlan = SimpleNamespace(active=lambda value: None, isconnected=lambda: False,
                               connect=unittest.mock.Mock())
        secrets = ModuleType("secrets")
        secrets.WIFI_SSID = "test"
        secrets.WIFI_PASSWORD = "password"
        secrets.FISHFACE_API_URL = "https://custom-api.example.test/"
        secrets.FISHFACE_SITE_URL = "https://custom-site.example.test/FishFace/"
        with patch.dict(sys.modules, {"secrets": secrets}), \
                patch.object(app.network, "WLAN", return_value=wlan, create=True), \
                patch.object(app.network, "STA_IF", 0, create=True):
            app.init()
        wlan.connect.assert_called_once_with("test", "password")
        self.assertEqual(app.FISHFACE_API_URL, "https://custom-api.example.test")
        self.assertEqual(app.FISHFACE_SITE_URL, "https://custom-site.example.test/FishFace")

    def test_photo_uses_writable_root(self):
        app = self.app
        app.entries = [{"id": "a", "selfieUrl": "/api/media/selfie/" + "a" * 24,
                        "target": {"imageUrl": "/fish/fish-999.jpg"},
                        "match": {"imageUrl": "/fish/fish-005.jpg"}}]
        app.index = 0
        responses = [BytesIO(b"target image bytes"), BytesIO(b"test image bytes"), BytesIO(b"match image bytes")]
        with patch.object(app, "urlopen", side_effect=responses) as get, \
                patch.object(app.Image, "load") as load:
            app.load_photo()
            target, selfie, match = [app.cache_path(app.image_url(app.entries[0], view), ".png")
                                     for view in (0, 1, 2)]
            self.assertEqual([call.args[0] for call in load.call_args_list], [target, selfie, match])
            self.assertEqual(len(app.photos), 3)
            app.load_photo()
            self.assertEqual(get.call_count, 3)
            load.assert_called_with(match)
            # Returning to the row does not download any image again.
            app.index = 0
            app.load_photo()
            self.assertEqual(get.call_count, 3)
        self.assertEqual(Path(selfie).read_bytes(), b"test image bytes")
        self.assertEqual(Path(match).read_bytes(), b"match image bytes")
        self.assertTrue(all(response.closed for response in responses))
        with patch.object(app.Image, "load", side_effect=ValueError("bad PNG")), \
                patch.object(app, "urlopen") as get:
            with self.assertRaises(ValueError):
                app.load_photo()
            get.assert_not_called()
        self.assertFalse(Path(target).exists())
        self.assertTrue(Path(selfie).exists())
        self.assertTrue(Path(match).exists())

    def test_gallery_cache_refresh_and_offline_fallback(self):
        app = self.app
        batch = {"entries": [{"id": "a"}], "nextBefore": None}
        with patch.object(app, "urlopen", return_value=BytesIO(json.dumps(batch).encode())) as get:
            app.fetch_batch()
            app.fetch_batch()
            self.assertEqual(get.call_count, 1)
        # A new session can read persisted JSON without a network request.
        app.batch_times.clear()
        with patch.object(app, "urlopen", side_effect=OSError("offline")) as get:
            app.fetch_batch()
            get.assert_not_called()
            self.io.ticks += app.REFRESH_MS
            app.fetch_batch()
            self.assertEqual(get.call_count, 1)
            self.assertEqual(app.entries, batch["entries"])
            app.fetch_batch()
            self.assertEqual(get.call_count, 1)
        self.io.ticks += 30000
        batch["entries"] = [{"id": "new"}]
        with patch.object(app, "urlopen", return_value=BytesIO(json.dumps(batch).encode())):
            app.fetch_batch()
        self.assertEqual(app.entries, [{"id": "new"}])

    def test_cache_eviction_stays_in_cache_directory(self):
        app = self.app
        app.CACHE_BYTES = 10
        old = Path(app.CACHE_DIR) / "old.png"
        keep = Path(app.CACHE_DIR) / "keep.png"
        old.write_bytes(b"123456")
        keep.write_bytes(b"123456")
        app.trim_cache(0, [keep.as_posix()])
        self.assertFalse(old.exists())
        self.assertTrue(keep.exists())

    def test_badge_rotation_pagination_pause_and_retry(self):
        app, io = self.app, self.io
        app.wlan = SimpleNamespace(isconnected=lambda: True)
        first = {"entries": [{"id": "a", "fullName": "Alex"}, {"id": "b"}], "nextBefore": "b"}
        last = {"entries": [{"id": "c"}], "nextBefore": None}
        with patch.object(app, "urlopen", side_effect=lambda url: BytesIO(json.dumps(last if "before=" in url else first).encode())) as get, \
                patch.object(app, "load_photo") as load, \
                patch.object(app.screen, "text") as text:
            app.update()
            self.assertEqual(app.index, 0)
            text.assert_called_with("Alex", 3, 1)
            io.ticks = 29999
            app.update()
            self.assertEqual(app.index, 0)
            io.ticks = 30000
            app.update()
            self.assertEqual(app.index, 1)
            io.pressed = {"A"}
            app.update()
            self.assertTrue(get.call_args.args[0].endswith("?before=b"))
            io.pressed = {"C"}
            app.update()
            self.assertEqual(app.entries, first["entries"])
            self.assertEqual(get.call_count, 2)
            io.pressed = {"B"}
            app.update()
            count = load.call_count
            io.pressed = set()
            io.ticks += 30000
            app.update()
            self.assertEqual(load.call_count, count)
        app.entries = []
        app.index = -1
        for path in Path(app.CACHE_DIR).iterdir():
            path.unlink()
        io.ticks = 100000
        with patch.object(app, "urlopen", side_effect=OSError("offline")) as get:
            app.update()
            app.update()
            self.assertEqual(get.call_count, 1)
            self.assertEqual(app.status, "Fetch: offline")

    def test_centered_image_row(self):
        app = self.app
        app.photos = tuple(SimpleNamespace(width=w, height=h)
                           for w, h in [(50, 40), (40, 50), (50, 30)])
        with patch.object(app.screen, "blit") as blit:
            app.update()
        row = blit.call_args_list[:3]
        self.assertEqual([call.args[1:] for call in row], [(9, 31), (60, 26), (101, 36)])
        self.assertEqual(160 - (101 + 50), 9)

    def test_waits_for_wifi_before_loading_cached_gallery(self):
        app = self.app
        app.wlan = SimpleNamespace(isconnected=lambda: False)
        with patch.object(app, "advance") as advance:
            app.update()
            advance.assert_not_called()
            app.wlan.isconnected = lambda: True
            app.update()
            advance.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
