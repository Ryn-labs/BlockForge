"""Real block colours, read from the textures in the player's own Minecraft jar.

Every full, solid, untinted cube block is found by following its block model up to `block/cube`. Its visible face
is averaged (the side for a wall, the top for a floor), and how busy the texture is gets measured too, so pixel art
can prefer calm textures. The result is cached per game version in DATA/blockdb."""
import json
import os
import zipfile

from . import mods

CACHE_VERSION = 1
_DEFAULTS = {"axis": "y", "snowy": "false", "lit": "false", "powered": "false", "waterlogged": "false"}
_SKIP_WORDS = ("infested_", "waxed_", "concrete_powder", "command_block", "structure_block", "jigsaw", "barrier",
               "spawner", "vault", "suspicious_", "budding_", "_shulker_box", "shulker_box", "reinforced_deepslate")
_SKIP = {"sand", "red_sand", "gravel", "light", "tnt", "sponge", "wet_sponge", "dragon_egg", "beacon", "frosted_ice",
         "ice", "slime_block", "honey_block", "magma_block", "sculk_catalyst", "test_block", "test_instance_block",
         "petrified_oak_slab", "creaking_heart", "pale_moss_block"}
BUSY_LIMIT = 30          # luma standard deviation: above this a texture is too speckled to read as one pixel
_mem = {}


def _ref(name):
    name = name.split(":")[-1]
    return name if "/" in name else "block/" + name


def _load(z, path):
    try:
        return json.loads(z.read(path))
    except (KeyError, ValueError):
        return None


def _faces(z, model):
    """(south texture, up texture) for a plain full-cube model, else None."""
    textures, ref, depth = {}, _ref(model), 0
    while ref and depth < 12:
        if ref == "block/cube":
            break
        m = _load(z, f"assets/minecraft/models/{ref}.json")
        if m is None or "elements" in m:                    # custom shape (leaves, grass overlay, slabs...): not a plain cube
            return None
        for k, v in (m.get("textures") or {}).items():
            textures.setdefault(k, v)
        ref = _ref(m["parent"]) if m.get("parent") else None
        depth += 1
    if ref != "block/cube":
        return None

    def tex(key):
        v, seen = "#" + key, 0
        while isinstance(v, str) and v.startswith("#") and seen < 8:
            v = textures.get(v[1:])
            seen += 1
        return _ref(v) if isinstance(v, str) else None
    s, u = tex("south"), tex("up")
    return (s, u) if s and u else None


def _default_model(bs):
    variants = bs.get("variants")
    if not isinstance(variants, dict):
        return None                                         # multipart blocks (fences, walls...) are never full cubes
    for key, v in variants.items():
        props = dict(p.split("=", 1) for p in key.split(",") if "=" in p)
        if all(_DEFAULTS.get(k) == val for k, val in props.items()):
            v = v[0] if isinstance(v, list) else v
            return v.get("model") if isinstance(v, dict) and not v.get("x") and not v.get("y") else None
    return None


def _stats(z, tex):
    try:
        px = mods.png_pixels(z.read(f"assets/minecraft/textures/{tex}.png"), max_rows=16)
    except KeyError:
        return None
    if not px or any(a < 250 for *_, a in px):              # see-through textures (glass, ice) can't be a pixel
        return None
    n = len(px)
    r = sum(p[0] for p in px) / n; g = sum(p[1] for p in px) / n; b = sum(p[2] for p in px) / n
    lum = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px]
    m = sum(lum) / n
    std = (sum((v - m) ** 2 for v in lum) / n) ** 0.5
    return [round(r), round(g), round(b)], round(std, 1)


def build(version):
    """{'version', 'wall': [[id, [r,g,b], busy]], 'floor': [...]} or None if that game version isn't on this PC."""
    jar = mods.find_client_jar(version)
    if not jar:
        return None
    wall, floor = [], []
    with zipfile.ZipFile(jar) as z:
        for name in sorted(mods._blockstate_ids(z).get("minecraft", set())):
            if name in _SKIP or any(w in name for w in _SKIP_WORDS):
                continue
            if name.endswith("_coral_block") and not name.startswith("dead_"):
                continue                                    # live coral turns into dead coral out of water
            bs = _load(z, f"assets/minecraft/blockstates/{name}.json")
            model = _default_model(bs) if bs else None
            faces = _faces(z, model) if model else None
            if not faces:
                continue
            for face, out in zip(faces, (wall, floor)):
                st = _stats(z, face)
                if st:
                    out.append(["minecraft:" + name, st[0], st[1]])
    return {"cache": CACHE_VERSION, "version": version, "wall": wall, "floor": floor}


def load(version):
    """Cached build() for a version, or None."""
    if version in _mem:
        return _mem[version]
    path = os.path.join(mods.VANILLA_DIR, f"texcolors-{version}.json")
    data = None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("cache") != CACHE_VERSION:
            data = None
    except (OSError, ValueError):
        pass
    if data is None:
        data = build(version)
        if data:
            os.makedirs(mods.VANILLA_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
    _mem[version] = data
    return data


def best_version():
    """The game version to read textures from: the build target if it's installed, else the newest installed."""
    _, version, _ = mods.build_opts()
    if mods.find_client_jar(version):
        return version
    vs = [v for v in mods.installed_versions() if mods.find_client_jar(v)]
    return vs[0] if vs else None


def palette(orient="wall", calm_only=True, version=None):
    """[(id, (r, g, b))] for pixel art, or None when no game jar is available."""
    version = version or best_version()
    data = load(version) if version else None
    if not data:
        return None
    rows = data["floor" if orient == "floor" else "wall"]
    return [(n, tuple(rgb)) for n, rgb, busy in rows if not calm_only or busy <= BUSY_LIMIT]
