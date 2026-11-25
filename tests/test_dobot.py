import unittest
from unittest.mock import Mock, call, patch

from armischestra.dobot import Device, Dobot, fresh_frame


def configuration():
    return {"host": "127.0.0.1", "camera_source": 0, "tool_index": 2, "user_index": 0,
            "speed_l_percent": 10, "command_timeout_s": 30,
            "suction": {"bank": "tool", "index": 1, "active_level": 0},
            "blow": {"bank": "controller", "index": 3, "active_level": 1}}


class DobotTest(unittest.TestCase):
    def setUp(self):
        self.dashboard = Mock()
        self.move = Mock()
        self.robot = Dobot(self.dashboard, self.move, Device.parse(configuration()))
        self.dashboard.RobotMode.return_value = "0,{5},RobotMode();"
        self.dashboard.GetPose.return_value = "0,{100,60,-25,42},GetPose();"
        self.dashboard.User.return_value = "0,{},User(0);"
        self.dashboard.Tool.return_value = "0,{},Tool(2);"
        self.dashboard.ResetRobot.return_value = "0,{},ResetRobot();"
        self.move.MovL.return_value = "0,{},MovL(10,20,30,42,SpeedL=10);"
        self.move.Sync.return_value = "0,{},Sync();"

    def test_holds_orientation_and_waits_until_queue_finishes(self):
        self.robot.prepare()
        self.robot.move_xyz(10, 20, 30)
        self.assertEqual(self.move.mock_calls, [call.Sync(), call.MovL(10, 20, 30, 42., "SpeedL=10"),
                                               call.Sync()])
        self.assertEqual(self.robot.read_xy().x, 100)

    def test_unconfirmed_motion_or_controller_error_attempts_stop(self):
        self.robot.prepare()
        for reply in ("0,{", "-1,{},Sync();", b"", "0,{},Other();"):
            self.move.Sync.return_value = reply
            with self.assertRaisesRegex(RuntimeError, "Sync"):
                self.robot.move_xyz(10, 20, 30)
        self.assertEqual(self.dashboard.ResetRobot.call_count, 4)

    def test_output_polarity_and_order(self):
        self.dashboard.ToolDOExecute.side_effect = lambda i, v: f"0,{{}},ToolDOExecute({i},{v});"
        self.dashboard.DOExecute.side_effect = lambda i, v: f"0,{{}},DOExecute({i},{v});"
        for mode in ("suck", "blow", "release"):
            self.robot.set_pump(mode)
        self.assertEqual(self.dashboard.mock_calls,
                         [call.DOExecute(3, 0), call.ToolDOExecute(1, 0),
                          call.ToolDOExecute(1, 1), call.DOExecute(3, 1),
                          call.ToolDOExecute(1, 1), call.DOExecute(3, 0)])

    def test_disabled_robot_stops_before_queue(self):
        self.dashboard.RobotMode.return_value = "0,{4},RobotMode();"
        with self.assertRaisesRegex(RuntimeError, "RobotMode=4"):
            self.robot.prepare()
        self.move.Sync.assert_not_called()

    def test_frame_is_acquired_from_a_new_capture_after_parking(self):
        cv2 = Mock()
        first, second = Mock(), Mock()
        cv2.VideoCapture.side_effect = [first, second]
        for capture, frame in [(first, "before"), (second, "after")]:
            capture.read.return_value = True, frame
        with patch.dict("sys.modules", {"cv2": cv2}):
            self.assertEqual([fresh_frame(0), fresh_frame(0)], ["before", "after"])
        for capture in (first, second):
            self.assertEqual(capture.mock_calls,
                             [call.isOpened(), call.grab(), call.read(), call.release()])
