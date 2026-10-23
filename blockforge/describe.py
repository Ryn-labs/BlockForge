"""A compact, readable description of an existing build, so the AI can edit a build it didn't write (an imported
schematic). Sizes, materials with where they are, and three ASCII views (top, front, side)."""
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
MAX_VIEW = 64


def _name(st):
    return st.split("[", 1)[0].replace("minecraft:", "")


def describe(blocks, budget=9000):
    if not blocks:
        return "The build is empty."
    xs = [p[0] for p in blocks]; ys = [p[1] for p in blocks]; zs = [p[2] for p in blocks]
    W, H, L = max(xs) + 1, max(ys) + 1, max(zs) + 1
    counts, boxes = {}, {}
    for (x, y, z), st in blocks.items():
        n = _name(st)
        counts[n] = counts.get(n, 0) + 1
        b = boxes.get(n)
        boxes[n] = (min(b[0], x), min(b[1], y), min(b[2], z), max(b[3], x), max(b[4], y), max(b[5], z)) if b else (x, y, z, x, y, z)
    mats = sorted(counts, key=lambda n: -counts[n])
    legend = {n: LETTERS[i] for i, n in enumerate(mats[:len(LETTERS)])}
    lines = [f"Size: {W} wide (x 0..{W - 1}, west to east) x {H} tall (y 0..{H - 1}) x {L} long (z 0..{L - 1}, north to south). "
             f"{len(blocks):,} blocks.", "", "Materials (letter = used in the views below, count, area it covers x1,y1,z1 -> x2,y2,z2):"]
    for n in mats[:40]:
        b = boxes[n]
        lines.append(f"  {legend.get(n, '?')} {n}: {counts[n]:,}  ({b[0]},{b[1]},{b[2]} -> {b[3]},{b[4]},{b[5]})")
    if len(mats) > 40:
        lines.append(f"  ...and {len(mats) - 40} more kinds")
    sx = max(1, -(-W // MAX_VIEW)); sz = max(1, -(-L // MAX_VIEW)); sy = max(1, -(-H // MAX_VIEW))
    note = f" (every {sx}th/{sy}th/{sz}th block, the build is big)" if max(sx, sy, sz) > 1 else ""

    def ch(st):
        return legend.get(_name(st), "?") if st else "."

    # top view: the highest block in each column (north at the top)
    top = {}
    for (x, y, z), st in blocks.items():
        if (x, z) not in top or y > top[(x, z)][0]:
            top[(x, z)] = (y, st)
    lines += ["", f"Top view{note}: rows are z (north first), columns are x (west first); letter = highest block there."]
    for z in range(0, L, sz):
        lines.append("".join(ch(top.get((x, z), (0, None))[1]) for x in range(0, W, sx)))
    # front view from the south: the first block seen looking north
    front = {}
    for (x, y, z), st in blocks.items():
        if (x, y) not in front or z > front[(x, y)][0]:
            front[(x, y)] = (z, st)
    lines += ["", f"Front view from the south{note}: rows are y (top first), columns are x (west first)."]
    for y in range(H - 1, -1, -sy):
        lines.append("".join(ch(front.get((x, y), (0, None))[1]) for x in range(0, W, sx)))
    side = {}
    for (x, y, z), st in blocks.items():
        if (z, y) not in side or x > side[(z, y)][0]:
            side[(z, y)] = (x, st)
    lines += ["", f"Side view from the east{note}: rows are y (top first), columns are z (north first)."]
    for y in range(H - 1, -1, -sy):
        lines.append("".join(ch(side.get((z, y), (0, None))[1]) for z in range(0, L, sz)))
    text = "\n".join(lines)
    if len(text) > budget:
        text = text[:budget] + "\n(views cut short to save space)"
    return text


def base_brief(blocks, has_picture):
    return ("## You are editing an existing build (an imported schematic)\n"
            "All of its blocks are ALREADY placed when your script starts. Write ONLY the changes the player asked for: "
            "do not rebuild what is already there. Use get(x, y, z) to read what is at a spot, replace(x1, y1, z1, x2, y2, "
            "z2, old, new) to swap materials in an area, fill(..., 'air') or block(x, y, z, 'air') to remove blocks, and "
            "the normal tools to add new parts. Everything you don't touch stays exactly as it is. Keep the same "
            "coordinates (the build already sits at 0,0,0 -> size-1).\n"
            + ("A picture of the build as it looks now is attached.\n" if has_picture else "")
            + "\n" + describe(blocks))
