"""Check GitHub for a newer BlockForge release, download its installer and run it."""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

from . import store
from .version import GITHUB_REPO, VERSION

API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_cache = {"t": 0, "data": None}


class UpdateError(Exception):
    pass


def _ver(s):
    nums = [int(n) for n in re.findall(r"\d+", s or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": f"BlockForge/{VERSION}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def check(force=False):
    if not force and _cache["data"] and time.time() - _cache["t"] < 600:
        return _cache["data"]
    try:
        with _get(API) as r:
            rel = json.load(r)
    except Exception as e:                           # noqa: BLE001
        raise UpdateError(f"Couldn't reach GitHub to check for updates ({e}).")
    latest = rel.get("tag_name", "")
    asset = next((a for a in rel.get("assets", []) if re.fullmatch(r"BlockForge-[\d.]+\.msi", a.get("name", ""))), None)
    data = {
        "current": VERSION, "latest": latest.lstrip("v"), "available": _ver(latest) > _ver(VERSION) and bool(asset),
        "notes": (rel.get("body") or "")[:4000], "page": rel.get("html_url"),
        "asset": asset and {"name": asset["name"], "size": asset["size"], "url": asset["browser_download_url"],
                            "digest": asset.get("digest")},
        "installed_app": bool(getattr(sys, "frozen", False)),
    }
    _cache.update(t=time.time(), data=data)
    return data


def install(log=print):
    """Download the new MSI, check it, start the installer and close BlockForge so files aren't in use."""
    info = check(force=True)
    if not info["available"]:
        raise UpdateError(f"You already have the latest version ({VERSION}).")
    if not info["installed_app"]:
        raise UpdateError("You're running BlockForge from its source code, so update with git instead "
                          "(or install the MSI from the release page).")
    a = info["asset"]
    if not a["url"].startswith(f"https://github.com/{GITHUB_REPO}/releases/download/"):
        raise UpdateError("The update file isn't hosted on BlockForge's GitHub releases, so it wasn't downloaded.")
    folder = os.path.join(store.DATA, "updates")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, a["name"])
    log(f"Downloading BlockForge {info['latest']} ({a['size'] / 1e6:.0f} MB)...")
    h, done, last = hashlib.sha256(), 0, 0
    with _get(a["url"], timeout=60) as r, open(path + ".part", "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            pct = int(100 * done / max(1, a["size"]))
            if pct >= last + 10:
                last = pct - pct % 10
                log(f"Downloading... {last}%")
    if done != a["size"]:
        os.remove(path + ".part")
        raise UpdateError("The download was incomplete. Please try again.")
    digest = (a.get("digest") or "").lower()
    if digest.startswith("sha256:") and digest[7:] != h.hexdigest():
        os.remove(path + ".part")
        raise UpdateError("The downloaded installer didn't match GitHub's checksum, so it wasn't run.")
    os.replace(path + ".part", path)
    log("Starting the installer. BlockForge will close and reopen when it's done.")
    exe = sys.executable                             # ...\BlockForge.exe in the installed app
    # Wait for this app to exit, install quietly (never restarting the PC), then reopen BlockForge.
    run_update(path, exe)
    return {"ok": True, "version": info["latest"]}


def run_update(msi_path, exe):
    """Wait for BlockForge to exit, install the MSI quietly (never restarting the PC), then reopen BlockForge.
    The steps go in a .cmd file: passing them inline lets Python's argument quoting mangle the paths."""
    script = os.path.join(os.path.dirname(msi_path), "run_update.cmd")
    with open(script, "w", encoding="utf-8") as f:
        f.write("@echo off\r\n"
                "ping -n 4 127.0.0.1 >nul\r\n"
                f'msiexec /i "{msi_path}" /passive /norestart\r\n'
                f'start "" "{exe}"\r\n')
    subprocess.Popen(["cmd", "/c", script], creationflags=0x00000200 | 0x08000000,  # own group, no window
                     close_fds=True, cwd=os.path.dirname(msi_path))
