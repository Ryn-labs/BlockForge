"""The building quality score (blockforge/quality.py): calibration builds from a bare box to a pattern-built manor, the
bench builds the owner's reviewer found too generously scored (tests/data, rounds 2 and 3 of 27 Nov) and the looks
measured on the render (round 3: the 1.13.0 manor read near-black but scored 85)."""
import json
import os
import re
import unittest

from tests import _env  # noqa: F401
from blockforge import checks, examples, patterns, quality, sandbox

KINDS = ("buried_path", "jump_step", "door_blocked", "floating", "headroom", "wrong_facing", "corner_turn")
BOX = ("fill(0,0,0,8,0,8,'cobblestone')\n"                        # plain 9 x 9 cobblestone box with a flat roof and a door
       "walls(0,1,0,8,4,8,'cobblestone')\n"
       "fill(0,5,0,8,5,8,'cobblestone')\n"
       "block(4,1,8,B('oak_door',facing='south',half='lower'))\n"
       "block(4,2,8,B('oak_door',facing='south',half='upper'))\n")
_cache = {}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# the two bench builds of 27 Nov (1.16-quality) that scored 87 and 94 but look nothing like the references: single
# storey looking, dark wood everywhere, long and low (blocks.json of the bench, kept as fixtures)
BENCH = {"manor": ("bench_wooden_manor_blocks.json", "large",
                   "A wooden manor with log frames, a layered roof, a balcony, window boxes and a terrace garden."),
         "cottage": ("bench_small_cottage_blocks.json", "small", "A small cottage."),
         # the 1.13.0 manor (owner, 27 Nov: "the whole house reads near-black": dark oak frames, spruce and deepslate,
         # a black roof) that scored 85
         "dark": ("bench_dark_manor_1130_blocks.json", "large",
                  "A wooden manor with log frames, a layered roof, a balcony, window boxes and a terrace garden.")}


def blocks_of(code):
    if code not in _cache:
        _cache[code] = sandbox.run_safe(code)[0]
    return _cache[code]


def bench_build(key):
    """(blocks, size, prompt) of a stored bench build."""
    name, size, prompt = BENCH[key]
    if name not in _cache:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            bj = json.load(f)
        b = bj["blocks"]
        _cache[name] = {(b[i], b[i + 1], b[i + 2]): bj["palette"][b[i + 3]] for i in range(0, len(b), 4)}
    return _cache[name], size, prompt


def light(house):
    return quality.score(blocks_of(house))


