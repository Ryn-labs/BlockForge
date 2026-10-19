import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { blockColor, shapeOf } from './blocks.js';
import { createCharacter, Animator } from './character.js';

const FACES = [
  { d: [1, 0, 0], c: [[1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 1]], shade: .82 },
  { d: [-1, 0, 0], c: [[0, 0, 1], [0, 1, 1], [0, 1, 0], [0, 0, 0]], shade: .82 },
  { d: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], shade: 1.0 },
  { d: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], shade: .55 },
  { d: [0, 0, 1], c: [[1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]], shade: .9 },
  { d: [0, 0, -1], c: [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]], shade: .72 },
];

class MeshBuilder {
  constructor() { this.pos = []; this.nor = []; this.col = []; this.idx = []; }
  quad(face, x, y, z, box, r, g, b) {
    const [x0, y0, z0, x1, y1, z1] = box;
    const base = this.pos.length / 3;
    for (const c of face.c) {
      this.pos.push(x + (c[0] ? x1 : x0), y + (c[1] ? y1 : y0), z + (c[2] ? z1 : z0));
      this.nor.push(...face.d);
      this.col.push(r * face.shade, g * face.shade, b * face.shade);
    }
    this.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
  }
  geometry() {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.nor, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
    g.setIndex(this.pos.length / 3 > 65535 ? new THREE.Uint32BufferAttribute(this.idx, 1) : new THREE.Uint16BufferAttribute(this.idx, 1));
    g.computeBoundingSphere();
    return g;
  }
}

