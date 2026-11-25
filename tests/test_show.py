import unittest
from pathlib import Path

from armischestra.motion import Motion, Point
from armischestra.show import load_show, load_stage, parse_show, perform
from armischestra.vision import MarkerMissing
from armischestra.simulation import Simulation

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.stage = load_stage(EXAMPLES / "stage.json")
        self.show = load_show(EXAMPLES / "show.json", self.stage)
        # Start outside the script's example positions to verify live pickup localization.
        self.sim = Simulation(self.stage.width, self.stage.height,
                              {"艾露猫": Point(30, 40), "黑龙": Point(270, 170)})
        self.motion = Motion(self.sim, self.stage.width, self.stage.height, wait=self.sim.wait)

    def run_show(self, camera):
        perform(self.show, self.stage, motion=self.motion, camera=camera,
                wait=self.sim.wait, cue=self.sim.cue)

    def test_complete_duel_from_unexpected_start(self):
        self.run_show(self.sim)
        self.assertEqual(self.sim.actors, {"艾露猫": Point(200, 75), "黑龙": Point(250, 150)})
        self.assertEqual(self.sim.position, Point(250, 150))
        positions = [e["arm"] for e in self.sim.events if e["action"] == "move_xy"]
        self.assertNotIn([self.stage.park.x, self.stage.park.y], positions)
        self.assertEqual(positions[:4], [[30, 40], [75, 75], [125, 100], [270, 170]])
        self.assertIsNone(self.sim.held)
        self.assertEqual(self.sim.caption, self.show.steps[-2].text)

    def test_failed_placement_stops_before_the_next_scene(self):
        points = iter([Point(30, 40), Point(35, 40)])

        class Camera:
            def locate(self, actor):
                return next(points)

        with self.assertRaisesRegex(RuntimeError, "放置偏差"):
            self.run_show(Camera())
        self.assertEqual(self.sim.actors["黑龙"], Point(270, 170))
        self.assertEqual(self.sim.caption, self.show.steps[0].text)

    def test_push_uses_only_low_straight_contact_stroke(self):
        self.show = parse_show({"title": "推道具", "steps": [
            {"op": "move", "actor": "艾露猫", "method": "push", "push_back_mm": 8,
             "to_mm": [54, 72]}]}, self.stage)
        self.run_show(self.sim)
        # Observed (30,40) to (54,72) gives unit direction (0.6,0.8).
        self.assertEqual(self.sim.actors["艾露猫"], Point(54, 72))
        self.assertEqual(self.sim.position, Point(49.2, 65.6))
        travel = [e for e in self.sim.events if e["action"] == "move_xy"]
        self.assertEqual([(e["height"], e["arm"]) for e in travel],
                         [("high", [25.2, 33.6]), ("low", [49.2, 65.6])])
        self.assertTrue(all(e["held"] is None and e["pump"] == "release" for e in self.sim.events))

    def test_require_verified_push_setup_before_any_step(self):
        self.show = parse_show({"title": "推道具", "steps": [
            {"op":"cue","text":"开幕"},
            {"op":"move","actor":"艾露猫","method":"push","push_back_mm":8,"to_mm":[80, 75]}
        ]}, self.stage)
        self.motion.contact_push_enabled = False
        with self.assertRaisesRegex(ValueError, "contact_push_enabled"):
            self.run_show(self.sim)
        self.assertEqual([e["action"] for e in self.sim.events], ["start"])

    def test_one_local_clearance_if_tip_obscures_placed_card(self):
        self.show = parse_show({"title": "遮挡", "steps": [
            {"op":"move","actor":"艾露猫","to_mm":[60, 50]}]}, self.stage)
        sim = self.sim
        class Camera:
            def locate(self, actor):
                if sim.position == Point(60, 50):
                    raise MarkerMissing(actor)
                return sim.locate(actor)
        self.run_show(Camera())
        self.assertEqual(sim.position, Point(85, 50))
        self.assertEqual(sim.actors["艾露猫"], Point(60, 50))

    def test_out_of_bounds_actual_push_contact_prevents_lowering(self):
        self.show = parse_show({"title": "偏离起点", "steps": [
            {"op":"move","actor":"艾露猫","to_mm":[80, 75],"method":"push","push_back_mm":10}
        ]}, self.stage)
        self.sim.actors["艾露猫"] = Point(1,75)
        with self.assertRaisesRegex(RuntimeError, "范围"):
            self.run_show(self.sim)
        self.assertEqual([e["action"] for e in self.sim.events], ["start", "locate"])
