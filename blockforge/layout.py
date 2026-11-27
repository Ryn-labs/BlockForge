"""Layout planner for big builds: where to put houses, a plaza, a castle... on real terrain, and the streets between them.

plan(top, area, parts, street_width) works on a ground height map `top` {(x, z): y} (terrain.ground_top) and is pure
Python, deterministic and fast (a 256 x 256 area takes well under 2 s).

  1. Every part gets the flattest free spot (box sums on prefix grids): a castle likes high ground, a plaza the middle,
     a house sits near its `near` part. Parts keep a gap of at least 3 blocks (street width + 2 when streets are wider).
  2. Parts are joined by a street network: every part is linked to the nearest part already on the network. A street is a
     chain of straight legs found with a weighted A* that avoids the parts, prefers flat ground and merges into streets
     that already exist. Corners are landings.
  3. The height along each street is the ground, smoothed so that it never climbs more than 1 block in 2 (cut and fill).
"""
import heapq
import itertools
import statistics

KINDS = ("house", "plaza", "castle", "shrine", "park")
MAX_SLOPE_RUN = 2            # a street rises at most 1 block in 2
MIN_LEG = 4                  # shortest straight leg (the landing at a corner needs room)
MAX_EXPAND = 250000


class LayoutError(Exception):
    pass


def _prefix(rows):
    """2D prefix sums: P[z][x] = sum of rows[:z][:x]."""
    out = [[0] * (len(rows[0]) + 1)]
    for r in rows:
        acc = list(itertools.accumulate(r, initial=0))
        prev = out[-1]
        out.append([a + b for a, b in zip(prev, acc)])
    return out


def _box(P, x1, z1, x2, z2):
    """Sum of cells x1..x2-1, z1..z2-1 (grid coordinates)."""
    return P[z2][x2] - P[z1][x2] - P[z2][x1] + P[z1][x1]


def _parse(area, parts, street_width):
    try:
        x1, z1, x2, z2 = (int(v) for v in area)
    except (TypeError, ValueError):
        raise LayoutError("area must be [x1, z1, x2, z2].") from None
    x1, x2, z1, z2 = min(x1, x2), max(x1, x2), min(z1, z2), max(z1, z2)
    if not isinstance(parts, list) or not parts:
        raise LayoutError("parts must be a list of {name, w, l, kind}.")
    out, names = [], set()
    for i, p in enumerate(parts, 1):
        if not isinstance(p, dict):
            raise LayoutError(f"Part {i} must be an object {{name, w, l, kind}}.")
        try:
            w, l = int(p.get("w")), int(p.get("l"))
        except (TypeError, ValueError):
            raise LayoutError(f"Part {i} needs whole numbers w (x size) and l (z size).") from None
        kind = str(p.get("kind") or "house").lower()
        if kind not in KINDS:
            raise LayoutError(f"Part {i}: kind must be one of {', '.join(KINDS)}.")
        name = str(p.get("name") or f"{kind}{i}")
        if name in names:
            raise LayoutError(f"Two parts are called '{name}'.")
        names.add(name)
        if w < 1 or l < 1 or not ((w <= x2 - x1 + 1 and l <= z2 - z1 + 1) or (l <= x2 - x1 + 1 and w <= z2 - z1 + 1)):
            raise LayoutError(f"Part '{name}' ({w} x {l}) does not fit in the area.")
        out.append({"name": name, "w": w, "l": l, "kind": kind, "near": p.get("near")})
    try:
        sw = max(1, int(street_width))
    except (TypeError, ValueError):
        sw = 5
    return (x1, z1, x2, z2), out, sw


