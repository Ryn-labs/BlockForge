# PyInstaller spec: builds dist/BlockForge/ with BlockForge.exe (window) and blockforge-cli.exe (helper).
import os
import re

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP = os.path.join(ROOT, "blockforge")
ICON = os.path.join(APP, "static", "icon.ico")
VERSION = re.search(r'VERSION = "([0-9.]+)"', open(os.path.join(APP, "version.py"), encoding="utf-8").read()).group(1)
_t = ", ".join((VERSION.split(".") + ["0"] * 4)[:4])
VERSION_FILE = os.path.join(SPECPATH, "build", "version_info.generated.txt")
os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
with open(VERSION_FILE, "w", encoding="utf-8") as f:
    f.write(open(os.path.join(SPECPATH, "version_info.txt"), encoding="utf-8").read()
            .replace("__TUPLE__", _t).replace("__VERSION__", VERSION))
VOICE = os.path.join(APP, "voice")
if not os.path.isfile(os.path.join(VOICE, "piper", "piper.exe")):
    raise SystemExit("HD voice files are missing - run: python installer/get_voice.py")

a = Analysis(
    [os.path.join(APP, "app_main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(APP, "static"), "blockforge/static"), (VOICE, "blockforge/voice")],
    hiddenimports=[
        "blockforge.server", "blockforge.mcp_server", "blockforge._runner", "blockforge.buildkit",
        "blockforge.engine", "blockforge.exporters", "blockforge.prompts", "blockforge.sandbox", "blockforge.store",
        "blockforge.nbt", "blockforge.tts", "blockforge.updater", "blockforge.version", "blockforge.voices", "blockforge.eleven", "blockforge.redstone", "blockforge.mods", "blockforge.placement", "blockforge.learn", "blockforge.pixelart", "blockforge.texpalette", "blockforge.modules", "blockforge.edits", "blockforge.describe", "blockforge.testlab", "blockforge.testkit", "colorsys", "itertools", "functools", "collections", "anthropic",
        "webview", "webview.platforms.edgechromium", "webview.platforms.winforms",
    ],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="BlockForge", icon=ICON, console=False,
          version=VERSION_FILE)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="blockforge-cli", icon=ICON, console=True,
          version=VERSION_FILE)

COLLECT(gui, cli, a.binaries, a.datas, name="BlockForge")
