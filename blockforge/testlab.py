"""BlockForge's test lab: a hidden Minecraft server where redstone builds and farms are proven before the player
sees them.

The player sets it up once (Settings -> Test lab): BlockForge downloads Mojang's official server for their game
version and checks its SHA-1, uses a Java their launchers already installed, and only writes eula=true after the
player has accepted Mojang's EULA themselves. The server runs without a window, listens only on 127.0.0.1 and
is controlled over RCON. A test places the build in a fresh spot of a flat world, runs the build's test steps at high
speed (/tick sprint) and reads the results back as text."""
import glob
import hashlib
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import threading
import time
import urllib.request

from . import exporters, store

LAB = os.path.join(store.DATA, "testlab")
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
GAME_PORT, RCON_PORT = 25570, 25576
IDLE_STOP = 15 * 60                     # stop the server after this long without a test
_lock = threading.RLock()
_proc = {"p": None, "version": None, "last": 0.0, "adopted": False}


class LabError(Exception):
    pass


def _dir(version):
    return os.path.join(LAB, re.sub(r"[^0-9A-Za-z._-]", "_", version))


# ---------------------------------------------------------------- Java
def _java_major(exe):
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out.stderr + out.stdout)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major


def java_candidates():
    env = os.environ
    appdata, local, home = env.get("APPDATA", ""), env.get("LOCALAPPDATA", ""), os.path.expanduser("~")
    pf86 = env.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pats = [os.path.join(appdata, "ModrinthApp", "meta", "java_versions", "*", "bin", "java.exe"),
            os.path.join(appdata, "com.modrinth.theseus", "meta", "java_versions", "*", "bin", "java.exe"),
            os.path.join(local, "Packages", "Microsoft.4297127D64EC6_8wekyb3d8bbwe", "LocalCache", "Local", "runtime", "*", "*", "*", "bin", "java.exe"),
            os.path.join(pf86, "Minecraft Launcher", "runtime", "*", "*", "*", "bin", "java.exe"),
            os.path.join(appdata, ".minecraft", "runtime", "*", "*", "*", "bin", "java.exe"),
            os.path.join(home, "curseforge", "minecraft", "Install", "runtime", "*", "*", "*", "bin", "java.exe"),
            os.path.join(appdata, "PrismLauncher", "java", "*", "bin", "java.exe"),
            os.path.join(appdata, "ATLauncher", "runtimes", "*", "bin", "java.exe"),
            os.path.join(env.get("ProgramFiles", r"C:\Program Files"), "*", "*", "bin", "java.exe")]
    seen = []
    for pat in pats:
        for exe in glob.glob(pat):
            if exe not in seen:
                seen.append(exe)
    return seen


def find_java(major):
    """The best installed Java for `major` (an exact match, else the closest newer one)."""
    best = None
    for exe in java_candidates():
        m = _java_major(exe)
        if m is None or m < major:
            continue
        if best is None or m < best[1]:
            best = (exe, m)
        if m == major:
            break
    return best


# ---------------------------------------------------------------- setup
def status():
    s = store.load_settings()
    v = s.get("testlab_version")
    d = _dir(v) if v else None
    ready = bool(v and s.get("testlab_eula") and os.path.isfile(os.path.join(d, "server.jar")))
    info = {}
    if d and os.path.isfile(os.path.join(d, "lab.json")):
        with open(os.path.join(d, "lab.json"), encoding="utf-8") as f:
            info = json.load(f)
    return {"ready": ready, "enabled": bool(s.get("testlab_enabled")) and ready, "version": v,
            "java": info.get("java"), "java_major": info.get("java_major"),
            "running": _running(), "tests_run": info.get("tests", 0)}


