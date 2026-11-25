"""Automatic XY registration with four board tags and an axial tool tag."""
import math

import cv2
import numpy as np

from .hardware import build_camera
from .motion import Point
from .show import number
from .vision import aruco_markers

BOARD_IDS = (45, 46, 47, 48)
TOOL_ID = 49


def board_points(stage):
    # Cut-out tabs are 24 mm square, with an 18 mm black square.
    w, h = stage.width, stage.height
    if h <= 48:
        raise ValueError("使用四角标定码时棋盘高度须大于 48 mm")
    centers = [(-12, 12), (w+12, 12), (w+12, h-12), (-12, h-12)]
    return np.float32([(x+dx, y+dy, 0) for x, y in centers
                       for dx, dy in [(-9, 9), (9, 9), (9, -9), (-9, -9)]])


def board_pixels(tags):
    missing = set(BOARD_IDS).difference(tags)
    if missing:
        raise ValueError(f"棋盘定位码不可见 {sorted(missing)}")
    return np.float32([p for i in BOARD_IDS for p in tags[i]])


def lens_profile(stage, photos=(), *, frames=()):
    objects, images, size = [], [], None
    def load_photos():
        for path in photos:
            frame = cv2.imread(str(path))
            if frame is None:
                raise ValueError(f"无法读取 {path}")
            yield frame

    for frame in (load_photos() if photos else frames):
        dims = frame.shape[1::-1]
        if size and size != dims:
            raise ValueError("镜头标定照片分辨率不同")
        size = dims
        images.append(board_pixels(aruco_markers(frame)))
        objects.append(board_points(stage))
    if len(images) < 6:
        raise ValueError("至少提供六张不同倾角和位置的棋盘照片")
    rms, k, dist, rotations, _ = cv2.calibrateCamera(objects, images, size, None, None)
    if not math.isfinite(rms) or rms > 1.5 or not np.isfinite(k).all() or not np.isfinite(dist).all():
        raise ValueError(f"镜头标定误差 {rms:.2f} px，请重新拍摄")
    normals = np.array([cv2.Rodrigues(r)[0][:,2] for r in rotations])
    if np.max(np.linalg.norm(normals[:,None]-normals,axis=2)) < 0.25:
        raise ValueError("各张照片的棋盘倾角太接近，请从不同方向倾斜拍摄")
    return dict(size_px=list(size), matrix=k.tolist(), distortion=dist.ravel().tolist(), rms_px=rms)


