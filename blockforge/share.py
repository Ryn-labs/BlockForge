"""3D preview links anyone can open.

The whole build is packed into the link itself (after the #, so it never reaches any server):
  https://ryn-labs.github.io/BlockForge/view/#1<data>

<data> is base64url(deflate-raw(payload)), and payload is:
  varint W, H, L
  varint title length, title (utf-8)
  varint palette count, then per entry: varint length, block state (utf-8, "minecraft:" dropped)
  runs over the volume in y, z, x order: varint value (0 = air, else palette index + 1), varint run length
  4 bytes CRC-32 (little endian) of everything before it, so a link damaged in copying is caught
The viewer page (docs/view in the GitHub repo) unpacks it in the browser.
"""
import base64
import json
import zlib

VIEWER = "https://ryn-labs.github.io/BlockForge/view/"
CHAT_LIMIT = 8000          # longer links are too long to paste into a chat reliably
MAX_LINK = 2_000_000       # browsers stop around here


def _varint(n, out):
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return


def pack(d, title=""):
    W, H, L = d["size"]
    pal = d["palette"]
    f = d["blocks"]
    out = bytearray()
    for v in (W, H, L):
        _varint(v, out)
    t = (title or "")[:120].encode("utf-8")
    _varint(len(t), out)
    out += t
    _varint(len(pal), out)
    for st in pal:
        s = (st[10:] if st.startswith("minecraft:") else st).encode("utf-8")
        _varint(len(s), out)
        out += s
    # sorted (cell index, value) pairs, then runs: no dense pass over a mostly empty volume
    cells = sorted(((f[i + 1] * L + f[i + 2]) * W + f[i], f[i + 3] + 1) for i in range(0, len(f), 4)
                   if 0 <= f[i] < W and 0 <= f[i + 1] < H and 0 <= f[i + 2] < L)
    pos, run_v, run_n = 0, None, 0

    def emit(v, n):
        nonlocal run_v, run_n
        if n <= 0:
            return
        if v == run_v:
            run_n += n
        else:
            if run_n:
                _varint(run_v, out)
                _varint(run_n, out)
            run_v, run_n = v, n

    for idx, v in cells:
        if idx < pos:                               # duplicate position: keep the first
            continue
        emit(0, idx - pos)
        emit(v, 1)
        pos = idx + 1
    emit(0, W * H * L - pos)
    if run_n:
        _varint(run_v, out)
        _varint(run_n, out)
    out += (zlib.crc32(out) & 0xFFFFFFFF).to_bytes(4, "little")
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    z = c.compress(bytes(out)) + c.flush()
    return base64.urlsafe_b64encode(z).rstrip(b"=").decode("ascii")


def link(d, title=""):
    return VIEWER + "#1" + pack(d, title)


def chat_text(bid):
    """What Claude should pass on to the user after making or changing a build."""
    try:
        r = best_link(bid)
    except (OSError, ValueError, KeyError) as e:
        return f"\n\n(No 3D preview link: {e})"
    url = r["url"]
    if not url:
        return "\n\n" + r["note"]
    if len(url) <= CHAT_LIMIT:
        return ("\n\n3D preview anyone can open in a browser (rotate, zoom, see inside layer by layer). Always give the "
                f"user this exact link, unchanged, as a markdown link:\n{url}")
    return (f"\n\nThis build is too big for a chat link ({len(url):,} characters). Tell the user to press Share in the "
            f"BlockForge app to copy its 3D preview link (or add a GitHub token in Settings for short links), "
            f"or to drop the .schem file on {VIEWER}")


def unpack(data):
    """Inverse of pack, for tests: returns (dict, title)."""
    raw = zlib.decompress(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)), -15)
    body, crc = raw[:-4], int.from_bytes(raw[-4:], "little")
    if zlib.crc32(body) & 0xFFFFFFFF != crc:
        raise ValueError("damaged link")
    p = 0

    def rv():
        nonlocal p
        n = s = 0
        while True:
            b = body[p]
            p += 1
            n |= (b & 0x7F) << s
            s += 7
            if not b & 0x80:
                return n

    W, H, L = rv(), rv(), rv()
    n = rv()
    title = body[p:p + n].decode("utf-8")
    p += n
    pal = []
    for _ in range(rv()):
        n = rv()
        s = body[p:p + n].decode("utf-8")
        p += n
        pal.append(s if ":" in s else "minecraft:" + s)
    blocks, i = [], 0
    while p < len(body):
        v, r = rv(), rv()
        if v:
            for k in range(i, i + r):
                x, z, y = k % W, (k // W) % L, k // (W * L)
                blocks += [x, y, z, v - 1]
        i += r
    return {"size": [W, H, L], "palette": pal, "blocks": blocks}, title


# ------------------------------------------------------------------ short links: a secret gist on the user's GitHub
API = "https://api.github.com"


def _github(method, path, token, body=None, timeout=20):
    import urllib.request
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "BlockForge"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def github_login(token):
    """Check a token: returns the GitHub username, or raises ValueError with a plain reason."""
    import urllib.error
    try:
        return _github("GET", "/user", token)["login"]
    except urllib.error.HTTPError as e:
        raise ValueError("GitHub didn't accept that token." if e.code in (401, 403) else f"GitHub said {e.code}.") from None
    except OSError as e:
        raise ValueError(f"Couldn't reach GitHub: {e}") from None


def _gist_settings():
    from blockforge import store
    s = store.load_settings().get("share") or {}
    return s.get("github_token") or "", s.get("github_user") or ""


def short_link(bid, packed):
    """Upload the packed build as a secret gist (once per build) and return the short link, or None."""
    from blockforge import store
    token, user = _gist_settings()
    if not token or not user:
        return None
    m = store.get_meta(bid)
    gid = m.get("share_gist")
    if not gid or m.get("share_gist_v") != packed[:64] + str(len(packed)):
        title = (m.get("title") or "build")[:80]
        r = _github("POST", "/gists", token, {"description": f"BlockForge build: {title}", "public": False,
                                              "files": {"blockforge-build.txt": {"content": "1" + packed}}})
        gid = r["id"]
        store.update_meta(bid, share_gist=gid, share_gist_v=packed[:64] + str(len(packed)))
    return f"{VIEWER}#g{user}/{gid}"


def best_link(bid):
    """{url, short, note}: the short gist link when set up, else the packed link."""
    from blockforge import store
    m = store.get_meta(bid)
    packed = pack(json.loads(store.get_blocks_raw(bid)), m.get("title") or "")
    try:
        s = short_link(bid, packed)
        if s:
            return {"url": s, "short": True, "note": ""}
    except Exception as e:                           # noqa: BLE001  (offline, token revoked...): fall back
        note = f"Short link failed ({e}), so this is the full link."
    else:
        note = ""
    url = VIEWER + "#1" + packed
    if len(url) > MAX_LINK:
        return {"url": None, "short": False, "note": f"Too big for a link. Drop its .schem file on {VIEWER} instead."}
    return {"url": url, "short": False, "note": note}
