// Packs a build into a preview link and back. Same format as blockforge/share.py:
//   base64url(deflate-raw( varint W,H,L | title | palette | runs (value, length) over y,z,x | CRC-32 ))
// Everything happens in the browser; the build is after the #, so it never reaches a server.

const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
export function crc32(bytes) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) c = CRC[(c ^ bytes[i]) & 255] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

export function b64urlDecode(s) {
  s = s.replace(/[\s]/g, '').replace(/-/g, '+').replace(/_/g, '/');
  s += '='.repeat((4 - s.length % 4) % 4);
  const bin = atob(s), out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
export function b64urlEncode(bytes) {
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function stream(bytes, s) {
  const out = new Response(new Blob([bytes]).stream().pipeThrough(s));
  return new Uint8Array(await out.arrayBuffer());
}
export const inflateRaw = b => stream(b, new DecompressionStream('deflate-raw'));
export const deflateRaw = b => stream(b, new CompressionStream('deflate-raw'));
export const gunzip = b => stream(b, new DecompressionStream('gzip'));
export const inflate = b => stream(b, new DecompressionStream('deflate'));

export class LinkError extends Error {}

/** "<data>" (the part after "#1") -> { size, palette, blocks (Int32Array x,y,z,p), title } */
export async function unpack(data) {
  let body;
  try { body = await inflateRaw(b64urlDecode(data)); }
  catch { throw new LinkError('This link is damaged: part of it was lost when it was copied. Ask for the link again, or open the schematic file instead.'); }
  if (body.length < 8) throw new LinkError('This link is empty.');
  const crc = (body[body.length - 4] | body[body.length - 3] << 8 | body[body.length - 2] << 16 | body[body.length - 1] << 24) >>> 0;
  body = body.subarray(0, body.length - 4);
  if (crc32(body) !== crc) throw new LinkError('This link is damaged: some characters changed when it was copied. Ask for the link again, or open the schematic file instead.');
  let p = 0;
  const rv = () => { let n = 0, s = 0, b; do { b = body[p++]; n += (b & 0x7F) * 2 ** s; s += 7; } while (b & 0x80); return n; };
  const dec = new TextDecoder();
  const W = rv(), H = rv(), L = rv();
  let n = rv();
  const title = dec.decode(body.subarray(p, p + n)); p += n;
  const palette = [];
  for (let k = rv(); k > 0; k--) { n = rv(); const s = dec.decode(body.subarray(p, p + n)); p += n; palette.push(s.includes(':') ? s : 'minecraft:' + s); }
  // first pass counts blocks so the array is allocated once
  const start = p; let count = 0;
  while (p < body.length) { const v = rv(), r = rv(); if (v) count += r; }
  const blocks = new Int32Array(count * 4);
  p = start; let i = 0, o = 0;
  const WL = W * L;
  while (p < body.length) {
    const v = rv(), r = rv();
    if (v) for (let k = i, e = i + r; k < e; k++) {
      blocks[o++] = k % W; blocks[o++] = Math.floor(k / WL); blocks[o++] = Math.floor(k / W) % L; blocks[o++] = v - 1;
    }
    i += r;
  }
  return { size: [W, H, L], palette, blocks, title };
}

/** { size, palette, blocks } -> "<data>" (put after "#1") */
export async function pack(d, title = '') {
  const [W, H, L] = d.size, f = d.blocks, out = [];
  const wv = n => { do { let b = n % 128; n = Math.floor(n / 128); out.push(n ? b | 0x80 : b); } while (n); };
  const enc = new TextEncoder();
  const str = s => { const b = enc.encode(s); wv(b.length); for (const x of b) out.push(x); };
  wv(W); wv(H); wv(L);
  str(title.slice(0, 120));
  wv(d.palette.length);
  for (const st of d.palette) str(st.startsWith('minecraft:') ? st.slice(10) : st);
  const n = f.length / 4, idx = new Float64Array(n), val = new Uint32Array(n), order = new Uint32Array(n);
  for (let b = 0; b < n; b++) { idx[b] = (f[b * 4 + 1] * L + f[b * 4 + 2]) * W + f[b * 4]; val[b] = f[b * 4 + 3] + 1; order[b] = b; }
  order.sort((a, b) => idx[a] - idx[b]);
  let pos = 0, rvv = -1, rn = 0;
  const emit = (v, c) => { if (c <= 0) return; if (v === rvv) rn += c; else { if (rn) { wv(rvv); wv(rn); } rvv = v; rn = c; } };
  for (const b of order) { if (idx[b] < pos) continue; emit(0, idx[b] - pos); emit(val[b], 1); pos = idx[b] + 1; }
  emit(0, W * H * L - pos);
  if (rn) { wv(rvv); wv(rn); }
  const body = new Uint8Array(out.length + 4);
  body.set(out);
  const c = crc32(body.subarray(0, out.length));
  body[out.length] = c & 255; body[out.length + 1] = (c >>> 8) & 255; body[out.length + 2] = (c >>> 16) & 255; body[out.length + 3] = c >>> 24;
  return b64urlEncode(await deflateRaw(body));
}