def plan(top, area, parts, street_width=5):
    """Returns the plan dict: {"area", "street_width", "parts": [...], "streets": [...], "warnings": [...]}."""
    (ax1, az1, ax2, az2), specs, sw = _parse(area, parts, street_width)
    W, L = ax2 - ax1 + 1, az2 - az1 + 1
    H = [[top.get((ax1 + x, az1 + z)) for x in range(W)] for z in range(L)]
    has = [[0 if v is None else 1 for v in row] for row in H]
    h0 = [[0 if v is None else v for v in row] for row in H]
    Ph, Ps, Pn = _prefix(h0), _prefix([[v * v for v in row] for row in h0]), _prefix(has)
    gap = max(3, sw + 2)
    blocked = [[0] * W for _ in range(L)]                   # parts and their gaps
    warnings = []
    heights = [v for row in H for v in row if v is not None]
    if not heights:
        raise LayoutError("There is no ground in that area.")
    hmax, hmin = max(heights), min(heights)

    order = sorted(range(len(specs)), key=lambda i: (specs[i]["kind"] != "castle", specs[i]["kind"] != "plaza",
                                                      -(specs[i]["w"] * specs[i]["l"]), i))
    placed = {}
    step = max(1, int(((W * L) / 5000) ** 0.5))
    for i in _after_near(order, specs):
        sp = specs[i]
        Pb = _prefix(blocked)
        cx = sum((r["x1"] + r["x2"]) / 2 for r in placed.values()) / len(placed) if placed else (W / 2 + ax1)
        cz = sum((r["z1"] + r["z2"]) / 2 for r in placed.values()) / len(placed) if placed else (L / 2 + az1)
        near = placed.get(sp["near"]) if sp.get("near") else None
        if near:
            cx, cz = (near["x1"] + near["x2"]) / 2, (near["z1"] + near["z2"]) / 2
        best = None
        for (w, l) in ((sp["w"], sp["l"]), (sp["l"], sp["w"])) if sp["w"] != sp["l"] else ((sp["w"], sp["l"]),):
            if w > W or l > L:
                continue
            area_n = w * l
            for z in range(0, L - l + 1, step):
                for x in range(0, W - w + 1, step):
                    if _box(Pn, x, z, x + w, z + l) != area_n or _box(Pb, x, z, x + w, z + l):
                        continue
                    s1 = _box(Ph, x, z, x + w, z + l)
                    s2 = _box(Ps, x, z, x + w, z + l)
                    mean = s1 / area_n
                    var = max(0.0, s2 / area_n - mean * mean)
                    dist = abs(x + w / 2 + ax1 - cx) + abs(z + l / 2 + az1 - cz)
                    cost = var * 4 + 0.02 * dist
                    if placed and sp["kind"] != "castle":        # a street has to climb between neighbours: keep levels close
                        d_n, lv = min((abs(r["x1"] + r["w"] / 2 - x - w / 2 - ax1) + abs(r["z1"] + r["l"] / 2 - z - l / 2 - az1), r["level"])
                                      for r in placed.values())
                        cost += 8 * max(0.0, abs(mean - lv) - max(0.0, d_n - 12) / 2.5)
                    if sp["kind"] == "castle":
                        cost += (hmax - mean) * 2.5
                    elif sp["kind"] == "shrine":
                        cost += (hmax - mean) * 0.4
                    elif sp["kind"] == "plaza":
                        cost += 0.04 * dist
                    elif near:
                        cost += 0.15 * dist
                    key = (cost, z, x, w)
                    if best is None or key < best[0]:
                        best = (key, x, z, w, l)
        if best is None:
            raise LayoutError(f"No free spot for '{sp['name']}' ({sp['w']} x {sp['l']}) in the area: make the area bigger or "
                              "the parts smaller.")
        _, x, z, w, l = best
        vals = sorted(H[zz][xx] for zz in range(z, z + l) for xx in range(x, x + w))
        level = int(statistics.median(vals))
        cut = sum(v - level for v in vals if v > level)
        fill = sum(level - v for v in vals if v < level)
        placed[sp["name"]] = {"name": sp["name"], "kind": sp["kind"], "x1": x + ax1, "z1": z + az1, "x2": x + ax1 + w - 1,
                              "z2": z + az1 + l - 1, "w": w, "l": l, "level": level, "cut": cut, "fill": fill,
                              "max_dev": max(abs(v - level) for v in vals), "rotated": (w, l) != (sp["w"], sp["l"])}
        g = gap
        for zz in range(max(0, z - g), min(L, z + l + g)):
            row = blocked[zz]
            for xx in range(max(0, x - g), min(W, x + w + g)):
                row[xx] = 1
    plist = [placed[sp["name"]] for sp in specs]
    streets = _streets(plist, H, (ax1, az1, W, L), sw, warnings)
    return {"area": [ax1, az1, ax2, az2], "street_width": sw, "parts": plist, "streets": streets, "warnings": warnings}


