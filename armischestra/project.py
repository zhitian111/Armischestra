"""The portable editor document is the input to both the director and the simulator."""
import base64
import binascii
from dataclasses import dataclass
from pathlib import Path

from .motion import Motion, Point
from .show import Show, Stage, load_json, parse_show, parse_stage, perform, xy
from .simulation import Simulation

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@dataclass
class Project:
    stage: Stage
    show: Show
    cards: dict
    reserves: list


def parse_project(raw):
    if not isinstance(raw, dict) or type(raw.get("version")) is not int or raw["version"] != 1:
        raise ValueError("请选择版本为 1 的小剧场工程 JSON")
    try:
        stage = parse_stage(raw["stage"])
        show = parse_show(raw["show"], stage)
        reserves = raw["stage"].get("reserves", [])
        if not isinstance(reserves, list):
            raise ValueError("候场区应为矩形区域列表")
        names = set()
        for reserve in reserves:
            if not isinstance(reserve, dict):
                raise ValueError("请填写候场区名称、左下角和宽高")
            name = reserve["name"]
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError("候场区名称不能为空或重复")
            names.add(name)
            origin = xy(reserve["origin_mm"], f"{name} 左下角")
            size = xy(reserve["size_mm"], f"{name} 宽高")
            if min(size.x, size.y) <= 0:
                raise ValueError(f"{name} 的宽高必须为正")
            stage.check(origin)
            stage.check(Point(origin.x + size.x, origin.y + size.y))
        cards = raw["stage"]["actors"]
        health_tokens = {token for bar in stage.health_bars for token in bar.tokens}
        for name, card in cards.items():
            size = xy(card["print_size_mm"], f"{name} 印刷尺寸")
            if min(size.x, size.y) < 16:
                raise ValueError(f"{name} 的卡片宽高至少为 16 mm")
            offset = stage.actors[name].pickup_offset
            marker = xy(card.get("marker_offset_mm", [0, 0]), f"{name} 的标记偏移")
            # OpenCV's six-module square plus a white quiet zone one module wide.
            short_side = min(size.x, size.y)
            black_side = (min(12, short_side * 0.48) if name in health_tokens
                          else min(18, short_side * 0.75))
            half_marker = black_side * 4 / 6
            if abs(marker.x) + half_marker > size.x / 2 or abs(marker.y) + half_marker > size.y / 2:
                raise ValueError(f"{name} 的标记白边超出卡片")
            if abs(marker.x + offset.x) > size.x / 2 or abs(marker.y + offset.y) > size.y / 2:
                raise ValueError(f"{name} 的吸取点超出卡片")
            image = card.get("image")
            if image is not None:
                prefix = "data:image/png;base64,"
                if not isinstance(image, str) or not image.startswith(prefix):
                    raise ValueError(f"{name} 的图片需要是工程内嵌的 PNG")
                try:
                    encoded = base64.b64decode(image[len(prefix):], validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError(f"{name} 的图片编码无效") from exc
                if not encoded.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError(f"{name} 的图片缺少 PNG 文件头")
    except KeyError as exc:
        raise ValueError(f"缺少工程字段 {exc}") from exc
    except TypeError as exc:
        raise ValueError(f"工程字段类型错误：{exc}") from exc
    return Project(stage, show, cards, reserves)


def example_document():
    return load_json(EXAMPLES / "schrade.armischestra.json")


def rehearse(stage, show):
    sim = Simulation(stage.width, stage.height,
                     {name: actor.start for name, actor in stage.actors.items()}, stage.health_bars)
    motion = Motion(sim, stage.width, stage.height, wait=sim.wait,
                    grip_seconds=0.2, release_seconds=0.1)
    perform(show, stage, motion=motion, camera=sim, cue=sim.cue, wait=sim.wait)
    return sim