class StageView:
    def __init__(self, stage, lens, read_frame):
        self.stage = stage
        self.read_frame = read_frame
        self.size = tuple(lens["size_px"])
        self.k = np.array(lens["matrix"], dtype=float)
        self.dist = np.array(lens["distortion"], dtype=float)
        if (self.k.shape != (3, 3) or not np.isfinite(self.k).all()
                or min(self.k[0, 0], self.k[1, 1]) <= 0
                or self.dist.size not in (4, 5, 8, 12, 14) or not np.isfinite(self.dist).all()):
            raise ValueError("镜头参数无效")
        if any(a.marker_id in (*BOARD_IDS, TOOL_ID) for a in stage.actors.values()):
            raise ValueError("自动模式下角色和道具请使用 ID 0–44")
        tags = self.snapshot()
        self.reference = board_pixels(tags)
        world = board_points(stage)
        ok, r, t = cv2.solvePnP(world, self.reference, self.k, self.dist)
        if not ok:
            raise ValueError("棋盘姿态无法确定")
        expected = cv2.projectPoints(world, r, t, self.k, self.dist)[0].reshape(-1, 2)
        if np.linalg.norm(expected-self.reference, axis=1).max() > 3:
            raise ValueError("棋盘码位置与打印尺寸、朝向或镜头参数不符")
        self.inverse_rotation = cv2.Rodrigues(r)[0].T
        self.eye = (-self.inverse_rotation @ t).ravel()
        if self.eye[2] <= 0:
            raise ValueError("棋盘朝向异常")

    def snapshot(self):
        frame = self.read_frame()
        if frame.shape[1::-1] != self.size:
            raise ValueError("视频分辨率与镜头档案不一致")
        return aruco_markers(frame)

    def read(self):
        tags = self.snapshot()
        if np.linalg.norm(board_pixels(tags)-self.reference, axis=1).max() > 3:
            raise ValueError("手机或棋盘已移动，请重新开场标定")
        return tags

    def on_plane(self, pixels, height):
        rays = cv2.undistortPoints(np.array(pixels, dtype=float).reshape(-1,1,2),
                                   self.k, self.dist).reshape(-1,2)
        directions = np.column_stack((rays, np.ones(len(rays)))) @ self.inverse_rotation.T
        if height >= self.eye[2] or np.any(directions[:, 2] >= -1e-6):
            raise ValueError("标记高度或镜头姿态不合理")
        return (self.eye + directions * ((height-self.eye[2])/directions[:,2:3]))[:,:2]

    def tool(self, height):
        tags = self.read()
        if TOOL_ID not in tags:
            raise ValueError("未看到吸盘码 49")
        corners = self.on_plane(tags[TOOL_ID], height)
        sides = np.linalg.norm(corners-np.roll(corners, 1, axis=0), axis=1)
        if np.max(abs(sides-18)) > 2:
            raise ValueError("吸盘码尺寸、朝向或码面高度异常")
        return corners.mean(axis=0)

    def camera(self, tags_provider=None):
        # Existing actor logic handles pickup offsets and card rotation in board mm.
        def measured():
            return {i: self.on_plane(q, 0).tolist() for i,q in (tags_provider or self.read)().items()}
        unit = [[0,0],[1,0],[1,1],[0,1]]
        return build_camera(self.stage, {"camera":{"corners_px":unit,"corners_mm":unit}}, measured)


def register_xy(robot, view, arm, options):
    high = number(arm["high_z_mm"], "high_z_mm")
    low = number(arm["low_z_mm"], "low_z_mm")
    offset = number(options["tag_height_at_low_mm"], "tag_height_at_low_mm")
    span = number(options["sample_span_mm"], "sample_span_mm")
    x, y, z, _ = robot.pose()
    if high <= low or offset <= 0 or span <= 0 or abs(z-high) > .5:
        raise ValueError("从已设定的安全高位开始，检查高低 Z、码面高度与采样边长")
    offsets = [(0,0),(span,0),(span,span),(0,span),(span/2,span/2)]
    targets = [(x+dx,y+dy,high) for dx,dy in offsets]
    for start, end in zip(targets, targets[1:]):
        robot.check_segment(start, end)
    board, actual = [], []
    for i, target in enumerate(targets):
        if i:
            robot.move_xyz(*target)
        ax, ay, az, _ = robot.pose()
        if math.dist((ax,ay,az), target) > 1:
            raise ValueError("标定采样点未到位")
        board.append(view.tool(offset+az-low))
        actual.append((ax,ay))
    # Rigid planar fit preserves physical millimetres across the entire stage.
    a, b = np.array(board[:4]), np.array(actual[:4])
    u, _, vt = np.linalg.svd((a-a.mean(0)).T @ (b-b.mean(0)))
    rot = u @ vt
    shift = b.mean(0)-a.mean(0) @ rot
    errors = np.linalg.norm(np.array(board) @ rot + shift - actual, axis=1)
    if np.linalg.det(rot) < 0 or errors.max() > view.stage.tolerance:
        raise ValueError(f"自动标定复核失败，最大残差 {errors.max():.2f} mm")
    robot.check_segment(targets[-1], targets[0])
    robot.move_xyz(*targets[0])
    return [{"board_mm":p.tolist(), "arm_mm":(p @ rot + shift).tolist()} for p in a]
