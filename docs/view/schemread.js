// Reads Minecraft schematic files in the browser: .schem (Sponge v1/v2/v3), .litematic, and structure-block .nbt.
// Returns { size, palette, blocks: Int32Array [x,y,z,paletteIndex, ...] } ready for the 3D viewer.
import { gunzip, inflate } from './linkcodec.js';

// ------------------------------------------------------------------ NBT (big endian, as Java Edition writes it)
function readNbt(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength), dec = new TextDecoder();
  let p = 0;
  const str = () => { const n = dv.getUint16(p); p += 2; const s = dec.decode(buf.subarray(p, p + n)); p += n; return s; };
  const payload = t => {
    switch (t) {
      case 1: return dv.getInt8(p++);
      case 2: { const v = dv.getInt16(p); p += 2; return v; }
      case 3: { const v = dv.getInt32(p); p += 4; return v; }
      case 4: { const hi = dv.getInt32(p), lo = dv.getUint32(p + 4); p += 8; return hi * 4294967296 + lo; }   // fine for small values
      case 5: { const v = dv.getFloat32(p); p += 4; return v; }
      case 6: { const v = dv.getFloat64(p); p += 8; return v; }
      case 7: { const n = dv.getInt32(p); p += 4; const v = buf.subarray(p, p + n); p += n; return v; }
      case 8: return str();
      case 9: { const et = dv.getUint8(p++), n = dv.getInt32(p); p += 4; const a = []; for (let i = 0; i < n; i++) a.push(payload(et)); return a; }
      case 10: { const o = {}; for (;;) { const ct = dv.getUint8(p++); if (ct === 0) return o; const k = str(); o[k] = payload(ct); } }
      case 11: { const n = dv.getInt32(p); p += 4; const a = new Int32Array(n); for (let i = 0; i < n; i++) { a[i] = dv.getInt32(p); p += 4; } return a; }
      case 12: {   // long array: kept as 32-bit words, low word first, so bits can be read as one little-endian stream
        const n = dv.getInt32(p); p += 4; const w = new Uint32Array(n * 2);
        for (let i = 0; i < n; i++) { w[i * 2 + 1] = dv.getUint32(p); w[i * 2] = dv.getUint32(p + 4); p += 8; }
        return { longWords: w };
      }
      default: throw new Error('Not a schematic file (unknown NBT tag ' + t + ')');
    }
  };
  const t = dv.getUint8(p++);
  if (t !== 10) throw new Error('Not a schematic file');
  str();
  return payload(10);
}

const stateStr = e => {
  const props = e.Properties ? Object.entries(e.Properties) : [];
  return e.Name + (props.length ? '[' + props.map(([k, v]) => `${k}=${v}`).join(',') + ']' : '');
};
const isAir = st => st === 'minecraft:air' || st === 'minecraft:cave_air' || st === 'minecraft:void_air' || st === 'minecraft:structure_void' || st.startsWith('minecraft:air[');

/** Collect blocks as [x,y,z,state] then normalise to a 0-based box. */
class Collector {
  constructor() { this.pal = new Map(); this.list = []; this.min = [Infinity, Infinity, Infinity]; this.max = [-Infinity, -Infinity, -Infinity]; }
  add(x, y, z, st) {
    if (isAir(st)) return;
    let i = this.pal.get(st);
    if (i === undefined) { i = this.pal.size; this.pal.set(st, i); }
    this.list.push(x, y, z, i);
    if (x < this.min[0]) this.min[0] = x; if (y < this.min[1]) this.min[1] = y; if (z < this.min[2]) this.min[2] = z;
    if (x > this.max[0]) this.max[0] = x; if (y > this.max[1]) this.max[1] = y; if (z > this.max[2]) this.max[2] = z;
  }
  result() {
    if (!this.list.length) throw new Error('That file has no blocks in it.');
    const [mx, my, mz] = this.min, f = this.list, blocks = new Int32Array(f.length);
    for (let i = 0; i < f.length; i += 4) { blocks[i] = f[i] - mx; blocks[i + 1] = f[i + 1] - my; blocks[i + 2] = f[i + 2] - mz; blocks[i + 3] = f[i + 3]; }
    return { size: [this.max[0] - mx + 1, this.max[1] - my + 1, this.max[2] - mz + 1], palette: [...this.pal.keys()], blocks };
  }
}