class Calibration(unittest.TestCase):
    def test_plain_box_scores_under_25(self):
        r = quality.score(blocks_of(BOX))
        self.assertTrue(r["building"])
        self.assertLess(r["total"], 25, quality.summary(r))
        self.assertLess(r["parts"]["roof"], 20)                          # a flat box top is a big roof penalty
        self.assertEqual(r["parts"]["facade"], 0)

    def test_plain_shell_with_a_roof_is_below_the_gate(self):
        r = quality.score(blocks_of(patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5)))
        self.assertTrue(r["building"])
        self.assertLess(r["total"], quality.QUALITY_MIN, quality.summary(r))
        self.assertGreater(r["parts"]["roof"], r["parts"]["facade"])     # it has a pitched roof, but flat walls

    def test_pattern_cottage_scores_70_or_more(self):
        r = quality.score(blocks_of(examples.code("good_cottage")))
        self.assertGreaterEqual(r["total"], 70, quality.summary(r))
        for part in quality.WEIGHTS:
            self.assertGreaterEqual(r["parts"][part], 60, (part, quality.summary(r)))

    def test_pattern_manor_scores_80_or_more(self):
        r = quality.score(blocks_of(examples.code("good_manor")))
        self.assertGreaterEqual(r["total"], 80, quality.summary(r))

    def test_reference_like_manor_scores_80_or_more(self):
        r = quality.score(blocks_of(examples.code("light_manor")))
        self.assertGreaterEqual(r["total"], 80, quality.summary(r))
        for part in ("contrast", "looks", "storeys", "balcony", "roof_style"):
            self.assertGreaterEqual(r["parts"][part], 80, (part, quality.summary(r)))
        self.assertIsNone(r["looks"]["cap"])
        self.assertGreaterEqual(r["looks"]["wall_lightness"], 50)                # light walls on the render
        self.assertGreaterEqual(r["looks"]["roof_colour"], 0.8)                  # a teal roof

    def test_dark_1130_manor_is_below_the_gate(self):
        blocks, size, prompt = bench_build("dark")
        r = quality.score(blocks, size, prompt)
        self.assertLess(r["total"], quality.QUALITY_MIN, quality.summary(r))
        self.assertIsNotNone(r["looks"]["cap"])                                  # held down because it reads dark
        self.assertLess(r["looks"]["wall_lightness"], 42)
        self.assertLess(r["looks"]["roof_colour"], 0.2)                          # the near-black deepslate roof
        self.assertLess(r["parts"]["looks"], 50)
        self.assertLess(r["parts"]["roof_style"], 60)
        self.assertTrue(any("reads dark" in f for f in r["findings"]), r["findings"][:3])

    def test_dark_build_asked_for_is_not_penalised_for_darkness(self):
        blocks, size, _ = bench_build("dark")
        r = quality.score(blocks, size, "A dark gothic manor with log frames and a terrace garden.")
        self.assertTrue(r["looks"]["dark_asked"])
        self.assertIsNone(r["looks"]["cap"])
        self.assertGreaterEqual(r["total"], 80, quality.summary(r))
        self.assertEqual(r["parts"]["looks"], 100)
        self.assertFalse(any("reads dark" in f for f in r["findings"]))
        for p in ("spooky witch house", "Haunted mansion at night", "a medieval stronghold", "Blackstone fortress"):
            self.assertTrue(quality.dark_asked(p), p)
        for p in ("A wooden manor", "a blacksmith's cottage", "A light birch house", None):
            self.assertFalse(quality.dark_asked(p), p)

    def test_near_black_house_cannot_pass_the_gate(self):
        """The reference-like manor rebuilt in dark oak, spruce and deepslate: same shape, so only the colours differ."""
        code = (examples.code("light_manor").replace("birch_planks", "spruce_planks").replace("'oak_log'", "'dark_oak_log'")
                .replace("prismarine_brick", "deepslate_tile").replace("birch_trapdoor", "dark_oak_trapdoor"))
        r = quality.score(blocks_of(code))
        self.assertLess(r["total"], quality.QUALITY_MIN, quality.summary(r))
        self.assertGreaterEqual(quality.score(blocks_of(code), prompt="a spooky manor")["total"], 80)

    def test_bench_manor_dark_long_and_low_is_below_the_gate(self):
        blocks, size, prompt = bench_build("manor")
        r = quality.score(blocks, size, prompt)
        self.assertLess(r["total"], quality.QUALITY_MIN, quality.summary(r))
        self.assertLess(r["parts"]["contrast"], 60)                     # dark spruce logs everywhere
        self.assertLess(r["parts"]["storeys"], 50)                      # long and low
        self.assertLess(r["parts"]["roof_style"], 60)                   # spruce roof on spruce walls
        self.assertTrue(any("long and low" in f for f in r["findings"]), r["findings"])

    def test_bench_cottage_dark_one_storey_is_below_the_gate(self):
        blocks, size, prompt = bench_build("cottage")
        r = quality.score(blocks, size, prompt)
        self.assertGreaterEqual(r["total"], 30, quality.summary(r))
        self.assertLess(r["total"], quality.QUALITY_MIN, quality.summary(r))      # dark logs, dark oak roof
        self.assertLess(r["parts"]["contrast"], 40)
        self.assertGreaterEqual(r["parts"]["storeys"], 60)               # one storey is fine for a small cottage

    def test_order_box_bench_patterns(self):
        box = quality.score(blocks_of(BOX))["total"]
        manor = max(quality.score(*bench_build("manor"))["total"], quality.score(*bench_build("dark"))["total"])
        ref = quality.score(blocks_of(examples.code("light_manor")))["total"]
        self.assertLess(box, manor)
        self.assertLess(manor, quality.score(blocks_of(examples.code("good_manor")))["total"])
        self.assertLess(manor, ref)

    def test_order_box_shell_cottage(self):
        box = quality.score(blocks_of(BOX))["total"]
        shell = quality.score(blocks_of(patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5)))["total"]
        cottage = quality.score(blocks_of(examples.code("good_cottage")))["total"]
        self.assertLess(box, shell)
        self.assertLess(shell, cottage)


