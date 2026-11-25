import math
import unittest
from unittest.mock import Mock, patch

try:
    import cv2
    import numpy as np
    from armischestra.registration import StageView, board_points, lens_profile, register_xy
except ImportError:
    cv2 = None

from armischestra.dobot import check_show
from armischestra.motion import Point
from armischestra.show import Actor, Move, Show, Stage


@unittest.skipUnless(cv2, "requires OpenCV")
class RegistrationTest(unittest.TestCase):
    def setUp(self):
        self.stage = Stage(300,200,25,Point(10,10),2,
                           {"cat":Actor(Point(100,60),1,Point(0,0))})
        self.pose = [200,80,40,0]
        self.robot = Mock()
        self.robot.pose.side_effect = lambda: self.pose
        self.robot.move_xyz.side_effect = lambda x,y,z: self.pose.__setitem__(slice(3),(x,y,z))
        self.k = np.array([[1100.,0,640],[0,1100,480],[0,0,1]])
        self.lens = dict(size_px=[1280,960],matrix=self.k.tolist(),distortion=[0]*5)
        self.frame = np.zeros((960,1280),np.uint8)
        self.shift = 0

    def project(self, points):
        return cv2.projectPoints(np.array(points,dtype=float), np.array([2.9,.12,.1]),
                                 np.array([-130.,100.,650.]), self.k,None)[0].reshape(-1,2)

    def tags(self, _frame):
        corners = self.project(board_points(self.stage))+self.shift
        tags = dict(zip(range(45,49), corners.reshape(4,4,2)))
        for i,x,y,z in [(49,self.pose[0]-140,self.pose[1]-20,60),(1,100,60,0)]:
            tags[i] = self.project([(x+a,y+b,z) for a,b in [(-9,9),(9,9),(9,-9),(-9,-9)]])
        return tags

    def test_lens_from_rendered_markers_at_different_tilts(self):
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        src = np.float32([[0,0],[119,0],[119,119],[0,119]])
        frames = []
        for i in range(10):
            frame = np.full((960,1280),255,np.uint8)
            corners = cv2.projectPoints(board_points(self.stage),
                        np.array([2.65+i*.07, .24*math.cos(i), .38*math.sin(i)]),
                        np.array([-150.+40*math.sin(i),80.+45*math.cos(i),490.+5*i]),
                        self.k,None)[0].reshape(4,4,2)
            for tag,dst in enumerate(corners,45):
                code = cv2.aruco.generateImageMarker(dictionary,tag,120)
                warp = cv2.warpPerspective(code,cv2.getPerspectiveTransform(src,dst),
                                           (1280,960),borderValue=255)
                frame = cv2.min(frame,warp)
            frames.append(frame)
        profile = lens_profile(self.stage, frames=frames)
        self.assertLess(profile["rms_px"],1)
        self.assertLess(abs(profile["matrix"][0][0]/1100-1),.1)

    def test_oblique_camera_high_tool_registration_and_drift(self):
        with patch("armischestra.registration.aruco_markers", self.tags):
            view = StageView(self.stage,self.lens,lambda:self.frame)
            arm = dict(high_z_mm=40,low_z_mm=0,grip_seconds=0,release_seconds=0,blow_seconds=0)
            pairs = register_xy(self.robot,view,arm,dict(sample_span_mm=50,tag_height_at_low_mm=20))
            for pair in pairs:
                x,y = pair["board_mm"]
                self.assertLess(math.dist(pair["arm_mm"],(x+140,y+20)),.001)
            p = view.camera().locate("cat")
            self.assertLess(math.dist((p.x,p.y),(100,60)),.001)
            self.shift = 8
            with self.assertRaisesRegex(ValueError,"已移动"):
                view.read()
            self.robot.check_segment.side_effect = ValueError("不可达")
            with self.assertRaisesRegex(ValueError,"第 1 步"):
                check_show(self.robot,self.stage,Show("test",(Move("cat",Point(150,50),()),)),
                           {"arm":dict(arm,pairs=pairs)},{"cat":p})