def setup(version, accept_eula, log=print):
    """Download + verify Mojang's server for `version`, pick a Java, write the lab config. Needs accept_eula=True."""
    if not accept_eula:
        raise LabError("You need to accept Mojang's EULA to run a Minecraft server.")
    version = str(version).strip()
    log("Looking up Minecraft " + version + " on Mojang's servers...")
    man = json.load(urllib.request.urlopen(MANIFEST, timeout=30))
    entry = next((e for e in man["versions"] if e["id"] == version), None)
    if not entry:
        raise LabError(f"Mojang has no version called {version}. The newest release is {man['latest']['release']}.")
    info = json.load(urllib.request.urlopen(entry["url"], timeout=30))
    srv = (info.get("downloads") or {}).get("server")
    if not srv:
        raise LabError(f"Mojang doesn't publish a server for {version}.")
    need = int((info.get("javaVersion") or {}).get("majorVersion") or 17)
    log(f"Finding Java {need} (from your launchers)...")
    java = find_java(need)
    if not java:
        raise LabError(f"Minecraft {version} needs Java {need}, and none was found. Open Minecraft {version} once in your "
                       "launcher (it installs the right Java), then try again.")
    d = _dir(version)
    os.makedirs(d, exist_ok=True)
    jar = os.path.join(d, "server.jar")
    if not (os.path.isfile(jar) and _sha1(jar) == srv["sha1"]):
        log(f"Downloading the official server ({srv['size'] / 1e6:.0f} MB) from Mojang...")
        data = urllib.request.urlopen(srv["url"], timeout=300).read()
        if hashlib.sha1(data).hexdigest() != srv["sha1"]:
            raise LabError("The download was damaged (its checksum didn't match). Try again.")
        with open(jar + ".part", "wb") as f:
            f.write(data)
        os.replace(jar + ".part", jar)
    log("Checksum verified. Writing the test world settings...")
    with open(os.path.join(d, "eula.txt"), "w", encoding="utf-8") as f:
        f.write("# Accepted by the player in BlockForge (Settings -> Test lab), see https://aka.ms/MinecraftEULA\neula=true\n")
    pw_file = os.path.join(d, "rcon.txt")
    if not os.path.isfile(pw_file):
        with open(pw_file, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(16))
    with open(pw_file, encoding="utf-8") as f:
        pw = f.read().strip()
    props = {"level-name": "world", "level-type": "minecraft\\:flat", "gamemode": "creative", "difficulty": "normal",
             "spawn-monsters": "false", "spawn-animals": "false", "generate-structures": "false", "online-mode": "false",
             "server-ip": "127.0.0.1", "server-port": GAME_PORT, "enable-rcon": "true", "rcon.port": RCON_PORT,
             "rcon.password": pw, "broadcast-rcon-to-ops": "false", "max-players": 1, "view-distance": 4,
             "simulation-distance": 4, "spawn-protection": 0, "motd": "BlockForge test lab", "enable-query": "false"}
    with open(os.path.join(d, "server.properties"), "w", encoding="utf-8") as f:
        f.write("".join(f"{k}={v}\n" for k, v in props.items()))
    meta = {"version": version, "java": java[0], "java_major": java[1], "sha1": srv["sha1"], "tests": 0}
    with open(os.path.join(d, "lab.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    store.save_settings({"testlab_version": version, "testlab_eula": True, "testlab_enabled": True})
    log("Starting the test server for the first time (about 20 seconds)...")
    start(log)
    log("Test lab is ready.")
    return status()


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- server process
def _lab_meta():
    v = store.load_settings().get("testlab_version")
    if not v:
        raise LabError("The test lab isn't set up yet (Settings -> Test lab).")
    d = _dir(v)
    with open(os.path.join(d, "lab.json"), encoding="utf-8") as f:
        return v, d, json.load(f)


def _running():
    return bool((_proc["p"] and _proc["p"].poll() is None) or _proc["adopted"])


def start(log=print):
    with _lock:
        if _proc["p"] and _proc["p"].poll() is None:
            return
        v, d, meta = _lab_meta()
        try:                                             # a lab server left running (BlockForge was closed abruptly)
            rcon(["list"])
            _proc.update(adopted=True, version=v, last=time.time())
            threading.Thread(target=_idle_watch, daemon=True).start()
            return
        except (OSError, LabError):
            _proc["adopted"] = False
        logf = open(os.path.join(d, "console.log"), "w", encoding="utf-8", errors="replace")
        _proc["p"] = subprocess.Popen([meta["java"], "-Xms512M", "-Xmx2G", "-jar", "server.jar", "nogui"], cwd=d,
                                      stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _proc["version"], _proc["last"] = v, time.time()
        t0 = time.time()
        while time.time() - t0 < 180:
            if _proc["p"].poll() is not None:
                raise LabError("The test server stopped while starting. See " + os.path.join(d, "console.log"))
            try:
                with open(os.path.join(d, "console.log"), encoding="utf-8", errors="replace") as f:
                    if "RCON running" in f.read():
                        break
            except OSError:
                pass
            time.sleep(1)
        else:
            stop()
            raise LabError("The test server took too long to start.")
        rcon(["gamerule doDaylightCycle true", "gamerule doWeatherCycle false", "gamerule doTraderSpawning false",
              "gamerule doPatrolSpawning false", "gamerule doInsomnia false", "difficulty normal", "weather clear"])
        threading.Thread(target=_idle_watch, daemon=True).start()


def stop():
    with _lock:
        p = _proc["p"]
        if _proc["adopted"] and not p:
            try:
                rcon(["stop"])
            except (OSError, LabError):
                pass
            _proc["adopted"] = False
        if p and p.poll() is None:
            try:
                rcon(["stop"])
                p.wait(30)
            except Exception:                           # noqa: BLE001
                p.kill()
        _proc["p"] = None


def _idle_watch():
    while _running():
        time.sleep(30)
        if time.time() - _proc["last"] > IDLE_STOP:
            stop()
            return


# ---------------------------------------------------------------- RCON
def _send(s, rid, kind, body):
    data = struct.pack("<ii", rid, kind) + body.encode("utf-8") + b"\x00\x00"
    s.sendall(struct.pack("<i", len(data)) + data)


def _recv(s):
    head = b""
    while len(head) < 4:
        c = s.recv(4 - len(head))
        if not c:
            raise LabError("the test server closed the connection")
        head += c
    n = struct.unpack("<i", head)[0]
    data = b""
    while len(data) < n:
        data += s.recv(n - len(data))
    return struct.unpack("<i", data[:4])[0], data[8:-2].decode("utf-8", "replace")


def rcon(commands):
    _, d, _ = _lab_meta()
    with open(os.path.join(d, "rcon.txt"), encoding="utf-8") as f:
        pw = f.read().strip()
    with socket.create_connection(("127.0.0.1", RCON_PORT), timeout=60) as s:
        _send(s, 1, 3, pw)
        if _recv(s)[0] == -1:
            raise LabError("couldn't log in to the test server")
        out = []
        for i, c in enumerate(commands, 2):
            _send(s, i, 2, c)
            out.append(_recv(s)[1])
        return out


def _run_ticks(n):
    rcon([f"tick sprint {int(n)}"])
    t0 = time.time()
    while time.time() - t0 < max(60, n / 100):
        time.sleep(0.5)
        q = rcon(["tick query"])[0].lower()
        if "sprint" not in q or "running normally" in q:
            return
    rcon(["tick sprint stop"])


# ---------------------------------------------------------------- running a test
def _stack(item):
    from . import modules
    n = item.split(":", 1)[1]
    if modules.UNSTACKABLE.search(n) and n != "bucket":
        return 1
    return 16 if modules.STACK16.match(n) else 64


def _items(pos):
    body = rcon([f"data get block {pos} Items"])[0]
    found = {}
    for m in re.finditer(r'count: (\d+)[^}]*?id: "([a-z0-9_:.-]+)"', body):
        found[m.group(2)] = found.get(m.group(2), 0) + int(m.group(1))
    return found, body


def _pretty(i):
    return i.split(":", 1)[-1].replace("_", " ")


def run_test(blocks, tiles, entities, steps, log=print, label="build"):
    """Place the build in the lab and run its test steps. Returns {'passed', 'results': [...], 'report'}."""
    if not steps or not any(s["do"].startswith("expect") for s in steps):
        return {"passed": None, "results": [], "report": "No test steps with a check, so nothing was proven."}
    with _lock:
        start(log)
        v, d, meta = _lab_meta()
        _proc["last"] = time.time()
        k = int(meta.get("tests", 0)) + 1
        meta["tests"] = k
        with open(os.path.join(d, "lab.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        mn = (min(p[0] for p in blocks), min(p[1] for p in blocks), min(p[2] for p in blocks))
        dct = exporters.to_dict(blocks, tiles, [[x, y, z, e] for x, y, z, e in entities or []])
        W, H, L = dct["size"]
        name = f"bf_t{k}"
        sdir = os.path.join(d, "world", "generated", "minecraft", "structure")
        os.makedirs(sdir, exist_ok=True)
        exporters.write_nbt_structure(os.path.join(sdir, name + ".nbt"), dct, name)
        ox, oy, oz = 2000 + (k % 400) * 160, -60, 2000 + (k // 400) * 160
        at = lambda p: f"{ox + p[0] - mn[0]} {oy + p[1] - mn[1]} {oz + p[2] - mn[2]}"
        cx1, cz1, cx2, cz2 = (ox - 16) >> 4, (oz - 16) >> 4, (ox + W + 16) >> 4, (oz + L + 16) >> 4
        loads = []
        for x in range(cx1, cx2 + 1, 15):
            for z in range(cz1, cz2 + 1, 15):
                loads.append(f"forceload add {x * 16} {z * 16} {min(cx2, x + 14) * 16} {min(cz2, z + 14) * 16}")
        out = rcon(loads + ["reload", f"place template minecraft:{name} {ox} {oy} {oz}"])
        if "Loaded template" not in out[-1]:
            raise LabError("The test server couldn't place the build: " + out[-1][:200])
        log(f"Test lab: placed the {label} in a hidden test world. Running its test...")
        results, passed = [], True
        kinds = sorted({e["id"] for *_, e in entities or []})
        if kinds:
            placed = []
            for kind in kinds:
                r = rcon([f"execute if entity @e[type={kind},x={ox - 2},y={oy - 2},z={oz - 2},dx={W + 4},dy={H + 4},dz={L + 4}]"])[0]
                m = re.search(r"count: (\d+)", r, re.I)
                placed.append(f"{m.group(1) if m else 0} {_pretty(kind)}")
            results.append({"ok": None, "text": "Mobs placed: " + ", ".join(placed)})
        next_slot = {}                                   # several puts into one chest fill it slot after slot
        for st in steps:
            do = st["do"]
            if do == "note":
                results.append({"ok": None, "text": st["text"]})
            elif do == "put":
                left, slot = st["count"], next_slot.get(tuple(st["pos"]), 0)
                size = _stack(st["item"])
                cmds = []
                while left > 0 and slot < 54:
                    n = min(size, left)
                    cmds.append(f"item replace block {at(st['pos'])} container.{slot} with {st['item']} {n}")
                    left -= n
                    slot += 1
                next_slot[tuple(st["pos"])] = slot
                res = rcon(cmds) if cmds else ["no free slot left in that container"]
                ok = all("Replaced" in r for r in res)
                results.append({"ok": None if ok else False, "text": f"Put {st['count']} {_pretty(st['item'])} in at {tuple(st['pos'])}"
                                + ("" if ok else f": {res[0][:120]}")})
                passed &= ok
            elif do == "press":
                st0 = blocks.get(tuple(st["pos"]), "")
                if "lever" not in st0 and "button" not in st0:
                    results.append({"ok": False, "text": f"There is no lever or button at {tuple(st['pos'])} to press"})
                    passed = False
                    continue
                on = re.sub(r"powered=(true|false)", "powered=true", st0) if "powered=" in st0 else st0.rstrip("]") + (",powered=true]" if "[" in st0 else "[powered=true]")
                rcon([f"setblock {at(st['pos'])} {on}"])
                if "button" in st0:
                    _run_ticks(st["ticks"])
                    rcon([f"setblock {at(st['pos'])} {on.replace('powered=true', 'powered=false')}"])
                results.append({"ok": None, "text": f"Pressed the {_pretty(st0.split('[')[0])} at {tuple(st['pos'])}"})
            elif do == "power":
                rcon([f"setblock {at(st['pos'])} {'minecraft:redstone_block' if st['on'] else 'minecraft:air'}"])
                results.append({"ok": None, "text": ("Powered" if st["on"] else "Unpowered") + f" the circuit at {tuple(st['pos'])}"})
            elif do == "wait":
                _run_ticks(st["ticks"])
                results.append({"ok": None, "text": f"Let {st['ticks'] / 20:.0f} seconds of game time pass"})
            elif do == "expect_items":
                found, _ = _items(at(st["pos"]))
                n = found.get(st["item"], 0)
                ok = n >= st["at_least"] and (st["at_most"] is None or n <= st["at_most"])
                passed &= ok
                results.append({"ok": ok, "text": f"{_pretty(st['item']).capitalize()} at {tuple(st['pos'])}: {n}"
                                f" (needs {'at least ' + str(st['at_least']) if st['at_most'] is None else str(st['at_least']) + '-' + str(st['at_most'])})"
                                + ("" if ok else f"; that container has {', '.join(f'{c} {_pretty(i)}' for i, c in found.items()) or 'nothing'}")})
            elif do == "expect_block":
                r = rcon([f"execute if block {at(st['pos'])} {st['block'] if ':' in st['block'] else 'minecraft:' + st['block']}"])[0]
                ok = r.startswith("Test passed")
                passed &= ok
                results.append({"ok": ok, "text": f"Block at {tuple(st['pos'])} is {st['block']}: {'yes' if ok else 'no'}"
                                + ("" if ok or "Test failed" in r else f" ({r[:100]})")})
            elif do == "expect_mob":
                b = st["box"]
                x1, y1, z1 = min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5])
                dx, dy, dz = abs(b[3] - b[0]), abs(b[4] - b[1]), abs(b[5] - b[2])
                r = rcon([f"execute if entity @e[type={st['kind']},x={ox + x1 - mn[0]},y={oy + y1 - mn[1]},z={oz + z1 - mn[2]},"
                          f"dx={dx},dy={dy},dz={dz}]"])[0]
                m = re.search(r"count: (\d+)", r, re.I)
                n = int(m.group(1)) if m else 0
                ok = n >= st["at_least"] and (st["at_most"] is None or n <= st["at_most"])
                passed &= ok
                results.append({"ok": ok, "text": f"{_pretty(st['kind']).capitalize()}s in the area: {n} (needs "
                                + (f"at least {st['at_least']}" if st["at_most"] is None else f"{st['at_least']}-{st['at_most']}") + ")"})
        report = _report(results, passed, blocks, tiles, at, mn, ox, oy, oz, W, H, L, entities)
        rcon([cmd.replace("forceload add", "forceload remove") for cmd in loads])
        _proc["last"] = time.time()
        return {"passed": passed, "results": results, "report": report, "version": v}


def _report(results, passed, blocks, tiles, at, mn, ox, oy, oz, W, H, L, entities):
    lines = [("PASSED" if passed else "FAILED") + f" in Minecraft {_proc['version']} (real game rules, run at high speed):"]
    for r in results:
        mark = {True: "OK ", False: "FAIL", None: "   "}[r["ok"]]
        lines.append(f"  [{mark}] {r['text']}")
    if not passed:
        conts = [p for p, s in blocks.items() if re.search(r"(chest|hopper|barrel|dropper|dispenser|furnace|smoker|shulker_box)\b",
                                                          s.split("[")[0])][:25]
        if conts:
            lines.append("What every container held at the end:")
            for p in conts:
                found, _ = _items(at(p))
                lines.append(f"  {blocks[p].split('[')[0].replace('minecraft:', '')} at {p}: "
                             + (", ".join(f"{c} {_pretty(i)}" for i, c in found.items()) or "empty"))
        kinds = sorted({e["id"] for *_, e in entities or []} | {"minecraft:iron_golem", "minecraft:item"})
        mobs = []
        for kind in kinds:
            r = rcon([f"execute if entity @e[type={kind},x={ox - 4},y={oy - 4},z={oz - 4},dx={W + 8},dy={H + 8},dz={L + 8}]"])[0]
            m = re.search(r"count: (\d+)", r, re.I)
            mobs.append(f"{_pretty(kind)}: {m.group(1) if m else 0}")
        lines.append("Mobs / dropped items around the build at the end: " + ", ".join(mobs))
    return "\n".join(lines)