def _after_near(order, specs):
    """Placement order: `order`, but a part with `near` comes after the part it names."""
    names = {s["name"]: i for i, s in enumerate(specs)}
    out, done = [], set()

    def add(i):
        if i in done:
            return
        done.add(i)
        n = specs[i].get("near")
        if n in names and names[n] != i:
            add(names[n])
        out.append(i)
    for i in order:
        add(i)
    return out


# ------------------------------------------------------------------ streets
def _entrance(r, toward, sw):
    """The street cell in front of a part: on the side that faces `toward` (x, z), sw // 2 + 1 outside the wall."""
    cx, cz = (r["x1"] + r["x2"]) / 2, (r["z1"] + r["z2"]) / 2
    dx, dz = toward[0] - cx, toward[1] - cz
    off = sw // 2 + 1
    if abs(dx) / max(1, r["w"]) >= abs(dz) / max(1, r["l"]):
        return (r["x2"] + off if dx > 0 else r["x1"] - off), int(round(max(r["z1"], min(r["z2"], cz))))
    return int(round(max(r["x1"], min(r["x2"], cx)))), (r["z2"] + off if dz > 0 else r["z1"] - off)


def _streets(plist, H, geom, sw, warnings):
    ax1, az1, W, L = geom
    if len(plist) < 2:
        return []
    clear = sw // 2 + 1                                       # street centre lines keep this far from a wall
    wall = [[0] * W for _ in range(L)]
    for r in plist:
        for zz in range(max(0, r["z1"] - az1 - clear + 1), min(L, r["z2"] - az1 + clear)):
            row = wall[zz]
            for xx in range(max(0, r["x1"] - ax1 - clear + 1), min(W, r["x2"] - ax1 + clear)):
                row[xx] = 1
    centre = lambda r: ((r["x1"] + r["x2"]) / 2, (r["z1"] + r["z2"]) / 2)
    linked, rest = [plist[0]], list(plist[1:])
    first_plaza = next((r for r in plist if r["kind"] == "plaza"), None)
    if first_plaza:
        linked, rest = [first_plaza], [r for r in plist if r is not first_plaza]
    used = {}                                                 # street cells already built: (x, z) -> y
    streets = []
    while rest:
        a, b = min(((a, b) for b in rest for a in linked),
                   key=lambda ab: (abs(centre(ab[0])[0] - centre(ab[1])[0]) + abs(centre(ab[0])[1] - centre(ab[1])[1]),
                                   ab[1]["name"], ab[0]["name"]))
        rest.remove(b)
        linked.append(b)
        ea, eb = _entrance(a, centre(b), sw), _entrance(b, centre(a), sw)
        path = _route(H, wall, (ax1, az1, W, L), ea, eb, used)
        if path is None:
            warnings.append(f"No street found between {a['name']} and {b['name']}.")
            continue
        ys, bad = _profile(path, H, (ax1, az1), used, a["level"], b["level"])
        for c, y in zip(path, ys):
            used.setdefault(c, y)
        if bad:
            warnings.append(f"Street {a['name']} - {b['name']}: {bad}")
        streets.append(_street_dict(a, b, path, ys))
    return streets


