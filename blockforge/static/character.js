// Flint - BlockForge's blocky guide. Story-mode style: chunky boxy body, big expressive face.
import * as THREE from 'three';

export const LOOK_DEFAULTS = { skin: '#e0ac7e', hair: '#3b2416', hoodie: '#2f8f5b', pants: '#34405a',
  bandana: '#d9532b', shoes: '#4a3424' };

const EXPRESSIONS = ['neutral', 'happy', 'excited', 'think', 'surprised', 'sad', 'wink', 'determined'];

function drawFace(ctx, look, expr, mouthOpen, blink, lookX, lookY) {
  const S = 64;
  ctx.fillStyle = look.skin; ctx.fillRect(0, 0, S, S);
  // subtle shading at the jaw
  ctx.fillStyle = 'rgba(0,0,0,.08)'; ctx.fillRect(0, 52, S, 12);
  // hair fringe
  ctx.fillStyle = look.hair;
  ctx.fillRect(0, 0, S, 13);
  for (let i = 0; i < 8; i++) ctx.fillRect(i * 8 + (i % 2) * 2, 12, 6, 4 + ((i * 5) % 4));
  ctx.fillRect(0, 0, 5, 30); ctx.fillRect(S - 5, 0, 5, 30);
  // eyes
  const ey = 28, exL = 18, exR = 46;
  const eye = (cx, closed) => {
    if (closed || blink) { ctx.fillStyle = '#2a1b12'; ctx.fillRect(cx - 6, ey + 1, 12, 3); return; }
    ctx.fillStyle = '#fff'; ctx.fillRect(cx - 6, ey - 5, 12, 11);
    ctx.fillStyle = '#3a7bd5'; ctx.fillRect(cx - 3 + lookX * 2, ey - 3 + lookY, 6, 7);
    ctx.fillStyle = '#10131a'; ctx.fillRect(cx - 1 + lookX * 2, ey - 1 + lookY, 3, 4);
    ctx.fillStyle = '#fff'; ctx.fillRect(cx + lookX * 2, ey - 2 + lookY, 1, 1);
  };
  eye(exL, false); eye(exR, expr === 'wink');
  // brows
  ctx.fillStyle = look.hair;
  const brow = (cx, tilt, lift) => { for (let i = -6; i < 6; i += 2) ctx.fillRect(cx + i, ey - 10 - lift + Math.round(i * tilt / 6), 3, 3); };
  const b = { neutral: [0, 0], happy: [0, 2], excited: [0, 4], think: [2, 1], surprised: [0, 5], sad: [-3, 0], wink: [0, 2], determined: [3, -1] }[expr] || [0, 0];
  brow(exL, -b[0], b[1]); brow(exR, b[0], expr === 'think' ? b[1] + 3 : b[1]);
  // cheeks
  if (['happy', 'excited', 'wink'].includes(expr)) { ctx.fillStyle = 'rgba(230,90,80,.35)'; ctx.fillRect(8, 38, 8, 4); ctx.fillRect(48, 38, 8, 4); }
  // mouth
  ctx.fillStyle = '#5a2418';
  const mx = 32, my = 46;
  if (mouthOpen > 0.15) {
    const h = 3 + Math.round(mouthOpen * 7);
    ctx.fillRect(mx - 7, my - 1, 14, h);
    ctx.fillStyle = '#c94a4a'; ctx.fillRect(mx - 5, my + h - 3, 10, 2);
    ctx.fillStyle = '#fff'; ctx.fillRect(mx - 6, my - 1, 12, 2);
  } else if (expr === 'happy' || expr === 'excited' || expr === 'wink') {
    ctx.fillRect(mx - 9, my - 2, 2, 2); ctx.fillRect(mx + 7, my - 2, 2, 2); ctx.fillRect(mx - 7, my, 14, 3);
    if (expr === 'excited') { ctx.fillStyle = '#fff'; ctx.fillRect(mx - 6, my, 12, 1); }
  } else if (expr === 'sad') {
    ctx.fillRect(mx - 6, my + 1, 12, 2); ctx.fillRect(mx - 8, my + 3, 2, 2); ctx.fillRect(mx + 6, my + 3, 2, 2);
  } else if (expr === 'surprised') {
    ctx.fillRect(mx - 3, my - 2, 6, 7);
  } else if (expr === 'think') {
    ctx.fillRect(mx - 2, my, 9, 2);
  } else if (expr === 'determined') {
    ctx.fillRect(mx - 7, my, 14, 2); ctx.fillRect(mx + 5, my - 2, 2, 2);
  } else {
    ctx.fillRect(mx - 6, my, 12, 2);
  }
}

