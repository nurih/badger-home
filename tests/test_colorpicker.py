"""Host checks for the archived Badge25 color picker."""

from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


APP = Path(__file__).resolve().parents[1] / "badge25/lib/colorpicker.py"


class ColorPickerTests(unittest.TestCase):
    def setUp(self):
        self.views = []
        self.screen = Mock(width=160, height=120, font="caller font", brush="caller brush")

        def window(*args):
            view = Mock(width=160, height=120)
            view.measure_text.side_effect = lambda text: (len(text) * 5, 8)
            self.views.append(view)
            return view

        self.screen.window.side_effect = window
        self.io = SimpleNamespace(pressed=set(), BUTTON_A="A", BUTTON_B="B", BUTTON_C="C",
                                  BUTTON_UP="UP", BUTTON_DOWN="DOWN")
        badgeware = SimpleNamespace(screen=self.screen, io=self.io, PixelFont=Mock(),
                                    brushes=SimpleNamespace(color=lambda *rgb: SimpleNamespace(rgb=rgb)),
                                    shapes=SimpleNamespace(rectangle=lambda *args: args))
        with patch.dict(sys.modules, {"badgeware": badgeware}):
            self.Picker = runpy.run_path(str(APP))["ColorPicker"]

    def test_confirm_returns_brush_and_stops(self):
        picker = self.Picker((10, 20, 30))
        self.assertTrue(picker.busy)
        self.assertEqual(picker.pick().rgb, (10, 20, 30))
        self.io.pressed = {"B", "UP"}
        self.assertEqual(picker.pick().rgb, (10, 20, 30))
        self.assertFalse(picker.busy)
        self.views[0].clear.reset_mock()
        self.io.pressed = {"UP"}
        self.assertEqual(picker.pick().rgb, (10, 20, 30))
        self.views[0].clear.assert_not_called()
        picker.start()
        self.assertTrue(picker.busy)
        self.assertEqual(picker.pick().rgb, (15, 20, 30))
        self.io.pressed = {"B"}
        self.assertEqual(picker.pick().rgb, (15, 20, 30))

    def test_channel_navigation_wraps_and_changes_one_value(self):
        picker = self.Picker((10, 20, 30))
        for pressed in ({"A", "UP"}, {"C", "DOWN"}, {"C", "UP"}):
            self.io.pressed = pressed
            picker.pick()
            self.assertTrue(picker.busy)
        self.io.pressed = {"B"}
        self.assertEqual(picker.pick().rgb, (5, 25, 35))

    def test_step_rounding_and_endpoint_wrap(self):
        cases = ((0, "DOWN", 255), (255, "UP", 0),
                 (250, "UP", 255), (255, "DOWN", 250),
                 (5, "UP", 10), (5, "DOWN", 0),
                 (4, "UP", 5), (4, "DOWN", 255),
                 (1, "DOWN", 255), (254, "UP", 255))
        for start, button, expected in cases:
            with self.subTest(start=start, button=button):
                picker = self.Picker((start, 0, 0))
                self.io.pressed = {button}
                picker.pick()
                self.io.pressed = {"B"}
                self.assertEqual(picker.pick().rgb, (expected, 0, 0))

    def test_initial_value_rounds_down_and_no_direction_keeps_it(self):
        picker = self.Picker((7, 0, 0))
        self.assertEqual(picker.pick().rgb, (5, 0, 0))
        self.io.pressed = {"UP", "DOWN"}
        self.assertEqual(picker.pick().rgb, (5, 0, 0))

    def test_instances_and_caller_state_are_independent(self):
        initial = [10, 20, 30]
        first = self.Picker(initial)
        second = self.Picker(initial)
        self.io.pressed = {"UP"}
        first.pick()
        self.assertEqual(initial, [10, 20, 30])
        self.io.pressed = {"B"}
        self.assertEqual(first.pick().rgb, (15, 20, 30))
        self.assertEqual(second.pick().rgb, (10, 20, 30))
        self.assertEqual(self.screen.font, "caller font")
        self.assertEqual(self.screen.brush, "caller brush")
        self.assertIsNot(self.views[0], self.views[1])

    def test_preview_and_channel_labels(self):
        picker = self.Picker((10, 20, 30))
        colors = []
        self.views[0].clear.side_effect = lambda: colors.append(self.views[0].brush.rgb)
        self.io.pressed = {"A", "UP"}
        picker.pick()
        self.assertEqual(colors, [(10, 25, 30)])
        self.views[0].text.assert_any_call("G:", 4, 43)

    def test_complement_tracks_selection_and_confirmation(self):
        picker = self.Picker((0, 128, 255))
        self.assertEqual(picker.complement.rgb, (255, 130, 0))
        self.io.pressed = {"UP"}
        picker.pick()
        self.assertEqual(picker.complement.rgb, (250, 130, 0))
        self.io.pressed = {"B"}
        picker.pick()
        self.assertEqual(picker.complement.rgb, (250, 130, 0))


if __name__ == "__main__":
    unittest.main()
