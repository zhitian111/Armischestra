"""MG400/M1Pro adapter for the official TCP-IP-4Axis-Python SDK."""

from __future__ import annotations

import importlib.util
import math
import re
from contextlib import ExitStack, closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .hardware import build_camera, build_motion
from .motion import Point
from .show import Move, check_push_capability, number, perform
from .vision import aruco_markers


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} 必须是 {low} 到 {high} 之间的整数")
    return value


@dataclass(frozen=True)
class Valve:
    bank: str
    index: int
    active_level: int

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw, dict) or raw.get("bank") not in ("controller", "tool"):
            raise ValueError("请填写阀门的输出类型 controller 或 tool")
        return cls(raw["bank"], _integer(raw.get("index"), 1, 24, "阀门输出编号"),
                   _integer(raw.get("active_level"), 0, 1, "阀门有效电平"))

    def switch(self, dashboard, on):
        write = dashboard.ToolDOExecute if self.bank == "tool" else dashboard.DOExecute
        _result(write(self.index, self.active_level if on else 1 - self.active_level),
                "ToolDOExecute" if self.bank == "tool" else "DOExecute")


@dataclass(frozen=True)
class Device:
    host: str
    source: int | str
    camera_size: tuple[int, int] | None
    user: int
    tool: int
    speed: int
    timeout: float
    suction: Valve
    blow: Valve | None

    @classmethod
    def parse(cls, raw):
        host = raw["host"]
        if not isinstance(host, str) or not host.strip():
            raise ValueError("请填写 Dobot 控制器地址 host")
        source = raw["camera_source"]
        usb = type(source) is int and source >= 0
        url = (isinstance(source, str) and urlsplit(source).scheme in ("rtsp", "http", "https")
               and urlsplit(source).hostname)
        if not (usb or url):
            raise ValueError("camera_source 应为摄像头编号或实时视频流 URL")
        suction = Valve.parse(raw["suction"])
        blow = Valve.parse(raw["blow"]) if raw.get("blow") is not None else None
        if blow and (suction.bank, suction.index) == (blow.bank, blow.index):
            raise ValueError("吸气和吹气阀门不能共用一个输出")
        timeout = number(raw["command_timeout_s"], "command_timeout_s")
        if timeout <= 0:
            raise ValueError("command_timeout_s 必须大于零")
        size = raw.get("camera_size_px")
        if size is not None and (not isinstance(size, list) or len(size) != 2 or
                                 not all(type(n) is int and n > 0 for n in size)):
            raise ValueError("camera_size_px 应为 [标定图像宽度, 标定图像高度]")
        return cls(host.strip(), source, tuple(size) if size else None,
                   _integer(raw["user_index"], 0, 9, "user_index"),
                   _integer(raw["tool_index"], 0, 9, "tool_index"),
                   _integer(raw["speed_l_percent"], 1, 100, "speed_l_percent"),
                   timeout, suction, blow)


def _result(reply, command):
    # The SDK returns the raw controller string and can return an empty value
    # on socket errors. Match a complete reply, including the echoed command.
    pattern = r"\s*(-?\d+),\s*\{([^{}]*)\},\s*(\w+)\([^;]*\)\s*;\s*"
    match = re.fullmatch(pattern, reply) if isinstance(reply, str) else None
    if not match or match[3].lower() != command.lower():
        raise RuntimeError(f"Dobot {command} 应答无效：{reply!r}")
    if int(match[1]) != 0:
        raise RuntimeError(f"Dobot {command} 返回错误码 {match[1]}")
    return match[2].strip()


def load_sdk(sdk_dir):
    file = Path(sdk_dir) / "dobot_api.py"
    if not file.is_file():
        raise ValueError(f"在 SDK 目录中找不到 {file}")
    spec = importlib.util.spec_from_file_location("armischestra_dobot_sdk", file)
    sdk = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(sdk)
    except ImportError as exc:
        raise RuntimeError(f"Dobot SDK 需要 NumPy 和 Python Tk 支持：{exc}") from exc
    return sdk


class Dobot:
    def __init__(self, dashboard, move, device):
        self.dashboard = dashboard
        self.move = move
        self.device = device
        self.rotation = None

    def pose(self):
        fields = _result(self.dashboard.GetPose(), "GetPose").split(",")
        pose = tuple(float(v) for v in fields)
        if len(pose) != 4 or not all(math.isfinite(v) for v in pose):
            raise ValueError("GetPose 应返回有限的 X、Y、Z、R")
        return pose

    def prepare(self):
        mode = _result(self.dashboard.RobotMode(), "RobotMode")
        if mode != "5":
            raise RuntimeError(f"控制器须处于已使能且空闲状态，当前 RobotMode={mode}")
        _result(self.dashboard.User(self.device.user), "User")
        _result(self.dashboard.Tool(self.device.tool), "Tool")
        _result(self.move.Sync(), "Sync")
        self.rotation = self.pose()[3]

    def read_xy(self):
        x, y, _, _ = self.pose()
        return Point(x, y)

    def move_xyz(self, x, y, z):
        if self.rotation is None:
            raise RuntimeError("尚未读取吸盘的初始朝向")
        try:
            _result(self.move.MovL(x, y, z, self.rotation, f"SpeedL={self.device.speed}"), "MovL")
            _result(self.move.Sync(), "Sync")
        except (Exception, KeyboardInterrupt) as exc:
            # A missing reply does not tell us whether the move was accepted.
            # Stop via the independent dashboard channel before ending the show.
            try:
                _result(self.dashboard.ResetRobot(), "ResetRobot")
            except Exception as stop_error:
                raise RuntimeError(f"移动中断，控制器未确认停止：{stop_error}") from exc
            raise

    def check_segment(self, start, end):
        count = max(1, math.ceil(math.dist(start, end) / 10))
        for i in range(count+1):
            xyz = tuple(a+(b-a)*i/count for a,b in zip(start,end))
            reply = self.dashboard.InverseSolution(*xyz, self.rotation, self.device.user, self.device.tool)
            try:
                joints = [float(v) for v in _result(reply, "InverseSolution").split(",")]
                if len(joints) != 4 or not all(math.isfinite(v) for v in joints):
                    raise ValueError("关节解无效")
            except (RuntimeError, ValueError) as exc:
                raise ValueError(f"无法确认位置 {xyz} 可达：{exc}") from exc

    def set_pump(self, mode):
        if mode not in ("suck", "release", "blow"):
            raise ValueError(f"未知气泵模式 {mode}")
        if mode == "blow" and not self.device.blow:
            raise ValueError("吹气需要配置吹气阀门")
        # Deactivate the opposing valve before energizing a valve.
        if mode == "suck":
            if self.device.blow:
                self.device.blow.switch(self.dashboard, False)
            self.device.suction.switch(self.dashboard, True)
        else:
            self.device.suction.switch(self.dashboard, False)
            if self.device.blow:
                self.device.blow.switch(self.dashboard, mode == "blow")