function srgb(c) {
  const f = v => { v /= 255; return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  return [f((c >> 16) & 255), f((c >> 8) & 255), f(c & 255)];
}

export class Viewer {
  constructor(el) {
    this.el = el;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    el.appendChild(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.3);
    sun.position.set(0.6, 1, 0.35);
    this.scene.add(sun);
    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.data = null;
    this.cutY = Infinity;
    this.setTheme(true);
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    this.onFrame = new Set();
    this.clock = new THREE.Clock();
    const loop = () => {
      const dt = Math.min(0.05, this.clock.getDelta());
      for (const f of this.onFrame) f(dt);
      this.controls.update(); this.renderer.render(this.scene, this.camera); requestAnimationFrame(loop);
    };
    loop();
  }

  setTheme(dark, bg = null) {
    this.scene.background = new THREE.Color(bg || (dark ? 0x15171c : 0xdfe6ee));
    if (this.gridHelper) this.buildGrid();
  }

  setGrid(on) { this.showGrid = on; if (this.gridHelper) this.gridHelper.visible = on; }

  setAutoRotate(on) { this.controls.autoRotate = on; this.controls.autoRotateSpeed = 0.8; }

  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
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
      const f = this.data.blocks, cand = [];
      for (let i = 0; i < f.length; i += 4) if (f[i + 1] === y) cand.push(i);
      for (let k = 0; k < Math.min(8, cand.length); k++) {
        const i = cand[(Math.random() * cand.length) | 0];
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
        this._buildCleanup = () => { this.onFrame.delete(cheer); this.scene.remove(ch.root); };
      }
      this._stopBuild = null;
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

  clear() {
    this.stopBuild();
    for (const c of [...this.group.children]) { c.geometry?.dispose(); this.group.remove(c); }
    if (this.gridHelper) { this.scene.remove(this.gridHelper); this.gridHelper = null; }
    this.data = null;
  }

  load(data) {
    this.stopBuild();
    this.data = data;
    const [W, H, L] = data.size;
    this.W = W; this.H = H; this.L = L;
    const pal = data.palette.map((st, i) => {
      const s = shapeOf(st);
      return { st, i, name: st.split('[')[0].replace('minecraft:', ''), s, rgb: srgb(blockColor(st)),
        full: s.kind === 'full', solidish: s.kind === 'full' || s.kind === 'glass' };
    });
    this.pal = pal;
    this.focusName = null;
    this.counts = {};
    for (let i = 3; i < data.blocks.length; i += 4) { const n = pal[data.blocks[i]].name; this.counts[n] = (this.counts[n] || 0) + 1; }
    const grid = new Map();
    const f = data.blocks;
    for (let i = 0; i < f.length; i += 4) grid.set((f[i + 1] * L + f[i + 2]) * W + f[i], f[i + 3]);
    this.grid = grid;
    this.cutY = H - 1;
    this.rebuild();
    this.buildGrid();
    this.frame();
  }

  setCut(y) { this.cutY = y; this.rebuild(); }

  at(x, y, z) {
    if (x < 0 || y < 0 || z < 0 || x >= this.W || y >= this.H || z >= this.L || y > this.cutY) return undefined;
    const v = this.grid.get((y * this.L + z) * this.W + x);
    return v === undefined ? undefined : this.pal[v];
  }

  rebuild() {
    for (const c of [...this.group.children]) { c.geometry?.dispose(); this.group.remove(c); }
    if (!this.data) return;
    const opaque = new MeshBuilder(), glass = new MeshBuilder(), water = new MeshBuilder(), ghostMb = new MeshBuilder();
    const f = this.data.blocks;
    const fn = this.focusName, inF = q => !fn || q.name === fn;
    const DIRS4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    for (let i = 0; i < f.length; i += 4) {
      const x = f[i], y = f[i + 1], z = f[i + 2];
      if (y > this.cutY) continue;
      const p = this.pal[f[i + 3]];
      const k = p.s.kind;
      if (k === 'skip') continue;
      const h = ((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) >>> 0;
      const j = 0.93 + ((h % 1000) / 1000) * 0.12;
      const [r, g, b] = p.rgb;
      const ghost = !inF(p);
      if (k === 'full' || k === 'glass' || k === 'water') {
        const mb = ghost ? ghostMb : k === 'full' ? opaque : k === 'glass' ? glass : water;
        const box = k === 'water' ? [0, 0, 0, 1, (this.at(x, y + 1, z)?.s.kind === 'water') ? 1 : .875, 1] : [0, 0, 0, 1, 1, 1];
        for (const face of FACES) {
          const n = this.at(x + face.d[0], y + face.d[1], z + face.d[2]);
          if (n) {
            if (n.full && (ghost || inF(n))) continue;      // a highlighted block shows through faded neighbours
            if (k !== 'full' && n.s.kind === k && inF(n) === !ghost) continue;
          }
          mb.quad(face, x, y, z, box, r * j, g * j, b * j);
        }
        continue;
      }
      let boxes;
      if (k === 'boxes') boxes = p.s.boxes;
      else if (k === 'plant') boxes = [[.25, 0, .25, .75, .8, .75]];
      else if (k === 'connect') {
        const a = p.s.post, top = p.s.wall ? 1 : 1, arm = p.s.arm;
        boxes = [[a, 0, a, 1 - a, top, 1 - a]];
        for (const [dx, dz] of DIRS4) {
          const n = this.at(x + dx, y, z + dz);
          if (!n || !(n.full || n.s.kind === 'connect' || n.s.kind === 'glass')) continue;
          const ay1 = p.s.wall ? .8125 : .9375, ay0 = p.s.wall ? 0 : .375;
          if (dx === 1) boxes.push([1 - a, ay0, arm, 1, ay1, 1 - arm]);
          if (dx === -1) boxes.push([0, ay0, arm, a, ay1, 1 - arm]);
          if (dz === 1) boxes.push([arm, ay0, 1 - a, 1 - arm, ay1, 1]);
          if (dz === -1) boxes.push([arm, ay0, 0, 1 - arm, ay1, a]);
        }
      }
      const tgt = ghost ? ghostMb : p.st.includes('pane') || p.st.includes('glass') ? glass : opaque;
      for (const box of boxes) for (const face of FACES) tgt.quad(face, x, y, z, box, r * j, g * j, b * j);
    }
    const ox = -this.W / 2, oz = -this.L / 2;
    const add = (mb, mat) => {
      if (!mb.idx.length) return;
      const m = new THREE.Mesh(mb.geometry(), mat);
      m.position.set(ox, 0, oz);
      this.group.add(m);
    };
    add(opaque, new THREE.MeshLambertMaterial({ vertexColors: true }));
    add(water, new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: .6, depthWrite: false }));
    add(glass, new THREE.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: .38, depthWrite: false }));
    if (ghostMb.idx.length) {
      const m = new THREE.Mesh(ghostMb.geometry(), new THREE.MeshBasicMaterial({ color: 0x9aa3b5, transparent: true, opacity: 0.07, depthWrite: false }));
      m.position.set(ox, 0, oz); m.userData.ghost = true; m.renderOrder = 2;
      this.group.add(m);
    }
  }

  /** Show only blocks named `name` (e.g. 'stone_bricks'); the rest turn into faint ghosts. null clears. */
  setFocus(name) {
    this.focusName = name || null;
    this.rebuild();
  }

  // ------------------------------------------------------------ hover / click to identify blocks
  enablePicking({ onHover, onPick } = {}) {
    this.onHover = onHover; this.onPick = onPick;
    const el = this.renderer.domElement, ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.04, 1.04, 1.04)),
      new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 }));
    edges.renderOrder = 10; edges.visible = false;
    this.scene.add(edges);
    this.pickBox = edges;
    const pick = e => {
      if (!this.data || this.building) return null;
      const r = el.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, this.camera);
      const meshes = this.group.children.filter(m => !m.userData.ghost);
      const hit = ray.intersectObjects(meshes, false)[0];
      if (!hit) return null;
      const n = hit.face.normal, lp = hit.point.clone().sub(hit.object.position);
      for (const sgn of [-1, 1]) {                    // step just inside the face we hit
        const x = Math.floor(lp.x + sgn * n.x * 0.01), y = Math.floor(lp.y + sgn * n.y * 0.01), z = Math.floor(lp.z + sgn * n.z * 0.01);
        const v = this.grid.get((y * this.L + z) * this.W + x);
        if (v !== undefined && y <= this.cutY) {
          const pe = this.pal[v];
          if (this.focusName && pe.name !== this.focusName) continue;
          const props = {};
          if (pe.st.includes('[')) for (const kv of pe.st.slice(pe.st.indexOf('[') + 1, -1).split(',')) { const [a, b] = kv.split('='); props[a] = b; }
          return { x, y, z, state: pe.st, name: pe.name, props, count: this.counts[pe.name] || 0, color: pe.rgb };
        }
      }
      return null;
    };
    let pending = null, down = null;
    el.addEventListener('pointermove', e => {
      if (e.buttons) { edges.visible = false; this.onHover?.(null); return; }   // dragging the camera
      if (pending) return;
      pending = requestAnimationFrame(() => {
        pending = null;
        const info = this.hoverEnabled === false ? null : pick(e);
        if (info) {
          edges.position.set(info.x + 0.5 - this.W / 2, info.y + 0.5, info.z + 0.5 - this.L / 2);
          edges.visible = true;
        } else edges.visible = false;
        this.onHover?.(info, e.clientX, e.clientY);
      });
    });
    el.addEventListener('pointerleave', () => { edges.visible = false; this.onHover?.(null); });
    el.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
    el.addEventListener('pointerup', e => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || e.button !== 0) { down = null; return; }
      down = null;
      this.onPick?.(pick(e));
    });
  }

  buildGrid() {
    if (this.gridHelper) this.scene.remove(this.gridHelper);
    if (!this.data) return;
    const s = Math.max(this.W, this.L) + 16;
    const dark = this.scene.background.getHex() < 0x808080;
    this.gridHelper = new THREE.GridHelper(s, s, dark ? 0x3a3f4a : 0xaab4c0, dark ? 0x242830 : 0xc5cdd6);
    this.gridHelper.position.y = -0.01;
    this.gridHelper.visible = this.showGrid !== false;
    if (this.W % 2 !== s % 2) this.gridHelper.position.x = 0.5;
    if (this.L % 2 !== s % 2) this.gridHelper.position.z = 0.5;
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
