"""How natural does a piece of terrain look? 0-100, from the land surface you see in the render (the top ground block of
every column; trees, leaves and water are not ground).

Parts, each a penalty taken off 100 (the total never goes below 0):
- cuts:    sheer walls - neighbouring columns 6+ blocks apart (a real cliff here and there is fine, a mountain made of them is not)
- steps:   staircase land - long straight step lines and flat shelves, the "built like a house" look of stacked boxes
- regular: too perfect - a cone or pyramid whose height only depends on the distance to the top
- edges:   the land is cut off at the box edge instead of meeting the ground (a wall standing at the box side)
- plate:   a lone peak on a flat plate - most of the land is one dead-flat sheet at the bottom - or a top cut flat
- banding: contour stripes - on the slopes the 1-block steps come at the same spacing again and again (terraces in lines)
- silhouette: the outline seen from the four sides is one symmetric cone with straight flanks (no saddles, no shoulders)
- slopes:  every slope equally steep - along the fall line the steps repeat (3, 3, 3...) instead of ledges and risers
- snow:    the snow is a clean white cap (snow exactly above one height) and the high faces are one plain colour, instead
           of snow on ledges with dark rock showing on the steep faces, in streaks and patches

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
PARTS = {"cuts": 25, "steps": 20, "regular": 15, "edges": 45, "plate": 30, "banding": 15, "silhouette": 15, "slopes": 15,
         "snow": 20}
DARK = ("deepslate", "cobbled_deepslate", "polished_deepslate", "tuff", "blackstone", "basalt", "smooth_basalt",
        "coal_ore", "deepslate_coal_ore", "mud", "packed_mud", "dripstone_block")
PALE = ("stone", "andesite", "cobblestone", "mossy_cobblestone", "gravel", "diorite", "calcite", "granite", "dirt",
        "coarse_dirt", "rooted_dirt", "sand", "sandstone", "clay", "terracotta")
GREEN = ("grass_block", "moss_block", "podzol", "mycelium")


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
    # ---- cuts: sheer walls between neighbours (a river bank under water is not a wall)
    wet = {(x, z) for (x, y, z), st in blocks.items() if _base(st) == "water" and y > h.get((x, z), y)}
    pairs = cliffs = walls = 0
    steps_x, steps_z = {}, {}
    for (x, z), y in h.items():
        for (dx, dz), store in (((1, 0), steps_x), ((0, 1), steps_z)):
            o = h.get((x + dx, z + dz))
            if o is None:
                continue
            pairs += 1
            d = abs(y - o)
            if wet and ((x, z) in wet or (x + dx, z + dz) in wet):
                d = min(d, 3)
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
    wall_at = max(5, relief * 0.15)                                   # seen from outside the box: a wall this high or more
    b_lo = sorted(border)[len(border) // 10] if border else lo         # above the low part of the border (not a river bed)
    fb = sum(1 for y in border if y - b_lo >= wall_at) / max(1, len(border))
    edge_pen = min(PARTS["edges"], max(0.0, fe - 0.15) * 50 + fb * 120)
    out["edge_walls"] = round(fb, 3)
    if fe > 0.3 or fb > 0.05:
        out["notes"].append(f"the land is cut off at the box edge (the border stands {fe:.0%} of the height up, "
                            f"{fb:.0%} of it is a wall)")
    # ---- plate: dead-flat bottom sheet around a lone peak
    bottom = flat_bottom = 0
    for (x, z), y in h.items():
        if y - lo <= 1:
            bottom += 1
            if all(h.get((x + a, z + b), y) == y for a in (-2, 0, 2) for b in (-2, 0, 2)):
                flat_bottom += 1
    fp = flat_bottom / max(1, len(h))
    plate_pen = min(15.0, max(0.0, fp - 0.15) * 80) if relief >= 15 else 0.0
    if fp > 0.3 and relief >= 15:
        out["notes"].append(f"{fp:.0%} of the land is one flat sheet at the bottom (a lone peak on a plate; add foothills, rolling ground)")
    upper = sum(1 for y in h.values() if y - lo > relief * 0.15)
    ft = sum(1 for y in h.values() if y >= hi - 1) / max(1, upper)      # a top cut flat: many columns at the very top
    out["top_plate"] = round(ft, 3)
    if relief >= 10 and ft > 0.05:
        plate_pen += min(PARTS["plate"], (ft - 0.05) * 250)
        out["notes"].append(f"the top is cut flat ({ft:.0%} of the high ground is one level at the top)")
    plate_pen = min(PARTS["plate"], plate_pen)
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
    sil_pen = _silhouette(h, lo, relief, out)
    slope_pen = _slopes(h, lo, relief, out)
    snow_pen = _snow(blocks, top, h, lo, relief, out)
    pens = {"cuts": cut_pen, "steps": step_pen, "regular": reg_pen, "edges": edge_pen, "plate": plate_pen, "banding": band_pen,
            "silhouette": sil_pen, "slopes": slope_pen, "snow": snow_pen}
    out["parts"] = {k: round(PARTS[k] - v, 1) for k, v in pens.items()}
    out["total"] = max(0, int(round(100 - sum(pens.values()))))
    out["relief"] = relief
    return out


def _profiles(h):
    """The outline seen from the four sides (along x, z and both diagonals): the highest column on every sight line."""
    out = []
    for f in (lambda x, z: x, lambda x, z: z, lambda x, z: x + z, lambda x, z: x - z):
        d = {}
        for (x, z), y in h.items():
            k = f(x, z)
            if y > d.get(k, -10 ** 9):
                d[k] = y
        out.append([d[k] for k in sorted(d)])
    return out


def _silhouette(h, lo, relief, out):
    """Penalty for a cone outline: from every side one summit, the same left and right, flanks that are straight lines."""
    if relief < 12:
        return 0.0
    cones = []
    for prof in _profiles(h):
        n = len(prof)
        if n < 12:
            continue
        v = [(p - lo) / relief for p in prof]
        s = [sum(v[max(0, i - 1):i + 2]) / len(v[max(0, i - 1):i + 2]) for i in range(n)]
        mx = max(s)
        tops = [i for i in range(n) if s[i] == mx]
        p = tops[len(tops) // 2]
        summits = 0
        for i in range(n):                                      # summits: local tops that stand 5%+ above their saddles
            if s[i] < 0.45 * mx or s[i] < max(s[max(0, i - 3):i + 4]):
                continue
            j, lmin = i, s[i]
            while j > 0 and s[j - 1] <= s[i]:
                j -= 1
                lmin = min(lmin, s[j])
            k, rmin = i, s[i]
            while k < n - 1 and s[k + 1] <= s[i]:
                k += 1
                rmin = min(rmin, s[k])
            if i == p or min(s[i] - lmin, s[i] - rmin) >= 0.05:
                summits += 1
        reach = min(p, n - 1 - p)
        asym = sum(abs(s[p - d] - s[p + d]) for d in range(1, reach + 1)) / max(1, reach)
        res = []
        for side in (-1, 1):                                    # flank: a straight line from the top down?
            pts, i = [], p
            while 0 <= i < n and s[i] >= 0.15 * mx:
                if s[i] <= 0.9 * mx:
                    pts.append((abs(i - p), s[i]))
                i += side
            if len(pts) > 4:
                mxx = sum(q[0] for q in pts) / len(pts)
                my = sum(q[1] for q in pts) / len(pts)
                sxx = sum((q[0] - mxx) ** 2 for q in pts) or 1.0
                b = sum((q[0] - mxx) * (q[1] - my) for q in pts) / sxx
                res.append(math.sqrt(sum((q[1] - my - b * (q[0] - mxx)) ** 2 for q in pts) / len(pts)))
        rms = sum(res) / len(res) if res else 0.05
        cones.append(((summits == 1) + max(0.0, 1.0 - asym / 0.15) + max(0.0, 1.0 - rms / 0.05)) / 3.0)
    if not cones:
        return 0.0
    c = sum(cones) / len(cones)
    out["cone_outline"] = round(c, 3)
    pen = min(PARTS["silhouette"], max(0.0, c - 0.45) / 0.4 * PARTS["silhouette"])
    if c > 0.6:
        out["notes"].append(f"the outline is a cone from every side (one summit, both flanks alike and straight, {c:.2f}); "
                            "give it saddles, shoulders and a second summit")
    return pen


def _slopes(h, lo, relief, out):
    """Penalty for slopes that are all equally steep: along the fall line the steps repeat instead of ledge / riser."""
    tot = cnt = 0
    for dx, dz in ((1, 0), (0, 1)):
        for (x, z), y in h.items():
            if not (lo + relief * 0.15 <= y <= lo + relief * 0.9):
                continue
            a, b = h.get((x + dx, z + dz)), h.get((x - dx, z - dz))
            if a is None or b is None:
                continue
            d1, d2 = y - b, a - y
            if d1 * d2 < 0 or not 2 <= max(abs(d1), abs(d2)) <= 3:
                continue                                        # steep slopes only; walls are the cuts part's business
            tot += abs(d1 - d2)
            cnt += 1
    if cnt < 200 or relief < 12:
        return 0.0
    rough = tot / cnt
    out["slope_rhythm"] = round(rough, 3)
    pen = min(PARTS["slopes"], max(0.0, 1.1 - rough) / 0.3 * PARTS["slopes"])
    if rough < 0.95:
        out["notes"].append(f"the slopes are all equally steep (steps repeat along the slope, rhythm {rough:.2f}); "
                            "add ledges and shoulders, steeper and gentler bits")
    return pen


def _look(state, above):
    n = _base(state)
    if "snow" in n or "snow" in _base(above or "air") or n in ("ice", "packed_ice", "blue_ice", "powder_snow"):
        return "W"
    if n in DARK:
        return "D"
    if n in GREEN:
        return "V"
    return "G" if n in PALE else "O"


def _snow(blocks, top, h, lo, relief, out):
    """Penalty for a clean snow cap and plain high faces: snow exactly above one height, high ground in one colour."""
    if relief < 12:
        return 0.0
    look = {c: _look(st, blocks.get((c[0], y + 1, c[1]))) for c, (y, st) in top.items()}
    high = [c for c, y in h.items() if y >= lo + relief * 0.5]
    bare = sum(1 for c in high if look[c] in ("W", "D", "G")) / max(1, len(high))
    if bare < 0.5:                                              # green hills: no snow or rock faces to judge
        return 0.0
    pairs = diff = 0
    for (x, z) in high:
        for o in ((x + 1, z), (x, z + 1)):
            if o in look and h[o] >= lo + relief * 0.5:
                pairs += 1
                diff += look[o] != look[(x, z)]
    mosaic = diff / max(1, pairs)
    out["high_mosaic"] = round(mosaic, 3)
    pen = max(0.0, 0.40 - mosaic) / 0.15 * 10.0
    snowy = sorted(h[c] for c in look if look[c] == "W")
    if len(snowy) >= 30:
        z0 = snowy[int(len(snowy) * 0.05)] - 4
        zone = [c for c in h if h[c] >= z0]
        best = 0
        for t in sorted(set(h[c] for c in zone)):               # how well does one height alone say snow / no snow?
            best = max(best, sum(1 for c in zone if (h[c] >= t) == (look[c] == "W")))
        cap = best / len(zone)
        out["snow_cap"] = round(cap, 3)
        pen += max(0.0, cap - 0.8) / 0.12 * 10.0
        if cap > 0.86:
            out["notes"].append(f"the snow is a clean cap ({cap:.0%} of the high ground is snow above one line, rock below); "
                                "let snow lie on ledges and gentle bits and dark rock show on steep faces")
    if mosaic < 0.25:
        out["notes"].append(f"the high faces are one plain colour (mix {mosaic:.2f}); show dark rock (deepslate, tuff) "
                            "in streaks and patches, snow on the ledges")
    return min(PARTS["snow"], pen)


def summary(q):
    return f"terrain {q['total']}/100 (" + ", ".join(f"{k} {v:g}/{PARTS[k]}" for k, v in q["parts"].items()) + ")"


def gate_text(q):
    notes = "; ".join(q["notes"]) or "the land looks built, not grown"
    return (f"The terrain scores {q['total']}/100 (needs {TERRAIN_MIN}): {notes}. Natural land has uneven slopes of 1-3 blocks, "
            "a few real cliffs, ridges that bend and land that meets the ground at the edges. Use natural_terrain(...) for "
            "mountains, hills and valleys instead of cones, cylinders and stacked boxes.")