class Parts(unittest.TestCase):
    def test_weights_add_up(self):
        self.assertEqual(sum(quality.WEIGHTS.values()), 100)
        self.assertEqual(set(quality.WEIGHTS), {"facade", "roof", "massing", "palette", "detail", "surroundings",
                                                "contrast", "looks", "storeys", "windows", "balcony", "roof_style"})
        self.assertGreaterEqual(quality.WEIGHTS["contrast"] + quality.WEIGHTS["looks"], 30)    # colours on the render
        new = sum(quality.WEIGHTS[k] for k in ("contrast", "storeys", "windows", "balcony", "roof_style"))
        self.assertGreaterEqual(new, 60)                                 # the reference look carries the score
        self.assertEqual(set(quality.LABELS) >= set(quality.WEIGHTS), True)

    def test_findings_have_coordinates(self):
        r = quality.score(blocks_of(BOX))
        self.assertTrue(r["findings"])
        self.assertTrue(any(re.search(r"\(-?\d+, -?\d+, -?\d+\)", f) for f in r["findings"]))
        for part, score, fixes in quality.weakest(r):
            self.assertTrue(fixes, part)
            self.assertTrue(any(re.search(r"\d", f) for f in fixes), fixes)

    def test_gate_text_lists_three_weakest_parts(self):
        r = quality.score(blocks_of(BOX))
        text = quality.gate_text(r)
        self.assertIn(str(quality.QUALITY_MIN), text)
        self.assertEqual(len([ln for ln in text.splitlines() if ln.startswith("- ")]), 3)
        self.assertIn("Wall contrast", text)

    def test_one_material_and_random_materials_are_low(self):
        r = quality.score(blocks_of(BOX))
        self.assertLess(r["parts"]["palette"], 30)
        mats = ["stone", "andesite", "granite", "diorite", "bricks", "oak_planks", "spruce_planks", "birch_planks",
                "sandstone", "end_stone_bricks", "prismarine", "white_wool"]
        code = "fill(0,0,0,11,0,11,'cobblestone')\n" + "".join(
            f"fill({i},1,0,{i},4,0,'{m}')\nfill({i},1,11,{i},4,11,'{m}')\nfill(0,1,{i},0,4,{i},'{m}')\nfill(11,1,{i},11,4,{i},'{m}')\n"
            for i, m in enumerate(mats)) + "fill(0,5,0,11,5,11,'oak_planks')\n"
        rr = quality.score(blocks_of(code))
        self.assertTrue(any("random" in f for f in rr["findings"]), rr["findings"])

    def test_small_size_or_prompt_lets_one_storey_pass(self):
        self.assertTrue(quality.is_small("small"))
        self.assertTrue(quality.is_small(None, "A tiny hut by the lake"))
        self.assertTrue(quality.is_small("", "A Small Cottage."))
        self.assertFalse(quality.is_small("large", "A wooden manor"))
        one = patterns.framed_house(0, 0, 12, 8, 1, floors=1, storey=4, style="light", spacing=4)
        big = quality.score(blocks_of(one))
        small = quality.score(blocks_of(one), size="small")
        self.assertGreater(small["parts"]["storeys"], big["parts"]["storeys"])
        self.assertEqual(quality.score(blocks_of(one), prompt="a cottage")["parts"]["storeys"], small["parts"]["storeys"])
        self.assertLess(quality.score(blocks_of(BOX), size="small")["total"], 25)


class Looks(unittest.TestCase):
    """The looks are measured on the side views drawn with render.py's block colours, not on block lists."""

    def test_render_measures(self):
        light_house = patterns.framed_house(0, 0, 15, 10, 1, floors=2, storey=4, spacing=5)
        dark_house = patterns.framed_house(0, 0, 15, 10, 1, floors=2, storey=4, spacing=5, style="dark")
        lit = quality.score(blocks_of(light_house + patterns.gable_roof_trim(0, 0, 15, 10, 11, overhang=2)))["looks"]
        dark = quality.score(blocks_of(dark_house + patterns.gable_roof_trim(0, 0, 15, 10, 11, "gray", "dark_oak",
                                                                             overhang=2)))["looks"]
        self.assertGreater(lit["wall_lightness"], dark["wall_lightness"] + 15)
        self.assertGreater(lit["light_share"], 0.5)
        self.assertLess(dark["light_share"], 0.2)
        self.assertGreater(lit["fill_lightness"] - lit["frame_lightness"], 20)    # birch fill, oak log frame
        self.assertGreater(lit["roof_colour"], 0.8)                               # teal
        self.assertLess(dark["roof_colour"], 0.1)                                 # deepslate
        self.assertGreater(lit["closeness"], dark["closeness"])

    def test_reference_palette_is_derived_numbers_only(self):
        refs = quality.ref_palette()
        self.assertGreaterEqual(len(refs), 5)                                     # the five photos (refs 6-7 are plans)
        for name, h in refs.items():
            self.assertEqual(len(h), quality.HIST_SIZE, name)
            self.assertAlmostEqual(sum(h), 1.0, places=2)
        self.assertAlmostEqual(quality.hist_closeness(refs[min(refs)], refs[min(refs)]), 1.0)
        oak = quality.colour_hist([quality.colour("oak_planks")] * 10)
        black = quality.colour_hist([quality.colour("blackstone")] * 10)
        self.assertGreater(max(quality.hist_closeness(oak, h) for h in refs.values()),
                           max(quality.hist_closeness(black, h) for h in refs.values()))