def fresh_frame(source, size=None):
    """Start acquisition after the current move to avoid reusing a pre-motion frame."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("读取设备摄像头需要 OpenCV") from exc
    capture = cv2.VideoCapture(source)
    try:
        if not capture.isOpened():
            raise RuntimeError("无法打开实时相机")
        if size and isinstance(source, int):
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        # Drop the first frame from USB/phone startup buffers.
        if not capture.grab():
            raise RuntimeError("实时相机未提供画面")
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError("实时相机未提供新画面")
        if size and frame.shape[:2] != (size[1], size[0]):
            raise RuntimeError(f"实时画面为 {frame.shape[1]}×{frame.shape[0]}，与标定图像 {size} 不符")
        return frame
    finally:
        capture.release()


def check_show(robot, stage, show, calibration, positions):
    current = robot.pose()[:3]

    def check_move(x, y, z):
        nonlocal current
        robot.check_segment(current, (x,y,z))
        current = (x,y,z)

    motion = build_motion(stage, calibration, read_xy=lambda: Point(*current[:2]),
                          move_xyz=check_move, set_pump=lambda mode: None, wait=lambda t: None)
    positions = positions.copy()
    for i, step in enumerate(show.steps, 1):
        if isinstance(step, Move):
            try:
                if step.method == "push":
                    motion.push(positions[step.actor], step.to, step.push_back_mm)
                else:
                    motion.carry(positions[step.actor], step.to, step.via)
            except ValueError as exc:
                raise ValueError(f"预检第 {i} 步「{step.actor}」：{exc}") from exc
            positions[step.actor] = step.to


def run_dobot(stage, show, calibration, device, sdk_dir, *, lens=None, preflight_only=False):
    """Perform an already parsed editor show on a calibrated, enabled robot."""
    check_push_capability(show, calibration["arm"].get("contact_push_enabled", False))
    settings = Device.parse(device)
    def read_frame():
        return fresh_frame(settings.source, settings.camera_size)

    auto = lens is not None
    if not auto:
        camera = build_camera(stage, calibration, lambda: aruco_markers(read_frame()))
    if calibration["arm"]["blow_seconds"] and not settings.blow:
        raise ValueError("启用吹气时，请先配置 blow 阀门")
    sdk = load_sdk(sdk_dir)
    with ExitStack() as connections:
        def connect(client, port):
            try:
                channel = connections.enter_context(closing(client(settings.host, port)))
            except Exception as exc:
                raise RuntimeError(f"无法连接 Dobot {settings.host}:{port}：{exc}") from exc
            channel.socket_dobot.settimeout(settings.timeout)
            return channel

        robot = Dobot(connect(sdk.DobotApiDashboard, 29999),
                      connect(sdk.DobotApiMove, 30003), settings)
        robot.prepare()
        if auto:
            from .registration import StageView, register_xy
            view = StageView(stage, lens, read_frame)
            arm = calibration["arm"]
            pairs = register_xy(robot, view, arm, calibration["auto_xy"])
            calibration = {**calibration, "camera": calibration.get("camera", {}),
                           "arm": {**arm, "pairs": pairs}}
            camera = view.camera()
        else:
            read_frame()
        if auto or preflight_only:
            actors = {step.actor for step in show.steps if isinstance(step, Move)}
            if auto:
                snapshot = view.read()
                initial = view.camera(lambda: snapshot)
            else:
                initial = camera
            check_show(robot, stage, show, calibration, {a: initial.locate(a) for a in actors})
            print("演前运动学采样预检通过")
            if preflight_only:
                return
        def move_xyz(x, y, z):
            if auto:
                # Covers live pickup corrections and occlusion-clearance detours.
                robot.check_segment(robot.pose()[:3], (x,y,z))
            robot.move_xyz(x,y,z)

        motion = build_motion(stage, calibration, read_xy=robot.read_xy,
                              move_xyz=move_xyz, set_pump=robot.set_pump)
        perform(show, stage, motion=motion, camera=camera, cue=print, wait=motion.wait,
                occlusion_clearance_mm=calibration["camera"].get("occlusion_clearance_mm"))
