import unittest

from tests import _env  # noqa: F401
from tests.test_bench_score import S, build
from blockforge import checks, examples, patterns, sandbox

KINDS = ("buried_path", "jump_step", "door_blocked", "floating", "headroom", "wrong_facing", "corner_turn")
HILL = ("for x in range(-24, 25):\n"                              # uneven ground for the manor on stilts
        "  for z in range(-24, 25):\n"
        "    h = int(2 + 3 * noise(x, z, 9))\n"
        "    fill(x, 0, z, x, h, z, 'dirt')\n"
        "    block(x, h + 1, z, 'grass_block')\n")

CASES = {
    "stair_run_east": lambda: patterns.straight_stair_run(2, 1, 2, "east", 6, 3),
    "stair_run_north": lambda: patterns.straight_stair_run(10, 3, 10, "north", 5, 2, "spruce"),
    "stair_run_west": lambda: patterns.straight_stair_run(10, 3, 4, "west", 4, 1, landing=0),
    "switchback": lambda: patterns.switchback_landing(2, 1, 2, "south", 4, 2),
    "switchback_east": lambda: patterns.switchback_landing(2, 1, 2, "east", 5, 3),
    "lantern_japanese": lambda: patterns.lantern_post(3, 1, 3, "japanese"),
    "lantern_medieval": lambda: patterns.lantern_post(3, 1, 3, "medieval"),
    "lantern_modern": lambda: patterns.lantern_post(3, 1, 3, "modern"),
    "lantern_nordic": lambda: patterns.lantern_post(3, 1, 3, "nordic"),
    "door_north": lambda: patterns.doorway(5, 1, 5, "north", "dark_oak"),
    "door_east": lambda: patterns.doorway(5, 1, 5, "east", "spruce"),
    "window_south": lambda: patterns.window(5, 2, 5, "south"),
    "window_west": lambda: patterns.window(5, 2, 5, "west", "glass_pane"),
    "house_x": lambda: patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5, "white_terracotta", "spruce_stairs", "spruce"),
    "house_z": lambda: patterns.gable_roof_house_shell(0, 0, 6, 9, 1, 4, "spruce_planks", "oak_stairs", "oak", "east"),
    "bridge": lambda: patterns.stone_arch_bridge(2, 6, 2, 11, 3),
    "bridge_wide": lambda: patterns.stone_arch_bridge(2, 5, 2, 8, 5),
    "tree_oak": lambda: patterns.tree("oak", 4, 1, 4, 6),
    "tree_birch": lambda: patterns.tree("birch", 4, 1, 4, 6),
    "tree_spruce": lambda: patterns.tree("spruce", 4, 1, 4, 9),
    "tree_dark_oak": lambda: patterns.tree("dark_oak", 4, 1, 4, 6),
    "tree_maple": lambda: patterns.tree("maple", 4, 1, 4, 6),
    "framed_wall": lambda: patterns.framed_wall(0, 0, 8, 0, 1, 4, "north"),
    "framed_wall_z": lambda: patterns.framed_wall(3, 0, 3, 8, 1, 5, "east", "white_terracotta", "dark_oak_log", 3),
    "framed_house": lambda: patterns.framed_house(0, 0, 12, 8, 1, 2, 4),
    "framed_house_wing": lambda: patterns.framed_house(0, 0, 8, 8, 1, 1, 4, skip=["east"], clear=True, flat=["north"]),
    "window_with_box": lambda: patterns.window_with_box(4, 3, 4, "south", 2, 2, wall="oak_planks"),
    "window_with_box_w": lambda: patterns.window_with_box(4, 3, 4, "west", 1, 2, wall="spruce_planks"),
    "porch": lambda: patterns.porch(5, 2, 3, "south"),
    "porch_steps": lambda: patterns.porch(5, 3, 3, "east", 5, 3, steps=2, path=2),
    "balcony": lambda: patterns.balcony(2, 6, 2, "south", 5, 2, ground_y=0),
    "balcony_door": lambda: (patterns.framed_wall(0, 2, 8, 2, 1, 8, "south")
                             + patterns.balcony(1, 5, 3, "south", 3, 2, ground_y=0, door=True)),
    "gable_roof_trim_x": lambda: patterns.gable_roof_trim(0, 0, 10, 6, 1, overhang=2),
    "gable_roof_trim_z": lambda: patterns.gable_roof_trim(0, 0, 6, 9, 1, "oak_stairs", "spruce", ridge="z"),
    "gable_roof_trim_even": lambda: patterns.gable_roof_trim(0, 0, 9, 5, 1, overhang=1),
    "gable_roof_trim_open": lambda: patterns.gable_roof_trim(0, 0, 8, 6, 1, open_end="east"),
    "hip_roof_trim": lambda: patterns.hip_roof_trim(0, 0, 8, 6, 1),
    "cross_gable_roof": lambda: patterns.cross_gable_roof(0, 0, 16, 10, 1, front="south", overhang=2),
    "cross_gable_roof_e": lambda: patterns.cross_gable_roof(0, 0, 10, 16, 1, front="east"),
    "chimney": lambda: patterns.chimney(2, 1, 2, 8),
    "stilt_base": lambda: patterns.stilt_base(0, 0, 8, 6, 6),
    "farm_plot": lambda: patterns.farm_plot(2, 2, 2, 7, 7),
    "farm_plot_carrots": lambda: patterns.farm_plot(2, 2, 2, 9, 5, "carrots"),
    "fence_garden": lambda: patterns.fence_garden(0, 0, 10, 8, 2, gates=("south", "north")),
    "site": lambda: patterns.site(0, 0, 5, 5, 1),
    "road": lambda: patterns.road([[0, 0], [8, 0], [12, 6], [12, 12]], 1),
    "plaza": lambda: patterns.plaza(0, 0, 8, 8, 1),
    "external_stair": lambda: patterns.external_stair(0, 1, 0, "east", 9, 2, 4, 2),
    "external_stair_north": lambda: patterns.external_stair(5, 1, 20, "north", 6, 2, 3, 2, rails="left"),
    "external_stair_narrow": lambda: patterns.external_stair(0, 1, 0, "south", 3, 1, 4, 1, rails="none"),
    "balcony_access": lambda: (patterns.framed_wall(0, 2, 10, 2, 1, 10, "south")
                               + patterns.balcony(4, 6, 3, "south", 5, 3, ground_y=0, door=True, gap="start")
                               + patterns.external_stair(-4, 1, 4, "east", 6, 2, 3, 1, rails="right")),
    "storey_band": lambda: (patterns.framed_house(0, 0, 15, 10, 1, floors=2, storey=4, spacing=5, style="light")
                            + patterns.storey_band(0, 0, 15, 10, 5)),
    "storey_band_gaps": lambda: (patterns.framed_house(0, 0, 15, 10, 1, floors=2, storey=4, spacing=5)
                                 + patterns.storey_band(0, 0, 15, 10, 4, "teal", skip=["east"], gaps=[[5, 11, 9, 13]])),
    "gable_roof_teal": lambda: patterns.gable_roof_trim(0, 0, 10, 6, 1, "teal", "oak", overhang=2),
    "cross_gable_green": lambda: patterns.cross_gable_roof(0, 0, 16, 10, 1, "green", "spruce", front="south", overhang=2),
    "hip_roof_gray": lambda: patterns.hip_roof_trim(0, 0, 8, 6, 1, "gray", "dark_oak"),
    "manor_layout": lambda: patterns.manor_layout(0, 2, 0),
    "manor_layout_north": lambda: patterns.manor_layout(0, 2, 0, "north", raised=2),
    "manor_layout_east": lambda: patterns.manor_layout(0, 2, 0, "east", "plaster", "red", raised=5),
    "manor_layout_west": lambda: patterns.manor_layout(0, 2, 0, "west", raised=1),
    "manor_layout_stilts": lambda: (HILL + patterns.manor_layout(0, 8, 0, raised=3, stilts=True, ground=1)),
    "bay_window": lambda: (patterns.framed_house(0, 0, 12, 8, 1, floors=2, storey=4)
                           + patterns.bay_window(6, 1, 8, "south", 3, floors=2)),
    "bay_window_wide": lambda: (patterns.framed_house(0, 0, 12, 8, 1, floors=1, storey=4)
                                + patterns.bay_window(0, 1, 4, "west", 5, depth=2)),
    "dormer": lambda: (patterns.framed_house(0, 0, 14, 8, 1, floors=1, storey=4)
                       + patterns.gable_roof_trim(0, 0, 14, 8, 6, overhang=2) + patterns.dormer(7, 9, 8, "south")),
}
# every pattern that people walk up: 0 jump steps and 0 corner turns by checks.run AND by bench/score.py
STAIRS = ("stair_run_east", "stair_run_north", "stair_run_west", "switchback", "switchback_east", "porch_steps",
          "external_stair", "external_stair_north", "external_stair_narrow", "balcony_access", "storey_band",
          "storey_band_gaps", "manor_layout", "manor_layout_north", "manor_layout_east", "manor_layout_west",
          "manor_layout_stilts")


