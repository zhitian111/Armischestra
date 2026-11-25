"""Board-plane motion. Driver calls must return only when the move is complete."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


def _finite(value: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __post_init__(self) -> None:
        if not all(_finite(v) for v in (self.x, self.y)):
            raise ValueError("XY 坐标必须是有限数值")


Height = Literal["high", "low"]
PumpMode = Literal["suck", "release", "blow"]


class Arm(Protocol):
    def move_xy(self, x: float, y: float) -> None: ...
    def push_xy(self, x: float, y: float, *, object_at: Point) -> None: ...
    def set_height(self, level: Height) -> None: ...
    def pump(self, mode: PumpMode) -> None: ...


class Motion:
    """Translate stage actions to blocking arm commands. Distances are in mm."""

    def __init__(
        self,
        arm: Arm,
        width_mm: float,
        height_mm: float,
        *,
        wait: Callable[[float], None] = time.sleep,
        grip_seconds: float = 0.0,
        release_seconds: float = 0.0,
        blow_seconds: float = 0.0,
        contact_push_enabled: bool = True,
    ) -> None:
        if not all(_finite(v) and v > 0 for v in (width_mm, height_mm)):
            raise ValueError("舞台长宽必须为正数")
        if not all(_finite(v) and v >= 0 for v in (grip_seconds, release_seconds, blow_seconds)):
            raise ValueError("等待时间必须为非负有限数值")
        self.arm = arm
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.wait = wait
        self.grip_seconds = grip_seconds
        self.release_seconds = release_seconds
        self.blow_seconds = blow_seconds
        if type(contact_push_enabled) is not bool:
            raise ValueError("contact_push_enabled 应为 true 或 false")
        self.contact_push_enabled = contact_push_enabled

    def check_point(self, point: Point) -> None:
        if not (0 <= point.x <= self.width_mm and 0 <= point.y <= self.height_mm):
            raise ValueError(f"坐标超出舞台范围: {point}")

    def park(self, at: Point) -> None:
        self.check_point(at)
        self.arm.set_height("high")
        self.arm.move_xy(at.x, at.y)

    def carry(self, source: Point, target: Point, via: Sequence[Point] = ()) -> None:
        # Validate the entire path before the first arm command.
        route = [*via, target]
        self.check_point(source)
        for point in route:
            self.check_point(point)

        self.park(source)
        self.arm.set_height("low")
        self.arm.pump("suck")
        self.wait(self.grip_seconds)
        self.arm.set_height("high")
        for point in route:
            self.arm.move_xy(point.x, point.y)
        self.arm.set_height("low")
        if self.blow_seconds:
            self.arm.pump("blow")
            self.wait(self.blow_seconds)
        self.arm.pump("release")
        self.wait(self.release_seconds)
        self.arm.set_height("high")


    def push(self, source: Point, target: Point, back_mm: float) -> Point:
        """A single straight slide. The low tool touches a measured rear tab."""
        if not self.contact_push_enabled:
            raise ValueError("尚未标定低位接触推移，可将该动作改为吸移")
        start, end = push_contacts(source, target, back_mm)
        for point in (source, target, start, end):
            self.check_point(point)
        self.park(start)
        self.arm.pump("release")
        self.arm.set_height("low")
        self.arm.push_xy(end.x, end.y, object_at=source)
        self.arm.set_height("high")
        return end


def push_contacts(source: Point, target: Point, back_mm: float) -> tuple[Point, Point]:
    dx, dy = target.x - source.x, target.y - source.y
    distance = math.hypot(dx, dy)
    if distance == 0:
        raise ValueError("推移起点和终点重合，无法确定推向")
    if not _finite(back_mm) or back_mm <= 0:
        raise ValueError("推触点后距 push_back_mm 必须大于零")
    bx, by = back_mm * (dx / distance), back_mm * (dy / distance)
    return Point(source.x - bx, source.y - by), Point(target.x - bx, target.y - by)


@dataclass(frozen=True)
class AffineMap:
    """Planar calibration in mm: arm XY = matrix * board XY + translation."""

    xx: float
    xy: float
    tx: float
    yx: float
    yy: float
    ty: float

    def __post_init__(self) -> None:
        if not all(_finite(v) for v in (self.xx, self.xy, self.tx, self.yx, self.yy, self.ty)):
            raise ValueError("标定结果包含无效数值")
        area = self.xx * self.yy - self.xy * self.yx
        if abs(area) <= 1e-12 * math.hypot(self.xx, self.yx) * math.hypot(self.xy, self.yy):
            raise ValueError("机械臂标定点未覆盖二维平面")

    def transform(self, point: Point) -> Point:
        return Point(
            self.xx * point.x + self.xy * point.y + self.tx,
            self.yx * point.x + self.yy * point.y + self.ty,
        )

    @classmethod
    def fit(cls, pairs: Iterable[tuple[Point, Point]]) -> AffineMap:
        """Least-squares fit from corresponding (board XY, measured arm XY)."""
        samples = list(pairs)
        n = len(samples)
        if n < 3:
            raise ValueError("至少需要三组标定点")
        bx = sum(board.x for board, arm in samples) / n
        by = sum(board.y for board, arm in samples) / n
        ax = sum(arm.x for board, arm in samples) / n
        ay = sum(arm.y for board, arm in samples) / n

        # Removing the translation leaves a 2x2 normal equation per output axis.
        sxx = syy = sxy = sxu = syu = sxv = syv = 0.0
        for board, arm in samples:
            x, y = board.x - bx, board.y - by
            u, v = arm.x - ax, arm.y - ay
            sxx += x * x
            syy += y * y
            sxy += x * y
            sxu += x * u
            syu += y * u
            sxv += x * v
            syv += y * v
        det = sxx * syy - sxy * sxy
        if det <= 1e-12 * sxx * syy:
            raise ValueError("棋盘标定点必须分散且不共线")
        xx = (syy * sxu - sxy * syu) / det
        xy = (sxx * syu - sxy * sxu) / det
        yx = (syy * sxv - sxy * syv) / det
        yy = (sxx * syv - sxy * sxv) / det
        return cls(xx, xy, ax - xx * bx - xy * by, yx, yy, ay - yx * bx - yy * by)


class HardwareArm:
    """Adapt vendor callbacks using measured arm coordinates (mm).

    move_xyz must perform a straight Cartesian move and block until arrival.
    read_xy returns the current tool center in the arm coordinate system.
    Heights use the vendor's Z convention. set_pump selects one exclusive mode.
    """

    def __init__(
        self,
        mapping: AffineMap,
        *,
        high_z: float,
        low_z: float,
        read_xy: Callable[[], Point],
        move_xyz: Callable[[float, float, float], None],
        set_pump: Callable[[PumpMode], None],
    ) -> None:
        if not all(_finite(v) for v in (high_z, low_z)) or high_z == low_z:
            raise ValueError("请提供实测且不同的高位与低位 Z")
        self.mapping = mapping
        self.heights = {"high": high_z, "low": low_z}
        self.read_xy = read_xy
        self.move_xyz = move_xyz
        self.set_pump = set_pump
        self._level: Height | None = None

    def set_height(self, level: Height) -> None:
        if self._level == level:
            return
        z = self.heights[level]
        self._level = None
        current = self.read_xy()
        self.move_xyz(current.x, current.y, z)
        self._level = level

    def move_xy(self, x: float, y: float) -> None:
        if self._level != "high":
            raise RuntimeError("横向移动前需先到达高位")
        self._translate(x, y, "high")

    def push_xy(self, x: float, y: float, *, object_at: Point) -> None:
        if self._level != "low":
            raise RuntimeError("接触推移前必须下降到实测接触高度")
        self._translate(x, y, "low")

    def _translate(self, x: float, y: float, level: Height) -> None:
        dest = self.mapping.transform(Point(x, y))
        self._level = None
        self.move_xyz(dest.x, dest.y, self.heights[level])
        self._level = level

    def pump(self, mode: PumpMode) -> None:
        self.set_pump(mode)
