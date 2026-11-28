"""How natural does a piece of terrain look? 0-100, from the land surface you see in the render (the top ground block of
every column; trees, leaves and water are not ground).

Four parts, each a penalty taken off 100:
- cuts:    sheer walls - neighbouring columns 6+ blocks apart (a real cliff here and there is fine, a mountain made of them is not)
- steps:   staircase land - long straight step lines and flat shelves, the "built like a house" look of stacked boxes
- regular: too perfect - a cone or pyramid whose height only depends on the distance to the top
- edges:   the land is cut off at the box edge instead of meeting the ground
- plate:   a lone peak on a flat plate - most of the land is one dead-flat sheet at the bottom
- banding: contour stripes - on the slopes the 1-block steps come at the same spacing again and again (terraces in lines)

is_terrain() says whether a build is mostly natural land at all (then the score applies); score() gives the numbers and
the words the save gate shows."""
import math

from . import terrain

TERRAIN_MIN = 60                  # save_build refuses AI-made terrain below this (unless the user keeps it)
NATURAL = ("grass_block", "dirt", "coarse_dirt", "rooted_dirt", "podzol", "mycelium", "moss_block", "mud", "stone",
           "andesite", "diorite", "granite", "tuff", "deepslate", "calcite", "gravel", "sand", "red_sand", "clay",
           "snow_block", "snow", "powder_snow", "ice", "packed_ice", "blue_ice", "cobblestone", "mossy_cobblestone",
           "sandstone", "red_sandstone", "terracotta", "dripstone_block", "basalt", "blackstone", "netherrack",
           "end_stone", "smooth_basalt", "dirt_path", "farmland")
PARTS = {"cuts": 25, "steps": 20, "regular": 15, "edges": 10, "plate": 15, "banding": 15}


def _base(state):
    s = str(state)
    s = s.split("[", 1)[0]
    return s.split(":", 1)[1] if ":" in s else s


def surface(blocks):
    """{(x, z): (y, state)} of the top ground block (logs, leaves, plants and water skipped)."""
    top, ground = {}, {}
    for (x, y, z), st in blocks.items():
        g = ground.get(st)
        if g is None:
            g = ground[st] = terrain.is_ground_block(st)                # per block state, not per block
        if not g:
            continue
        c = (x, z)
        if c not in top or y > top[c][0]:
            top[c] = (y, st)
    return top


def is_terrain(blocks, min_columns=400, min_relief=8, top=None):
    """True when the build is mostly natural land: 60%+ of the surface is natural ground, it covers 400+ columns and
    rises 8+ blocks. Houses, castles and towns are not terrain (their own quality score handles them).
    top = surface(blocks) when the caller has it already."""
    top = surface(blocks) if top is None else top
    if len(top) < min_columns:
        return False
    nat = sum(1 for y, st in top.values() if _base(st) in NATURAL)
    ys = sorted(y for y, _ in top.values())
    lo, hi = ys[int(len(ys) * 0.03)], ys[int(len(ys) * 0.97)]
    high = [st for y, st in top.values() if y >= lo + (hi - lo) * 0.5]
    high_nat = sum(1 for st in high if _base(st) in NATURAL)          # a house on a lawn: the high part is roof, not land
    return nat >= 0.6 * len(top) and hi - lo >= min_relief and high_nat >= 0.5 * max(1, len(high))


