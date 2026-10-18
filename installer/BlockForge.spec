# PyInstaller spec: builds dist/BlockForge/ with BlockForge.exe (window) and blockforge-cli.exe (helper).
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP = os.path.join(ROOT, "blockforge")
ICON = os.path.join(APP, "static", "icon.ico")

a = Analysis(
    [os.path.join(APP, "app_main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(APP, "static"), "blockforge/static")],
    hiddenimports=[
        "blockforge.server", "blockforge.mcp_server", "blockforge._runner", "blockforge.buildkit",
        "blockforge.engine", "blockforge.exporters", "blockforge.prompts", "blockforge.sandbox", "blockforge.store",
        "blockforge.nbt", "colorsys", "itertools", "functools", "collections", "anthropic",
        "webview", "webview.platforms.edgechromium", "webview.platforms.winforms",
    ],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="BlockForge", icon=ICON, console=False,
          version=os.path.join(SPECPATH, "version_info.txt"))
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="blockforge-cli", icon=ICON, console=True,
          version=os.path.join(SPECPATH, "version_info.txt"))

COLLECT(gui, cli, a.binaries, a.datas, name="BlockForge")
