"""Read a board and a script, then direct one actor at a time."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .motion import Motion, Point, push_contacts
from .vision import MarkerMissing


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} 必须是有限数值")
    return float(value)


def xy(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} 应为 [x, y]")
    return Point(number(value[0], name), number(value[1], name))


def load_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


@dataclass(frozen=True)
class Actor:
    start: Point
    marker_id: int
    pickup_offset: Point
    kind: str = "actor"


@dataclass(frozen=True)
class HealthBar:
    name: str
    actor: str
    origin: Point
    size: Point
    tokens: tuple[str, ...]

    def contains(self, point: Point) -> bool:
        return (self.origin.x <= point.x <= self.origin.x + self.size.x
                and self.origin.y <= point.y <= self.origin.y + self.size.y)

    def remaining(self, positions: dict[str, Point]) -> int:
        return sum(self.contains(positions[token]) for token in self.tokens)


@dataclass(frozen=True)
class Stage:
    width: float
    height: float
    cell: float
    park: Point
    tolerance: float
    actors: dict[str, Actor]
    health_bars: tuple[HealthBar, ...] = ()

    def check(self, point):
        if not (0 <= point.x <= self.width and 0 <= point.y <= self.height):
            raise ValueError(f"坐标 {point} 超出了棋盘")


@dataclass(frozen=True)
class Move:
    actor: str
    to: Point
    via: tuple[Point, ...]
    method: str = "carry"
    push_back_mm: float | None = None


@dataclass(frozen=True)
class Cue:
    text: str


@dataclass(frozen=True)
class Wait:
    seconds: float


@dataclass(frozen=True)
class Show:
    title: str
    steps: tuple[Move | Cue | Wait, ...]


def load_stage(path):
    return parse_stage(load_json(path))


def parse_health_bars(raw_bars, actors):
    if not isinstance(raw_bars, list):
        raise ValueError("health_bars 应为血条列表")
    bars = []
    bar_names = set()
    owners = set()
    assigned = set()
    for item in raw_bars:
        if not isinstance(item, dict):
            raise ValueError("血条应包含名称、所属角色、矩形和血块")
        name = item.get("name")
        owner = item.get("actor")
        if not isinstance(name, str) or not name.strip() or name in bar_names:
            raise ValueError("血条名称不能为空或重复")
        if not isinstance(owner, str) or owner not in actors or actors[owner].kind != "actor":
            raise ValueError(f"{name} 的所属角色不存在或不是演员")
        if owner in owners:
            raise ValueError(f"角色 {owner} 已有血条")
        tokens = item.get("tokens")
        if not isinstance(tokens, list) or not tokens:
            raise ValueError(f"{name} 至少需要一块血块")
        origin = xy(item.get("origin_mm"), f"{name} 左下角")
        size = xy(item.get("size_mm"), f"{name} 宽高")
        if min(size.x, size.y) <= 0:
            raise ValueError(f"{name} 的宽高必须为正")
        bar = HealthBar(name, owner, origin, size, tuple(tokens))
        for token in tokens:
            if not isinstance(token, str) or token not in actors or actors[token].kind != "prop":
                raise ValueError(f"{name} 的血块 {token} 必须是舞台上的道具")
            if token in assigned:
                raise ValueError(f"血块 {token} 重复分配")
            if not bar.contains(actors[token].start):
                raise ValueError(f"血块 {token} 的开场吸取点必须位于 {name} 内")
            assigned.add(token)
        bars.append(bar)
        bar_names.add(name)
        owners.add(owner)
    return tuple(bars)


def parse_stage(raw):
    size = xy(raw["size_mm"], "size_mm")
    width, height = size.x, size.y
    cell = number(raw["cell_mm"], "cell_mm")
    tolerance = number(raw["placement_tolerance_mm"], "placement_tolerance_mm")
    if min(width, height, cell) <= 0 or tolerance < 0:
        raise ValueError("棋盘和格子尺寸必须大于零，位置容差不能为负")
    actors = {}
    ids = set()
    if not isinstance(raw["actors"], dict):
        raise ValueError("actors 应为按名称索引的角色表")
    for name, values in raw["actors"].items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("请填写角色名称")
        marker = values["marker_id"]
        if type(marker) is not int or not 0 <= marker < 50 or marker in ids:
            raise ValueError(f"{name} 的标记编号须唯一且位于 0～49")
        kind = values.get("kind", "actor")
        if kind not in ("actor", "prop"):
            raise ValueError(f"{name} 类型应为角色 actor 或道具 prop")
        ids.add(marker)
        actors[name] = Actor(xy(values["start_mm"], "start_mm"), marker,
                             xy(values["pickup_offset_mm"], "pickup_offset_mm"), kind)
    if not actors:
        raise ValueError("舞台至少需要一个角色")
    bars = parse_health_bars(raw.get("health_bars", []), actors)
    stage = Stage(width, height, cell, xy(raw["park_mm"], "park_mm"), tolerance, actors, bars)
    for bar in bars:
        stage.check(bar.origin)
        stage.check(Point(bar.origin.x + bar.size.x, bar.origin.y + bar.size.y))
    stage.check(stage.park)
    for actor in actors.values():
        stage.check(actor.start)
    return stage


def load_show(path, stage):
    return parse_show(load_json(path), stage)


def parse_show(raw, stage):
    if not isinstance(raw["title"], str) or not raw["title"].strip():
        raise ValueError("请填写剧本名称")
    if not isinstance(raw["steps"], list):
        raise ValueError("steps 应为动作数组")
    steps = []
    positions = {name: actor.start for name, actor in stage.actors.items()}
    for i, item in enumerate(raw["steps"], start=1):
        if item["op"] == "move":
            actor = item["actor"]
            if actor not in stage.actors:
                raise ValueError(f"第 {i} 步出现未知角色 {actor}")
            target = xy(item["to_mm"], "to_mm")
            via = tuple(xy(p, "via_mm") for p in item.get("via_mm", []))
            for point in (*via, target):
                stage.check(point)
            method = item.get("method", "carry")
            back_mm = None
            if method == "push":
                if via:
                    raise ValueError(f"第 {i} 步接触推移只支持单段直线")
                back_mm = number(item.get("push_back_mm"), f"第 {i} 步 push_back_mm")
                for contact in push_contacts(positions[actor], target, back_mm):
                    stage.check(contact)
            elif method != "carry":
                raise ValueError(f"第 {i} 步未识别移动方式 {method}")
            steps.append(Move(actor, target, via, method, back_mm))
            positions[actor] = target
        elif item["op"] == "cue":
            if not isinstance(item["text"], str):
                raise ValueError(f"第 {i} 步字幕需要文字")
            steps.append(Cue(item["text"]))
        elif item["op"] == "wait":
            seconds = number(item["seconds"], "seconds")
            if seconds < 0:
                raise ValueError(f"第 {i} 步等待时间不能为负")
            steps.append(Wait(seconds))
        else:
            raise ValueError(f"第 {i} 步出现未知动作 {item['op']}")
    return Show(raw["title"], tuple(steps))


class Camera(Protocol):
    def locate(self, actor: str) -> Point: ...


def _clearance_point(tool: Point, stage: Stage, distance: float) -> Point:
    """Move along the axis that has the most board room, keeping the detour local."""
    directions = [(stage.width-tool.x, 1, 0), (tool.x, -1, 0),
                  (stage.height-tool.y, 0, 1), (tool.y, 0, -1)]
    room, dx, dy = max(directions, key=lambda direction: direction[0])
    amount = min(room, distance)
    return Point(tool.x + dx*amount, tool.y + dy*amount)


def check_push_capability(show: Show, contact_push_enabled: bool):
    if not contact_push_enabled and any(
        isinstance(s, Move) and s.method == "push" for s in show.steps
    ):
        raise ValueError("此剧本含接触推移。请实测后设置 arm.contact_push_enabled 为 true，或将推移步骤改为吸移")


def perform(show: Show, stage: Stage, *, motion: Motion, camera: Camera,
            cue: Callable[[str], None], wait: Callable[[float], None],
            occlusion_clearance_mm: float | None = None):
    """Observe in place. A missing marker can trigger one high clearance move and retry."""
    clearance = stage.cell if occlusion_clearance_mm is None else occlusion_clearance_mm
    if number(clearance, "occlusion_clearance_mm") < 0:
        raise ValueError("occlusion_clearance_mm 不能为负")
    check_push_capability(show, motion.contact_push_enabled)

    tool = None

    def observe(actor):
        nonlocal tool
        try:
            return camera.locate(actor)
        except MarkerMissing:
            if not clearance:
                raise
            tool = stage.park if tool is None else _clearance_point(tool, stage, clearance)
            motion.park(tool)
            return camera.locate(actor)

    for i, step in enumerate(show.steps, start=1):
        if isinstance(step, Cue):
            cue(step.text)
        elif isinstance(step, Wait):
            wait(step.seconds)
        else:
            try:
                source = observe(step.actor)
                if step.method == "push":
                    tool = motion.push(source, step.to, step.push_back_mm)
                else:
                    motion.carry(source, step.to, via=step.via)
                    tool = step.to
                actual = observe(step.actor)
                error = math.hypot(actual.x - step.to.x, actual.y - step.to.y)
                if not math.isfinite(error) or error > stage.tolerance:
                    raise ValueError(f"放置偏差 {error:.1f} mm，允许 {stage.tolerance:g} mm")
            except Exception as exc:
                raise RuntimeError(f"第 {i} 步移动「{step.actor}」中止：{exc}") from exc
