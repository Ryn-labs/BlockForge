"""Derive the reference colour histograms for blockforge/quality.py (dev tool, run by hand; needs Pillow).

    python tools/ref_palette.py <folder with the reference pictures> [--preview <folder>]

The owner's seven reference houses (quality-refs-1127: ref1-...jpg .. ref7-...jpg) have an unknown licence: they are read
here on the developer's machine only. What is written to blockforge/data/ref_palette.json is 64 numbers per picture (the
share of each colour bin of quality.colour_hist), never pixels. --preview writes the masked house areas as PNGs to check
the crops by eye (not shipped).

House area of a picture: a hand-picked crop round the house (CROPS, fractions of the width and height), minus sky,
water and blueprint background (saturated blue), grass and leaves (saturated green) and, on the drawn plans, the white
paper and the black grid lines.
"""
import colorsys
import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from blockforge import quality  # noqa: E402

OUT = os.path.join(ROOT, "blockforge", "data", "ref_palette.json")
# name prefix -> (crop boxes as (left, top, right, bottom) fractions, drawn plan)
CROPS = {
    "ref1": ([(0.0, 0.33, 1.0, 0.64)], False),                       # the shore manor; the sea and fields are masked
    "ref2": ([(0.04, 0.05, 0.97, 0.80)], False),                     # the stilt manor above the water
    "ref3": ([(0.12, 0.06, 0.92, 0.86)], False),                     # terrace farmhouse on the blueprint background
    "ref4": ([(0.18, 0.34, 0.88, 0.62)], False),                     # farm house, below the ship
    "ref5": ([(0.13, 0.0, 0.87, 0.82)], False),                      # front manor on the blueprint background
    "ref6": ([(0.03, 0.59, 0.49, 0.77), (0.03, 0.80, 0.37, 0.98)], True),   # the four drawn elevations
    "ref7": ([(0.05, 0.07, 0.65, 0.84)], True),                      # the drawn layers
}


def keep(rgb, plan):
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    deg = h * 360
    if s > 0.3 and 196 <= deg <= 265:
        return False                                                 # sky, water, blueprint paper
    if s > 0.3 and 62 <= deg <= 160:
        return False                                                 # grass, leaves, crops
    if plan and (min(rgb) > 225 or max(rgb) < 40 or (s < 0.06 and v > 0.7)):
        return False                                                 # white paper, its grey and black grid lines
    return True


def house_colours(path, boxes, plan, preview=None):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    step = max(1, int((W * H / 250000) ** 0.5))                     # about 250 000 samples a picture at most
    counts = {}
    shots = []
    for (a, b, c, d) in boxes:
        box = (int(a * W), int(b * H), int(c * W), int(d * H))
        crop = im.crop(box)
        px = crop.load()
        shot = Image.new("RGB", crop.size, (255, 0, 255)) if preview else None
        for y in range(0, crop.size[1], step):
            for x in range(0, crop.size[0], step):
                rgb = px[x, y]
                if keep(rgb, plan):
                    counts[rgb] = counts.get(rgb, 0) + 1
                    if shot:
                        shot.putpixel((x, y), rgb)
        shots.append(shot)
    if preview:
        os.makedirs(preview, exist_ok=True)
        for i, s in enumerate(shots):
            s.save(os.path.join(preview, os.path.splitext(os.path.basename(path))[0] + f"-{i}.png"))
    return counts


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    folder = argv[0]
    preview = argv[argv.index("--preview") + 1] if "--preview" in argv else None
    refs = {}
    for fn in sorted(os.listdir(folder)):
        key = fn.split("-", 1)[0]
        if key not in CROPS:
            continue
        boxes, plan = CROPS[key]
        counts = house_colours(os.path.join(folder, fn), boxes, plan, preview)
        h = quality.colour_hist(counts)
        Ls = sorted((quality.lab(c)[0], n) for c, n in counts.items())
        tot = sum(n for _, n in Ls)
        acc, med = 0, 0.0
        for L, n in Ls:
            acc += n
            if acc >= tot / 2:
                med = L
                break
        refs[os.path.splitext(fn)[0]] = {"kind": "plan" if plan else "photo", "hist": [round(v, 4) for v in h],
                                         "median_lightness": round(med, 1), "samples": tot}
        print(f"{fn}: {tot} samples, median lightness {med:.0f}")
    data = {"about": "Colour histograms of the house areas of the owner's 7 reference pictures (quality-refs-1127), "
                     "made by tools/ref_palette.py with quality.colour_hist: 4 lightness bands x (grey + 15 hue sectors). "
                     "Derived numbers only; no image data.",
            "bins": [quality.HIST_BANDS, quality.HIST_HUES + 1],
            "refs": refs}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