def _route(H, wall, geom, start, goal, used):
    """Weighted A* on the ground grid (4 moves). State = (x, z, direction, run length since the last turn)."""
    ax1, az1, W, L = geom
    s = (start[0] - ax1, start[1] - az1)
    g = (goal[0] - ax1, goal[1] - az1)
    for c in (s, g):
        if not (0 <= c[0] < W and 0 <= c[1] < L) or H[c[1]][c[0]] is None:
            return None
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    h = lambda x, z: abs(x - g[0]) + abs(z - g[1])
    cnt = itertools.count()
    heap = [(1.4 * h(*s), next(cnt), 0.0, s[0], s[1], -1, MIN_LEG)]
    best = {}
    prev = {}
    n = 0
    while heap:
        _, _, cost, x, z, d, run = heapq.heappop(heap)
        key = (x, z, d, run)
        if key in best and best[key] <= cost:
            continue
        best[key] = cost
        if (x, z) == g and run >= 1:
            path = [(x, z)]
            k = key
            while k in prev:
                k = prev[k]
                path.append((k[0], k[1]))
            path.reverse()
            return [(px + ax1, pz + az1) for px, pz in path]
        n += 1
        if n > MAX_EXPAND:
            return None
        for nd, (dx, dz) in enumerate(dirs):
            if d >= 0 and nd != d and (dx, dz) == (-dirs[d][0], -dirs[d][1]):
                continue
            if d >= 0 and nd != d and run < MIN_LEG and (x, z) != g:
                continue                                     # a leg is at least MIN_LEG long: no zigzags
            nx, nz = x + dx, z + dz
            if not (0 <= nx < W and 0 <= nz < L):
                continue
            hv = H[nz][nx]
            if hv is None or (wall[nz][nx] and (nx, nz) != g):
                continue
            dh = abs(hv - H[z][x])
            step = 1.0 + 3.0 * dh + (0.8 if d >= 0 and nd != d else 0.0)
            if (nx + ax1, nz + az1) in used:
                step = 0.35 + 0.5 * dh                       # merge into a street that is there
            nrun = 1 if nd != d else min(run + 1, MIN_LEG)
            nk = (nx, nz, nd, nrun)
            nc = cost + step
            if nk in best and best[nk] <= nc:
                continue
            prev[nk] = key
            heapq.heappush(heap, (nc + 1.4 * h(nx, nz), next(cnt), nc, nx, nz, nd, nrun))
    return None


def _profile(path, H, org, used, y_start, y_end):
    """Street height per cell: the ground, smoothed to rise at most 1 block in 2 (so streets are cut or filled),
    with a flat landing at each corner, cells of earlier streets and both ends pinned. Returns (heights, problem text)."""
    n = len(path)
    ax1, az1 = org
    g = [H[z - az1][x - ax1] for x, z in path]
    cap = lambda k: (k + 1) // 2                             # allowed difference over k cells
    pins = {}
    # cells of existing streets keep their height; both ends meet the part
    cand = [(0, y_start), (n - 1, y_end)] + [(i, used[c]) for i, c in enumerate(path) if c in used]
    corners = [i for i in range(1, n - 1) if (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) !=
               (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])]

    def ok(i, y):
        return all(abs(y - py) <= cap(abs(i - pi)) for pi, py in pins.items())
    for i, y in sorted(cand, key=lambda t: (t[0] not in (0, n - 1) and path[t[0]] not in used, t[0])):
        if ok(i, y):
            pins[i] = y
    notes = []
    if 0 not in pins or (n - 1) not in pins:
        notes.append("the street is too short or too steep to reach both parts with a 1 in 2 slope: add a stair run or move a part")
    # the closest profile to the ground that obeys the slope limit: halfway between the highest and the lowest one,
    # then held inside the band the pins allow
    up = _lipschitz(g, cap, True)
    lo = _lipschitz(g, cap, False)
    ys = []
    for i in range(n):
        base = (up[i] + lo[i]) // 2
        hi_p = min([py + cap(abs(i - pi)) for pi, py in pins.items()] + [10 ** 6])
        lo_p = max([py - cap(abs(i - pi)) for pi, py in pins.items()] + [-10 ** 6])
        ys.append(min(max(base, lo_p), hi_p))
    # landings: the corner and the cell on each side are level (when that keeps the slope limit)
    for c in corners:
        for j in (c - 1, c + 1):
            if 0 <= j < n and j not in pins and ys[c] != ys[j] and _fits(ys, j, ys[c], cap, pins):
                ys[j] = ys[c]
    for i in range(n):
        for j in range(max(0, i - 6), i):
            if abs(ys[i] - ys[j]) > cap(i - j):
                notes.append(f"slope over 1 in 2 near ({path[i][0]}, {path[i][1]})")
                return ys, "; ".join(notes)
    return ys, "; ".join(notes)


