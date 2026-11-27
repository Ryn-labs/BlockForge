"""The benchmark scorer (bench/score.py, v2) must still flag real buried paths and must not flag walls next to roof stairs."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench"))
import score as S


def build(blocks):
    d = tempfile.mkdtemp(prefix="bf-score-test-")
    pal = sorted(set(blocks.values())); idx = {p: i for i, p in enumerate(pal)}
    flat = []
    for (x, y, z), s in sorted(blocks.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        flat += [x, y, z, idx[s]]
    xs = [p[0] for p in blocks]; ys = [p[1] for p in blocks]; zs = [p[2] for p in blocks]
    json.dump({"size": [max(xs) + 1, max(ys) + 1, max(zs) + 1], "palette": pal, "blocks": flat}, open(os.path.join(d, "blocks.json"), "w"))
    json.dump({"title": "t", "fixes": []}, open(os.path.join(d, "meta.json"), "w"))
    return d


def ground(b, w=12, l=6):
    for x in range(w):
        for z in range(l): b[(x, 0, z)] = "minecraft:stone"


class ScoreV2(unittest.TestCase):
    def test_stair_with_a_block_over_it_is_buried(self):
        b = {}; ground(b)
        for i in range(5):
            for z in range(1, 4):
                b[(2 + i, 1 + i, z)] = "minecraft:stone_brick_stairs[facing=east,half=bottom,shape=straight]"
                for k in range(1, 1 + i): b[(2 + i, k, z)] = "minecraft:stone_bricks"
        b[(4, 4, 2)] = "minecraft:stone"                                    # a block right over the third step (walk space)
        self.assertGreaterEqual(S.score(build(b))["buried_path"], 1)

    def test_path_running_into_a_hill_is_buried(self):
        b = {}; ground(b)
        for x in range(12):
            b[(x, 1, 2)] = "minecraft:gravel"
        b[(3, 1, 3)] = "minecraft:stone_brick_slab[type=bottom]"            # a step beside the path makes it a path
        for x in range(5, 9):
            for y in (2, 3):
                b[(x, y, 2)] = "minecraft:dirt"                             # the hill: the path goes on under it
        self.assertGreaterEqual(S.score(build(b))["buried_path"], 1)

    def test_wall_next_to_roof_stairs_is_not_a_path(self):
        b = {}; ground(b)
        for x in range(1, 10):
            for y in range(1, 5):
                b[(x, y, 2)] = "minecraft:stone_bricks"                     # a wall
            b[(x, 5, 1)] = "minecraft:stone_brick_stairs[facing=south,half=bottom,shape=straight]"
            b[(x, 5, 3)] = "minecraft:stone_brick_stairs[facing=north,half=bottom,shape=straight]"
            b[(x, 5, 2)] = "minecraft:stone_brick_slab[type=bottom]"
        self.assertEqual(S.score(build(b))["buried_path"], 0)


if __name__ == "__main__":
    unittest.main()
