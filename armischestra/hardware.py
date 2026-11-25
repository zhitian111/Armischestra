"""Connect a measured stage and synchronous device drivers to the show."""

import time
from dataclasses import dataclass

from .motion import AffineMap, HardwareArm, Motion, Point
from .show import Stage, perform, xy
from .vision import BoardMap, MarkerCamera, MarkerReader, MarkerSpec, aruco_markers


@dataclass
class BoardCamera:
    markers: MarkerCamera

    def locate(self, actor: str) -> Point:
        return Point(*self.markers.locate(actor))


def _coordinates(data, key):
    if not isinstance(data.get(key), list):
        raise ValueError(f"请填写 {key} 的四个坐标")
    points = [xy(value, key) for value in data[key]]
    return [(p.x, p.y) for p in points]


def build_camera(stage: Stage, calibration: dict, read_markers: MarkerReader) -> BoardCamera:
    camera = calibration["camera"]
    mapping = BoardMap.from_corners(
        _coordinates(camera, "corners_px"), _coordinates(camera, "corners_mm")
    )
    specs = {
        name: MarkerSpec(actor.marker_id, (actor.pickup_offset.x, actor.pickup_offset.y))
        for name, actor in stage.actors.items()
    }
    return BoardCamera(MarkerCamera(mapping, specs, read_markers))


def build_motion(stage, calibration, *, read_xy, move_xyz, set_pump, wait=time.sleep):
    settings = calibration["arm"]
    mapping = AffineMap.fit(
        (xy(pair["board_mm"], "board_mm"), xy(pair["arm_mm"], "arm_mm"))
        for pair in settings["pairs"]
    )
    arm = HardwareArm(
        mapping, high_z=settings["high_z_mm"], low_z=settings["low_z_mm"],
        read_xy=read_xy, move_xyz=move_xyz, set_pump=set_pump,
    )
    return Motion(
        arm, stage.width, stage.height, wait=wait, grip_seconds=settings["grip_seconds"],
        release_seconds=settings["release_seconds"], blow_seconds=settings["blow_seconds"],
        contact_push_enabled=settings.get("contact_push_enabled", False),
    )


def run_hardware(stage, show, calibration, *, read_xy, move_xyz, set_pump,
                 read_frame, cue, wait=time.sleep):
    """read_frame supplies one fresh, calibrated-view image per observation."""
    camera = build_camera(stage, calibration, lambda: aruco_markers(read_frame()))
    motion = build_motion(stage, calibration, read_xy=read_xy, move_xyz=move_xyz,
                          set_pump=set_pump, wait=wait)
    perform(show, stage, motion=motion, camera=camera, cue=cue, wait=wait,
            occlusion_clearance_mm=calibration["camera"].get("occlusion_clearance_mm"))