function solid(color) { return new THREE.MeshLambertMaterial({ color }); }

function box(w, h, d, mat, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  return m;
}

function pivot(x, y, z, ...children) {
  const g = new THREE.Group();
  g.position.set(x, y, z);
  children.forEach(c => g.add(c));
  return g;
}

/** Build Flint. Units: 1 = one Minecraft pixel-ish block-person is ~2.1 tall. */
export function createCharacter(look = LOOK_DEFAULTS) {
  look = { ...LOOK_DEFAULTS, ...look };
  const root = new THREE.Group();
  const body = new THREE.Group();          // everything above the feet, bobs/leans
  root.add(body);
  const M = {
    skin: solid(look.skin), hair: solid(look.hair), hoodie: solid(look.hoodie),
    hoodieDark: solid(new THREE.Color(look.hoodie).multiplyScalar(0.72)), pants: solid(look.pants),
    shoes: solid(look.shoes), bandana: solid(look.bandana), belt: solid('#6b4a2b'), metal: solid('#b9c0c8'),
    goggle: new THREE.MeshLambertMaterial({ color: '#7fd3ff', emissive: '#103850' }),
  };

  // face texture (redrawn for expressions / lip-sync)
  const faceCanvas = document.createElement('canvas');
  faceCanvas.width = faceCanvas.height = 64;
  const faceCtx = faceCanvas.getContext('2d');
  const faceTex = new THREE.CanvasTexture(faceCanvas);
  faceTex.magFilter = THREE.NearestFilter; faceTex.minFilter = THREE.NearestFilter;
  faceTex.colorSpace = THREE.SRGBColorSpace;
  const faceMat = new THREE.MeshLambertMaterial({ map: faceTex });

  // legs (pivot at hip)
  const legL = pivot(-0.16, 0.75, 0, box(0.3, 0.6, 0.32, M.pants, 0, -0.3, 0), box(0.32, 0.16, 0.38, M.shoes, 0, -0.68, 0.03));
  const legR = pivot(0.16, 0.75, 0, box(0.3, 0.6, 0.32, M.pants, 0, -0.3, 0), box(0.32, 0.16, 0.38, M.shoes, 0, -0.68, 0.03));
  body.add(legL, legR);
  // torso + hoodie details + tool belt
  const torso = new THREE.Group();
  torso.position.y = 0.75;
  torso.add(box(0.64, 0.66, 0.36, M.hoodie, 0, 0.33, 0));
  torso.add(box(0.66, 0.08, 0.38, M.belt, 0, 0.04, 0));
  torso.add(box(0.12, 0.1, 0.06, M.metal, 0, 0.04, 0.2));
  torso.add(box(0.14, 0.16, 0.12, M.belt, 0.26, -0.02, 0.17));            // pouch
  torso.add(box(0.06, 0.24, 0.06, M.metal, -0.27, -0.04, 0.17));          // hammer handle
  torso.add(box(0.16, 0.07, 0.08, M.metal, -0.27, 0.08, 0.17));           // hammer head
  torso.add(box(0.5, 0.18, 0.02, M.hoodieDark, 0, 0.22, 0.185));          // front pocket
  torso.add(box(0.06, 0.2, 0.02, M.bandana, -0.1, 0.55, 0.185));          // drawstrings
  torso.add(box(0.06, 0.2, 0.02, M.bandana, 0.1, 0.55, 0.185));
  body.add(torso);
  // arms (pivot at shoulder)
  const mkArm = s => {
    const a = pivot(s * 0.44, 1.37, 0,
      box(0.26, 0.5, 0.3, M.hoodie, 0, -0.22, 0),
      box(0.27, 0.07, 0.31, M.hoodieDark, 0, -0.47, 0),
      box(0.24, 0.16, 0.26, M.skin, 0, -0.57, 0));
    return a;
  };
  const armL = mkArm(-1), armR = mkArm(1);
  body.add(armL, armR);
  // held block in the right hand (shown while building)
  const held = box(0.26, 0.26, 0.26, solid('#9a6b3f'), 0, -0.68, 0.14);
  held.visible = false;
  armR.add(held);
  // head (pivot at neck)
  const head = new THREE.Group();
  head.position.y = 1.43;
  const skull = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.62, 0.6),
    [M.skin, M.skin, M.hair, M.skin, faceMat, M.hair]);       // +x,-x,+y,-y,+z(front),-z(back)
  skull.position.y = 0.31;
  head.add(skull);
  head.add(box(0.66, 0.14, 0.64, M.hair, 0, 0.6, 0));                      // hair top
  head.add(box(0.66, 0.36, 0.1, M.hair, 0, 0.42, -0.28));                  // hair back
  for (let i = 0; i < 4; i++) head.add(box(0.14, 0.12, 0.14, M.hair, -0.24 + i * 0.16, 0.71, 0.05 - (i % 2) * 0.12)); // spikes
  head.add(box(0.68, 0.1, 0.66, M.bandana, 0, 0.53, 0));                   // bandana
  head.add(box(0.14, 0.22, 0.06, M.bandana, -0.12, 0.38, -0.34));          // bandana tails
  head.add(box(0.12, 0.18, 0.06, M.bandana, 0.02, 0.36, -0.35));
  const goggles = new THREE.Group();
  goggles.add(box(0.7, 0.05, 0.68, solid('#2b2b2b'), 0, 0, 0));
  goggles.add(box(0.16, 0.12, 0.05, M.goggle, -0.13, 0, 0.34));
  goggles.add(box(0.16, 0.12, 0.05, M.goggle, 0.13, 0, 0.34));
  goggles.position.y = 0.66;
  head.add(goggles);
  body.add(head);

  root.traverse(o => { if (o.isMesh) { o.castShadow = true; } });

  const face = { expr: 'happy', mouth: 0, blink: false, lookX: 0, lookY: 0, dirty: true };
  const redraw = () => { drawFace(faceCtx, look, face.expr, face.mouth, face.blink, face.lookX, face.lookY); faceTex.needsUpdate = true; face.dirty = false; };
  redraw();

  return { root, parts: { body, head, torso, armL, armR, legL, legR, held, goggles }, face, redraw, look };
}

