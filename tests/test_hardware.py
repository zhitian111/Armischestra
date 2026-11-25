import unittest
from pathlib import Path
from unittest.mock import patch

from armischestra.hardware import build_camera, run_hardware
from armischestra.motion import Point
from armischestra.show import Move, Show, load_json, load_stage


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class HardwareTest(unittest.TestCase):
    def setUp(self):
        self.stage = load_stage(EXAMPLES / "stage.json")
        self.calibration = load_json(EXAMPLES / "hardware.template.json")
        self.calibration["camera"] = {
            "corners_px": [[0, 0], [600, 0], [600, 400], [0, 400]],
            "corners_mm": [[0, 200], [300, 200], [300, 0], [0, 0]],
        }

    def test_camera_without_arm_calibration(self):
        frame = {1: [(80, 230), (120, 230), (120, 270), (80, 270)]}
        camera = build_camera(self.stage, self.calibration, lambda: frame)
        self.assertEqual(camera.locate("艾露猫"), Point(50, 75))

    def test_show_with_callback_devices_takes_fresh_images(self):
        self.calibration["arm"] = {
            "high_z_mm": -10, "low_z_mm": -27,
            "pairs": [{"board_mm": xy, "arm_mm": xy} for xy in ([0, 0], [300, 0], [0, 200])],
            "grip_seconds": 1.5, "release_seconds": 0.2, "blow_seconds": 0,
        }
        frames = iter([
            {1: [(80, 230), (120, 230), (120, 270), (80, 270)]},
            {1: [(180, 230), (220, 230), (220, 270), (180, 270)]},
        ])
        xy = Point(1, 2)
        actions = []

        def move_xyz(x, y, z):
            nonlocal xy
            xy = Point(x, y)
            actions.append((x, y, z))

        observed_at = []

        def read_frame():
            observed_at.append(xy)
            return next(frames)

        show = Show("试演", (Move("艾露猫", Point(100, 75), ()),))
        with patch("armischestra.hardware.aruco_markers", side_effect=lambda markers: markers) as detect:
            run_hardware(self.stage, show, self.calibration, read_xy=lambda: xy,
                         move_xyz=move_xyz, set_pump=actions.append, read_frame=read_frame,
                         cue=actions.append, wait=actions.append)
        self.assertEqual(detect.call_count, 2)
        self.assertEqual(observed_at, [Point(1, 2), Point(100, 75)])
        self.assertEqual(actions[:2], [(1, 2, -10), (50, 75, -10)])
        self.assertEqual(actions[actions.index("suck") + 1], 1.5)
        self.assertEqual(actions[actions.index("release") - 1], (100, 75, -27))
