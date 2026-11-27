"""Benchmark scorer (v2, 27 Nov: path blocks must be column tops; buried counts steps only): counts the mistakes in one finished build (lower is better, nothing hidden).
Works on a build folder in the (temp) data dir: blocks.json, meta.json, code.py.
  floating       solid blocks in groups that never touch the ground layer (y 0)
  removed        lights/signs/plants/doors the final pass deleted (from meta.fixes "Removed ...")
  overwritten    blocks the script placed and later replaced with a different block (re-run of code.py, counted)
  buried_path    walkable stairs/slabs/path blocks with a solid block in the 2 cells above
  jump_steps     next-door standing spots on a path whose feet height differs by more than 0.6 (a jump either way)
  corner_turns   walkable stairs turning 90 degrees on one block (next stair at the same/next height facing sideways)
  blocked_doors  doors with a solid block right in front of or behind them
  wrong_facing   walkable stairs whose high side points downhill
  size_off       how far the largest side is outside the asked size range (blocks)
  terrain_floating / terrain_buried   (builds on a terrain) floating groups with ground under them, and path blocks / steps with
                 untouched terrain on top of them. They are counted INSTEAD of floating / buried_path, never twice.
  terrain_score  blockforge.terrain_quality total 0-100 of AI-made land (HIGHER is better; null when the build is not mostly land)
  quality        blockforge.quality.score total 0-100 (HIGHER is better; buildings and towns only, null for a bridge, tree,
                 terrain...). On terrain only what was built is scored. Not a mistake count: it is never added to the totals.
python bench/score.py <build dir> [target_lo target_hi] [--terrain file.schem]   -> one JSON line"""
import sys, os, json, collections, re

FULLISH = ("planks", "stone", "bricks", "log", "wood", "cobblestone", "dirt", "grass_block", "sand", "gravel", "terracotta", "concrete",
           "wool", "glass", "deepslate", "andesite", "diorite", "granite", "tuff", "calcite", "basalt", "blackstone", "quartz_block",
           "prismarine", "mud", "clay", "moss_block", "podzol", "netherrack", "obsidian", "ore", "_block", "bookshelf", "hay_block")
