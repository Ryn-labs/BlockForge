"""Tiny NBT writer/reader (big-endian for Java, little-endian for Bedrock .mcstructure)."""
import gzip
import io
import struct

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


class Writer:
    def __init__(self, little=False):
        self.e = "<" if little else ">"
        self.out = bytearray()

    def p(self, fmt, *v):
        self.out += struct.pack(self.e + fmt, *v)

    def s(self, txt):
        b = txt.encode("utf-8")
        self.p("H", len(b))
        self.out += b

    def val(self, t, v):
        if t == BYTE:
            self.p("b", v)
        elif t == SHORT:
            self.p("h", v)
        elif t == INT:
            self.p("i", v)
        elif t == LONG:
            self.p("q", v)
        elif t == FLOAT:
            self.p("f", v)
        elif t == DOUBLE:
            self.p("d", v)
        elif t == BYTE_ARRAY:
            self.p("i", len(v))
            self.out += bytes(v)
        elif t == STRING:
            self.s(v)
        elif t == LIST:
            et, items = v
            self.p("bi", et if items else (et or END), len(items))
            for it in items:
                self.val(et, it)
        elif t == COMPOUND:
            for name, (ct, cv) in v.items():
                self.p("b", ct)
                self.s(name)
                self.val(ct, cv)
            self.p("b", 0)
        elif t == INT_ARRAY:
            self.p("i%di" % len(v), len(v), *v)
        elif t == LONG_ARRAY:
            self.p("i%dq" % len(v), len(v), *v)
        else:
            raise ValueError(t)


def dumps(root_name, compound, little=False):
    w = Writer(little)
    w.p("b", COMPOUND)
    w.s(root_name)
    w.val(COMPOUND, compound)
    return bytes(w.out)


def write(path, root_name, compound, little=False, compress=True):
    data = dumps(root_name, compound, little)
    if compress:
        with gzip.open(path, "wb") as f:
            f.write(data)
    else:
        with open(path, "wb") as f:
            f.write(data)


# ------------------------------------------------------------------ reader (plain python values)
class _Reader:
    def __init__(self, data):
        self.b = io.BytesIO(data)

    def u(self, fmt):
        n = struct.calcsize(">" + fmt)
        return struct.unpack(">" + fmt, self.b.read(n))

    def s(self):
        (n,) = self.u("H")
        return self.b.read(n).decode("utf-8", "replace")

    def val(self, t):
        if t == BYTE:
            return self.u("b")[0]
        if t == SHORT:
            return self.u("h")[0]
        if t == INT:
            return self.u("i")[0]
        if t == LONG:
            return self.u("q")[0]
        if t == FLOAT:
            return self.u("f")[0]
        if t == DOUBLE:
            return self.u("d")[0]
        if t == BYTE_ARRAY:
            (n,) = self.u("i")
            return self.b.read(n)
        if t == STRING:
            return self.s()
        if t == LIST:
            et, n = self.u("bi")
            return [self.val(et) for _ in range(n)]
        if t == COMPOUND:
            d = {}
            while True:
                (ct,) = self.u("b")
                if ct == END:
                    return d
                key = self.s()
                d[key] = self.val(ct)
        if t == INT_ARRAY:
            (n,) = self.u("i")
            return list(self.u("%di" % n))
        if t == LONG_ARRAY:
            (n,) = self.u("i")
            return list(self.u("%dq" % n))
        raise ValueError(t)


def loads(data):
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    r = _Reader(data)
    (t,) = r.u("b")
    r.s()
    return r.val(t)
