"""Run with: python -m unittest discover -s tools -p test_fishface.py"""

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch, mock_open

ROOT = Path(__file__).resolve().parents[1]


class FishFaceTests(unittest.TestCase):
    def setUp(self):
        screen = SimpleNamespace(clear=lambda: None, blit=lambda *a: None,
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

    def test_image_urls(self):
        from urllib.parse import parse_qs, urlsplit
        app = self.app
        entry = {"selfieUrl": "/api/media/selfie/" + "a" * 24,
                 "target": {"imageUrl": "/fish/fish-999.jpg"},
                 "match": {"imageUrl": "/api/media/fish/fish-005.jpg"}}
        for path in ("/api/media/fish/fish-005.jpg", "/fish/fish-005.jpg",
                     app.FISHFACE_SITE_URL + "/fish/fish-005.jpg"):
            entry["match"]["imageUrl"] = path
            query = parse_qs(urlsplit(app.image_url(entry, 1)).query)
            self.assertEqual(query["url"], [app.FISHFACE_SITE_URL + "/fish/fish-005.jpg"])
            self.assertEqual(query["output"], ["png"])
            self.assertEqual((query["w"], query["h"]), (["160"], ["76"]))
        entry["selfieUrl"] += "?a=1&b=two words"
        query = parse_qs(urlsplit(app.image_url(entry, 0)).query)
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
                        "match": {"imageUrl": "/fish/fish-005.jpg"}}]
        app.index = 0
        responses = [BytesIO(b"test image bytes"), BytesIO(b"match image bytes")]
        with patch.object(app, "urlopen", side_effect=responses) as get, \
                patch("builtins.open", mock_open()) as output, \
                patch.object(app.Image, "load") as load:
            app.load_photo()
            load.assert_called_once_with("/fishface-selfie.png")
            app.view = 1
            app.load_photo()
            self.assertEqual(get.call_count, 2)
            load.assert_called_with("/fishface-match.png")
        self.assertEqual([call.args[0] for call in output.call_args_list], list(app.SLIDE_PATHS))
        self.assertTrue(all(response.closed for response in responses))
        with patch.object(app.os, "remove") as remove:
            app.on_exit()
        self.assertEqual([call.args[0] for call in remove.call_args_list], list(app.SLIDE_PATHS))

    def test_badge_rotation_pagination_pause_and_retry(self):
        app, io = self.app, self.io
        app.wlan = SimpleNamespace(isconnected=lambda: True)
        first = {"entries": [{"id": "a", "fullName": "Alex"}, {"id": "b"}], "nextBefore": "b"}
        last = {"entries": [{"id": "c"}], "nextBefore": None}
        with patch.object(app, "urlopen", side_effect=lambda url: BytesIO(json.dumps(last if "before=" in url else first).encode())) as get, \
                patch.object(app, "load_photo") as load, \
                patch.object(app.screen, "text") as text:
            app.update()
            self.assertEqual((app.index, app.view), (0, 0))
            text.assert_called_with("Alex", 3, 1)
            for step in range(1, 6):
                io.ticks = step * 3000 - 1
                app.update()
                self.assertEqual((app.index, app.view), (0, (step - 1) % 2))
                io.ticks += 1
                app.update()
                self.assertEqual((app.index, app.view), (0, step % 2))
            io.ticks = 18000
            app.update()
            self.assertEqual((app.index, app.view), (1, 0))
            self.assertEqual(app.pair_step, 0)
            app.advance(True)
            self.assertTrue(get.call_args.args[0].endswith("?before=b"))
            app.advance(True)
            self.assertFalse("before=" in get.call_args.args[0])
            io.pressed = {"B"}
            app.update()
            count = load.call_count
            io.pressed = set()
            io.ticks += 20000
            app.update()
            self.assertEqual(load.call_count, count)
        app.entries = []
        app.index = -1
        io.ticks = 100000
        with patch.object(app, "urlopen", side_effect=OSError("offline")) as get:
            app.update()
            app.update()
            self.assertEqual(get.call_count, 1)
            self.assertEqual(app.status, "Fetch: offline")


if __name__ == "__main__":
    unittest.main()
