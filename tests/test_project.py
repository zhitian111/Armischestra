import json
import unittest
from itertools import combinations
from copy import deepcopy

from armischestra.show import parse_stage

from armischestra.project import example_document, parse_project, rehearse


class ProjectTest(unittest.TestCase):
    def test_portable_document_runs_with_a_new_actor(self):
        bundle = example_document()
        cards = bundle["stage"]["actors"]
        free_id = next(i for i in range(50) if i not in {card["marker_id"] for card in cards.values()})
        cards["布景师"] = dict(cards["艾露猫"], start_mm=[55, 66], marker_id=free_id)
        bundle["show"]["steps"] = [
            {"op": "move", "actor": "布景师", "via_mm": [[50, 80]], "to_mm": [88, 99]},
            {"op": "cue", "text": "谢幕"},
        ]
        project = parse_project(json.loads(json.dumps(bundle)))
        sim = rehearse(project.stage, project.show)
        self.assertEqual(sim.events[-1]["actors"]["布景师"], [88, 99])
        self.assertTrue(project.cards["布景师"]["image"].startswith("data:image/png;base64,"))
        self.assertEqual(sim.caption, "谢幕")

    def test_cast_and_effects_can_share_the_physical_board(self):
        project = parse_project(example_document())
        sim = rehearse(project.stage, project.show)
        self.assertTrue(any(e["action"] == "move_xy" and e["height"] == "low" for e in sim.events))
        for frame in sim.events:
            if frame["action"] not in ("start", "locate"):
                continue
            # All examples use upright cards. Physically a card is centered away
            # from its pickup by both of the marker-related offsets.
            for a, b in combinations(project.cards, 2):
                ax, ay = frame["actors"][a]
                bx, by = frame["actors"][b]
                am, bm = (project.cards[name].get("marker_offset_mm", [0, 0]) for name in (a, b))
                ap, bp = (project.cards[name]["pickup_offset_mm"] for name in (a, b))
                ax, ay = ax - am[0] - ap[0], ay - am[1] - ap[1]
                bx, by = bx - bm[0] - bp[0], by - bm[1] - bp[1]
                aw, ah = project.cards[a]["print_size_mm"]
                bw, bh = project.cards[b]["print_size_mm"]
                self.assertTrue(abs(ax - bx) >= (aw + bw) / 2 or abs(ay - by) >= (ah + bh) / 2,
                                f"{a} 和 {b} 在 {frame['time_s']:.1f} s 落位重叠")
        scores = []
        for frame in sim.events:
            score = tuple(frame["health"][name] for name in ("艾露猫", "黑龙"))
            if not scores or score != scores[-1]:
                scores.append(score)
        self.assertEqual(scores, [(2, 3), (2, 2), (1, 2), (1, 1), (1, 0)])
        for name in ("扇形吐息", "兜割刀光", "呆猫·举刀替身"):
            self.assertEqual(sim.events[-1]["actors"][name], project.cards[name]["start_mm"])

    def test_reject_mismatch_between_artwork_and_pickup(self):
        bundle = example_document()
        bundle["stage"]["actors"]["艾露猫"]["pickup_offset_mm"] = [100, 0]
        with self.assertRaisesRegex(ValueError, "吸取点"):
            parse_project(bundle)

    def test_validate_script_before_running_it(self):
        bundle = example_document()
        bundle["show"]["steps"].append({"op": "move", "actor": "艾露猫", "to_mm": [bundle["stage"]["size_mm"][0] + 1, 20]})
        with self.assertRaisesRegex(ValueError, "棋盘"):
            parse_project(bundle)

class HealthBarTest(unittest.TestCase):
    def setUp(self):
        self.bar = {"name": "猫槽", "actor": "猫", "tokens": ["红块"],
                    "origin_mm": [30, 65], "size_mm": [20, 20]}
        def card(marker_id, kind, point):
            return {"marker_id": marker_id, "kind": kind, "start_mm": point,
                    "print_size_mm": [20, 20], "pickup_offset_mm": [0, 0]}
        self.stage = {"size_mm": [100, 100], "cell_mm": 10, "placement_tolerance_mm": 1,
                      "park_mm": [10, 10], "health_bars": [self.bar], "actors": {
                          "猫": card(0, "actor", [80, 30]), "红块": card(1, "prop", [40, 75]),
                          "龙": card(2, "actor", [20, 30])}}

    def test_rehearsal_counts_pickup_inside_region_while_lifted_and_after_return(self):
        self.stage["actors"]["红块"]["marker_offset_mm"] = [3, 0]  # Fits small HP marker only.
        steps = [{"op": "move", "actor": "红块", "via_mm": [[50, 75]], "to_mm": [75, 75]},
                 {"op": "cue", "text": "零血量"},
                 {"op": "move", "actor": "红块", "to_mm": [40, 75]}]
        project = parse_project({"version": 1, "stage": self.stage,
                                 "show": {"title": "一格纸血", "steps": steps}})
        sim = rehearse(project.stage, project.show)
        self.assertEqual([(e["actors"]["红块"], e["health"]["猫"]) for e in sim.events
                          if e["held"] == "红块" and e["action"] == "move_xy"],
                         [([50, 75], 1), ([75, 75], 0), ([40, 75], 1)])
        self.assertEqual(next(e["health"] for e in sim.events if e["action"] == "cue"), {"猫": 0})
        self.assertEqual(sim.events[-1]["health"], {"猫": 1})

    def test_health_bar_cannot_share_tokens_or_owners(self):
        for second, error in [
            (dict(self.bar, name="另一条"), "已有血条"),
            (dict(self.bar, name="龙槽", actor="龙"), "重复分配"),
            (dict(self.bar, actor="龙"), "名称"),
        ]:
            with self.subTest(second=second):
                stage = dict(self.stage, health_bars=[self.bar, second])
                with self.assertRaisesRegex(ValueError, error):
                    parse_stage(stage)

    def test_health_bar_must_fit_the_board_and_contain_its_assigned_props(self):
        for change, error in [
            ({"size_mm": [200, 20]}, "棋盘"),
            ({"origin_mm": [50, 65]}, "开场吸取点"),
            ({"actor": "红块"}, "所属角色"),
            ({"tokens": ["龙"]}, "血块"),
            ({"tokens": ["红块", "红块"]}, "重复分配"),
            ({"tokens": []}, "至少"),
        ]:
            with self.subTest(change=change):
                stage = dict(self.stage, health_bars=[dict(self.bar, **change)])
                with self.assertRaisesRegex(ValueError, error):
                    parse_stage(stage)

    def test_original_stage_without_health_bars_remains_valid(self):
        stage = deepcopy(self.stage)
        del stage["health_bars"]
        self.assertEqual(parse_stage(stage).health_bars, ())