function readLitematic(root, c) {
  for (const reg of Object.values(root.Regions)) {
    const sx = reg.Size.x, sy = reg.Size.y, sz = reg.Size.z;
    const W = Math.abs(sx), H = Math.abs(sy), L = Math.abs(sz);
    const ox = reg.Position.x + Math.min(sx + 1, 0), oy = reg.Position.y + Math.min(sy + 1, 0), oz = reg.Position.z + Math.min(sz + 1, 0);
    const pal = reg.BlockStatePalette.map(stateStr);
    const bits = Math.max(2, Math.ceil(Math.log2(pal.length))), mask = 2 ** bits - 1;
    const w = reg.BlockStates.longWords;
    for (let i = 0, n = W * H * L; i < n; i++) {
      const start = i * bits, wi = Math.floor(start / 32), o = start % 32;
      let v = w[wi] >>> o;
      if (o + bits > 32) v |= w[wi + 1] << (32 - o);
      v = (v >>> 0) & mask;
      const st = pal[v];
      if (st) c.add(ox + i % W, oy + Math.floor(i / (W * L)), oz + Math.floor(i / W) % L, st);
    }
  }
}

function readSponge(root, c) {
  const W = root.Width, H = root.Height, L = root.Length;
  const blk = root.Blocks && !Array.isArray(root.Blocks) && root.Blocks.Palette ? root.Blocks : null;   // v3
  const palRaw = blk ? blk.Palette : root.Palette, data = blk ? blk.Data : root.BlockData;
  if (!palRaw || !data) throw new Error('This .schem has no blocks (it may be an old MCEdit .schematic, which isn\'t supported).');
  const pal = [];
  for (const [k, v] of Object.entries(palRaw)) pal[v] = k;
  let i = 0, v = 0, s = 0;
  for (let k = 0; k < data.length; k++) {
    const b = data[k] & 255;
    v |= (b & 0x7F) << s;
    if (b & 0x80) { s += 7; continue; }
    const st = pal[v];
    if (st) c.add(i % W, Math.floor(i / (W * L)), Math.floor(i / W) % L, st);
    i++; v = 0; s = 0;
  }
}

function readStructure(root, c) {
  const pal = (root.palette || (root.palettes && root.palettes[0]) || []).map(stateStr);
  for (const b of root.blocks) { const st = pal[b.state]; if (st) c.add(b.pos[0], b.pos[1], b.pos[2], st); }
}

/** File bytes -> build data. name is only used for messages. */
export async function readSchematic(bytes, name = '') {
  if (/\.mcstructure$/i.test(name)) throw new Error('Bedrock .mcstructure files can\'t be previewed yet. Use the .schem, .litematic or .nbt version.');
  let buf = bytes;
  if (buf[0] === 0x1f && buf[1] === 0x8b) buf = await gunzip(buf);
  else if (buf[0] === 0x78) { try { buf = await inflate(buf); } catch { /* not zlib after all */ } }
  let root = readNbt(buf);
  if (root.Schematic && typeof root.Schematic === 'object' && !Array.isArray(root.Schematic)) root = root.Schematic;
  const c = new Collector();
  if (root.Regions) readLitematic(root, c);
  else if (Array.isArray(root.blocks) && (root.palette || root.palettes)) readStructure(root, c);
  else if (root.Width !== undefined) readSponge(root, c);
  else throw new Error('Unrecognised schematic file. Supported: .schem, .litematic and structure-block .nbt.');
  return c.result();
}