class Patterns(unittest.TestCase):
    def test_every_pattern_is_clean(self):
        for name, make in CASES.items():
            with self.subTest(name):
                blocks, meta = sandbox.run_safe(make())
                self.assertTrue(blocks)
                found = [f for f in checks.run(blocks) if f["check"] in KINDS]
                self.assertEqual(found, [], [f["text"] for f in found])
                self.assertEqual(meta.get("warnings"), [])
                self.assertEqual(meta.get("fixes"), [])

    def test_stair_patterns_have_no_jumps_or_corner_turns_by_the_bench(self):
        for name in STAIRS:
            with self.subTest(name):
                blocks, _ = sandbox.run_safe(CASES[name]())
                found = [f["text"] for f in checks.run(blocks) if f["check"] in ("jump_step", "corner_turn", "wrong_facing")]
                self.assertEqual(found, [])
                out = S.score(build(blocks))
                self.assertEqual((out["jump_steps"], out["corner_turns"], out["wrong_facing"], out["buried_path"]),
                                 (0, 0, 0, 0), out)

    def test_examples_have_no_jumps_or_corner_turns_by_the_bench(self):
        for name in examples.EXAMPLES:
            with self.subTest(name):
                out = S.score(build(sandbox.run_safe(examples.code(name))[0]))
                self.assertEqual((out["jump_steps"], out["corner_turns"]), (0, 0), out)

    def test_external_stair_climbs_in_flights_with_landings(self):
        blocks, _ = sandbox.run_safe(patterns.external_stair(0, 1, 0, "east", 6, 1, 3, 2, rails="none"))
        tops = {}
        for (x, y, z), s in blocks.items():
            tops[x] = max(tops.get(x, -1), y)
        self.assertEqual([tops[x] for x in range(10)], [1, 2, 3, 3, 3, 4, 5, 6, 6, 6])   # 3 steps, landing, 3, landing
        for x in (0, 1, 2, 5, 6, 7):
            self.assertIn("facing=east", blocks[(x, tops[x], 0)])
            self.assertIn("half=bottom", blocks[(x, tops[x], 0)])
        self.assertNotIn("stairs", blocks[(3, 3, 0)])

    def test_colours_and_styles(self):
        self.assertIn("prismarine_brick_stairs", patterns.gable_roof_trim(0, 0, 6, 4, 1, "teal", "oak"))
        self.assertIn("oxidized_cut_copper_stairs", patterns.hip_roof_trim(0, 0, 6, 4, 1, "green"))
        self.assertEqual(patterns._full("prismarine_brick_stairs"), "prismarine_bricks")
        self.assertEqual(patterns._full("dark_oak"), "dark_oak_planks")
        house = patterns.framed_house(0, 0, 8, 8, 1, style="light")
        self.assertIn("birch_planks", house)
        self.assertIn("'oak_log'", house)
        self.assertNotIn("dark_oak", house)
        self.assertEqual(patterns.framed_house(0, 0, 8, 8, 1), house)                  # the reference look is the default
        dark = patterns.framed_house(0, 0, 8, 8, 1, style="dark")                     # only when a dark build is asked
        self.assertIn("dark_oak_log", dark)
        self.assertIn("spruce_planks", dark)
        roof = patterns.gable_roof_trim(0, 0, 6, 4, 1)                                 # teal with an oak trim by default
        self.assertIn("prismarine_brick_stairs", roof)
        self.assertIn("'oak_stairs'", roof)
        for code in (roof, patterns.hip_roof_trim(0, 0, 6, 4, 1), patterns.cross_gable_roof(0, 0, 12, 8, 1),
                     patterns.window_with_box(0, 2, 0, "south", 2, 2), patterns.porch(0, 1, 0, "south"),
                     patterns.balcony(0, 5, 0, "south"), patterns.storey_band(0, 0, 8, 8, 4)):
            self.assertNotIn("dark_oak", code)
            self.assertNotIn("deepslate", code)
        self.assertIn("birch_trapdoor", patterns.window_with_box(0, 2, 0, "south"))   # white-framed windows
        self.assertIn("stripped_birch_log", patterns.window_with_box(0, 2, 0, "south"))
        self.assertIn("white_terracotta", patterns.framed_wall(0, 0, 8, 0, 1, 4, "north", style="plaster"))
        with self.assertRaises(ValueError):
            patterns.framed_house(0, 0, 8, 8, 1, style="neon")
        with self.assertRaises(ValueError):
            patterns.external_stair(0, 1, 0, "east", 4, rails="top")
        with self.assertRaises(ValueError):
            patterns.balcony(0, 5, 0, "south", gap="middle")

    def test_stairs_face_uphill(self):
        blocks, _ = sandbox.run_safe(patterns.straight_stair_run(0, 1, 0, "east", 4, 1))
        for i in range(4):
            self.assertIn("facing=east", blocks[(i, 1 + i, 0)])
            self.assertIn("half=bottom", blocks[(i, 1 + i, 0)])

    def test_switchback_climbs_twice(self):
        blocks, _ = sandbox.run_safe(patterns.switchback_landing(0, 1, 0, "south", 4, 2))
        self.assertEqual(max(p[1] for p in blocks), 1 + 2 * 4 - 1)

    def test_house_has_door_and_roof(self):
        blocks, _ = sandbox.run_safe(patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5))
        self.assertTrue(any("_door" in s for s in blocks.values()))
        self.assertTrue(any("stairs" in s for s in blocks.values()))

    def test_framed_wall_sticks_out(self):
        blocks, _ = sandbox.run_safe(patterns.framed_wall(0, 0, 8, 0, 1, 4, "north"))
        self.assertIn("minecraft:oak_log", blocks[(0, 2, -1)])           # a post one block out of the wall
        self.assertIn("axis=x", blocks[(3, 4, -1)])                      # the top beam
        self.assertIn("birch_planks", blocks[(2, 2, 0)])

    def test_window_boxes_only_directly_under_windows(self):
        for facing in ("north", "south", "east", "west"):
            for width, height in ((1, 1), (1, 2), (2, 2), (3, 2)):
                with self.subTest(facing=facing, width=width):
                    blocks, _ = sandbox.run_safe(patterns.window_with_box(5, 4, 5, facing, width, height,
                                                                          wall="oak_planks"))
                    dx, dz = patterns.DIRS[facing]
                    glass = {p for p, s in blocks.items() if "glass" in s}
                    bottom = {p for p in glass if (p[0], p[1] - 1, p[2]) not in glass}
                    self.assertEqual(len(bottom), width)
                    flowers = {p for p, s in blocks.items() if "poppy" in s}
                    soil = {p for p, s in blocks.items() if "grass_block" in s}
                    self.assertEqual(flowers, {(x + dx, y - 1, z + dz) for x, y, z in bottom})    # under each bottom pane, never in front of a pane
                    self.assertEqual(soil, {(x + dx, y - 2, z + dz) for x, y, z in bottom})   # the box right under it
                    self.assertEqual(len({s for p, s in blocks.items() if "poppy" in s}), 1)  # one flower kind

    def test_stilts_reach_the_ground(self):
        code = "fill(-2, 0, -2, 10, 0, 8, 'dirt')\nfill(4, 1, -2, 10, 2, 8, 'dirt')\n" + patterns.stilt_base(0, 0, 8, 6, 8)
        blocks, _ = sandbox.run_safe(code)
        self.assertIn("spruce_log", blocks[(0, 1, 0)])                   # down to the low ground
        self.assertIn("spruce_log", blocks[(8, 3, 0)])                   # stops on the high ground
        self.assertIn("dirt", blocks[(8, 2, 0)])
        found = [f for f in checks.run(blocks) if f["check"] in KINDS]
        self.assertEqual(found, [])

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            patterns.straight_stair_run(0, 0, 0, "up", 3)
        with self.assertRaises(ValueError):
            patterns.tree("palm", 0, 0, 0)
        with self.assertRaises(ValueError):
            patterns.framed_wall(0, 0, 4, 4, 1, 4, "north")
        with self.assertRaises(ValueError):
            patterns.framed_wall(0, 0, 4, 0, 1, 4, "east")
        with self.assertRaises(ValueError):
            patterns.gable_roof_trim(0, 0, 8, 4, 1, ridge="x", open_end="north")
        with self.assertRaises(ValueError):
            patterns.farm_plot(0, 1, 0, 12, 12)
        with self.assertRaises(ValueError):
            patterns.road([[0, 0]], 1)


