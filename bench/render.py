"""Bench renders for an eye check: 4 side views (iso from NE, SE, SW, NW) + a top map, real-ish block colours, one PNG.
python bench/render.py <build dir> <out.png>   (needs Pillow)"""
import sys, os, json, zlib
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import load, nm

COL = [("red_maple", (170, 50, 30)), ("orange_maple", (215, 120, 30)), ("leaves", (52, 110, 45)), ("grass_block", (95, 150, 60)),
       ("short_grass", (90, 145, 55)), ("fern", (80, 130, 55)), ("water", (50, 90, 200)), ("glass", (190, 220, 230)), ("pane", (190, 220, 230)),
       ("lantern", (250, 200, 90)), ("torch", (250, 190, 80)), ("dark_oak", (66, 43, 21)), ("spruce", (100, 72, 42)), ("birch", (200, 185, 130)),
       ("oak", (160, 125, 75)), ("jungle", (160, 110, 75)), ("acacia", (170, 90, 50)), ("cherry", (225, 175, 170)), ("mangrove", (120, 50, 45)),
       ("deepslate", (70, 70, 75)), ("blackstone", (45, 40, 45)), ("cobblestone", (120, 120, 120)), ("mossy", (100, 120, 85)),
       ("stone_brick", (125, 125, 125)), ("andesite", (135, 135, 135)), ("diorite", (190, 190, 190)), ("granite", (150, 105, 85)),
       ("tuff", (105, 105, 95)), ("calcite", (225, 225, 220)), ("stone", (125, 125, 125)), ("brick", (150, 75, 60)), ("terracotta", (160, 90, 65)),
       ("white", (230, 230, 230)), ("red", (170, 45, 40)), ("black", (30, 30, 30)), ("dirt", (130, 95, 65)), ("podzol", (100, 70, 40)),
       ("gravel", (135, 130, 125)), ("sand", (215, 205, 160)), ("path", (150, 125, 75)), ("mud", (140, 105, 80)), ("wool", (220, 220, 220)),
       ("hay", (200, 170, 50)), ("flower", (220, 90, 120)), ("poppy", (200, 40, 40)), ("dandelion", (230, 210, 50)), ("bookshelf", (120, 85, 50)),
       ("chest", (150, 105, 50)), ("bed", (170, 40, 40)), ("carpet", (170, 60, 60)), ("iron", (200, 200, 200)), ("gold", (230, 200, 60))]


def col(n):
    for k, c in COL:
        if k in n: return c
    h = zlib.crc32(n.encode()); return (90 + h % 120, 90 + (h >> 8) % 120, 90 + (h >> 16) % 120)


def iso(cells, size, rot, S=6):
    W, H, L = size
    def tr(x, z):
        for _ in range(rot): x, z = L - 1 - z, x; W_, L_ = L, W
        return x, z
    pts = []
    for (x, y, z), s in cells.items():
        n = nm(s)
        if n in ("air", "light", "structure_void"): continue
        tx, tz = x, z
        for _ in range(rot): tx, tz = (max(W, L) - 1 - tz), tx
        pts.append((tx, y, tz, col(n)))
    if not pts: return Image.new("RGB", (64, 64), (180, 215, 245))
    pts.sort(key=lambda p: (p[0] + p[2], p[1]))
    mx = max(p[0] for p in pts) + 1; mz = max(p[2] for p in pts) + 1; my = max(p[1] for p in pts) + 1
    w = (mx + mz) * S + 2 * S; h = (mx + mz) * S // 2 + my * S + 2 * S
    im = Image.new("RGB", (w, h), (180, 215, 245)); dr = ImageDraw.Draw(im)
    for x, y, z, c in pts:
        cx = (x - z) * S + mz * S + S; cy = (x + z) * S // 2 - y * S + my * S + S
        top = [(cx, cy - S // 2), (cx + S, cy), (cx, cy + S // 2), (cx - S, cy)]
        left = [(cx - S, cy), (cx, cy + S // 2), (cx, cy + S // 2 + S), (cx - S, cy + S)]
        right = [(cx + S, cy), (cx, cy + S // 2), (cx, cy + S // 2 + S), (cx + S, cy + S)]
        dr.polygon(top, fill=c); dr.polygon(left, fill=tuple(int(v * 0.75) for v in c)); dr.polygon(right, fill=tuple(int(v * 0.6) for v in c))
    bb = im.getbbox(); return im


def top(cells, size, S=4):
    W, H, L = size; t = {}
    for (x, y, z), s in cells.items():
        n = nm(s)
        if n in ("air", "light", "structure_void"): continue
        if y >= t.get((x, z), (-1, ""))[0]: t[(x, z)] = (y, n)
    im = Image.new("RGB", (W * S, L * S), (40, 40, 40)); dr = ImageDraw.Draw(im)
    for (x, z), (y, n) in t.items():
        f = 0.55 + 0.45 * y / max(1, H); c = col(n)
        dr.rectangle([x * S, z * S, x * S + S - 1, z * S + S - 1], fill=tuple(int(v * f) for v in c))
    return im


def sheet(d, out):
    size, cells = load(d)
    S = 6 if max(size) <= 48 else (3 if max(size) <= 120 else 2)
    ims = [iso(cells, size, r, S) for r in range(4)] + [top(cells, size, max(2, S - 2))]
    w = sum(i.width for i in ims) + 10 * len(ims); h = max(i.height for i in ims) + 20
    sh = Image.new("RGB", (w, h), (250, 250, 250)); x = 0; dr = ImageDraw.Draw(sh)
    for k, i in enumerate(ims):
        sh.paste(i, (x, 20)); dr.text((x + 4, 4), ("from NE", "from SE", "from SW", "from NW", "top (north up)")[k], fill=(0, 0, 0)); x += i.width + 10
    meta = json.load(open(os.path.join(d, "meta.json")))
    dr.text((w - 400, 4), (meta.get("title") or "")[:60], fill=(0, 0, 0))
    sh.save(out)


if __name__ == "__main__":
    sheet(sys.argv[1], sys.argv[2]); print("RENDER_OK", sys.argv[2])
