"""Makes the fixed natural hill used by bench prompt 11: bench/terrain/hill.schem (160 x 70 x 160, seed 11).
Smooth value-noise hills (one clearly highest), grass over dirt over stone, a few oak and spruce trees.
Deterministic: the same seed always gives the same file.   python bench/make_terrain.py [out.schem]"""
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from blockforge import exporters  # noqa: E402

W = L = 160
H = 70
SEED = 11
OUT = os.path.join(ROOT, "bench", "terrain", "hill.schem")


def _lattice(rng, n):
    return [[rng.random() for _ in range(n)] for _ in range(n)]


def _noise(lat, x, z, cell):
    gx, gz = x / cell, z / cell
    x0, z0 = int(gx), int(gz)
    fx, fz = gx - x0, gz - z0
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = lat[z0][x0], lat[z0][x0 + 1]
    c, d = lat[z0 + 1][x0], lat[z0 + 1][x0 + 1]
    return (a + (b - a) * fx) * (1 - fz) + (c + (d - c) * fx) * fz


def heights():
    rng = random.Random(SEED)
    big, mid, small = _lattice(rng, W // 40 + 3), _lattice(rng, W // 16 + 3), _lattice(rng, W // 6 + 3)
    out = {}
    for z in range(L):
        for x in range(W):
            h = 12 + 20 * _noise(big, x, z, 40) + 8 * _noise(mid, x, z, 16) + 2.0 * _noise(small, x, z, 6)
            # one clear highest hill (the castle hill) and a gentle valley rim
            d = math.hypot(x - 105, z - 62)
            h += 26 * math.exp(-(d * d) / (2 * 22 ** 2))
            edge = min(x, z, W - 1 - x, L - 1 - z)
            if edge < 10:
                h = h * (0.55 + 0.045 * edge)
            out[(x, z)] = max(4, min(H - 14, int(round(h))))
    return out


def build():
    top = heights()
    blocks = {}
    for (x, z), h in top.items():
        for y in range(h + 1):
            blocks[(x, y, z)] = ("minecraft:grass_block" if y == h else "minecraft:dirt" if y >= h - 3 else "minecraft:stone")
    rng = random.Random(SEED + 1)
    trees = 0
    tries = 0
    while trees < 34 and tries < 4000:
        tries += 1
        x, z = rng.randrange(6, W - 6), rng.randrange(6, L - 6)
        h = top[(x, z)]
        if h > 44 or any(abs(top[(x + a, z + c)] - h) > 1 for a in (-1, 0, 1) for c in (-1, 0, 1)):
            continue
        if math.hypot(x - 105, z - 62) < 14:
            continue                                                  # keep the hilltop free for the castle
        spruce = rng.random() < 0.4
        tall = rng.randrange(4, 7)
        log, leaf = ("minecraft:spruce_log", "minecraft:spruce_leaves") if spruce else ("minecraft:oak_log", "minecraft:oak_leaves")
        for y in range(h + 1, h + 1 + tall):
            blocks[(x, y, z)] = log
        top_y = h + tall
        for dy in range(-2, 2):
            r = 2 if dy < 1 else 1
            for a in range(-r, r + 1):
                for c in range(-r, r + 1):
                    p = (x + a, top_y + dy, z + c)
                    if abs(a) + abs(c) <= r + 1 and p not in blocks:
                        blocks[p] = leaf
        blocks.setdefault((x, top_y + 2, z), leaf)
        trees += 1
    return blocks


def main(path=OUT):
    blocks = build()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exporters.write_schem(path, exporters.to_dict(blocks), "bench hill")
    return path, len(blocks)


if __name__ == "__main__":
    p, n = main(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print(f"{p}: {n:,} blocks, {os.path.getsize(p):,} bytes")
