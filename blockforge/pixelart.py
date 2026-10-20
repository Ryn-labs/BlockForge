"""Turns a picture into a flat block mosaic (pixel art), with no AI involved: instant and free.

The page shrinks the picture to the size you pick and sends the raw pixels; this picks the closest block colour for
each pixel (optionally with Floyd-Steinberg dithering so gradients look smooth) and lays the blocks out as a wall or a
floor."""
MAX_SIDE = 128

_WOOL = {"white": "E9ECEC", "orange": "F07613", "magenta": "BD44B3", "light_blue": "3AAFD9", "yellow": "F8C627", "lime": "70B919",
         "pink": "ED8DAC", "gray": "3E4447", "light_gray": "8E8E86", "cyan": "158991", "purple": "792AAC", "blue": "35399D",
         "brown": "724728", "green": "546D1B", "red": "A12722", "black": "141519"}
_CONCRETE = {"white": "CFD5D6", "orange": "E06101", "magenta": "A9309F", "light_blue": "2389C6", "yellow": "F1AF15",
             "lime": "5EA818", "pink": "D6658F", "gray": "36393D", "light_gray": "7D7D73", "cyan": "157788", "purple": "64209C",
             "blue": "2C2E8F", "brown": "603C20", "green": "495B24", "red": "8E2121", "black": "080A0F"}
_TERRACOTTA = {"white": "D1B2A1", "orange": "A25426", "magenta": "95576C", "light_blue": "706C8A", "yellow": "BA8523",
               "lime": "677535", "pink": "A14E4E", "gray": "392A23", "light_gray": "876B62", "cyan": "575B5B", "purple": "764656",
               "blue": "4A3B5B", "brown": "4D3323", "green": "4C532A", "red": "8F3D2E", "black": "251610"}
_NATURAL = {"stone": "7D7D7D", "stone_bricks": "7A7A7A", "smooth_stone": "9E9E9E", "deepslate": "505053", "oak_planks": "B8945F",
            "spruce_planks": "7A5A34", "birch_planks": "C5B077", "jungle_planks": "B88764", "acacia_planks": "A95A32",
            "dark_oak_planks": "3E2912", "bricks": "976053", "sandstone": "E0D6A8", "sand": "DBD3A0", "snow_block": "F9FEFE",
            "gold_block": "F6D03D", "iron_block": "DCDCDC", "diamond_block": "62EDE4", "emerald_block": "2BCB5D",
            "lapis_block": "1F43A0", "redstone_block": "A81A09", "coal_block": "101010", "netherrack": "6F3737",
            "quartz_block": "ECE6DF", "glowstone": "AB8654", "obsidian": "0F0B19", "pumpkin": "C07615", "prismarine": "63AB9B",
            "dark_prismarine": "345C4C", "purpur_block": "A97DA9", "end_stone": "DFE2A4", "dirt": "866043", "moss_block": "596D2D",
            "copper_block": "C06C50", "oxidized_copper": "52A385"}


def _hex(h):
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _make(tables):
    out = []
    for suffix, table in tables:
        for name, h in table.items():
            out.append(("minecraft:" + (name if suffix is None else name + suffix), _hex(h)))
    return out


PALETTES = {
    "concrete": ("Concrete (bright, flat colours)", _make([("_concrete", _CONCRETE)])),
    "wool": ("Wool (soft colours)", _make([("_wool", _WOOL)])),
    "terracotta": ("Terracotta (earthy)", _make([("_terracotta", _TERRACOTTA)])),
    "colors": ("All coloured blocks", _make([("_concrete", _CONCRETE), ("_wool", _WOOL), ("_terracotta", _TERRACOTTA)])),
    "all": ("Everything (colours + natural blocks)",
            _make([("_concrete", _CONCRETE), ("_wool", _WOOL), ("_terracotta", _TERRACOTTA), (None, _NATURAL)])),
    "mono": ("Black and white", [("minecraft:white_concrete", _hex(_CONCRETE["white"])), ("minecraft:light_gray_concrete", _hex(_CONCRETE["light_gray"])),
                                 ("minecraft:gray_concrete", _hex(_CONCRETE["gray"])), ("minecraft:black_concrete", _hex(_CONCRETE["black"]))]),
}


TEXTURES_LABEL = "Every full block (real game colours)"
_DYN = {}


def _textures(orient):
    """Palette from the real textures in the player's game jar (cached), or None if no game is installed."""
    from . import texpalette
    key = "floor" if orient == "floor" else "wall"
    if key not in _DYN:
        try:
            _DYN[key] = texpalette.palette(key) or None
        except Exception:                                   # noqa: BLE001 - fall back to the built-in colours
            _DYN[key] = None
    return _DYN[key]


def palette_info():
    info = {k: v[0] for k, v in PALETTES.items()}
    if _textures("wall"):
        info = {"textures": TEXTURES_LABEL, **info}         # first = the default in the menu
    return info


