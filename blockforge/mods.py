"""Modpack support: find the user's modpacks, read every mod jar (name, version, blocks), sample real textures for
colours, and give the generator and the placement checker a list of valid block ids.

Block ids come from `assets/<namespace>/blockstates/*.json` inside each jar. Vanilla ids come from the game's own
client jar on this PC (never bundled)."""
import difflib
import glob
import hashlib
import json
import os
import re
import struct
import time
import zipfile
import zlib

from . import store

MODS_DIR = os.path.join(store.DATA, "mods")
VANILLA_DIR = os.path.join(store.DATA, "blockdb")
APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
HOME = os.path.expanduser("~")

CLIENT_JAR_BASES = [
    os.path.join(APPDATA, ".minecraft"), os.path.join(HOME, "curseforge", "minecraft", "Install"),
    os.path.join(APPDATA, "ModrinthApp", "meta"), os.path.join(APPDATA, "com.modrinth.theseus", "meta"),
    os.path.join(APPDATA, "PrismLauncher"), os.path.join(APPDATA, "PrismLauncher", "libraries"),
    os.path.join(APPDATA, "MultiMC"), os.path.join(APPDATA, "ATLauncher", "Minecraft"), os.path.join(APPDATA, "ATLauncher"),
    os.path.join(APPDATA, "gdlauncher_next", "datastore"),
]
RENAMES = {"grass": "short_grass", "tallgrass": "short_grass", "grass_path": "dirt_path", "stone_slab2": "stone_slab",
           "mob_spawner": "spawner", "web": "cobweb", "reeds": "sugar_cane", "waterlily": "lily_pad",
           "snow_layer": "snow", "hardened_clay": "terracotta", "stained_hardened_clay": "white_terracotta",
           "wool": "white_wool", "planks": "oak_planks", "log": "oak_log", "leaves": "oak_leaves", "sapling": "oak_sapling",
           "stonebrick": "stone_bricks", "brick_block": "bricks", "nether_brick": "nether_bricks", "quartz_ore": "nether_quartz_ore",
           "lit_pumpkin": "jack_o_lantern", "noteblock": "note_block", "golden_rail": "powered_rail", "fence": "oak_fence",
           "wooden_door": "oak_door", "trapdoor": "oak_trapdoor", "standing_sign": "oak_sign", "wall_sign": "oak_wall_sign"}


# ================================================================== vanilla ids from the user's own game
def find_client_jar(version):
    if not version:
        return None
    for base in CLIENT_JAR_BASES:
        for pat in (os.path.join(base, "versions", version, version + ".jar"), os.path.join(base, version, version + ".jar"),
                    os.path.join(base, "**", version, version + ".jar")):
            hit = glob.glob(pat, recursive=True)
            if hit:
                return hit[0]
    return None


def installed_versions():
    out = set()
    for base in CLIENT_JAR_BASES:
        for d in glob.glob(os.path.join(base, "versions", "*")) + glob.glob(os.path.join(base, "*")):
            v = os.path.basename(d)
            if re.fullmatch(r"\d+(\.\d+){1,2}", v) and os.path.isfile(os.path.join(d, v + ".jar")):
                out.add(v)
    return sorted(out, key=lambda v: [int(x) for x in v.split(".")], reverse=True)


def _blockstate_ids(zf):
    ids = {}
    for n in zf.namelist():
        m = re.fullmatch(r"assets/([^/]+)/blockstates/(.+)\.json", n)
        if m:
            ids.setdefault(m.group(1), set()).add(m.group(2))
    return ids