def score(blocks):
    top = surface(blocks)
    h = {c: v[0] for c, v in top.items()}
    out = {"terrain": is_terrain(blocks, top=top), "total": 100, "parts": {}, "notes": [], "columns": len(h)}
    if len(h) < 16:
        out["parts"] = {k: v for k, v in PARTS.items()}
        return out
    ys = sorted(h.values())
    lo, hi = ys[int(len(ys) * 0.03)], ys[-1]
    relief = max(1, hi - lo)
    # ---- cuts: sheer walls between neighbours
    pairs = cliffs = walls = 0
    steps_x, steps_z = {}, {}
    for (x, z), y in h.items():
        for (dx, dz), store in (((1, 0), steps_x), ((0, 1), steps_z)):
            o = h.get((x + dx, z + dz))
            if o is None:
                continue
            pairs += 1
            d = abs(y - o)
            if d >= 6:
                cliffs += 1
            if d >= 4:
                walls += 1
            if d:
                store[(x, z)] = y - o
    fc = cliffs / max(1, pairs)
    fw = walls / max(1, pairs)
    cut_pen = min(PARTS["cuts"], fc * 900 + fw * 400)                 # 4-5 block walls count too (stacked boxes)
    if fc > 0.01:
        out["notes"].append(f"{fc:.0%} of the land is sheer walls (6+ blocks straight down)")
    # ---- steps: straight step lines (a step edge that continues 6+ columns in a straight line) + flat shelves
    straight = total = 0
    for store, (ax, az) in ((steps_x, (0, 1)), (steps_z, (1, 0))):
        for (x, z), d in store.items():
            total += 1
            if store.get((x - ax, z - az)) == d:
                continue                                         # count each line once, from its start
            n = 1
            while store.get((x + ax * n, z + az * n)) == d:
                n += 1
            if n >= 6:
                straight += n
    fs = straight / max(1, total)
    flat = shelf = 0
    for (x, z), y in h.items():
        if y - lo < max(3, relief * 0.15):
            continue                                             # flat valley floors and plains are fine
        flat += 1
        if all(h.get((x + a, z + b)) == y for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))):
            shelf += 1
    ff = shelf / max(1, flat)
    step_pen = min(PARTS["steps"], max(0.0, fs - 0.40) * 100 + max(0.0, ff - 0.25) * 60)   # natural land has ~30-40% short straight runs
    if fs > 0.5:
        out["notes"].append(f"{fs:.0%} of the slopes are straight step lines (stacked boxes, not land)")
    if ff > 0.35:
        out["notes"].append(f"{ff:.0%} of the slopes are flat shelves (terraces)")
    # ---- regular: height explained by distance to the top alone (cone / pyramid)
    px, pz = max(h, key=lambda c: h[c])
    pts = [(math.hypot(x - px, z - pz), y) for (x, z), y in h.items() if y - lo > relief * 0.12]
    reg_pen = 0.0
    if len(pts) > 30:
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
        syy = sum((p[1] - my) ** 2 for p in pts) or 1.0
        r2 = (sxy * sxy) / (sxx * syy) if sxx else 0.0
        reg_pen = min(PARTS["regular"], max(0.0, r2 - 0.80) * 200)
        out["cone_r2"] = round(r2, 3)
        if r2 > 0.88:
            out["notes"].append(f"the shape is too regular (a cone or pyramid: height follows the distance to the top, r2 {r2:.2f})")
    # ---- edges: land cut off at the box edge
    xs = [c[0] for c in h]
    zs = [c[1] for c in h]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    border = [y for (x, z), y in h.items() if x in (x0, x1) or z in (z0, z1)]
    fe = (sum(border) / len(border) - lo) / relief if border else 0.0
    edge_pen = min(PARTS["edges"], max(0.0, fe - 0.15) * 50)
    if fe > 0.3:
        out["notes"].append(f"the land is cut off at the box edge (the border stands {fe:.0%} of the height up)")
    # ---- plate: dead-flat bottom sheet around a lone peak
    bottom = flat_bottom = 0
    for (x, z), y in h.items():
        if y - lo <= 1:
            bottom += 1
            if all(h.get((x + a, z + b), y) == y for a in (-2, 0, 2) for b in (-2, 0, 2)):
                flat_bottom += 1
    fp = flat_bottom / max(1, len(h))
    plate_pen = min(PARTS["plate"], max(0.0, fp - 0.15) * 80) if relief >= 15 else 0.0
    if fp > 0.3 and relief >= 15:
        out["notes"].append(f"{fp:.0%} of the land is one flat sheet at the bottom (a lone peak on a plate; add foothills, rolling ground)")
    # ---- banding: equal spacing between 1-block steps along the slopes
    gaps = []
    for (dx, dz) in ((1, 0), (0, 1)):
        lines = {}
        for (x, z) in h:
            lines.setdefault(z if dx else x, []).append(x if dx else z)
        for k, cs in lines.items():
            cs.sort()
            last, last_dir = None, 0
            for a, b in zip(cs, cs[1:]):
                if b != a + 1:
                    last = None
                    continue
                ya = h[(a, k) if dx else (k, a)]
                yb = h[(b, k) if dx else (k, b)]
                d = yb - ya
                if abs(d) != 1:
                    if d:
                        last = None
                    continue
                if last is not None and d == last_dir and b - last <= 10:
                    gaps.append(b - last)
                last, last_dir = b, d
    band_pen = 0.0
    if len(gaps) >= 150:
        m = sum(gaps) / len(gaps)
        cv = math.sqrt(sum((g - m) ** 2 for g in gaps) / len(gaps)) / m
        run1 = sum(1 for g in gaps if g == 1) / len(gaps)
        out["band_cv"] = round(cv, 3)
        out["band_run1"] = round(run1, 3)
        band_pen = min(PARTS["banding"], max(0.0, 0.62 - cv) * 60)
        if cv < 0.5:
            out["notes"].append(f"the slopes show regular contour stripes (steps every {m:.1f} blocks, spread {cv:.2f}; vary the slope)")
    pens = {"cuts": cut_pen, "steps": step_pen, "regular": reg_pen, "edges": edge_pen, "plate": plate_pen, "banding": band_pen}
    out["parts"] = {k: round(PARTS[k] - v, 1) for k, v in pens.items()}
    out["total"] = int(round(100 - sum(pens.values())))
    out["relief"] = relief
    return out


def summary(q):
    return f"terrain {q['total']}/100 (" + ", ".join(f"{k} {v:g}/{PARTS[k]}" for k, v in q["parts"].items()) + ")"


def gate_text(q):
    notes = "; ".join(q["notes"]) or "the land looks built, not grown"
    return (f"The terrain scores {q['total']}/100 (needs {TERRAIN_MIN}): {notes}. Natural land has uneven slopes of 1-3 blocks, "
            "a few real cliffs, ridges that bend and land that meets the ground at the edges. Use natural_terrain(...) for "
            "mountains, hills and valleys instead of cones, cylinders and stacked boxes.")
