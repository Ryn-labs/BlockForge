import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { blockColor, shapeOf } from './blocks.js';
import { createCharacter, Animator } from './character.js';

// Built for big builds: blocks live in a sparse chunk grid (typed arrays), meshes are cut into
// 32-block sections (so the GPU skips what's off screen), the layer slider moves a clipping plane
// instead of rebuilding, the scene only redraws when something changes, and hover walks the grid
// instead of testing every triangle.

const FACES = [
  { d: [1, 0, 0], c: [[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]], shade: .82 },
  { d: [-1, 0, 0], c: [[0, 0, 1], [0, 1, 1], [0, 1, 0], [0, 0, 0]], shade: .82 },
  { d: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], shade: 1.0 },
  { d: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], shade: .55 },
  { d: [0, 0, 1], c: [[1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]], shade: .9 },
  { d: [0, 0, -1], c: [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]], shade: .72 },
];
const K_SKIP = 0, K_FULL = 1, K_GLASS = 2, K_WATER = 3, K_BOXES = 4, K_PLANT = 5, K_CONNECT = 6;
const KIND = { skip: K_SKIP, full: K_FULL, glass: K_GLASS, water: K_WATER, boxes: K_BOXES, plant: K_PLANT, connect: K_CONNECT };
const SEC = 32;                 // mesh section edge, in blocks
const PLANT = [[.25, 0, .25, .75, .8, .75]];
const DIRS4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];

/** Growable typed-array quad list: 4 vertices per quad, positions + normals + colours. */
class QuadBuf {
  constructor() { this.n = 0; this.cap = 0; this.alloc(4096); }
  alloc(q) {
    const p = new Float32Array(q * 12), c = new Float32Array(q * 12), m = new Int8Array(q * 12);
    if (this.n) { p.set(this.pos.subarray(0, this.n * 12)); c.set(this.col.subarray(0, this.n * 12)); m.set(this.nor.subarray(0, this.n * 12)); }
    this.pos = p; this.col = c; this.nor = m; this.cap = q;
  }
  quad(fi, x, y, z, x0, y0, z0, x1, y1, z1, r, g, b) {
    if (this.n === this.cap) this.alloc(this.cap * 2);
    const face = FACES[fi], o = this.n * 12, s = face.shade, P = this.pos, C = this.col, N = this.nor;
    const nx = face.d[0] * 127, ny = face.d[1] * 127, nz = face.d[2] * 127;
    r *= s; g *= s; b *= s;
    for (let v = 0; v < 4; v++) {
      const c = face.c[v], k = o + v * 3;
      P[k] = x + (c[0] ? x1 : x0); P[k + 1] = y + (c[1] ? y1 : y0); P[k + 2] = z + (c[2] ? z1 : z0);
      C[k] = r; C[k + 1] = g; C[k + 2] = b;
      N[k] = nx; N[k + 1] = ny; N[k + 2] = nz;
    }
    this.n++;
  }
  /** Copy the quads out into a geometry and empty the buffer. */
  take() {
    const n = this.n * 12, g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.pos.slice(0, n), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nor.slice(0, n), 3, true));
    g.setAttribute('color', new THREE.BufferAttribute(this.col.slice(0, n), 3));
    g.setIndex(quadIndex(this.n));
    this.n = 0;
    return g;
  }
}

// One shared index pattern (0,1,2, 0,2,3 per quad) instead of building an index list per mesh.
let IDX16 = null, IDX32 = null;
function fillIdx(arr) { for (let q = 0, o = 0; o < arr.length; q++, o += 6) { const b = q * 4; arr[o] = b; arr[o + 1] = b + 1; arr[o + 2] = b + 2; arr[o + 3] = b; arr[o + 4] = b + 2; arr[o + 5] = b + 3; } return arr; }
function quadIndex(q) {
  if (q * 4 <= 65536) return new THREE.BufferAttribute((IDX16 ||= fillIdx(new Uint16Array(16384 * 6))).subarray(0, q * 6), 1);
  if (!IDX32 || IDX32.length < q * 6) IDX32 = fillIdx(new Uint32Array(Math.max(q, (IDX32?.length || 0) / 3) * 6));
  return new THREE.BufferAttribute(IDX32.subarray(0, q * 6), 1);
}