def _lab(r, g, b):
    """sRGB (0-255) -> CIE Lab, so 'closest colour' matches what the eye sees."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    R, G, B = lin(r), lin(g), lin(b)
    X = (0.4124 * R + 0.3576 * G + 0.1805 * B) / 0.95047
    Y = 0.2126 * R + 0.7152 * G + 0.0722 * B
    Z = (0.0193 * R + 0.1192 * G + 0.9505 * B) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(X), f(Y), f(Z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


_LABS = {}


def _pal_labs(pal):
    key = id(pal)
    if key not in _LABS:
        _LABS[key] = [_lab(*rgb) for _, rgb in pal]
    return _LABS[key]


def _nearest_idx(labs, idxs, r, g, b):
    L, A, B = _lab(r, g, b)
    best, bd = None, 1e18
    for i in idxs:
        pl, pa, pb = labs[i]
        d = (L - pl) ** 2 + (A - pa) ** 2 + (B - pb) ** 2
        if d < bd:
            best, bd = i, d
    return best


CONTRAST_PENALTY = 1.5        # blends prefer two similar-looking blocks over a high-contrast pair
_BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]     # 4x4 ordered-dither thresholds (0..15)


def _pair(labs, allowed, rgb):
    """The two block colours to blend for this colour: (first, second, how much of the second, 0..1).
    Only near neighbours are used, so a blend never sprinkles in unrelated colours."""
    t_lab = _lab(*rgb)
    near = sorted(allowed, key=lambda i: sum((a - b) ** 2 for a, b in zip(t_lab, labs[i])))[:6]
    c1 = near[0]
    best = (c1, c1, 0.0)
    best_d = None
    for k in near[1:]:
        seg = [b - a for a, b in zip(labs[c1], labs[k])]
        den = sum(v * v for v in seg)
        if den == 0:
            continue
        t = sum((x - a) * v for x, a, v in zip(t_lab, labs[c1], seg)) / den
        if t <= 0:
            continue
        t = min(t, 1.0)
        d = sum((x - (a + t * v)) ** 2 for x, a, v in zip(t_lab, labs[c1], seg)) ** 0.5 + CONTRAST_PENALTY * den ** 0.5
        if best_d is None or d < best_d:
            best, best_d = (c1, k, t), d
    return best


def convert(w, h, rgba, palette="concrete", dither=False, orient="wall", max_colors=0, scale=1):
    """rgba: bytes of (w*scale)*(h*scale)*4. Returns {(x, y, z): 'minecraft:...'}.
    scale > 1: the picture was sent at higher resolution, so every block is decided by a vote of scale*scale samples.
        That keeps edges crisp (no half-way colours where two colours meet).
    dither: blend the two closest block colours in an even checker pattern to fake shading (off keeps flat colours flat).
    max_colors: use at most this many different blocks (0 = no limit)."""
    scale = max(1, int(scale))
    if not (1 <= w <= MAX_SIDE and 1 <= h <= MAX_SIDE) or scale > 4 or len(rgba) != w * scale * h * scale * 4:
        raise ValueError(f"The picture must be between 1 and {MAX_SIDE} blocks on each side.")
    pal = (_textures(orient) if palette == "textures" else None) or PALETTES.get(palette, PALETTES["all"])[1]
    labs = _pal_labs(pal)
    sw = w * scale
    allowed = list(range(len(pal)))
    qcache = {}

    def idx_of(c, idxs=None):
        key = (c[0] >> 3, c[1] >> 3, c[2] >> 3) if idxs is None else None
        if key is not None and key in qcache:
            return qcache[key]
        v = _nearest_idx(labs, idxs or allowed, c[0], c[1], c[2])
        if key is not None:
            qcache[key] = v
        return v

    cells = {}                                              # (x, y) -> list of (r, g, b) from the opaque samples
    for y in range(h):
        for x in range(w):
            samples, opaque = [], 0
            for sy in range(scale):
                row = ((y * scale + sy) * sw + x * scale) * 4
                for sx in range(scale):
                    o = row + sx * 4
                    if rgba[o + 3] >= 128:
                        opaque += 1
                        samples.append((rgba[o], rgba[o + 1], rgba[o + 2]))
            if opaque * 2 >= scale * scale and samples:
                cells[(x, y)] = samples

    chosen = {}                                             # (x, y) -> palette index
    if dither:
        avg = {k: tuple(round(sum(c[i] for c in v) / len(v)) for i in range(3)) for k, v in cells.items()}
        if max_colors and max_colors > 0:
            allowed = _limit(labs, allowed, [idx_of(c) for c in avg.values()], max_colors)
        pcache = {}
        for (x, y), c in avg.items():
            key = (c[0] >> 2, c[1] >> 2, c[2] >> 2)
            if key not in pcache:
                pcache[key] = _pair(labs, allowed, c)
            i1, i2, t = pcache[key]
            chosen[(x, y)] = i2 if t > (_BAYER[y % 4][x % 4] + 0.5) / 16 else i1
    else:
        votes = {}
        for k, samples in cells.items():
            tally = {}
            for c in samples:
                i = idx_of(c)
                tally[i] = tally.get(i, 0) + 1
            votes[k] = max(tally.items(), key=lambda kv: kv[1])[0]
        if max_colors and max_colors > 0:
            keep = _limit(labs, allowed, list(votes.values()), max_colors)
            if len(keep) < len(set(votes.values())):
                votes = {k: (v if v in keep else _nearest_idx(labs, keep, *(round(t) for t in pal[v][1]))) for k, v in votes.items()}
        chosen = votes

    blocks = {}
    for (x, y), i in chosen.items():
        name = pal[i][0]
        if orient == "floor":
            blocks[(x, 0, y)] = name                        # picture lies flat, top of the picture to the north
        else:
            blocks[(x, h - 1 - y, 0)] = name                # picture stands up, facing south (towards +z)
    if not blocks:
        raise ValueError("That picture is completely transparent.")
    return blocks


def _limit(labs, allowed, used, max_colors):
    """The `max_colors` most-used palette entries among `used`."""
    counts = {}
    for i in used:
        counts[i] = counts.get(i, 0) + 1
    if len(counts) <= max_colors:
        return allowed
    return [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:max_colors]]