class NewParts(unittest.TestCase):
    """Each new part reacts to what it measures, on the same house with one thing changed."""

    def house(self, **kw):
        a = dict(floors=2, storey=4, spacing=5, style="light")
        a.update(kw)
        return patterns.framed_house(0, 0, 15, 10, 1, **a)

    def test_contrast_light_fill_in_dark_frame_beats_one_dark_wood(self):
        lit = light(self.house())
        dark = light(self.house(style=None, fill="spruce_planks", frame="spruce_log"))
        self.assertGreaterEqual(lit["parts"]["contrast"], 80, quality.summary(lit))
        self.assertLess(dark["parts"]["contrast"], 30, quality.summary(dark))
        self.assertTrue(any("Wall contrast" in f for f in dark["findings"]))
        self.assertLess(quality.lightness("spruce_log"), 25)
        self.assertGreater(quality.lightness("birch_planks"), 65)

    def test_storeys_two_floors_beat_one_long_low_floor(self):
        two = light(self.house())
        low = light(patterns.framed_house(0, 0, 40, 8, 1, floors=1, storey=4, spacing=5, style="light"))
        self.assertGreaterEqual(two["parts"]["storeys"], 75)
        self.assertLess(low["parts"]["storeys"], 20)
        self.assertTrue(any("long and low" in f for f in low["findings"]))

    def test_attic_under_the_roof_is_not_a_storey(self):
        one = self.house(floors=1) + patterns.gable_roof_trim(0, 0, 15, 10, 6, "teal", "oak", "x", overhang=2)
        r = light(one)
        self.assertTrue(any("1 floor" in f for f in r["findings"]), r["findings"])

    def test_big_framed_windows_beat_small_ones(self):
        def windows(width):
            spots = [(x, y, z, f) for y in (2, 7) for x, z, f in ((2, 10, "south"), (12, 10, "south"), (2, 0, "north"),
                                                                    (7, 0, "north"), (12, 0, "north"))]
            spots += [(0, y, z, "west") for y in (2, 7) for z in (2, 7)] + [(15, y, z, "east") for y in (2, 7) for z in (2, 7)]
            return "".join(patterns.window_with_box(x, y, z, f, width=width, height=2) for x, y, z, f in spots)
        big = light(self.house() + windows(2))
        small = light(self.house() + windows(1))
        bare = light(self.house())
        self.assertGreater(big["parts"]["windows"], small["parts"]["windows"])
        self.assertGreater(small["parts"]["windows"], bare["parts"]["windows"])
        self.assertGreaterEqual(big["parts"]["windows"], 80, quality.summary(big))

    def test_balconies_and_outside_stair_count(self):
        bare = light(self.house())
        one = light(self.house() + patterns.balcony(5, 5, 11, "south", 5, 3, door=True))
        two = light(self.house() + patterns.balcony(5, 5, 11, "south", 5, 3, door=True)
                    + patterns.balcony(5, 5, -1, "north", 5, 3, gap="start")
                    + patterns.external_stair(-2, 1, -2, "east", 5, 2, 3, 1, rails="left"))
        self.assertEqual(bare["parts"]["balcony"], 0)
        self.assertGreater(one["parts"]["balcony"], bare["parts"]["balcony"])
        self.assertGreater(two["parts"]["balcony"], one["parts"]["balcony"])
        self.assertGreaterEqual(two["parts"]["balcony"], 85, quality.summary(two))

    def test_roof_colour_and_layers(self):
        roof = patterns.gable_roof_trim(0, 0, 15, 10, 11, "{}", "dark_oak", "x", overhang=2)
        same = light(self.house(style=None, fill="spruce_planks", frame="spruce_log") + roof.replace("{}", "spruce_stairs"))
        teal = light(self.house() + roof.replace("{}", "prismarine_brick_stairs"))
        band = light(self.house() + patterns.storey_band(0, 0, 15, 10, 4)
                     + roof.replace("{}", "prismarine_brick_stairs")
                     + patterns.framed_house(15, 2, 23, 8, 1, storey=4, style="light", skip=["west"], clear=True)
                     + patterns.gable_roof_trim(15, 2, 23, 8, 6, "teal", "oak", "x", overhang=2, open_end="west"))
        self.assertLess(same["parts"]["roof_style"], 30, quality.summary(same))
        self.assertGreater(teal["parts"]["roof_style"], same["parts"]["roof_style"] + 40)
        self.assertGreaterEqual(band["parts"]["roof_style"], 90, quality.summary(band))


