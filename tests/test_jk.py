"""Host checks for the archived joke app; hardware modules are stubbed."""

import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import Mock, patch


APP = Path(__file__).resolve().parents[1] / "badge25/apps/jk/__init__.py"


class JokeTests(unittest.TestCase):
    def setUp(self):
        self.screen = Mock(width=160, height=120)
        self.screen.measure_text.side_effect = lambda text: (len(text) * 6, 8)
        self.io = types.SimpleNamespace(ticks=0)
        self.urlopen = Mock()
        modules = {
            "network": types.ModuleType("network"),
            "urllib.urequest": types.SimpleNamespace(urlopen=self.urlopen),
            "badgeware": types.SimpleNamespace(
                screen=self.screen, io=self.io, PixelFont=Mock(),
                brushes=Mock(), run=Mock(),
            ),
        }
        self.font_files = ["ziplock.ppf", "nope.ppf", "ark.ppf", "MonaSans-Medium.af"]
        self.font_loader = modules["badgeware"].PixelFont.load
        with patch.dict(sys.modules, modules), patch("os.listdir", return_value=self.font_files):
            app = runpy.run_path(str(APP))
        self.app = app["update"].__globals__
        self.app["font_files"] = ["ark.ppf", "nope.ppf", "ziplock.ppf"]
        self.app["first_frame"] = False
        self.app["wlan"] = Mock()
        self.app["wlan"].isconnected.return_value = True

    def respond(self, jokes):
        response = Mock()
        response.read.return_value = json.dumps(jokes).encode()
        self.urlopen.return_value = response
        return response

    def frame(self, ticks):
        self.io.ticks = ticks
        self.screen.text.reset_mock()
        self.app["update"]()
        return [
            call.args[0] for call in self.screen.text.call_args_list
            if call.args[0] != self.app["font_name"]
        ]

    def test_font_cycle_and_bottom_right_label(self):
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.assertEqual(self.app["font_files"], ["ark.ppf", "nope.ppf", "ziplock.ppf"])
        for ticks, name in [(0, "ark"), (10000, "nope"), (20000, "ziplock"), (30000, "ark")]:
            self.frame(ticks)
            self.assertEqual(self.app["font_name"], name)
            self.assertEqual(self.screen.font, self.app["joke_font"])
            if name != "nope":
                self.font_loader.assert_called_with(self.app["FONT_DIR"] + name + ".ppf")
            self.screen.text.assert_any_call(name, 160 - len(name) * 6 - 3, 109)
            self.frame(ticks + 5000)
            self.assertEqual(self.app["font_name"], name)

    def test_font_scan_failure_and_empty_directory(self):
        expected = [name + ".ppf" for name in self.app["BUNDLED_FONTS"]]
        with patch("os.listdir", side_effect=OSError("cannot list fonts")):
            self.assertEqual(self.app["available_fonts"](), expected)
        with patch("os.listdir", return_value=["._broken.ppf", "other.af"]):
            self.assertEqual(self.app["available_fonts"](), expected)
        with patch("os.listdir", return_value=["nope.ppf"]):
            self.assertEqual(self.app["available_fonts"](), expected)

    def test_font_cycle_when_directory_scan_fails(self):
        self.app["font_files"] = []
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        with patch("os.listdir", side_effect=OSError("cannot list fonts")):
            self.frame(0)
        self.assertEqual(self.app["font_name"], "absolute")
        self.frame(5000)
        self.frame(10000)
        self.assertEqual(self.app["font_name"], "ark")
        self.frame(15000)
        self.frame(20000)
        self.assertEqual(self.app["font_name"], "awesome")

    def test_bundled_fonts_match_repository_assets(self):
        actual = sorted(path.stem for path in (APP.parents[2] / "assets/fonts").glob("*.ppf"))
        self.assertEqual(list(self.app["BUNDLED_FONTS"]), actual)

    def test_launcher_draws_before_network_or_font_scan(self):
        self.app["font_files"] = []
        self.app["first_frame"] = True
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        with patch("os.listdir", return_value=self.font_files) as scan:
            self.assertEqual(self.frame(0), ["Connecting Wi-Fi"])
            scan.assert_not_called()
            self.urlopen.assert_not_called()
            self.assertEqual(self.frame(1), ["Setup"])
            scan.assert_called_once_with(self.app["FONT_DIR"])
            self.assertEqual(self.app["font_files"], ["ark.ppf", "nope.ppf", "ziplock.ppf"])

    def test_unreadable_font_does_not_interrupt_joke(self):
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.font_loader.side_effect = OSError("bad font")
        self.assertEqual(self.frame(0), ["Setup"])
        self.assertEqual(self.app["font_name"], "nope")
        self.assertEqual(self.frame(5000), ["Setup", "Punch"])

    def test_drawing_does_not_require_font_getter(self):
        screen = self.screen

        class WriteOnlyFontScreen:
            @property
            def font(self):
                raise AttributeError("font is write-only")

            @font.setter
            def font(self, value):
                screen.font = value

            def __getattr__(self, name):
                return getattr(screen, name)

        self.app["screen"] = WriteOnlyFontScreen()
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.assertEqual(self.frame(0), ["Setup"])
        self.assertEqual(self.frame(5000), ["Setup", "Punch"])

    def test_timing_and_batch_refill(self):
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.assertEqual(self.frame(0), ["Setup"])
        self.assertEqual(self.frame(4999), ["Setup"])
        self.assertEqual(self.frame(5000), ["Setup", "Punch"])
        self.assertEqual(self.frame(9999), ["Setup", "Punch"])
        self.respond([{"setup": "Next", "punchline": "Answer"}])
        self.assertEqual(self.frame(10000), ["Next"])
        self.assertEqual(self.urlopen.call_count, 2)

    def test_random_selection_consumes_batch_without_replacement(self):
        self.respond([
            {"setup": "First", "punchline": "One"},
            {"setup": "Second", "punchline": "Two"},
        ])
        with patch.object(self.app["random"], "randrange", return_value=1):
            self.assertEqual(self.frame(0), ["Second"])
        self.frame(5000)
        self.assertEqual(self.frame(10000), ["First"])
        self.assertEqual(self.urlopen.call_count, 1)

    def test_wait_for_wifi_and_retry_failed_fetch(self):
        self.app["wlan"].isconnected.return_value = False
        self.assertEqual(self.frame(0), ["Connecting Wi-Fi"])
        self.urlopen.assert_not_called()
        self.app["wlan"].isconnected.return_value = True
        self.urlopen.side_effect = OSError("offline")
        self.assertEqual(self.frame(100), ["Jokes unavailable"])
        self.frame(30099)
        self.assertEqual(self.urlopen.call_count, 1)
        self.urlopen.side_effect = None
        self.respond([{"setup": "Recovered", "punchline": "OK"}])
        self.assertEqual(self.frame(30100), ["Recovered"])
        self.assertEqual(self.frame(35099), ["Recovered"])

    def test_invalid_batch_and_response_cleanup(self):
        response = self.respond([{}, {"setup": "Missing punch"}])
        with self.assertRaises(ValueError):
            self.app["fetch_jokes"]()
        response.close.assert_called_once()
        response.reset_mock()
        response.read.return_value = b"invalid json"
        with self.assertRaises(ValueError):
            self.app["fetch_jokes"]()
        response.close.assert_called_once()

    def test_wrapping_preserves_text_and_fits_width(self):
        text = "A setup with several words and " + "x" * 60
        lines = self.app["wrap_text"](text)
        self.assertTrue(all(len(line) * 6 <= 154 for line in lines))
        self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