if __name__ == "__main__":
    unittest.main()


class DirectCalls(unittest.TestCase):
    """Every pattern is callable by name inside a build script (the runner runs the text the pattern returns)."""

    SITE = "site(-30, -30, 30, 30, 1)\n"

    def _build(self, code):
        from blockforge import quality
        blocks, _ = sandbox.run_safe(self.SITE + code)
        return blocks, checks.run(blocks), quality.score(blocks)

    def test_manor_layout_by_name_equals_the_pattern_text(self):
        direct, found, q = self._build("manor_layout(0, 2, 0)\n")
        text, _ = sandbox.run_safe(self.SITE + patterns.manor_layout(0, 2, 0))
        self.assertEqual(direct, text)
        self.assertEqual([f for f in found if f["check"] in KINDS], [])
        self.assertGreaterEqual(q["total"], 85)

    def test_framed_house_by_name(self):
        direct, found, q = self._build("framed_house(0, 0, 12, 8, 2, 2, 4)\n")
        text, _ = sandbox.run_safe(self.SITE + patterns.framed_house(0, 0, 12, 8, 2, 2, 4))
        self.assertEqual(direct, text)
        self.assertEqual([f for f in found if f["check"] in KINDS], [])

    def test_keywords_and_variables_stay_separate(self):
        blocks, _ = sandbox.run_safe("x = 5\nwindow_with_box(0, 3, 0, 'south', width=2, height=2, wall='oak_planks')\n"
                                     "block(x, 0, 0, 'stone')\n")
        self.assertIn("stone", blocks[(5, 0, 0)])

    def test_unknown_name_still_errors(self):
        with self.assertRaises(sandbox.ScriptError) as c:
            sandbox.run_safe("not_a_pattern(0, 0, 0)\n")
        self.assertIn("not_a_pattern", str(c.exception))

    def test_private_helpers_are_not_exposed(self):
        with self.assertRaises(sandbox.ScriptError):
            sandbox.run_safe("_code(['x'])\n")

    def test_build_step_with_only_a_pattern_call(self):
        from blockforge import session
        s = session.start("Manor", "large")
        session.step(s, self.SITE)
        session.step(s, "manor_layout(0, 2, 0)\n", "manor")
        self.assertGreater(len(session.load(s.id).blocks), 1000)