/** Plays named animations on a character. Call update(dt) every frame. */
export class Animator {
  constructor(ch) {
    this.ch = ch;
    this.t = 0;
    this.state = 'idle';
    this.stateT = 0;
    this.talking = 0;           // >0 while speaking (seconds left, or Infinity while TTS runs)
    this.nextBlink = 2;
    this.onceDone = null;
  }

  play(state, { once = false, duration = 0, then = 'idle' } = {}) {
    this.state = state;
    this.stateT = 0;
    this.onceDone = once ? { at: duration || 1.6, then } : null;
    const P = this.ch.parts;
    P.held.visible = state === 'build';
  }

  express(expr) { if (this.ch.face.expr !== expr) { this.ch.face.expr = expr; this.ch.face.dirty = true; } }

  update(dt) {
    this.t += dt; this.stateT += dt;
    const t = this.t, s = this.stateT, P = this.ch.parts, F = this.ch.face;
    if (this.onceDone && s >= this.onceDone.at) { const n = this.onceDone.then; this.onceDone = null; this.play(n); }
    // reset pose
    for (const k of ['armL', 'armR', 'legL', 'legR', 'head', 'body', 'torso']) P[k].rotation.set(0, 0, 0);
    P.body.position.set(0, 0, 0);
    const breath = Math.sin(t * 2.2) * 0.012;
    P.torso.scale.y = 1 + breath;
    P.armL.rotation.z = -0.06; P.armR.rotation.z = 0.06;
    P.head.rotation.y = Math.sin(t * 0.5) * 0.08;

    const st = this.state;
    if (st === 'idle') {
      P.armL.rotation.x = Math.sin(t * 1.1) * 0.04; P.armR.rotation.x = -Math.sin(t * 1.1) * 0.04;
      if (Math.sin(t * 0.23) > 0.96) P.head.rotation.y = 0.5 * Math.sin(t * 3);          // looks around now and then
    } else if (st === 'wave') {
      P.armR.rotation.z = 2.6 + Math.sin(s * 10) * 0.35; P.head.rotation.z = Math.sin(s * 5) * 0.06;
    } else if (st === 'talk') {
      P.armR.rotation.x = -0.5 - Math.sin(s * 3) * 0.25; P.armR.rotation.z = 0.25;
      P.armL.rotation.x = -0.2 - Math.sin(s * 2.3 + 1) * 0.15;
      P.head.rotation.x = Math.sin(s * 6) * 0.04;
    } else if (st === 'walk' || st === 'run') {
      const k = st === 'run' ? 14 : 8, a = st === 'run' ? 0.9 : 0.55;
      P.legL.rotation.x = Math.sin(s * k) * a; P.legR.rotation.x = -Math.sin(s * k) * a;
      P.armL.rotation.x = -Math.sin(s * k) * a * 0.9; P.armR.rotation.x = Math.sin(s * k) * a * 0.9;
      P.body.position.y = Math.abs(Math.sin(s * k)) * 0.05;
    } else if (st === 'build') {
      const sw = Math.max(0, Math.sin(s * 9));
      P.armR.rotation.x = -1.6 + sw * 1.3;
      P.armL.rotation.x = -0.3;
      P.body.rotation.x = 0.08 + sw * 0.05;
      P.head.rotation.x = 0.25;
    } else if (st === 'think') {
      P.armR.rotation.x = -2.2; P.armR.rotation.z = 0.7;        // hand to chin
      P.armL.rotation.x = -0.6; P.armL.rotation.z = -0.5;
      P.head.rotation.z = 0.14; P.head.rotation.x = -0.15 + Math.sin(s * 1.5) * 0.04;
    } else if (st === 'celebrate') {
      const j = Math.abs(Math.sin(s * 6));
      P.body.position.y = j * 0.35;
      P.armL.rotation.z = -2.7 - Math.sin(s * 12) * 0.2; P.armR.rotation.z = 2.7 + Math.sin(s * 12) * 0.2;
      P.legL.rotation.x = -j * 0.4; P.legR.rotation.x = -j * 0.4;
    } else if (st === 'jump') {
      const p = Math.min(1, s / 0.7), h = Math.sin(p * Math.PI);
      P.body.position.y = h * 0.6; P.armL.rotation.z = -h * 1.2; P.armR.rotation.z = h * 1.2;
    } else if (st === 'sad') {
      P.head.rotation.x = 0.45; P.body.rotation.x = 0.1;
      P.armL.rotation.z = 0.05; P.armR.rotation.z = -0.05;
    } else if (st === 'point') {
      P.armR.rotation.x = -1.5; P.armR.rotation.y = 0.5; P.head.rotation.y = 0.45;
    } else if (st === 'dance') {
      P.body.rotation.y = Math.sin(s * 4) * 0.5; P.body.position.y = Math.abs(Math.sin(s * 8)) * 0.12;
      P.armL.rotation.z = -1.4 + Math.sin(s * 8) * 0.8; P.armR.rotation.z = 1.4 + Math.sin(s * 8 + Math.PI) * 0.8;
      P.legL.rotation.z = Math.max(0, Math.sin(s * 8)) * 0.4; P.legR.rotation.z = -Math.max(0, -Math.sin(s * 8)) * 0.4;
      P.head.rotation.z = Math.sin(s * 8) * 0.15;
    } else if (st === 'shrug') {
      const p = Math.min(1, s * 3);
      P.armL.rotation.z = -0.9 * p; P.armR.rotation.z = 0.9 * p; P.armL.rotation.x = P.armR.rotation.x = -0.6 * p;
      P.head.rotation.z = 0.2 * p;
    } else if (st === 'surprised') {
      const p = Math.min(1, s * 6);
      P.body.position.y = Math.sin(Math.min(1, s * 3) * Math.PI) * 0.2;
      P.armL.rotation.z = -0.9 * p; P.armR.rotation.z = 0.9 * p; P.head.rotation.x = -0.15 * p;
    } else if (st === 'search') {
      P.armR.rotation.x = -1.7; P.armR.rotation.z = 0.15;      // hand shading eyes
      P.armL.rotation.x = -0.25;
      P.head.rotation.y = Math.sin(s * 1.6) * 0.7; P.head.rotation.x = -0.1;
      P.goggles.position.y = 0.66 - Math.min(1, s * 2) * 0.26;  // goggles down
    } else if (st === 'type') {
      P.armL.rotation.x = -1.1 + Math.sin(s * 22) * 0.12; P.armR.rotation.x = -1.1 + Math.cos(s * 19) * 0.12;
      P.head.rotation.x = 0.3;
    }
    if (st !== 'search') P.goggles.position.y += (0.66 - P.goggles.position.y) * Math.min(1, dt * 6);

    // blinking
    this.nextBlink -= dt;
    if (this.nextBlink <= 0) { F.blink = true; F.dirty = true; if (this.nextBlink < -0.12) { F.blink = false; this.nextBlink = 2 + Math.random() * 3; } }
    // lip sync: a chattery open/close while talking
    if (this.talking > 0) {
      this.talking -= dt;
      const m = Math.max(0, Math.sin(t * 17) * 0.6 + Math.sin(t * 9.3) * 0.5);
      if (Math.abs(m - F.mouth) > 0.2) { F.mouth = m; F.dirty = true; }
    } else if (F.mouth) { F.mouth = 0; F.dirty = true; }
    // eyes drift a little
    const lx = Math.round(Math.sin(t * 0.7) * 0.7), ly = Math.round(Math.sin(t * 0.43) * 0.5);
    if (lx !== F.lookX || ly !== F.lookY) { F.lookX = lx; F.lookY = ly; F.dirty = true; }
    if (F.dirty) this.ch.redraw();
  }
}

export { EXPRESSIONS };
