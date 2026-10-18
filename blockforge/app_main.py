"""BlockForge entry point.
  BlockForge.exe                     open the app window
  blockforge-cli.exe --mcp           Claude Code link (MCP server over stdio)
  blockforge-cli.exe --run-script    run one build script from stdin (used by the sandbox)
"""
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"


def port_in_use():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def is_blockforge():
    import urllib.request
    try:
        with urllib.request.urlopen(URL + "/api/builds", timeout=2) as r:
            return r.status == 200
    except Exception:                                # noqa: BLE001
        return False


class WindowApi:
    """Called from the page as window.pywebview.api.* - native Save As dialogs."""
    _window = None

    def _ask_path(self, filename, kind):
        import webview
        dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        start = os.path.join(os.path.expanduser("~"), "Downloads")
        res = self._window.create_file_dialog(dialog, directory=start, save_filename=filename,
                                             file_types=(f"{kind} (*{os.path.splitext(filename)[1]})",))
        if isinstance(res, (list, tuple)):
            res = res[0] if res else None
        return res

    def save_export(self, build_id, fmt):
        import shutil
        from blockforge import store
        src = store.export_path(build_id, fmt)
        dest = self._ask_path(os.path.basename(src), "Schematic")
        if not dest:
            return None
        shutil.copy(src, dest)
        return dest

    def save_image(self, filename, data_url):
        import base64
        dest = self._ask_path(filename, "PNG image")
        if not dest:
            return None
        with open(dest, "wb") as f:
            f.write(base64.b64decode(data_url.split(",", 1)[1]))
        return dest


def run_gui():
    from blockforge import store
    if sys.stdout is None:                           # windowed exe: keep logs in a file
        sys.stdout = sys.stderr = open(os.path.join(store.DATA, "blockforge.log"), "a", buffering=1, encoding="utf-8")
    if not port_in_use():
        from blockforge import server
        threading.Thread(target=server.main, daemon=True).start()
        for _ in range(100):
            if port_in_use():
                break
            time.sleep(0.05)
    elif not is_blockforge():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"Another program is using port {PORT}, so BlockForge can't start.",
                                         "BlockForge", 0x10)
        return

    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    api = WindowApi()
    api._window = webview.create_window("BlockForge", URL, width=1440, height=900, min_size=(900, 600),
                                       background_color="#0f1115", text_select=True, js_api=api)
    webview.start(private_mode=False, storage_path=os.path.join(store.DATA, "webview"))


def main():
    args = sys.argv[1:]
    if "--mcp" in args:
        from blockforge import mcp_server
        mcp_server.main()
    elif "--run-script" in args:
        from blockforge import _runner
        _runner.main()
    else:
        run_gui()


if __name__ == "__main__":
    main()