function srgb(c) {
  const f = v => { v /= 255; return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  return [f((c >> 16) & 255), f((c >> 8) & 255), f(c & 255)];
}

export class Viewer {
  constructor(el) {
    this.el = el;
    // no preserveDrawingBuffer: snapshots render and read in the same task, so it isn't needed (and it costs every frame)
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.localClippingEnabled = true;
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.addEventListener('change', () => { this.dirty = true; });
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(0.6, 1, 0.35);
    this.scene.add(sun);
    this.group = new THREE.Group();          // build sections
    this.capGroup = new THREE.Group();       // tops of the cut layer
    this.scene.add(this.group, this.capGroup);
    this.clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
    this.clipList = [this.clipPlane];
    this.mats = [
      new THREE.MeshLambertMaterial({ vertexColors: true }),
      new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: .6, depthWrite: false }),
      new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: .38, depthWrite: false }),
      new THREE.MeshBasicMaterial({ color: 0x9aa3b5, transparent: true, opacity: 0.07, depthWrite: false }),
    ];
    this.bufs = [new QuadBuf(), new QuadBuf(), new QuadBuf(), new QuadBuf()];   // opaque, water, glass, ghost
    this.secMeshes = [];
    this.data = null;
    this.cutY = Infinity;
    this.dirty = true;
    this.setTheme(true);
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    this.onFrame = new Set();
    this.clock = new THREE.Clock();
    // draw only when something changed: the camera moved, an animation is running, or the scene was edited
    const loop = () => {
      requestAnimationFrame(loop);
      const dt = Math.min(0.05, this.clock.getDelta());
      const active = this.onFrame.size > 0;
      for (const f of this.onFrame) f(dt);
      this.controls.update();
      if (active || this.dirty) { this.dirty = false; this.renderer.render(this.scene, this.camera); }
    };
    loop();
  }

  /** Ask for a redraw on the next frame. */
  invalidate() { this.dirty = true; }

  setTheme(dark, bg = null) {
    this.scene.background = new THREE.Color(bg || (dark ? 0x15171c : 0xdfe6ee));
    if (this.gridHelper) this.buildGrid();
    this.dirty = true;
  }

  setGrid(on) { this.showGrid = on; if (this.gridHelper) this.gridHelper.visible = on; this.dirty = true; }

  setAutoRotate(on) { this.controls.autoRotate = on; this.controls.autoRotateSpeed = 0.8; this.dirty = true; }

  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.dirty = true;
  }

  /** Flint walks around the build, placing it layer by layer. Resolves when finished (or skipped). */
  playBuild({ look, seconds, onLayer, showBuilder = true } = {}) {
    this.stopBuild();
    if (!this.data) return Promise.resolve();
    const H = this.H, W = this.W, L = this.L;
    const total = seconds || Math.min(14, Math.max(4, H * 0.28));
    const perLayer = total / H;
    const ox = -W / 2, oz = -L / 2;
    let ch = null, anim = null;
    const fx = new THREE.Group();
    this.scene.add(fx);
    if (showBuilder) {
      ch = createCharacter(look);
      anim = new Animator(ch);
      anim.play('build');
      anim.express('determined');
      ch.root.scale.setScalar(Math.max(1.5, Math.min(5, Math.max(W, H, L) / 18)));
      this.scene.add(ch.root);
    }
    // a scaffolding tower that grows under the builder: four posts plus a plank deck
    const sc = ch ? ch.root.scale.x : 1;
    const scaffold = new THREE.Group();
    const wood = new THREE.MeshLambertMaterial({ color: 0xc8a55a });
    const posts = [];
    for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.12 * sc, 1, 0.12 * sc), wood);
      p.position.set(a * 0.42 * sc, 0, b * 0.42 * sc); scaffold.add(p); posts.push(p);
    }
    const deck = new THREE.Mesh(new THREE.BoxGeometry(1.0 * sc, 0.12, 1.0 * sc), wood);
    scaffold.add(deck);
    if (showBuilder) this.scene.add(scaffold);
    // walk path: a rectangle just outside the build
    const pad = 0.75 * sc + 0.3;
    const path = [[ox - pad, oz - pad], [ox + W + pad, oz - pad], [ox + W + pad, oz + L + pad], [ox - pad, oz + L + pad]];
    const perim = 2 * (W + L + 4 * pad);
    const posAt = u => {
      let d = (u % 1) * perim;
      for (let i = 0; i < 4; i++) {
        const a = path[i], b = path[(i + 1) % 4], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (d <= len) return [a[0] + (b[0] - a[0]) * d / len, a[1] + (b[1] - a[1]) * d / len];
        d -= len;
      }
      return path[0];
    };
    const poofs = [];
    const poofGeo = new THREE.BoxGeometry(0.35, 0.35, 0.35);
    const spawnPoofs = y => {
      const f = this.data.blocks, a = this.layerStart[y], n = this.layerStart[y + 1] - a;
      for (let k = 0; k < Math.min(8, n); k++) {
        const i = this.layerOrder[a + ((Math.random() * n) | 0)] * 4;
        const m = new THREE.Mesh(poofGeo, new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }));
        m.position.set(ox + f[i] + 0.5, y + 1, oz + f[i + 2] + 0.5);
        m.userData = { v: [(Math.random() - .5) * 2, 1.5 + Math.random(), (Math.random() - .5) * 2], life: 0.6 };
        fx.add(m); poofs.push(m);
      }
    };
    let t = 0, layer = -1, done;
    this.setCut(-1);
    const promise = new Promise(r => { done = r; });
    const finish = () => {
      this.onFrame.delete(step);
      this.setCut(H - 1);
      this.scene.remove(fx);
      poofGeo.dispose();
      if (ch) {
        this.scene.remove(scaffold);
        anim.play('celebrate'); anim.express('excited');
        const pos = posAt(0.1);
        ch.root.position.set(pos[0], 0, pos[1]);
        ch.root.lookAt(0, 0, 0);
        let end = 2.4;
        const cheer = dt => { anim.update(dt); end -= dt; if (end <= 0) { this.onFrame.delete(cheer); this.scene.remove(ch.root); } };
        this.onFrame.add(cheer);
        this._buildCleanup = () => { this.onFrame.delete(cheer); this.scene.remove(ch.root); this.dirty = true; };
      }
      this._stopBuild = null;
      this.dirty = true;
      done();
    };
    const step = dt => {
      t += dt;
      const want = Math.min(H - 1, Math.floor(t / perLayer));
      if (want !== layer) {
        layer = want;
        this.setCut(layer);
        spawnPoofs(layer);
        onLayer?.(layer, H);
      }
      for (let i = poofs.length - 1; i >= 0; i--) {
        const p = poofs[i], u = p.userData;
        u.life -= dt;
        p.position.x += u.v[0] * dt; p.position.y += u.v[1] * dt; p.position.z += u.v[2] * dt;
        p.material.opacity = Math.max(0, u.life / 0.6);
        p.scale.setScalar(0.5 + u.life);
        if (u.life <= 0) { fx.remove(p); p.material.dispose(); poofs.splice(i, 1); }
      }
      if (ch) {
        const u = t / total * 1.5;
        const [px, pz] = posAt(u);
        const y = Math.max(0, layer + 1);
        ch.root.position.set(px, y, pz);
        ch.root.lookAt(0, y, 0);
        scaffold.position.set(px, 0, pz);
        for (const p of posts) { p.scale.y = Math.max(0.01, y); p.position.y = y / 2; }
        deck.position.y = y - 0.06; deck.visible = y > 0;
        anim.update(dt);
      }
      if (t >= total) finish();
    };
    this.onFrame.add(step);
    this._stopBuild = finish;
    return promise;
  }

  stopBuild() {
    if (this._stopBuild) this._stopBuild();
    if (this._buildCleanup) { this._buildCleanup(); this._buildCleanup = null; }
  }

  get building() { return !!this._stopBuild; }

  static empty(g) { for (const c of [...g.children]) { c.geometry?.dispose(); g.remove(c); } }

  clear() {
    this.stopBuild();
    Viewer.empty(this.group); Viewer.empty(this.capGroup);
    this.secMeshes = [];
    if (this.gridHelper) { this.scene.remove(this.gridHelper); this.gridHelper = null; }
    this.data = null; this.chunks = null;
    this.dirty = true;
  }

  load(data) {
    this.stopBuild();
    this.data = data;
    const [W, H, L] = data.size;
    this.W = W; this.H = H; this.L = L;
    const pal = data.palette.map((st, i) => {
      const s = shapeOf(st);
      const kind = KIND[s.kind] ?? K_BOXES;
      return { st, i, name: st.split('[')[0].replace('minecraft:', ''), s, kind, rgb: srgb(blockColor(st)),
        full: kind === K_FULL, glassy: st.includes('pane') || st.includes('glass') };
    });
    this.pal = pal;
    this.focusName = null;
    // sparse grid: 16³ chunks of Uint16 (palette index + 1), only where there are blocks
    const cw = Math.ceil(W / 16), chh = Math.ceil(H / 16), cl = Math.ceil(L / 16);
    const chunks = new Array(cw * chh * cl).fill(null);
    this.cw = cw; this.cl = cl; this.chunks = chunks;
    const sw = Math.ceil(W / SEC), sl = Math.ceil(L / SEC), nsec = sw * Math.ceil(H / SEC) * sl;
    this.sw = sw; this.sl = sl;
    const f = data.blocks, n = f.length >> 2;
    const secStart = new Uint32Array(nsec + 1), layerStart = new Uint32Array(H + 1), palCount = new Uint32Array(pal.length);
    for (let b = 0, i = 0; b < n; b++, i += 4) {
      const x = f[i], y = f[i + 1], z = f[i + 2];
      if (x < 0 || y < 0 || z < 0 || x >= W || y >= H || z >= L) continue;
      const ci = ((y >> 4) * cl + (z >> 4)) * cw + (x >> 4);
      (chunks[ci] || (chunks[ci] = new Uint16Array(4096)))[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)] = f[i + 3] + 1;
      secStart[((y >> 5) * sl + (z >> 5)) * sw + (x >> 5) + 1]++;
      layerStart[y + 1]++;
      palCount[f[i + 3]]++;
    }
    for (let s = 0; s < nsec; s++) secStart[s + 1] += secStart[s];
    for (let y = 0; y < H; y++) layerStart[y + 1] += layerStart[y];
    // block order grouped by mesh section, and by layer (for the cut caps and Flint's poofs)
    const secOrder = new Uint32Array(secStart[nsec]), layerOrder = new Uint32Array(layerStart[H]);
    const sc = secStart.slice(0, nsec), lc = layerStart.slice(0, H);
    for (let b = 0, i = 0; b < n; b++, i += 4) {
      const x = f[i], y = f[i + 1], z = f[i + 2];
      if (x < 0 || y < 0 || z < 0 || x >= W || y >= H || z >= L) continue;
      secOrder[sc[((y >> 5) * sl + (z >> 5)) * sw + (x >> 5)]++] = b;
      layerOrder[lc[y]++] = b;
    }
    this.secStart = secStart; this.secOrder = secOrder; this.layerStart = layerStart; this.layerOrder = layerOrder;
    this.counts = {};
    pal.forEach((p, i) => { if (palCount[i]) this.counts[p.name] = (this.counts[p.name] || 0) + palCount[i]; });
    this.cutY = H - 1;
    this.rebuild();
    this.setCut(H - 1);
    this.buildGrid();
    this.frame();
  }

  /** Palette index + 1 at a cell, or 0 for air / outside. Ignores the layer cut. */
  raw(x, y, z) {
    if (x < 0 || y < 0 || z < 0 || x >= this.W || y >= this.H || z >= this.L) return 0;
    const c = this.chunks[((y >> 4) * this.cl + (z >> 4)) * this.cw + (x >> 4)];
    return c ? c[((y & 15) << 8) | ((z & 15) << 4) | (x & 15)] : 0;
  }

  at(x, y, z) {
    if (y > this.cutY) return undefined;
    const v = this.raw(x, y, z);
    return v ? this.pal[v - 1] : undefined;
  }

  /** Show layers 0..y only. Moves a clipping plane and re-caps the top layer: no rebuild. */
  setCut(y) {
    this.cutY = y;
    this.dirty = true;
    if (!this.data) return;
    const cut = y < this.H - 1;
    this.clipPlane.constant = y + 1 + 1e-3;
    for (const m of this.mats) m.clippingPlanes = cut ? this.clipList : null;
    this.group.visible = y >= 0;
    for (const m of this.secMeshes) m.visible = m.userData.y0 <= y;
    this.buildCap();
  }

  /** Top faces of the cut layer that are normally hidden by the block above. */
  buildCap() {
    Viewer.empty(this.capGroup);
    const y = this.cutY;
    if (!this.data || y < 0 || y >= this.H - 1) return;
    const inF = this.inF;
    for (let k = this.layerStart[y], e = this.layerStart[y + 1]; k < e; k++) this.emit(this.layerOrder[k] * 4, inF, true);
    const sphere = new THREE.Sphere(new THREE.Vector3(this.W / 2, y + 1, this.L / 2), Math.hypot(this.W, this.L) / 2 + 1);
    this.flush(this.capGroup, sphere, null);
  }

  /** Emit one block's faces into the bucket buffers. capOnly: just the hidden top face (for the cut layer). */
  emit(i, inF, capOnly) {
    const f = this.data.blocks, x = f[i], y = f[i + 1], z = f[i + 2], p = this.pal[f[i + 3]], k = p.kind;
    if (k === K_SKIP) return;
    const h = ((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) >>> 0;
    const j = 0.93 + ((h % 1000) / 1000) * 0.12;
    const r = p.rgb[0] * j, g = p.rgb[1] * j, b = p.rgb[2] * j;
    const ghost = !inF[p.i], bufs = this.bufs, pal = this.pal;
    if (k <= K_WATER) {
      const buf = ghost ? bufs[3] : k === K_FULL ? bufs[0] : k === K_GLASS ? bufs[2] : bufs[1];
      let top = 1;
      if (k === K_WATER && !capOnly) { const a = this.raw(x, y + 1, z); top = a && pal[a - 1].kind === K_WATER ? 1 : .875; }
      for (let fi = capOnly ? 2 : 0, fe = capOnly ? 3 : 6; fi < fe; fi++) {
        const d = FACES[fi].d, v = this.raw(x + d[0], y + d[1], z + d[2]);
        let hidden = false;
        if (v) { const n = pal[v - 1]; hidden = (n.full && (ghost || inF[n.i])) || (k !== K_FULL && n.kind === k && inF[n.i] === !ghost); }
        if (capOnly ? !hidden : hidden) continue;
        buf.quad(fi, x, y, z, 0, 0, 0, 1, top, 1, r, g, b);
      }
      return;
    }
    if (capOnly) return;
    let boxes;
    if (k === K_PLANT) boxes = PLANT;
    else if (k === K_CONNECT) {
      const a = p.s.post, arm = p.s.arm, wall = p.s.wall;
      boxes = [[a, 0, a, 1 - a, 1, 1 - a]];
      const ay1 = wall ? .8125 : .9375, ay0 = wall ? 0 : .375;
      for (const [dx, dz] of DIRS4) {
        const v = this.raw(x + dx, y, z + dz);
        if (!v) continue;
        const n = pal[v - 1];
        if (!(n.full || n.kind === K_CONNECT || n.kind === K_GLASS)) continue;
        if (dx === 1) boxes.push([1 - a, ay0, arm, 1, ay1, 1 - arm]);
        if (dx === -1) boxes.push([0, ay0, arm, a, ay1, 1 - arm]);
        if (dz === 1) boxes.push([arm, ay0, 1 - a, 1 - arm, ay1, 1]);
        if (dz === -1) boxes.push([arm, ay0, 0, 1 - arm, ay1, a]);
      }
    } else boxes = p.s.boxes || [[0, 0, 0, 1, 1, 1]];
    const buf = ghost ? bufs[3] : p.glassy ? bufs[2] : bufs[0];
    for (const bx of boxes) for (let fi = 0; fi < 6; fi++) buf.quad(fi, x, y, z, bx[0], bx[1], bx[2], bx[3], bx[4], bx[5], r, g, b);
  }

  /** Turn whatever is in the bucket buffers into meshes under `parent`. Returns the quad count. */
  flush(parent, sphere, y0) {
    let quads = 0;
    for (let bi = 0; bi < 4; bi++) {
      const buf = this.bufs[bi];
      if (!buf.n) continue;
      quads += buf.n;
      const geo = buf.take();
      geo.boundingSphere = sphere;
      const m = new THREE.Mesh(geo, this.mats[bi]);
      m.position.set(-this.W / 2, 0, -this.L / 2);
      if (bi === 3) { m.userData.ghost = true; m.renderOrder = 2; }
      if (y0 !== null) { m.userData.y0 = y0; this.secMeshes.push(m); }
      parent.add(m);
    }
    return quads;
  }

  rebuild() {
    Viewer.empty(this.group);
    this.secMeshes = [];
    this.dirty = true;
    if (!this.data) return;
    const fn = this.focusName;
    const inF = this.inF = this.pal.map(p => !fn || p.name === fn);
    const { secStart, secOrder, sw, sl } = this;
    const nsec = secStart.length - 1, half = SEC / 2, rad = half * Math.sqrt(3) + 1;
    let quads = 0;
    for (let s = 0; s < nsec; s++) {
      const a = secStart[s], e = secStart[s + 1];
      if (a === e) continue;
      for (let k = a; k < e; k++) this.emit(secOrder[k] * 4, inF, false);
      const sx = s % sw, sz = ((s / sw) | 0) % sl, sy = (s / (sw * sl)) | 0;
      quads += this.flush(this.group, new THREE.Sphere(new THREE.Vector3(sx * SEC + half, sy * SEC + half, sz * SEC + half), rad), sy * SEC);
    }
    this.quads = quads;
    // very big builds: draw fewer pixels so the frame rate holds up on laptop / integrated GPUs
    const pr = Math.min(devicePixelRatio, quads > 600000 ? 1 : quads > 250000 ? 1.5 : 2);
    if (pr !== this.renderer.getPixelRatio()) { this.renderer.setPixelRatio(pr); this.resize(); }
  }

  /** Show only blocks named `name` (e.g. 'stone_bricks'); the rest turn into faint ghosts. null clears. */
  setFocus(name) {
    this.focusName = name || null;
    this.rebuild();
    this.setCut(this.cutY);
  }

  // ------------------------------------------------------------ hover / click to identify blocks
  /** Walk the ray through the block grid (no triangle tests) to the first visible block. */
  pickCell(ray) {
    const W = this.W, L = this.L, Hm = Math.min(this.H, this.cutY + 1);
    if (Hm <= 0) return null;
    const ox = ray.origin.x + W / 2, oy = ray.origin.y, oz = ray.origin.z + L / 2;
    const dx = ray.direction.x, dy = ray.direction.y, dz = ray.direction.z;
    let t0 = 0, t1 = Infinity;
    for (const [o, d, max] of [[ox, dx, W], [oy, dy, Hm], [oz, dz, L]]) {
      if (Math.abs(d) < 1e-12) { if (o < 0 || o > max) return null; continue; }
      let a = -o / d, b = (max - o) / d;
      if (a > b) [a, b] = [b, a];
      if (a > t0) t0 = a;
      if (b < t1) t1 = b;
      if (t0 > t1) return null;
    }
    const t = t0 + 1e-6;
    let x = Math.min(W - 1, Math.max(0, Math.floor(ox + dx * t)));
    let y = Math.min(Hm - 1, Math.max(0, Math.floor(oy + dy * t)));
    let z = Math.min(L - 1, Math.max(0, Math.floor(oz + dz * t)));
    const sx = Math.sign(dx), sy = Math.sign(dy), sz = Math.sign(dz);
    const tdx = dx ? Math.abs(1 / dx) : Infinity, tdy = dy ? Math.abs(1 / dy) : Infinity, tdz = dz ? Math.abs(1 / dz) : Infinity;
    let tmx = dx > 0 ? (x + 1 - ox) / dx : dx < 0 ? (x - ox) / dx : Infinity;
    let tmy = dy > 0 ? (y + 1 - oy) / dy : dy < 0 ? (y - oy) / dy : Infinity;
    let tmz = dz > 0 ? (z + 1 - oz) / dz : dz < 0 ? (z - oz) / dz : Infinity;
    const fn = this.focusName, pal = this.pal;
    for (let i = W + Hm + L + 3; i > 0; i--) {
      const v = this.raw(x, y, z);
      if (v) { const pe = pal[v - 1]; if (pe.kind !== K_SKIP && (!fn || pe.name === fn)) return { x, y, z, pe }; }
      if (tmx < tmy && tmx < tmz) { x += sx; tmx += tdx; if (x < 0 || x >= W) break; }
      else if (tmy < tmz) { y += sy; tmy += tdy; if (y < 0 || y >= Hm) break; }
      else { z += sz; tmz += tdz; if (z < 0 || z >= L) break; }
    }
    return null;
  }

  enablePicking({ onHover, onPick } = {}) {
    this.onHover = onHover; this.onPick = onPick;
    const el = this.renderer.domElement, ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.04, 1.04, 1.04)),
      new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 }));
    edges.renderOrder = 10; edges.visible = false;
    this.scene.add(edges);
    this.pickBox = edges;
    const showBox = info => {
      const was = edges.visible ? edges.position.toArray().join() : null;
      if (info) { edges.position.set(info.x + 0.5 - this.W / 2, info.y + 0.5, info.z + 0.5 - this.L / 2); edges.visible = true; }
      else edges.visible = false;
      if ((edges.visible ? edges.position.toArray().join() : null) !== was) this.dirty = true;
    };
    const pick = e => {
      if (!this.data || this.building) return null;
      const r = el.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, this.camera);
      const hit = this.pickCell(ray.ray);
      if (!hit) return null;
      const { x, y, z, pe } = hit, props = {};
      if (pe.st.includes('[')) for (const kv of pe.st.slice(pe.st.indexOf('[') + 1, -1).split(',')) { const [a, b] = kv.split('='); props[a] = b; }
      return { x, y, z, state: pe.st, name: pe.name, props, count: this.counts[pe.name] || 0, color: pe.rgb };
    };
    let pending = null, down = null;
    el.addEventListener('pointermove', e => {
      if (e.buttons) { showBox(null); this.onHover?.(null); return; }   // dragging the camera
      if (pending) return;
      pending = requestAnimationFrame(() => {
        pending = null;
        const info = this.hoverEnabled === false ? null : pick(e);
        showBox(info);
        this.onHover?.(info, e.clientX, e.clientY);
      });
    });
    el.addEventListener('pointerleave', () => { showBox(null); this.onHover?.(null); });
    el.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
    el.addEventListener('pointerup', e => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || e.button !== 0) { down = null; return; }
      down = null;
      this.onPick?.(pick(e));
    });
  }

  buildGrid() {
    if (this.gridHelper) this.scene.remove(this.gridHelper);
    this.dirty = true;
    if (!this.data) return;
    const s = Math.max(this.W, this.L) + 16;
    const dark = this.scene.background.getHex() < 0x808080;
    // one line per block gets dense on huge builds: step up to every 2/4/8 blocks
    const step = s > 1200 ? 8 : s > 600 ? 4 : s > 300 ? 2 : 1;
    const size = Math.ceil(s / step) * step;
    this.gridHelper = new THREE.GridHelper(size, size / step, dark ? 0x3a3f4a : 0xaab4c0, dark ? 0x242830 : 0xc5cdd6);
    this.gridHelper.position.y = -0.01;
    this.gridHelper.visible = this.showGrid !== false;
    if (this.W % 2 !== size % 2) this.gridHelper.position.x = 0.5;
    if (this.L % 2 !== size % 2) this.gridHelper.position.z = 0.5;
    this.scene.add(this.gridHelper);
  }

  frame() {
    if (!this.data) return;
    const r = Math.max(this.W, this.H, this.L);
    this.controls.target.set(0, this.H * 0.4, 0);
    this.camera.position.set(r * 1.05, this.H * 0.4 + r * 0.8, r * 1.25);
    this.camera.far = r * 20 + 500;
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.dirty = true;
  }

  snapshot(w = 320, h = 220) {
    this.renderer.render(this.scene, this.camera);
    const src = this.renderer.domElement;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    const s = Math.max(w / src.width, h / src.height);
    const dw = src.width * s, dh = src.height * s;
    ctx.drawImage(src, (w - dw) / 2, (h - dh) / 2, dw, dh);
    return c.toDataURL('image/jpeg', 0.85);
  }

  screenshotFull() {
    this.renderer.render(this.scene, this.camera);
    return this.renderer.domElement.toDataURL('image/png');
  }
}
