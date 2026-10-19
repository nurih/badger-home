"""Host checks for the archived joke app; hardware modules are stubbed."""

import json
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import Mock, patch


APP = Path(__file__).resolve().parent / "__init__.py"


class JokeTests(unittest.TestCase):
    def setUp(self):
        self.screen = Mock(width=160, height=120)
        self.screen.window.return_value = Mock(width=160, height=120)
        self.screen.window.return_value.measure_text.side_effect = lambda text: (len(text) * 6, 8)
        self.screen.measure_text.side_effect = lambda text: (len(text) * 6, 8)
        self.io = types.SimpleNamespace(ticks=0, pressed=set(), BUTTON_A="A", BUTTON_B="B",
                                        BUTTON_C="C", BUTTON_UP="UP", BUTTON_DOWN="DOWN")
        self.urlopen = Mock()
        modules = {
            "network": types.ModuleType("network"),
            "urllib.urequest": types.SimpleNamespace(urlopen=self.urlopen),
            "badgeware": types.SimpleNamespace(
                screen=self.screen, io=self.io, PixelFont=Mock(),
                brushes=types.SimpleNamespace(color=lambda *rgb: rgb), run=Mock(),
                shapes=types.SimpleNamespace(rectangle=lambda *args: args),
            ),
        }
        self.font_loader = modules["badgeware"].PixelFont.load
        with patch.dict(sys.modules, modules):
            picker_module = types.ModuleType("colorpicker")
            picker_module.ColorPicker = runpy.run_path(str(APP.parents[2] / "lib/colorpicker.py"))["ColorPicker"]
            with patch.dict(sys.modules, {"colorpicker": picker_module}):
                app = runpy.run_path(str(APP))
        self.app = app["update"].__globals__
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
        ]

    def test_smart_font_stays_fixed_without_label(self):
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        font = self.screen.font
        for ticks in (0, 10000, 20000):
            self.assertEqual(self.frame(ticks), ["Setup"])
            self.assertEqual(self.frame(ticks + 5000), ["Setup", "Punch"])
            self.assertIs(self.screen.font, font)
        self.font_loader.assert_called_once_with("/system/assets/fonts/smart.ppf")

    def test_launcher_draws_before_network(self):
        self.app["first_frame"] = True
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.assertEqual(self.frame(0), ["Connecting Wi-Fi"])
        self.urlopen.assert_not_called()
        self.assertEqual(self.frame(1), ["Setup"])

    def test_picker_changes_background_and_pauses_joke_timer(self):
        self.respond([{"setup": "Setup", "punchline": "Punch"}])
        self.frame(0)
        font = self.screen.font
        self.io.pressed = {"B"}
        self.frame(1000)
        self.assertTrue(self.app["colorpicker"].busy)
        self.io.pressed = {"UP"}
        self.frame(11000)
        self.assertFalse(self.app["show_punch"])
        self.assertEqual(self.urlopen.call_count, 1)
        self.io.pressed = {"B"}
        backgrounds = []
        self.screen.clear.side_effect = lambda: backgrounds.append(self.screen.brush)
        self.assertEqual(self.frame(12000), ["Setup"])
        self.assertEqual(backgrounds, [(5, 0, 0)])
        self.assertEqual(self.app["background_color"], (5, 0, 0))
        self.assertFalse(self.app["colorpicker"].busy)
        self.assertIs(self.screen.font, font)
        self.io.pressed = set()
        self.assertEqual(self.frame(15999), ["Setup"])
        self.assertEqual(self.frame(16000), ["Setup", "Punch"])
        self.io.pressed = {"B"}
        self.frame(17000)
        self.io.pressed = {"B"}
        self.frame(17001)
        self.assertEqual(self.app["background_color"], (5, 0, 0))

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
