import unittest

from armischestra.motion import AffineMap, HardwareArm, Motion, Point


class MotionTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.xy = Point(300, -10)
        self.fail_at = None
        calibration = [
            (Point(0, 0), Point(100, 25)),
            (Point(0, 40), Point(60, 25)),
            (Point(60, 0), Point(100, 85)),
            (Point(20, 20), Point(80, 45)),
        ]
        self.mapping = AffineMap.fit(calibration)
        self.arm = HardwareArm(
            self.mapping, high_z=80, low_z=70,
            read_xy=lambda: self.xy, move_xyz=self.move_xyz,
            set_pump=lambda mode: self.calls.append(mode),
        )
        self.motion = Motion(
            self.arm, 100, 100, grip_seconds=1, release_seconds=2, blow_seconds=0.2,
            wait=lambda sec: self.calls.append(("wait", sec)),
        )

    def move_xyz(self, x, y, z):
        self.calls.append((x, y, z))
        if (x, y, z) == self.fail_at:
            raise RuntimeError("driver failure")
        self.xy = Point(x, y)

    def test_first_move_is_vertical_and_carry_uses_board_frame(self):
        self.motion.carry(Point(10, 10), Point(30, 20), via=[Point(20, 15)])
        self.assertEqual(self.calls, [
            (300, -10, 80), (90, 35, 80), (90, 35, 70), "suck", ("wait", 1),
            (90, 35, 80), (85, 45, 80), (80, 55, 80), (80, 55, 70),
            "blow", ("wait", 0.2), "release", ("wait", 2), (80, 55, 80),
        ])

    def test_reject_outside_waypoint_before_pick(self):
        with self.assertRaises(ValueError):
            self.motion.carry(Point(10, 10), Point(30, 20), via=[Point(-1, 0)])
        self.assertEqual(self.calls, [])

    def test_driver_failure_stops_script_while_holding(self):
        self.fail_at = (80, 55, 80)
        with self.assertRaisesRegex(RuntimeError, "driver failure"):
            self.motion.carry(Point(10, 10), Point(30, 20))
        self.assertIn("suck", self.calls)
        self.assertNotIn("release", self.calls)
        with self.assertRaises(RuntimeError):
            self.arm.move_xy(0, 0)

    def test_collinear_calibration_rejected_in_either_frame(self):
        row = [Point(5, 5), Point(10, 10), Point(15, 15)]
        triangle = [Point(0, 0), Point(5, 0), Point(0, 5)]
        for pairs in (zip(row, triangle), zip(triangle, row)):
            with self.assertRaises(ValueError):
                AffineMap.fit(pairs)

    def test_hardware_push_tracks_measured_tab_at_contact_z_without_suction(self):
        self.motion.push(Point(20,10), Point(40,10), 8)
        self.assertEqual(self.calls, [
            (300,-10,80), (90,37,80), "release", (90,37,70), (90,57,70), (90,57,80)
        ])
