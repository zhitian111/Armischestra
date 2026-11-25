"""Localize a paper actor's pickup point on a fixed, planar stage (millimetres)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import hypot, isfinite
from os import PathLike, fspath

Point = tuple[float, float]
Corners = Sequence[Point]
MarkerReader = Callable[[], Mapping[int, Corners]]


def _quad(points: Corners) -> None:
    """Require four finite, cyclically ordered corners of a convex quadrilateral."""
    if len(points) != 4 or not all(
        len(point) == 2 and all(isfinite(v) for v in point) for point in points
    ):
        raise ValueError("需要四个有限的二维角点")
    turns = []
    for i in range(4):
        a, b, c = (points[(i + j) % 4] for j in range(3))
        turns.append((b[0]-a[0]) * (c[1]-b[1]) - (b[1]-a[1]) * (c[0]-b[0]))
    if not (min(turns) > 0 or max(turns) < 0):
        raise ValueError("四个角点需沿边依次排列，并围成凸四边形")


def _solve(rows: list[list[float]]) -> tuple[float, ...]:
    """Solve the eight homography constraints by elimination with pivoting."""
    n = len(rows)
    for i in range(n):
        p = max(range(i, n), key=lambda j: abs(rows[j][i]))
        rows[i], rows[p] = rows[p], rows[i]
        pivot = rows[i][i]
        if abs(pivot) < 1e-12:
            raise ValueError("标定点无法确定平面映射")
        rows[i] = [v / pivot for v in rows[i]]
        for j in range(n):
            if j != i:
                factor = rows[j][i]
                rows[j] = [v - factor * w for v, w in zip(rows[j], rows[i])]
    return tuple(row[-1] for row in rows)


@dataclass(frozen=True)
class BoardMap:
    """Project image points onto the plane that contains the marker faces."""

    pixel_origin: Point
    coefficients: tuple[float, ...]

    @classmethod
    def from_corners(cls, pixels: Corners, board_mm: Corners) -> "BoardMap":
        """Pair four image and measured board corners in the same physical order."""
        _quad(pixels)
        _quad(board_mm)
        u0, v0 = pixels[0]
        rows = []
        for (u, v), (x, y) in zip(pixels, board_mm):
            # Normalizing h33 to 1 is valid at the first finite calibration point.
            u, v = u - u0, v - v0
            rows.append([u, v, 1, 0, 0, 0, -x*u, -x*v, x])
            rows.append([0, 0, 0, u, v, 1, -y*u, -y*v, y])
        return cls((u0, v0), _solve(rows))

    def to_board(self, pixel: Point) -> Point:
        u, v = pixel[0] - self.pixel_origin[0], pixel[1] - self.pixel_origin[1]
        a, b, c, d, e, f, g, h = self.coefficients
        denominator = g*u + h*v + 1
        if not isfinite(denominator) or abs(denominator) < 1e-12:
            raise ValueError("像素点无法映射到棋盘")
        return ((a*u + b*v + c) / denominator, (d*u + e*v + f) / denominator)


@dataclass(frozen=True)
class MarkerSpec:
    marker_id: int
    # Relative to printed marker center, +x towards its right, +y towards its top.
    pickup_offset_mm: Point = (0.0, 0.0)


class MarkerMissing(ValueError):
    """A valid, fresh frame did not contain this ID."""


@dataclass
class MarkerCamera:
    board_map: BoardMap
    specs_by_actor: Mapping[str, MarkerSpec]
    read_markers: MarkerReader

    def locate(self, actor: str) -> Point:
        """Locate from a fresh observation, with corners in decoded ArUco order."""
        spec = self.specs_by_actor[actor]
        observed = self.read_markers()
        if spec.marker_id not in observed:
            raise MarkerMissing(f"本帧未看到 {actor} 的标记 {spec.marker_id}")
        corners = [self.board_map.to_board(p) for p in observed[spec.marker_id]]
        _quad(corners)
        # Average corners after mapping to the stage to remove perspective bias.
        center_x, center_y = (sum(values) / 4 for values in zip(*corners))
        tl, tr, br, bl = corners
        dx = tr[0] + br[0] - tl[0] - bl[0]
        dy = tr[1] + br[1] - tl[1] - bl[1]
        length = hypot(dx, dy)
        ux, uy = dx / length, dy / length
        right, up = spec.pickup_offset_mm
        return center_x + right*ux - up*uy, center_y + right*uy + up*ux


def aruco_markers(frame) -> dict[int, list[Point]]:
    """Detect DICT_4X4_50 in an OpenCV frame or a photo supplied by path."""
    try:
        import cv2
        from cv2.aruco import ArucoDetector, DICT_4X4_50, getPredefinedDictionary
    except ImportError as exc:
        raise RuntimeError("读取真实图片需要 opencv-contrib-python-headless>=4.7,<5") from exc
    if isinstance(frame, (str, PathLike)):
        path = fspath(frame)
        frame = cv2.imread(path)
        if frame is None:
            raise ValueError(f"无法读取图片 {path}")
    if frame is None:
        raise ValueError("相机未提供图像")
    detector = ArucoDetector(getPredefinedDictionary(DICT_4X4_50))
    corners, ids, _ = detector.detectMarkers(frame)
    observed = {}
    if ids is not None:
        for marker_id, quad in zip(ids.ravel(), corners):
            marker_id = int(marker_id)
            if marker_id in observed:
                raise ValueError(f"同一帧出现多个标记 {marker_id}，无法区分角色")
            observed[marker_id] = [(float(x), float(y)) for x, y in quad.reshape(4, 2)]
    return observed