def _lipschitz(v, cap, upper):
    """Largest (upper) or smallest function below / above v obeying |f(i) - f(j)| <= cap(|i - j|)."""
    n = len(v)
    if upper:
        return [min(v[j] + cap(abs(i - j)) for j in range(n)) for i in range(n)]
    return [max(v[j] - cap(abs(i - j)) for j in range(n)) for i in range(n)]


def _fits(ys, j, y, cap, pins):
    n = len(ys)
    return all(abs(y - ys[k]) <= cap(abs(j - k)) for k in range(max(0, j - 6), min(n, j + 7)) if k != j)


def _street_dict(a, b, path, ys):
    pts = [(path[0], ys[0])]
    corners = []
    for i in range(1, len(path) - 1):
        if (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) != (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]):
            pts.append((path[i], ys[i]))
            corners.append(i)
    pts.append((path[-1], ys[-1]))
    legs = []
    for (p, y), (q, y2) in zip(pts, pts[1:]):
        legs.append({"from": [p[0], p[1], y], "to": [q[0], q[1], y2], "length": abs(q[0] - p[0]) + abs(q[1] - p[1])})
    rises = [abs(ys[i + 1] - ys[i]) for i in range(len(ys) - 1)]
    return {"from": a["name"], "to": b["name"], "points": [[p[0], p[1], y] for p, y in pts],
            "legs": legs, "cells": [[x, z, y] for (x, z), y in zip(path, ys)], "length": len(path),
            "landings": [[path[i][0], path[i][1], ys[i]] for i in corners], "total_rise": sum(rises)}


def plan_text(plan):
    out = [f"Layout plan for x {plan['area'][0]}..{plan['area'][2]}, z {plan['area'][1]}..{plan['area'][3]} "
           f"(street width {plan['street_width']}). Rectangles are x1,z1 -> x2,z2 (inclusive); level = the y of the ground "
           f"surface to build on; cut/fill = blocks of ground to remove / add on the footprint."]
    for r in plan["parts"]:
        out.append(f"- {r['name']} ({r['kind']}): x {r['x1']}..{r['x2']}, z {r['z1']}..{r['z2']} ({r['w']} x {r['l']}"
                   f"{', turned' if r['rotated'] else ''}), level y={r['level']}, cut {r['cut']}, fill {r['fill']}, "
                   f"worst {r['max_dev']} off the level")
    for s in plan["streets"]:
        out.append(f"Street {s['from']} - {s['to']}: {s['length']} cells, climbs {s['total_rise']} in total. Centre line "
                   "(x,z,y) corners, landings flat: " + " -> ".join(f"({p[0]},{p[1]},{p[2]})" for p in s["points"]))
    for w in plan["warnings"]:
        out.append("Warning: " + w)
    out.append("Full plan as JSON follows (each street has 'cells' with every x,z,y):")
    import json
    slim = dict(plan, streets=[{k: v for k, v in s.items() if k != "cells"} for s in plan["streets"]])
    out.append(json.dumps(slim, separators=(",", ":")))
    return "\n".join(out)
