import unittest

from tests import _env  # noqa: F401
from blockforge import blockinfo as bi

M = "minecraft:"


class Info(unittest.TestCase):
    def test_stairs(self):
        d = bi.info(M + "oak_stairs[facing=east]")
        self.assertEqual((d["shape"], d["solid"], d["needs_support"]), ("stairs", False, "none"))
        self.assertEqual(d["properties"]["half"], ["bottom", "top"])
        self.assertIn("shape", d["properties"])

    def test_slab_and_full(self):
        self.assertEqual(bi.info("stone_brick_slab")["shape"], "slab")
        self.assertEqual(bi.info("stone_bricks")["shape"], "full")
        self.assertTrue(bi.info("stone_bricks")["solid"])
        self.assertEqual(bi.info("spruce_planks")["properties"], {})

    def test_door_trapdoor(self):
        d = bi.info("dark_oak_door")
        self.assertEqual(d["shape"], "door")
        self.assertEqual(d["properties"]["hinge"], ["left", "right"])
        self.assertEqual(d["needs_support"], "below")
        self.assertEqual(bi.info("oak_trapdoor")["shape"], "trapdoor")

    def test_fence_wall_pane(self):
        self.assertEqual(bi.info("oak_fence")["shape"], "fence")
        self.assertEqual(bi.info("oak_fence_gate")["properties"]["open"], ["true", "false"])
        w = bi.info("cobblestone_wall")
        self.assertEqual((w["shape"], w["properties"]["north"]), ("wall", ["none", "low", "tall"]))
        self.assertEqual(bi.info("glass_pane")["shape"], "pane")
        self.assertEqual(bi.info("white_stained_glass_pane")["shape"], "pane")

    def test_lantern(self):
        self.assertEqual(bi.info("lantern[hanging=true]")["needs_support"], "above")
        self.assertEqual(bi.info("lantern[hanging=false]")["needs_support"], "below")
        self.assertEqual(bi.info("lantern")["light"], 15)
        self.assertEqual(bi.info("soul_lantern")["light"], 10)
        self.assertEqual(bi.info("sea_lantern")["light"], 15)
        self.assertNotEqual(bi.info("sea_lantern")["shape"], "lantern")

    def test_torches(self):
        t, w = bi.info("torch"), bi.info("wall_torch[facing=north]")
        self.assertEqual((t["needs_support"], t["light"]), ("below", 14))
        self.assertEqual((w["needs_support"], w["properties"]), ("side", {"facing": bi.HORIZ}))
        self.assertEqual(bi.info("soul_torch")["light"], 10)
        self.assertEqual(bi.info("redstone_torch")["light"], 7)

    def test_logs_leaves(self):
        self.assertEqual(bi.info("oak_log")["properties"]["axis"], ["x", "y", "z"])
        self.assertTrue(bi.info("oak_log")["solid"])
        self.assertIn("persistent", bi.info("oak_leaves")["properties"])
        self.assertEqual(bi.info("stripped_oak_log")["shape"], "full")

    def test_gravity(self):
        for n in ("sand", "gravel", "anvil", "white_concrete_powder", "red_sand"):
            self.assertTrue(bi.info(n)["gravity"], n)
            self.assertEqual(bi.info(n)["needs_support"], "below", n)
        self.assertFalse(bi.info("sandstone")["gravity"])
        self.assertFalse(bi.info("white_concrete")["gravity"])

    def test_plants_carpet_signs(self):
        self.assertEqual(bi.info("short_grass")["shape"], "plant")
        self.assertEqual(bi.info("poppy")["needs_support"], "below")
        self.assertEqual(bi.info("red_carpet")["shape"], "carpet")
        self.assertEqual(bi.info("oak_sign")["shape"], "sign")
        self.assertEqual(bi.info("oak_wall_sign")["needs_support"], "side")
        self.assertEqual(bi.info("oak_hanging_sign")["needs_support"], "above")
        self.assertEqual(bi.info("ladder")["needs_support"], "side")

    def test_light_props(self):
        self.assertEqual(bi.info("light[level=9]")["light"], 9)
        self.assertEqual(bi.info("furnace[lit=true]")["light"], 13)
        self.assertEqual(bi.info("furnace")["light"], 0)
        self.assertEqual(bi.info("glowstone")["light"], 15)
        self.assertEqual(bi.info("candle[candles=2,lit=true]")["light"], 6)

    def test_unknown_and_air(self):
        d = bi.info("minecraft:made_up_thing")
        self.assertEqual((d["shape"], d["solid"], d["properties"]), ("other", False, {}))
        self.assertFalse(bi.info("air")["solid"])

    def test_check_properties(self):
        self.assertEqual(bi.check_properties("oak_stairs[facing=east,half=bottom,shape=straight]"), [])
        self.assertEqual(bi.check_properties("oak_stairs[facing=up]"), ["facing=up"])
        self.assertEqual(bi.check_properties("oak_log[axis=q]"), ["axis=q"])

    def test_explain(self):
        s = bi.explain("lantern[hanging=true]")
        self.assertTrue(s.endswith(".") and "underside" in s and "15" in s, s)
        self.assertIn("falls", bi.explain("sand"))
        self.assertIn("facing", bi.explain("oak_stairs"))
        self.assertEqual(bi.explain("stone").count("."), 1)


if __name__ == "__main__":
    unittest.main()