def vanilla_ids(version):
    """Set of valid minecraft block names for a game version, or None if its jar isn't on this PC."""
    if not version:
        return None
    os.makedirs(VANILLA_DIR, exist_ok=True)
    cache = os.path.join(VANILLA_DIR, f"vanilla-{version}.json")
    if os.path.isfile(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                return set(json.load(f))
        except (OSError, ValueError):
            pass
    jar = find_client_jar(version)
    if not jar:
        return None
    try:
        with zipfile.ZipFile(jar) as z:
            names = sorted(_blockstate_ids(z).get("minecraft", set()))
    except (OSError, zipfile.BadZipFile):
        return None
    names += ["air", "cave_air", "void_air", "water", "lava"]
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(sorted(set(names)), f)
    return set(names)


# ================================================================== PNG average colour (no imaging library needed)
def png_average(data):
    """Average RGB of a PNG (alpha-weighted), or None for formats we can't read."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, plte, trns = 8, [], None, None
    w = h = depth = ctype = interlace = None
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if not w or interlace or depth not in (1, 2, 4, 8):
        return None
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if ch is None:
        return None
    raw = zlib.decompress(b"".join(idat))
    bpp = max(1, (ch * depth) // 8)
    stride = (w * ch * depth + 7) // 8
    rows, prev = [], bytearray(stride)
    p = 0
    for _ in range(min(h, 64)):                         # animated strips are tall: the first frames are enough
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                line[i] = (line[i] + (((line[i - bpp] if i >= bpp else 0) + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(line)
        prev = line
    r = g = b = n = 0
    for line in rows:
        for x in range(w):
            if ctype == 3:
                bit = x * depth
                idx = (line[bit // 8] >> (8 - depth - bit % 8)) & ((1 << depth) - 1)
                pr, pg, pb = plte[idx * 3:idx * 3 + 3]
                a = trns[idx] if trns and idx < len(trns) else 255
            elif depth != 8:
                v = line[x * depth // 8] >> (8 - depth - (x * depth) % 8) & ((1 << depth) - 1)
                pr = pg = pb = v * 255 // ((1 << depth) - 1)
                a = 255
            elif ctype == 0:
                pr = pg = pb = line[x]; a = 255
            elif ctype == 4:
                pr = pg = pb = line[x * 2]; a = line[x * 2 + 1]
            elif ctype == 2:
                pr, pg, pb = line[x * 3:x * 3 + 3]; a = 255
            else:
                pr, pg, pb, a = line[x * 4:x * 4 + 4]
            if a > 40:
                r += pr * a; g += pg * a; b += pb * a; n += a
    if not n:
        return None
    return (r // n, g // n, b // n)


# ================================================================== mod metadata
def _toml(text):
    try:
        import tomllib
        return tomllib.loads(text)
    except Exception:                                     # noqa: BLE001
        return {}


def read_mod_meta(zf, filename):
    """(id, name, version, mc_range) from whichever mod format the jar uses."""
    base = re.sub(r"\.jar$", "", os.path.basename(filename))
    names = set(zf.namelist())
    try:
        if "fabric.mod.json" in names:
            d = json.loads(zf.read("fabric.mod.json").decode("utf-8", "replace"), strict=False)
            return d.get("id"), d.get("name") or d.get("id"), str(d.get("version", "")), str((d.get("depends") or {}).get("minecraft", ""))
        if "quilt.mod.json" in names:
            d = json.loads(zf.read("quilt.mod.json").decode("utf-8", "replace"), strict=False)["quilt_loader"]
            return d.get("id"), (d.get("metadata") or {}).get("name") or d.get("id"), str(d.get("version", "")), ""
        for toml in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
            if toml in names:
                t = _toml(zf.read(toml).decode("utf-8", "replace"))
                m = (t.get("mods") or [{}])[0]
                mid = m.get("modId")
                ver = str(m.get("version", ""))
                if ver.startswith("${"):
                    ver = re.search(r"(\d+(\.\d+)+[\w.+-]*)", base.replace(str(mid), "")) and re.search(r"(\d+(\.\d+)+[\w.+-]*)", base).group(1) or ""
                mc = ""
                for dep in (t.get("dependencies") or {}).get(mid, []) or []:
                    if dep.get("modId") == "minecraft":
                        mc = str(dep.get("versionRange", ""))
                return mid, m.get("displayName") or mid, ver, mc
        if "mcmod.info" in names:
            d = json.loads(zf.read("mcmod.info").decode("utf-8", "replace"), strict=False)
            d = d[0] if isinstance(d, list) else (d.get("modList") or [{}])[0]
            return d.get("modid"), d.get("name"), str(d.get("version", "")), str(d.get("mcversion", ""))
    except Exception:                                     # noqa: BLE001
        pass
    return None, base, "", ""


def loader_of(zf):
    n = set(zf.namelist())
    if "fabric.mod.json" in n:
        return "fabric"
    if "quilt.mod.json" in n:
        return "quilt"
    if "META-INF/neoforge.mods.toml" in n:
        return "neoforge"
    if "META-INF/mods.toml" in n:
        return "forge"
    return None


# ================================================================== finding modpacks on this PC
def _instance_info(inst_dir):
    mc = loader = None
    j = os.path.join(inst_dir, "minecraftinstance.json")
    try:
        if os.path.isfile(j):
            d = json.load(open(j, encoding="utf-8"))
            mc = d.get("gameVersion")
            loader = ((d.get("baseModLoader") or {}).get("name")) or None
        elif os.path.isfile(os.path.join(inst_dir, "mmc-pack.json")):
            d = json.load(open(os.path.join(inst_dir, "mmc-pack.json"), encoding="utf-8"))
            for c in d.get("components", []):
                if c.get("uid") == "net.minecraft":
                    mc = c.get("version")
                elif c.get("uid", "").startswith(("net.fabricmc", "net.minecraftforge", "net.neoforged", "org.quiltmc")):
                    loader = c["uid"].split(".")[-1] + "-" + str(c.get("version", ""))
        elif os.path.isfile(os.path.join(inst_dir, "instance.json")):
            d = json.load(open(os.path.join(inst_dir, "instance.json"), encoding="utf-8"))
            mc = (d.get("launcher") or {}).get("loaderVersion", {}).get("type") and d.get("id")
    except (OSError, ValueError):
        pass
    return mc, loader


def detect_instances():
    found = []

    def add(launcher, name, inst):
        for sub in ("mods", os.path.join(".minecraft", "mods"), os.path.join("minecraft", "mods")):
            d = os.path.join(inst, sub)
            if os.path.isdir(d):
                jars = len(glob.glob(os.path.join(d, "*.jar")))
                if jars:
                    mc, loader = _instance_info(inst)
                    found.append({"launcher": launcher, "name": name, "path": d, "jars": jars, "mc": mc, "loader": loader})
                return

    roots = [("CurseForge", os.path.join(HOME, "curseforge", "minecraft", "Instances")),
             ("Modrinth", os.path.join(APPDATA, "ModrinthApp", "profiles")),
             ("Modrinth", os.path.join(APPDATA, "com.modrinth.theseus", "profiles")),
             ("Prism Launcher", os.path.join(APPDATA, "PrismLauncher", "instances")),
             ("MultiMC", os.path.join(APPDATA, "MultiMC", "instances")),
             ("ATLauncher", os.path.join(APPDATA, "ATLauncher", "instances")),
             ("GDLauncher", os.path.join(APPDATA, "gdlauncher_next", "instances"))]
    for launcher, root in roots:
        if os.path.isdir(root):
            for d in sorted(os.listdir(root)):
                if os.path.isdir(os.path.join(root, d)):
                    add(launcher, d, os.path.join(root, d))
    add("Minecraft launcher", "Default (.minecraft)", os.path.join(APPDATA, ".minecraft"))
    return found


def resolve_mods_dir(path):
    path = os.path.normpath(os.path.expandvars(str(path).strip().strip('"')))
    if os.path.isfile(path) and path.lower().endswith(".jar"):
        path = os.path.dirname(path)
    if not os.path.isdir(path):
        raise ValueError("That folder doesn't exist.")
    for cand in (path, os.path.join(path, "mods"), os.path.join(path, ".minecraft", "mods"), os.path.join(path, "minecraft", "mods")):
        if os.path.isdir(cand) and glob.glob(os.path.join(cand, "*.jar")):
            return cand
    raise ValueError("I couldn't find any .jar mods in that folder (pick the folder named 'mods', or the modpack's folder).")


# ================================================================== scanning a pack
def pack_id(path):
    return hashlib.sha1(os.path.normcase(path).encode("utf-8")).hexdigest()[:10]


def pack_file(pid):
    return os.path.join(MODS_DIR, pid + ".json")


def load_index(pid):
    try:
        with open(pack_file(pid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _model_textures(lookup, ns, ref, depth=0):
    """Merged texture map for a model reference like 'ns:block/name', following parents."""
    if depth > 8 or not ref:
        return {}
    mns, _, path = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
    data = lookup(f"assets/{mns}/models/{path}.json")
    if not data:
        return {}
    try:
        d = json.loads(data.decode("utf-8", "replace"), strict=False)
    except ValueError:
        return {}
    tex = _model_textures(lookup, mns, d.get("parent"), depth + 1)
    tex.update(d.get("textures") or {})
    return tex


def _first_model(bs):
    v = bs.get("variants")
    if isinstance(v, dict) and v:
        v = next(iter(v.values()))
        v = v[0] if isinstance(v, list) else v
        return v.get("model")
    for part in bs.get("multipart") or []:
        a = part.get("apply")
        a = a[0] if isinstance(a, list) else a
        if a and a.get("model"):
            return a["model"]
    return None


def _pick_texture(tex):
    def res(v, seen=0):
        while isinstance(v, str) and v.startswith("#") and seen < 6:
            v = tex.get(v[1:]); seen += 1
        return v if isinstance(v, str) and not v.startswith("#") else None
    for k in ("all", "side", "particle", "top", "front", "texture", "end", "0", "1", "layer0", "cross", "plant", "wall", "bottom"):
        if k in tex and res(tex[k]):
            return res(tex[k])
    for v in tex.values():
        if res(v):
            return res(v)
    return None


def _fallback_color(name):
    h = hashlib.md5(name.encode()).digest()
    return (110 + h[0] % 100, 110 + h[1] % 100, 110 + h[2] % 100)


def scan(mods_dir, name=None, log=print, extra_jars=()):
    """Read every jar in mods_dir. Saves and returns the pack index."""
    os.makedirs(MODS_DIR, exist_ok=True)
    pid = pack_id(mods_dir)
    inst_dir = os.path.dirname(mods_dir)
    mc, loader = _instance_info(inst_dir)
    jars = sorted(glob.glob(os.path.join(mods_dir, "*.jar")))
    log(f"Reading {len(jars)} mods...")
    zfs, per_jar, index = {}, {}, {}
    mc_votes, loader_votes = {}, {}
    for jp in jars:
        try:
            zf = zipfile.ZipFile(jp)
        except (OSError, zipfile.BadZipFile):
            continue
        zfs[jp] = zf
        ids = _blockstate_ids(zf)
        per_jar[jp] = ids
        for n in zf.namelist():
            if re.match(r"assets/[^/]+/(blockstates|models/block|textures/block)/", n):
                index.setdefault(n, jp)
        ld = loader_of(zf)
        if ld:
            loader_votes[ld] = loader_votes.get(ld, 0) + 1
    vz = None
    if not mc:
        for jp, zf in zfs.items():
            m = re.search(r"1\.\d+(?:\.\d+)?", read_mod_meta(zf, jp)[3] or "")
            if m:
                mc_votes[m.group(0)] = mc_votes.get(m.group(0), 0) + 1
        mc = max(mc_votes, key=mc_votes.get) if mc_votes else None
    if not loader:
        loader = max(loader_votes, key=loader_votes.get) if loader_votes else None
    vjar = find_client_jar(mc)
    if vjar:
        try:
            vz = zipfile.ZipFile(vjar)
            for n in vz.namelist():
                if re.match(r"assets/minecraft/(models/block|textures/block)/", n):
                    index.setdefault(n, vjar)
            zfs[vjar] = vz
        except (OSError, zipfile.BadZipFile):
            vz = None

    def lookup(path):
        jp = index.get(path)
        if jp and jp in zfs:
            try:
                return zfs[jp].read(path)
            except KeyError:
                return None
        return None

    mods, colors, total_blocks = [], {}, 0
    for n, jp in enumerate(jars, 1):
        zf = zfs.get(jp)
        if not zf:
            continue
        mid, mname, mver, _ = read_mod_meta(zf, jp)
        ids = per_jar.get(jp, {})
        blocks = sorted(f"{ns}:{b}" for ns, bs in ids.items() for b in bs if ns != "minecraft")
        for full in blocks:
            ns, b = full.split(":", 1)
            try:
                bs = json.loads(zf.read(f"assets/{ns}/blockstates/{b}.json").decode("utf-8", "replace"), strict=False)
                tex = _pick_texture(_model_textures(lookup, ns, _first_model(bs)))
                col = None
                if tex:
                    tns, _, tp = tex.partition(":") if ":" in tex else ("minecraft", "", tex)
                    png = lookup(f"assets/{tns}/textures/{tp}.png")
                    col = png_average(png) if png else None
                if not col:
                    png = lookup(f"assets/{ns}/textures/block/{b}.png")
                    col = png_average(png) if png else None
            except Exception:                              # noqa: BLE001
                col = None
            c = col or _fallback_color(full)
            colors[full] = "%02x%02x%02x" % tuple(int(x) for x in c)
        total_blocks += len(blocks)
        mods.append({"file": os.path.basename(jp), "id": mid, "name": mname or os.path.basename(jp), "version": mver,
                     "blocks": blocks, "enabled": True})
        if n % 10 == 0 or blocks and len(blocks) > 200:
            log(f"Mod {n}/{len(jars)}: {mname} ({len(blocks)} blocks)")
    for zf in zfs.values():
        zf.close()
    old = load_index(pid) or {}
    off = {m["file"] for m in old.get("mods", []) if not m.get("enabled", True)}
    for m in mods:
        m["enabled"] = m["file"] not in off
    idx = {"id": pid, "name": name or os.path.basename(inst_dir), "path": mods_dir, "mc": mc, "loader": loader,
           "scanned": time.time(), "mods": mods, "colors": colors, "vanilla_texture_source": bool(vz)}
    with open(pack_file(pid), "w", encoding="utf-8") as f:
        json.dump(idx, f, separators=(",", ":"))
    log(f"Done: {len(mods)} mods, {total_blocks:,} blocks.")
    return idx


def summary(idx):
    return {"id": idx["id"], "name": idx["name"], "path": idx["path"], "mc": idx.get("mc"), "loader": idx.get("loader"),
            "mods": len(idx["mods"]), "blocks": sum(len(m["blocks"]) for m in idx["mods"]), "scanned": idx.get("scanned"),
            "mods_off": sum(1 for m in idx["mods"] if not m.get("enabled", True))}


# ================================================================== using the active pack
def active_pack():
    s = store.load_settings()
    pid = s.get("active_pack")
    if not pid or not s.get("use_mods", True):
        return None
    return load_index(pid)


def enabled_blocks(idx):
    return {b for m in idx["mods"] if m.get("enabled", True) for b in m["blocks"]}


def mod_colors(names, idx=None):
    """{'ns:name': '#rrggbb'} for the modded block names in `names`."""
    out = {}
    packs = [idx] if idx else [load_index(p["id"]) for p in store.load_settings().get("modpacks", [])]
    for ix in filter(None, packs):
        for n in names:
            c = ix["colors"].get(n)
            if c and n not in out:
                out[n] = "#" + c
    return out


def search(idx, q, limit=60):
    q = q.lower().strip()
    out = []
    for m in idx["mods"]:
        if not m.get("enabled", True):
            continue
        for b in m["blocks"]:
            if not q or q in b.lower() or q in m["name"].lower():
                out.append({"id": b, "mod": m["name"], "color": "#" + idx["colors"].get(b, "888888")})
                if len(out) >= limit:
                    return out
    return out


def closest(name, candidates, cutoff=0.82):
    hit = difflib.get_close_matches(name, list(candidates), n=1, cutoff=cutoff)
    return hit[0] if hit else None


_STOP = set("a an the of in on with and or for to from at by is are it that this make build me my some very big small large tiny huge "
            "medieval modern style like using use into out up down over under around about add put place".split())


def prompt_section(idx, prompt, budget=7000):
    """Compact, request-aware description of the modpack's blocks for the AI."""
    mods = [m for m in idx["mods"] if m.get("enabled", True) and m["blocks"]]
    toks = [t for t in re.findall(r"[a-z]+", (prompt or "").lower()) if t not in _STOP and len(t) > 2]
    useful = ("planks", "log", "stairs", "slab", "wall", "fence", "door", "window", "glass", "lamp", "lantern", "brick", "tile", "roof",
              "chair", "table", "sofa", "couch", "bed", "shelf", "cabinet", "counter", "carpet", "pillar", "beam", "arch", "column")

    def score(b, mname):
        n = b.split(":", 1)[1].replace("_", " ")
        s = sum(4 for t in toks if t in n) + sum(1 for t in toks if t in mname.lower())
        return s * 10 + sum(1 for u in useful if u in n)
    lines = [f"## Modpack blocks (the player's pack: {idx['name']}, Minecraft {idx.get('mc') or '?'} {idx.get('loader') or ''})",
             "You may use blocks from these mods in addition to vanilla. Use their EXACT ids, e.g. block(x, y, z, 'modid:block_name'). "
             "Never invent a modded id: only use ids listed below (or in modded_blocks.txt if you can read it). Any id not in the pack gets replaced. Give modded blocks plain ids without "
             "properties unless you are sure of them (facing/half/axis usually work). Prefer vanilla blocks for the main structure "
             "and use modded blocks where they add real detail (furniture, decoration, special materials).", "", "Mods in the pack (blocks):"]
    for m in sorted(mods, key=lambda m: -len(m["blocks"]))[:60]:
        ns = max({b.split(":")[0] for b in m["blocks"]}, key=lambda n: sum(b.startswith(n + ":") for b in m["blocks"]))
        lines.append(f"- {m['name']} ({ns}): {len(m['blocks'])} blocks")
    pool = [(score(b, m["name"]), b) for m in mods for b in m["blocks"]]
    pool.sort(key=lambda x: (-x[0], x[1]))
    lines += ["", "Blocks most relevant to this request:"]
    used = sum(len(l) + 1 for l in lines)
    chosen = []
    for s, b in pool[:160]:
        if s <= 0 and len(chosen) >= 40:
            break
        if used + len(b) + 3 > budget:
            break
        chosen.append(b); used += len(b) + 3
    lines.append(", ".join(chosen))
    return "\n".join(lines)


def write_id_file(idx, folder):
    """All enabled modded block ids, one per line, for the AI to search with Grep (Claude Code engine)."""
    path = os.path.join(folder, "modded_blocks.txt")
    with open(path, "w", encoding="utf-8") as f:
        for m in idx["mods"]:
            if m.get("enabled", True):
                for b in m["blocks"]:
                    f.write(f"{b}\t{m['name']}\n")
    return path


DATA_VERSIONS = {"1.16.5": 2586, "1.17.1": 2730, "1.18.2": 2975, "1.19.2": 3120, "1.19.4": 3337, "1.20.1": 3465,
                 "1.20.2": 3578, "1.20.4": 3700, "1.20.6": 3839, "1.21": 3953, "1.21.1": 3955, "1.21.3": 4082,
                 "1.21.4": 4189, "1.21.5": 4325}


def data_version(mc):
    """Schematic DataVersion for a game version (None = BlockForge's default, which newer games accept)."""
    return DATA_VERSIONS.get(mc or "")


def build_opts(settings=None, use_mods=None):
    """(pack index or None, target version, options for placement.process / sandbox.run)."""
    settings = settings or store.load_settings()
    if use_mods is None:
        use_mods = settings.get("use_mods", True)
    pack = load_index(settings["active_pack"]) if use_mods and settings.get("active_pack") else None
    version = (pack or {}).get("mc") or settings.get("target_version") or "1.21.1"
    return pack, version, {"pack": pack, "version": version}


def register_pack(idx):
    """Remember a scanned pack in settings (and make it the active one if none is)."""
    s = store.load_settings()
    packs = [p for p in s.get("modpacks", []) if p.get("id") != idx["id"]]
    packs.append({"id": idx["id"], "name": idx["name"], "path": idx["path"]})
    upd = {"modpacks": packs}
    if not s.get("active_pack"):
        upd["active_pack"] = idx["id"]
    store.save_settings(upd)


def forget_pack(pid):
    s = store.load_settings()
    upd = {"modpacks": [p for p in s.get("modpacks", []) if p.get("id") != pid]}
    if s.get("active_pack") == pid:
        upd["active_pack"] = upd["modpacks"][0]["id"] if upd["modpacks"] else None
    store.save_settings(upd)
    try:
        os.remove(pack_file(pid))
    except OSError:
        pass


def list_packs():
    out = []
    for p in store.load_settings().get("modpacks", []):
        idx = load_index(p["id"])
        if idx:
            out.append(summary(idx))
    return out