class WindowsReadAsGlass(unittest.TestCase):
    def test_pattern_houses_have_no_bad_windows(self):
        from blockforge import quality
        for code in (patterns.manor_layout(0, 2, 0), patterns.framed_house(0, 0, 12, 8, 2, 2, 4)):
            blocks, _ = sandbox.run_safe("site(-30, -30, 30, 30, 1)\n" + code)
            m = quality._Model(blocks)
            self.assertEqual(quality._bad_window_cells(m), [])
            self.assertFalse(any("do not read as clear glass" in f for f in quality.score(blocks)["findings"]))

    def test_red_filled_windows_score_lower(self):
        from blockforge import quality
        code = "site(-30, -30, 30, 30, 1)\n" + patterns.manor_layout(0, 2, 0)
        blocks, _ = sandbox.run_safe(code)
        good = quality.score(blocks)
        red = dict(blocks)
        n = 0
        for p, s in blocks.items():
            if "glass_pane" in s:
                red[p] = "minecraft:red_stained_glass"
                n += 1
        self.assertGreater(n, 10)
        bad = quality.score(red)
        self.assertLess(bad["parts"]["windows"], good["parts"]["windows"])
        self.assertTrue(any("do not read as clear glass" in f for f in bad["findings"]), bad["findings"])
        self.assertTrue(any("red glass at x" in f for f in bad["findings"]))