class NotBuildings(unittest.TestCase):
    def test_bridge_tree_terrain_wall_are_not_scored(self):
        hill = ("for x in range(24):\n  for z in range(24):\n    h = int(3 + 3 * noise(x, z, 6))\n"
                "    fill(x, 0, z, x, h, z, 'dirt')\n    block(x, h + 1, z, 'grass_block')\n")
        for name, code in (("bridge", patterns.stone_arch_bridge(2, 6, 2, 11, 3)), ("tree", patterns.tree("oak", 4, 1, 4, 6)),
                           ("terrain", hill), ("wall", "fill(0,0,0,20,5,0,'stone_bricks')\n"),
                           ("pavilion", "fill(0,0,0,8,0,8,'stone')\nfor x, z in ((0,0),(0,8),(8,0),(8,8)):\n"
                                        "    fill(x,1,z,x,4,z,'oak_log')\nfill(0,5,0,8,5,8,'oak_planks')\n")):
            with self.subTest(name):
                r = quality.score(blocks_of(code))
                self.assertFalse(r["building"])
                self.assertIsNone(r["total"])
        self.assertFalse(quality.score({})["building"])

    def test_built_only_drops_the_land(self):
        land = {(0, 0, 0): "minecraft:dirt", (1, 0, 0): "minecraft:dirt"}
        blocks = dict(land)
        blocks[(1, 0, 0)] = "minecraft:cobblestone"
        blocks[(1, 1, 0)] = "minecraft:oak_planks"
        self.assertEqual(set(quality.built_only(blocks, land)), {(1, 0, 0), (1, 1, 0)})
        self.assertIs(quality.built_only(blocks, None), blocks)


ROW = ("for i in range(5):\n"                                     # five identical flat boxes on one straight road
       "    x = i * 12\n"
       "    fill(x,0,0,x+8,0,8,'cobblestone')\n"
       "    walls(x,1,0,x+8,4,8,'cobblestone')\n"
       "    fill(x,5,0,x+8,5,8,'cobblestone')\n"
       "    block(x+4,1,8,B('oak_door',facing='south',half='lower'))\n"
       "    block(x+4,2,8,B('oak_door',facing='south',half='upper'))\n"
       "fill(0,0,10,56,0,12,'gravel')\n")


class Towns(unittest.TestCase):
    def test_straight_row_of_identical_boxes_scores_under_30(self):
        r = quality.score(blocks_of(ROW))
        self.assertTrue(r["town"])
        self.assertEqual(r["buildings"], 5)
        self.assertLess(r["total"], 30, quality.summary(r))
        self.assertEqual(r["parts"]["variety"], 0)
        self.assertEqual(r["parts"]["landmark"], 0)
        self.assertTrue(any("straight line" in f for f in r["findings"]))

    def test_varied_pattern_village_scores_70_or_more(self):
        r = quality.score(blocks_of(examples.code("good_village")))
        self.assertTrue(r["town"])
        self.assertGreaterEqual(r["buildings"], 5)
        self.assertGreaterEqual(r["total"], 70, quality.summary(r))
        for part in quality.TOWN_WEIGHTS:
            self.assertGreaterEqual(r["parts"][part], 60, (part, quality.summary(r)))

    def test_a_house_with_a_wing_is_one_building(self):
        r = quality.score(blocks_of(examples.code("good_manor")))
        self.assertFalse(r["town"])
        self.assertEqual(r["buildings"], 1)

    def test_town_weights(self):
        self.assertEqual(sum(quality.TOWN_WEIGHTS.values()), 100)
        r = quality.score(blocks_of(ROW))
        self.assertAlmostEqual(sum(r["weights"].values()), 100)
        self.assertIn(quality.weakest(r)[0][0], set(quality.WEIGHTS) | set(quality.TOWN_WEIGHTS))


class Examples(unittest.TestCase):
    def test_examples_are_clean(self):
        for name in examples.EXAMPLES:
            with self.subTest(name):
                blocks, meta = sandbox.run_safe(examples.code(name))
                found = [f["text"] for f in checks.run(blocks) if f["check"] in KINDS]
                self.assertEqual(found, [])
                self.assertEqual(meta.get("warnings"), [])
                self.assertEqual(meta.get("fixes"), [])

    def test_examples_have_source_and_licence(self):
        for name, mod in examples.EXAMPLES.items():
            self.assertTrue(mod.TITLE and mod.SOURCE and mod.LICENCE, name)
        with self.assertRaises(KeyError):
            examples.code("nope")


if __name__ == "__main__":
    unittest.main()