PASS = ("air", "cave_air", "light", "short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "vine", "snow")
NAT = ("dirt", "grass_block", "stone", "andesite", "diorite", "granite", "tuff", "coarse_dirt", "podzol", "gravel", "rooted_dirt", "deepslate", "sand")
PATHMAT = ("gravel", "dirt_path", "cobblestone", "stone_bricks", "mossy_cobblestone", "polished_andesite", "packed_mud", "coarse_dirt")


def load(d):
    bj = json.load(open(os.path.join(d, "blocks.json")))
    pal = [p.replace("minecraft:", "") for p in bj["palette"]]
    b = bj["blocks"]; cells = {}
    for i in range(0, len(b), 4):
        cells[(b[i], b[i + 1], b[i + 2])] = pal[b[i + 3]]
    return bj["size"], cells


def nm(s): return (s or "air").split("[")[0]


def props(s):
    if not s or "[" not in s: return {}
    return dict(kv.split("=", 1) for kv in s.split("[", 1)[1].rstrip("]").split(",") if "=" in kv)


def solid(s):
    n = nm(s)
    if n in PASS or not s: return False
    if n.endswith(("_stairs", "_slab", "_fence", "_wall", "_pane", "_door", "_trapdoor", "_sign", "lantern", "torch", "_carpet", "_button",
                   "_pressure_plate", "flower", "sapling", "rail", "chain", "bars", "ladder", "_bed", "leaves")):
        return False
    return any(t in n for t in FULLISH) or n in ("chest", "barrel", "crafting_table", "furnace")


def feet(s, y):
    n = nm(s); p = props(s)
    if n.endswith("_slab"): return y + (0.5 if p.get("type") == "bottom" else 1.0)
    if n.endswith("_stairs"): return y + (0.5 if p.get("half") == "bottom" else 1.0)
    return y + 1.0


def feet_dir(s, y, dv, end):
    """Feet height on a block walked in direction dv: a bottom stair is low (y+.5) on its front and high (y+1) on its back side."""
    n = nm(s); p = props(s)
    if n.endswith("_stairs") and p.get("half") == "bottom":
        f = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.get(p.get("facing"))
        if f == dv: return y + (0.5 if end == "in" else 1.0)
        if f == (-dv[0], -dv[1]): return y + (1.0 if end == "in" else 0.5)
        return y + 0.5
    return feet(s, y)


def load_terrain(path):
    """{(x, y, z): name} of a .schem/.litematic terrain file, minecraft: stripped like load()."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from blockforge import exporters
    with open(path, "rb") as f:
        return {p: s.replace("minecraft:", "") for p, s in exporters.import_file(f.read()).items()}


def score(d, lo=None, hi=None, terrain=None):
    """terrain = {(x, y, z): name} the build was started on (load_terrain), or None."""
    size, C = load(d)
    meta = json.load(open(os.path.join(d, "meta.json")))
    g = lambda x, y, z: C.get((x, y, z))
    r = collections.Counter()
    T = terrain or {}

    def land(p):
        """An untouched natural ground block of the terrain (not a tree)."""
        s = T.get(p)
        return s is not None and C.get(p) == s and solid(s) and not nm(s).endswith(("log", "wood"))
    land_cols = collections.defaultdict(list)
    for p in T:
        if land(p):
            land_cols[(p[0], p[2])].append(p[1])
    # floating: solid groups (6-neighbour, all non-air blocks) not touching y 0
    seen = set()
    for p in C:
        if p in seen: continue
        comp = [p]; seen.add(p); k = 0; ground = False
        while k < len(comp):
            x, y, z = comp[k]; k += 1
            if y == 0 or (T and land((x, y, z))): ground = True
            for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + a, y + b, z + c)
                if q in C and q not in seen: seen.add(q); comp.append(q)
        if not ground:
            over = T and any(any(ly < q[1] for ly in land_cols.get((q[0], q[2]), ())) for q in comp)
            r["terrain_floating" if over else "floating"] += len(comp)
    # removed by the final pass
    for f in meta.get("fixes") or []:
        if f.startswith("Removed") and any(t in f for t in ("lantern", "torch", "sign", "plant", "door", "candle", "carpet", "pot")):
            m = re.search(r"\(×(\d+)\)", f); r["removed"] += int(m.group(1)) if m else 1
    # walkable stairs/slabs/path blocks
    DV = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
    stand = {}
    for (x, y, z), s in C.items():
        if solid(s) or nm(s).endswith(("_stairs", "_slab")):
            if not solid(g(x, y + 1, z)) and not solid(g(x, y + 2, z)) and not nm(g(x, y + 1, z)).endswith(("_stairs", "_slab")):
                stand[(x, z, y)] = feet(s, y)
    walk = {}
    for (x, y, z), s in C.items():
        n = nm(s)
        if (n.endswith("_stairs") and props(s).get("half") == "bottom") or (n.endswith("_slab") and props(s).get("type") == "bottom") or n in PATHMAT:
            covered = n in PATHMAT and g(x, y + 1, z) is not None and nm(g(x, y + 1, z)) not in PASS
            if covered:                                                     # v2: a path running on under natural ground (into a hill) is buried
                if nm(g(x, y + 1, z)) in NAT:
                    for a, c in ((1, 0), (0, 1)):
                        if nm(g(x + a, y, z + c)) in PATHMAT and nm(g(x - a, y, z - c)) in PATHMAT and any(
                                (x + a * k * sg, z + c * k * sg, y) in stand and nm(g(x + a * k * sg, y, z + c * k * sg)) in PATHMAT
                                for k in range(1, 9) for sg in (1, -1)):
                            r["terrain_buried" if land((x, y + 1, z)) else "buried_path"] += 1; break
                continue                                                    # a covered wall/floor block is not a path
            if n in PATHMAT and not any(nm(g(x + a, y + h, z + c)).endswith(("_stairs", "_slab")) for a, c in DV.values() for h in (-1, 0, 1)):
                continue                                                    # an open path material counts only next to steps (a path, not a floor)
            walk[(x, y, z)] = s
            if n not in PATHMAT and (solid(g(x, y + 1, z)) or solid(g(x, y + 2, z))):
                r["terrain_buried" if (land((x, y + 1, z)) or land((x, y + 2, z))) else "buried_path"] += 1   # v2: buried = a step (stair/slab) with a solid block over it
    pairs = set()
    for (x, y, z), s in walk.items():
        if (x, z, y) not in stand: continue
        h0 = stand[(x, z, y)]
        for a, c in DV.values():
            for dy in (-1, 0, 1):
                q = (x + a, z + c, y + dy)
                if q in stand and (x + a, y + dy, z + c) in walk:
                    key = tuple(sorted(((x, y, z), (x + a, y + dy, z + c))))
                    if key in pairs: continue
                    pairs.add(key)
                    hb = feet_dir(g(x + a, y + dy, z + c), y + dy, (a, c), "in"); ha = feet_dir(s, y, (a, c), "out")
                    if abs(hb - ha) > 0.6: r["jump_steps"] += 1
        if nm(s).endswith("_stairs"):
            fc = props(s).get("facing"); dv = DV.get(fc)
            if dv:
                up = (x + dv[0], z + dv[1], y + 1); dn = (x - dv[0], z - dv[1], y - 1)
                upw = (x - dv[0], z - dv[1], y + 1)
                if upw in stand and up not in stand and (x - dv[0], y + 1, z - dv[1]) in walk: r["wrong_facing"] += 1
                for side in ((dv[1], dv[0]), (-dv[1], -dv[0])):
                    for dy in (0, 1):
                        t = g(x + side[0], y + dy, z + side[1])
                        if nm(t).endswith("_stairs") and (x + side[0], y + dy, z + side[1]) in walk and DV.get(props(t).get("facing")) in (side, (-side[0], -side[1])):
                            r["corner_turns"] += 1
    # doors
    for (x, y, z), s in C.items():
        if nm(s).endswith("_door") and props(s).get("half") == "lower":
            dv = DV.get(props(s).get("facing"))
            if dv and (solid(g(x + dv[0], y, z + dv[1])) or solid(g(x - dv[0], y, z - dv[1]))): r["blocked_doors"] += 1
    if lo:
        big = max(size[0], size[2]); r["size_off"] = max(0, lo - big, big - hi)
    keys = ["floating", "removed", "buried_path", "jump_steps", "corner_turns", "blocked_doors", "wrong_facing", "size_off"]
    if T:
        keys += ["terrain_floating", "terrain_buried"]
    out = {k: r.get(k, 0) for k in keys}
    out["quality"] = quality_total(C, T, meta.get("prompt"))
    out["terrain_score"] = terrain_total(C, T)
    return out


def quality_total(C, T=None, prompt=None):
    """blockforge.quality total of the build (what was built on a terrain), or None when it is not a building. The prompt
    tells a small house (hut, cottage, small ...), which may have one storey."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from blockforge import quality
    return quality.score(quality.built_only(C, T or None), prompt=prompt)["total"]


def terrain_total(C, T=None):
    """blockforge.terrain_quality total 0-100 of the land the AI made (HIGHER is better), or None when the build is not
    mostly natural land. Not a mistake count: never added to the totals."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from blockforge import quality, terrain_quality
    built = quality.built_only(C, T or None)
    return terrain_quality.score(built)["total"] if terrain_quality.is_terrain(built) else None


def overwritten(code):
    """Re-run the build script on a counting block store: a different block written over a placed one counts once."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from blockforge import buildkit
    class Count(dict):
        n = 0
        def __setitem__(self, k, v):
            if k in self and self[k] != v: Count.n += 1
            dict.__setitem__(self, k, v)
    buildkit._blocks = Count()
    try:
        ns = {k: getattr(buildkit, k) for k in buildkit.EXPORTS if hasattr(buildkit, k)}
        for mod in ("redstone", "modules", "testkit"):
            try:
                m = __import__(f"blockforge.{mod}", fromlist=["EXPORTS"])
                ns.update({k: getattr(m, k) for k in getattr(m, "EXPORTS", []) if hasattr(m, k)})
            except Exception as e:                                          # report, never hide
                print(f"bench: could not load blockforge.{mod}: {e}", file=sys.stderr)
        exec(compile(code, "code.py", "exec"), ns)
        return Count.n
    except Exception as e:
        print(f"bench: re-run for overwrite count failed: {e}", file=sys.stderr)
        return -1


if __name__ == "__main__":
    argv = sys.argv[1:]
    terr = load_terrain(argv.pop(argv.index("--terrain") + 1)) if "--terrain" in argv else None
    if "--terrain" in argv: argv.remove("--terrain")
    d = argv[0]; lo = int(argv[1]) if len(argv) > 1 else None; hi = int(argv[2]) if len(argv) > 2 else None
    out = score(d, lo, hi, terr)
    cp = os.path.join(d, "code.py")
    out["overwritten"] = overwritten(open(cp, encoding="utf-8").read()) if os.path.exists(cp) else -1
    print(json.dumps(out))
