import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from armischestra.motion import Point
from armischestra.simulation import Simulation


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.sim = Simulation(100, 80, {"cat": Point(20, 20), "dragon": Point(85, 40)})

    def test_camera_observes_placement_and_history_is_immutable(self):
        sim = self.sim
        sim.move_xy(20, 20)
        sim.set_height("low")
        sim.pump("suck")
        sim.set_height("high")
        start = sim.time_s
        sim.move_xy(30, 20)
        self.assertAlmostEqual(sim.time_s - start, 0.1)
        self.assertEqual(sim.held, "cat")
        sim.set_height("low")
        sim.pump("release")
        sim.set_height("high")
        sim.move_xy(0, 0)
        self.assertEqual(sim.locate("cat"), Point(30, 20))
        self.assertEqual(sim.locate("dragon"), Point(85, 40))
        self.assertEqual(sim.events[0]["actors"]["cat"], [20, 20])

    def test_bad_pick_cannot_attach_distant_actor(self):
        self.sim.set_height("low")
        with self.assertRaises(RuntimeError):
            self.sim.pump("suck")
        self.assertIsNone(self.sim.held)
        with self.assertRaises(RuntimeError):
            self.sim.move_xy(20, 20)
        self.assertEqual(self.sim.position, Point(0, 0))

    def test_replay_handles_literal_markup_in_caption(self):
        sim = self.sim
        text = "登场 </script>"
        sim.cue(text)
        sim.wait(2)
        with TemporaryDirectory() as folder:
            target = Path(folder) / "show.html"
            sim.write_replay(target)
            html = target.read_text(encoding="utf-8")
        payload = re.search(r'<script type="application/json" id="data">(.*?)</script>', html).group(1)
        frames = json.loads(payload)["frames"]
        self.assertEqual(frames[-1]["cue"], text)
        self.assertEqual(frames[-1]["time_s"], 2)
