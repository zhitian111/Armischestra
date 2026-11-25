import unittest

from armischestra.vision import BoardMap, MarkerCamera, MarkerSpec, aruco_markers


def project(point):
    """An oblique pinhole view of the planar stage, with image y down."""
    x, y = point
    depth = 1 + x/200 + y/300
    return ((2*x + y + 240)/depth, (300 - 2*y)/depth)


class VisionTest(unittest.TestCase):
    def setUp(self):
        board = [(0, 0), (160, 0), (160, 120), (0, 120)]
        self.mapping = BoardMap.from_corners([project(p) for p in board], board)

    def test_perspective_and_rotated_offset(self):
        # Center (40, 40), marker +right points along board +y.
        corners = [(35, 35), (35, 45), (45, 45), (45, 35)]
        camera = MarkerCamera(
            self.mapping, {"艾露猫": MarkerSpec(3, (5, 2))},
            lambda: {3: [project(p) for p in corners]},
        )
        x, y = camera.locate("艾露猫")
        self.assertAlmostEqual(x, 38)
        self.assertAlmostEqual(y, 45)

    def test_missing_actor_never_reuses_old_position(self):
        corners = [(0, 10), (10, 10), (10, 0), (0, 0)]
        frames = iter([{1: [project(p) for p in corners]}, {}])
        camera = MarkerCamera(self.mapping, {"黑龙": MarkerSpec(1)}, lambda: next(frames))
        self.assertAlmostEqual(camera.locate("黑龙")[0], 5)
        with self.assertRaisesRegex(ValueError, "黑龙"):
            camera.locate("黑龙")

    def test_invalid_calibration(self):
        points = [(0, 0), (1, 1), (2, 2), (3, 3)]
        with self.assertRaises(ValueError):
            BoardMap.from_corners(points, points)

    def test_synthetic_aruco_photo(self):
        try:
            import cv2
            import numpy as np
            from cv2.aruco import generateImageMarker
        except ImportError:
            self.skipTest("optional OpenCV ArUco module not installed")
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        image = np.full((200, 200), 255, dtype=np.uint8)
        image[50:150, 50:150] = generateImageMarker(dictionary, 8, 100)
        self.assertEqual(set(aruco_markers(image)), {8})
