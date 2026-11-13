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

PORT = int(os.environ.get("BLOCKFORGE_PORT", "8765"))
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

    def pick_folder(self):
        import webview
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = self._window.create_file_dialog(dialog, directory=os.path.expanduser("~"))
        if isinstance(res, (list, tuple)):
            res = res[0] if res else None
        return res

    def save_image(self, filename, data_url):
        import base64
        dest = self._ask_path(filename, "PNG image")
        if not dest:
            return None
        with open(dest, "wb") as f:
            f.write(base64.b64decode(data_url.split(",", 1)[1]))
        return dest


def focus_running():
    """BlockForge is already open: bring its window to the front instead of opening a second one."""
    import urllib.request
    try:
        req = urllib.request.Request(URL + "/api/app/show", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:                                # noqa: BLE001
        return False


def window_hooks(window):
    """What the server (and so Claude, through the MCP server) may do with the window."""
    def show():
        try:
            window.restore()
        except Exception:                            # noqa: BLE001
            pass
        window.show()
        try:                                         # Windows won't let a background app steal focus; a brief on-top does it
            window.on_top = True
            time.sleep(0.3)
            window.on_top = False
        except Exception:                            # noqa: BLE001
            pass

    return {"show": show, "quit": window.destroy, "js": window.evaluate_js}


def run_gui():
    from blockforge import store
    if sys.stdout is None:                           # windowed exe: keep logs in a file
        sys.stdout = sys.stderr = open(os.path.join(store.DATA, "blockforge.log"), "a", buffering=1, encoding="utf-8")
    own_server = not port_in_use()
    if own_server:
        from blockforge import server
        threading.Thread(target=server.main, daemon=True).start()
        for _ in range(100):
            if port_in_use():
                break
            time.sleep(0.05)
    elif is_blockforge():
        if focus_running():
            return
    else:
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
    if own_server:
        server.APP.update(window_hooks(api._window))
    webview.start(private_mode=False, storage_path=os.path.join(store.DATA, "webview"))
    try:                                             # window closed: don't leave the hidden test server running
        from blockforge import testlab
        testlab.stop()
    except Exception:                                # noqa: BLE001
        pass


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
