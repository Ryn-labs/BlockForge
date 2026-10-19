// Flint v2: BlockForge's guide. A chunky, big-headed story-mode-style builder with a cartoon outline,
// customisable hair / hats / outfit / gear, emote bubbles, particles and ~40 animations.
import * as THREE from 'three';

export const LOOK_DEFAULTS = {
  skin: '#e0ac7e', hair: '#3b2416', hoodie: '#2f8f5b', pants: '#34405a', bandana: '#d9532b', shoes: '#4a3424',
  eyes: '#3a7bd5', hairStyle: 'messy', headwear: 'none', outfit: 'hoodie',
  goggles: true, backpack: true, cape: false, scarf: true, outline: true,
};
export const HAIR_STYLES = { messy: 'Messy', spiky: 'Spiky', ponytail: 'Ponytail', buzz: 'Buzz cut' };
export const HEADWEAR = { none: 'None', bandana: 'Bandana', hardhat: 'Hard hat', cap: 'Cap', beanie: 'Beanie', wizard: 'Wizard hat', crown: 'Crown' };
export const OUTFITS = { hoodie: 'Hoodie', overalls: 'Overalls', jacket: 'Jacket' };

// [id, label, group]
export const ANIMATIONS = [
  ['wave', 'Wave', 'Say hi'], ['nod', 'Nod', 'Say hi'], ['shake', 'Shake head', 'Say hi'], ['thumbsup', 'Thumbs up', 'Say hi'],
  ['salute', 'Salute', 'Say hi'], ['bow', 'Bow', 'Say hi'], ['shrug', 'Shrug', 'Say hi'], ['point', 'Point', 'Say hi'],
  ['talk', 'Talk', 'Say hi'],
  ['build', 'Build', 'Work'], ['hammer', 'Hammer', 'Work'], ['mine', 'Mine', 'Work'], ['type', 'Type', 'Work'],
  ['read', 'Read plans', 'Work'], ['search', 'Search', 'Work'], ['think', 'Think', 'Work'], ['idea', 'Bright idea', 'Work'],
  ['celebrate', 'Celebrate', 'Party'], ['victory', 'Victory', 'Party'], ['cheer', 'Cheer', 'Party'], ['clap', 'Clap', 'Party'],
  ['dance', 'Dance', 'Party'], ['disco', 'Disco', 'Party'], ['robot', 'Robot', 'Party'], ['moonwalk', 'Moonwalk', 'Party'],
  ['spin', 'Spin', 'Party'], ['jump', 'Jump', 'Party'], ['backflip', 'Backflip', 'Party'], ['flex', 'Flex', 'Party'],
  ['laugh', 'Laugh', 'Feelings'], ['love', 'Love', 'Feelings'], ['surprised', 'Surprised', 'Feelings'], ['scared', 'Scared', 'Feelings'],
  ['sad', 'Sad', 'Feelings'], ['angry', 'Angry', 'Feelings'], ['facepalm', 'Facepalm', 'Feelings'],
  ['walk', 'Walk', 'Move'], ['run', 'Run', 'Move'], ['sit', 'Sit', 'Rest'], ['stretch', 'Stretch', 'Rest'], ['sleep', 'Sleep', 'Rest'],
];
const EXPRESSIONS = ['neutral', 'happy', 'excited', 'think', 'surprised', 'sad', 'wink', 'determined', 'love', 'laugh',
  'sleepy', 'scared', 'smug', 'angry'];
export { EXPRESSIONS };

// expression: [brow angle (+ = angry), brow lift, eyes, mouth, blush, sweat]
const EXPR = {
  neutral: [0, 0, 'open', 'flat', 0, 0], happy: [0, 2, 'open', 'smile', 1, 0], excited: [0, 4, 'wide', 'grin', 1, 0],
  think: [-1, 1, 'open', 'side', 0, 0], surprised: [-1, 6, 'wide', 'o', 0, 0], sad: [-3, 1, 'open', 'frown', 0, 0],
  wink: [0, 2, 'wink', 'grin', 1, 0], determined: [3, -1, 'open', 'flat', 0, 0], love: [0, 3, 'heart', 'smile', 1, 0],
  laugh: [0, 3, 'happy', 'laugh', 1, 0], sleepy: [-1, -1, 'sleepy', 'flat', 0, 0], scared: [-2, 5, 'dots', 'wavy', 0, 1],
  smug: [2, 2, 'half', 'cat', 0, 0], angry: [5, -2, 'open', 'frown', 0, 0],
};

function drawFace(ctx, look, expr, mouthOpen, lid, lookX, lookY) {
  const S = 64, [angle, lift, eyes, mouth, blush, sweat] = EXPR[expr] || EXPR.neutral;
  ctx.clearRect(0, 0, S, S);
  ctx.fillStyle = look.skin; ctx.fillRect(0, 0, S, S);
  ctx.fillStyle = 'rgba(0,0,0,.07)'; ctx.fillRect(0, 54, S, 10);
  ctx.fillStyle = look.hair; ctx.fillRect(0, 0, S, 8);                          // forehead meets the hair
  const ey = 31, xs = [19, 45];
  const dark = '#2a1b12';
  xs.forEach((cx, side) => {
    const closed = eyes === 'happy' || (eyes === 'wink' && side === 1);
    if (eyes === 'heart') {
      ctx.fillStyle = '#e0245e';
      [[-4, -3, 3, 3], [1, -3, 3, 3], [-5, 0, 10, 2], [-4, 2, 8, 2], [-2, 4, 4, 2], [-1, 6, 2, 1]].forEach(([a, b, w, h]) => ctx.fillRect(cx + a, ey + b, w, h));
      ctx.fillStyle = '#ff9bb8'; ctx.fillRect(cx - 4, ey - 3, 1, 1);
    } else if (closed) {
      ctx.fillStyle = dark; ctx.fillRect(cx - 7, ey + 2, 3, 3); ctx.fillRect(cx - 4, ey - 1, 8, 3); ctx.fillRect(cx + 4, ey + 2, 3, 3);
    } else if (lid >= 0.95) {
      ctx.fillStyle = dark; ctx.fillRect(cx - 7, ey + 1, 14, 3);
    } else if (eyes === 'dots') {
      ctx.fillStyle = '#fff'; ctx.fillRect(cx - 7, ey - 7, 14, 15);
      ctx.fillStyle = dark; ctx.fillRect(cx - 1, ey - 1, 3, 3);
    } else {
      const w = eyes === 'wide' ? 16 : 14, h = eyes === 'wide' ? 17 : 15, y0 = ey - Math.floor(h / 2);
      ctx.fillStyle = dark; ctx.fillRect(cx - w / 2 - 1, y0 - 1, w + 2, h + 2);   // lash line / outline
      ctx.fillStyle = '#fff'; ctx.fillRect(cx - w / 2, y0, w, h);
      const ix = Math.round(cx - 4 + lookX * 2), iy = Math.round(ey - 5 + lookY + (eyes === 'wide' ? 0 : 1));
      ctx.fillStyle = look.eyes; ctx.fillRect(ix, iy, 8, 10);
      ctx.fillStyle = '#10131a'; ctx.fillRect(ix + 2, iy + 2, 4, 6);
      ctx.fillStyle = '#fff'; ctx.fillRect(ix + 1, iy + 1, 3, 3); ctx.fillRect(ix + 5, iy + 6, 2, 2);
      const cover = eyes === 'sleepy' ? 0.55 : eyes === 'half' ? 0.4 : lid;      // eyelid
      if (cover > 0.02) { ctx.fillStyle = look.skin; ctx.fillRect(cx - w / 2 - 1, y0 - 1, w + 2, Math.ceil((h + 2) * cover)); ctx.fillStyle = dark; ctx.fillRect(cx - w / 2 - 1, y0 - 1 + Math.ceil((h + 2) * cover), w + 2, 2); }
    }
    // brows
    ctx.fillStyle = look.hair;
    const dir = side === 0 ? 1 : -1;
    for (let i = 0; i < 12; i++) {
      const y = ey - 14 - lift + Math.round((i - 5.5) * dir * angle / 6);
      ctx.fillRect(cx - 6 + i, y, 1, 3);
    }
  });
  ctx.fillStyle = 'rgba(120,60,40,.35)'; ctx.fillRect(30, 40, 4, 3);              // nose
  if (blush) { ctx.fillStyle = 'rgba(235,90,90,.38)'; ctx.fillRect(6, 41, 9, 4); ctx.fillRect(49, 41, 9, 4); }
  const mx = 32, my = 47, m = '#5a2418';
  ctx.fillStyle = m;
  if (mouthOpen > 0.12 && mouth !== 'o') {
    const h = 3 + Math.round(mouthOpen * 8), w = 14 + Math.round(mouthOpen * 4);
    ctx.fillRect(mx - w / 2, my - 1, w, h);
    ctx.fillStyle = '#e8706a'; ctx.fillRect(mx - w / 2 + 2, my + h - 4, w - 4, 3);
    ctx.fillStyle = '#fff'; ctx.fillRect(mx - w / 2 + 1, my - 1, w - 2, 2);
  } else if (mouth === 'smile') {
    ctx.fillRect(mx - 9, my - 2, 2, 2); ctx.fillRect(mx + 7, my - 2, 2, 2); ctx.fillRect(mx - 7, my, 14, 3);
  } else if (mouth === 'grin') {
    ctx.fillRect(mx - 10, my - 2, 20, 2); ctx.fillRect(mx - 9, my, 18, 6); ctx.fillStyle = '#fff'; ctx.fillRect(mx - 8, my, 16, 2);
    ctx.fillStyle = '#e8706a'; ctx.fillRect(mx - 4, my + 4, 8, 2);
  } else if (mouth === 'laugh') {
    ctx.fillRect(mx - 11, my - 2, 22, 2); ctx.fillRect(mx - 10, my, 20, 9); ctx.fillStyle = '#fff'; ctx.fillRect(mx - 9, my, 18, 2);
    ctx.fillStyle = '#e8706a'; ctx.fillRect(mx - 5, my + 6, 10, 3);
  } else if (mouth === 'frown') {
    ctx.fillRect(mx - 6, my + 1, 12, 2); ctx.fillRect(mx - 8, my + 3, 2, 2); ctx.fillRect(mx + 6, my + 3, 2, 2);
  } else if (mouth === 'o') {
    ctx.fillRect(mx - 3, my - 2, 6, 8); ctx.fillStyle = '#c94a4a'; ctx.fillRect(mx - 2, my + 2, 4, 3);
  } else if (mouth === 'side') {
    ctx.fillRect(mx - 3, my, 10, 2); ctx.fillRect(mx + 7, my - 2, 2, 2);
  } else if (mouth === 'wavy') {
    for (let i = 0; i < 6; i++) ctx.fillRect(mx - 9 + i * 3, my + (i % 2) * 2, 3, 2);
  } else if (mouth === 'cat') {
    ctx.fillRect(mx - 8, my, 6, 2); ctx.fillRect(mx - 3, my + 2, 6, 2); ctx.fillRect(mx + 2, my, 6, 2);
  } else {
    ctx.fillRect(mx - 6, my, 12, 2);
  }
  if (sweat) { ctx.fillStyle = '#7fd0ff'; ctx.fillRect(54, 14, 4, 6); ctx.fillRect(55, 12, 2, 2); }
}

// ------------------------------------------------------------------ building blocks
const shade = (hex, f) => '#' + new THREE.Color(hex).multiplyScalar(f).getHexString();
const lighten = (hex, f) => '#' + new THREE.Color(hex).lerp(new THREE.Color('#ffffff'), f).getHexString();
const solid = c => new THREE.MeshLambertMaterial({ color: c });
function box(w, h, d, mat, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  return m;
}
function pivot(x, y, z, ...kids) {
  const g = new THREE.Group();
  g.position.set(x, y, z);
  kids.forEach(k => g.add(k));
  return g;
}

function addOutline(root) {
  const mat = new THREE.MeshBasicMaterial({ color: 0x18110c, side: THREE.BackSide });
  const list = [];
  root.traverse(o => { if (o.isMesh && o.geometry?.parameters && !o.userData.noOutline) list.push(o); });
  for (const m of list) {
    const p = m.geometry.parameters, grow = 0.05;
    const o = new THREE.Mesh(m.geometry, mat);
    o.position.copy(m.position); o.rotation.copy(m.rotation); o.quaternion.copy(m.quaternion);
    o.scale.set(m.scale.x * (1 + grow / Math.max(p.width, 0.05)), m.scale.y * (1 + grow / Math.max(p.height, 0.05)),
      m.scale.z * (1 + grow / Math.max(p.depth, 0.05)));
    o.userData.outline = true;
    m.parent.add(o);
  }
}

function makeEmote() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sp.scale.set(0.8, 0.8, 0.8); sp.visible = false; sp.renderOrder = 20;
  return { sp, c, tex, text: '' };
}

/** Build Flint. Roughly 2.2 units tall: a 0.78 head on a 0.62 body. */
export function createCharacter(look = LOOK_DEFAULTS) {
  look = { ...LOOK_DEFAULTS, ...look };
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const top = look.hoodie, M = {
    skin: solid(look.skin), hair: solid(look.hair), top: solid(top), topDark: solid(shade(top, 0.72)),
    topLight: solid(lighten(top, 0.45)), pants: solid(look.pants), pantsDark: solid(shade(look.pants, 0.7)),
    shoes: solid(look.shoes), sole: solid(shade(look.shoes, 0.5)), accent: solid(look.bandana), accentDark: solid(shade(look.bandana, 0.7)),
    belt: solid('#6b4a2b'), metal: solid('#b9c0c8'), wood: solid('#8a5f34'), gold: solid('#f0c63c'),
    dark: solid('#2b2b2b'), white: solid('#f2f2f2'),
    glass: new THREE.MeshLambertMaterial({ color: '#7fd3ff', emissive: '#14506f' }),
    lamp: new THREE.MeshLambertMaterial({ color: '#fff3a0', emissive: '#d8b300' }),
  };

  const faceCanvas = document.createElement('canvas');
  faceCanvas.width = faceCanvas.height = 64;
  const faceCtx = faceCanvas.getContext('2d');
  const faceTex = new THREE.CanvasTexture(faceCanvas);
  faceTex.magFilter = THREE.NearestFilter; faceTex.minFilter = THREE.NearestFilter; faceTex.colorSpace = THREE.SRGBColorSpace;
  const faceMat = new THREE.MeshLambertMaterial({ map: faceTex });

  // ---- legs (hip pivots at y .56)
  const mkLeg = s => pivot(s * 0.17, 0.56, 0,
    box(0.3, 0.42, 0.32, M.pants, 0, -0.21, 0), box(0.32, 0.06, 0.34, M.pantsDark, 0, -0.42, 0),
    box(0.34, 0.16, 0.44, M.shoes, 0, -0.5, 0.05), box(0.35, 0.05, 0.45, M.sole, 0, -0.55, 0.05));
  const legL = mkLeg(-1), legR = mkLeg(1);
  body.add(legL, legR);

  // ---- torso
  const torso = new THREE.Group();
  torso.position.y = 0.56;
  const out = look.outfit;
  torso.add(box(0.66, 0.64, 0.38, M.top, 0, 0.32, 0));
  torso.add(box(0.68, 0.08, 0.4, M.belt, 0, 0.04, 0));
  torso.add(box(0.12, 0.1, 0.05, M.gold, 0, 0.04, 0.21));
  if (out === 'hoodie') {
    torso.add(box(0.5, 0.2, 0.03, M.topDark, 0, 0.2, 0.2));                        // kangaroo pocket
    torso.add(box(0.05, 0.22, 0.03, M.white, -0.09, 0.5, 0.2)); torso.add(box(0.05, 0.22, 0.03, M.white, 0.09, 0.5, 0.2));
    torso.add(box(0.56, 0.16, 0.2, M.topDark, 0, 0.66, -0.2));                      // hood bundle
  } else if (out === 'overalls') {
    torso.add(box(0.42, 0.34, 0.03, M.pants, 0, 0.28, 0.2));                        // bib
    torso.add(box(0.08, 0.34, 0.4, M.pants, -0.21, 0.48, 0)); torso.add(box(0.08, 0.34, 0.4, M.pants, 0.21, 0.48, 0));
    torso.add(box(0.07, 0.07, 0.04, M.gold, -0.21, 0.4, 0.21)); torso.add(box(0.07, 0.07, 0.04, M.gold, 0.21, 0.4, 0.21));
    torso.add(box(0.14, 0.1, 0.04, M.pantsDark, 0, 0.34, 0.22));
  } else {                                                                          // jacket
    torso.add(box(0.2, 0.6, 0.03, M.topLight, 0, 0.32, 0.2));                       // tee
    torso.add(box(0.05, 0.6, 0.04, M.dark, 0, 0.32, 0.21));                         // zip
    torso.add(box(0.5, 0.12, 0.34, M.topDark, 0, 0.64, 0));                         // collar
  }
  torso.add(box(0.15, 0.17, 0.12, M.belt, 0.27, -0.02, 0.17));                      // pouch
  torso.add(box(0.06, 0.12, 0.06, M.metal, -0.27, -0.04, 0.18));                    // tool on belt
  body.add(torso);

  // ---- backpack, cape
  let cape = null, packGroup = null;
  if (look.backpack) {
    packGroup = new THREE.Group();
    packGroup.add(box(0.5, 0.52, 0.22, M.accentDark, 0, 0.86, -0.3));
    packGroup.add(box(0.4, 0.2, 0.06, M.accent, 0, 0.78, -0.43));
    const roll = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.54, 12), M.accent);
    roll.rotation.z = Math.PI / 2; roll.position.set(0, 1.18, -0.3); packGroup.add(roll);
    for (const s of [-1, 1]) packGroup.add(box(0.07, 0.5, 0.04, M.belt, s * 0.2, 0.84, 0.2));
    const pick = new THREE.Group();                                                  // pickaxe strapped on
    pick.add(box(0.05, 0.62, 0.05, M.wood, 0, 0, 0)); pick.add(box(0.4, 0.07, 0.07, M.metal, 0, 0.3, 0));
    pick.position.set(0.22, 0.92, -0.43); pick.rotation.z = -0.3;
    packGroup.add(pick);
    body.add(packGroup);
  }
  if (look.cape) {
    cape = pivot(0, 1.14, -0.2, box(0.66, 0.95, 0.05, M.accent, 0, -0.48, -0.02), box(0.66, 0.1, 0.07, M.gold, 0, -0.03, 0));
    body.add(cape);
  }

  // ---- arms (shoulder pivots at y 1.1); the right hand can hold a tool
  const mkArm = s => {
    const g = pivot(s * 0.44, 1.1, 0,
      box(0.26, 0.4, 0.3, M.top, 0, -0.18, 0), box(0.27, 0.07, 0.31, M.topDark, 0, -0.4, 0),
      box(0.24, 0.15, 0.26, M.skin, 0, -0.52, 0));
    return g;
  };
  const armL = mkArm(-1), armR = mkArm(1);
  const hammer = new THREE.Group();
  hammer.add(box(0.07, 0.07, 0.46, M.wood, 0, -0.55, 0.1)); hammer.add(box(0.22, 0.16, 0.14, M.metal, 0, -0.55, 0.36));
  hammer.visible = false; armR.add(hammer);
  const pickaxe = new THREE.Group();
  pickaxe.add(box(0.07, 0.07, 0.56, M.wood, 0, -0.55, 0.12)); pickaxe.add(box(0.07, 0.1, 0.46, M.metal, 0, -0.55, 0.44).rotateY(0));
  const crossbar = box(0.5, 0.08, 0.08, M.metal, 0, -0.55, 0.4); pickaxe.add(crossbar);
  pickaxe.visible = false; armR.add(pickaxe);
  const paper = new THREE.Group();
  paper.add(box(0.34, 0.02, 0.44, M.white, 0, -0.5, 0.15));
  for (let i = 0; i < 4; i++) paper.add(box(0.26, 0.025, 0.02, M.accentDark, 0, -0.495, 0.02 + i * 0.1));
  paper.rotation.x = -0.5; paper.visible = false; armL.add(paper);
  body.add(armL, armR);

  // ---- head
  const head = new THREE.Group();
  head.position.y = 1.15;
  const skull = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.78, 0.76), [M.skin, M.skin, M.skin, M.skin, faceMat, M.skin]);
  skull.position.y = 0.39;
  head.add(skull);
  head.add(box(0.12, 0.16, 0.06, M.skin, 0, 0.36, 0.4).translateY(-0.08));          // nose bump (tiny)
  for (const s of [-1, 1]) head.add(box(0.06, 0.16, 0.1, M.skin, s * 0.4, 0.34, 0));  // ears
  let ponytail = null;
  const hairStyle = look.hairStyle, hw = look.headwear;
  const showHair = hw !== 'wizard' && hw !== 'hardhat';
  const hairTopY = hw === 'none' || hw === 'bandana' ? 0.8 : 0.78;
  if (showHair) {
    head.add(box(0.82, 0.14, 0.8, M.hair, 0, hairTopY, 0));
    head.add(box(0.82, 0.5, 0.12, M.hair, 0, 0.52, -0.37));
    if (hairStyle === 'messy') {
      [[-0.3, 0.2], [-0.15, 0.32], [0.0, 0.18], [0.16, 0.34], [0.31, 0.22]].forEach(([x, h]) => head.add(box(0.17, h, 0.1, M.hair, x, 0.8 - h / 2, 0.4)));
      for (const s of [-1, 1]) head.add(box(0.1, 0.32, 0.66, M.hair, s * 0.41, 0.62, -0.02));
      if (hw === 'none') { const a = box(0.09, 0.26, 0.09, M.hair, 0.12, 1.02, 0.05); a.rotation.z = -0.35; head.add(a); }
    } else if (hairStyle === 'spiky') {
      [[-0.3, 0.22, -0.05], [-0.1, 0.3, 0.1], [0.1, 0.26, -0.12], [0.3, 0.2, 0.08], [0, 0.22, -0.28], [-0.2, 0.18, 0.28], [0.22, 0.18, 0.28]]
        .forEach(([x, h, z], i) => { const sp = box(0.17, h, 0.17, M.hair, x, 0.87 + h / 2 - 0.08, z); sp.rotation.z = (i % 2 ? 0.25 : -0.25); head.add(sp); });
      head.add(box(0.7, 0.12, 0.1, M.hair, 0, 0.74, 0.4));
      for (const s of [-1, 1]) head.add(box(0.1, 0.26, 0.6, M.hair, s * 0.41, 0.62, -0.05));
    } else if (hairStyle === 'ponytail') {
      head.add(box(0.74, 0.12, 0.1, M.hair, 0, 0.74, 0.4));
      for (const s of [-1, 1]) head.add(box(0.1, 0.34, 0.66, M.hair, s * 0.41, 0.6, -0.02));
      ponytail = pivot(0, 0.72, -0.44, box(0.2, 0.62, 0.16, M.hair, 0, -0.3, -0.04), box(0.14, 0.08, 0.2, M.accent, 0, 0.02, 0));
      head.add(ponytail);
    }
  }
  // headwear
  const hatTop = 0.86;
  if (hw === 'bandana') {
    head.add(box(0.86, 0.1, 0.84, M.accent, 0, 0.66, 0));
    head.add(box(0.14, 0.26, 0.05, M.accent, -0.12, 0.5, -0.44)); head.add(box(0.12, 0.22, 0.05, M.accent, 0.04, 0.48, -0.45));
  } else if (hw === 'hardhat') {
    const y = solid('#f4c20d');
    head.add(box(0.92, 0.22, 0.9, y, 0, 0.9, 0)); head.add(box(0.2, 0.1, 0.94, solid('#ddae00'), 0, 1.04, 0));
    head.add(box(0.92, 0.05, 0.32, y, 0, 0.8, 0.56)); head.add(box(0.16, 0.12, 0.06, M.lamp, 0, 0.94, 0.47));
  } else if (hw === 'cap') {
    head.add(box(0.86, 0.18, 0.84, M.accent, 0, hatTop, 0)); head.add(box(0.72, 0.04, 0.34, M.accentDark, 0, 0.78, 0.56));
    head.add(box(0.16, 0.05, 0.05, M.white, 0, 0.9, 0.43));
  } else if (hw === 'beanie') {
    head.add(box(0.88, 0.24, 0.86, M.accent, 0, 0.88, 0)); head.add(box(0.9, 0.08, 0.88, M.accentDark, 0, 0.76, 0));
    head.add(box(0.2, 0.2, 0.2, M.white, 0, 1.08, 0));
  } else if (hw === 'wizard') {
    const p = solid('#6a3fb0');
    head.add(box(1.14, 0.05, 1.12, p, 0, 0.8, 0)); head.add(box(0.74, 0.22, 0.74, p, 0, 0.93, 0)); head.add(box(0.54, 0.22, 0.54, p, 0, 1.15, 0));
    head.add(box(0.34, 0.22, 0.34, p, 0, 1.37, 0)); const tip = box(0.16, 0.22, 0.16, p, 0.04, 1.58, 0); tip.rotation.z = -0.3; head.add(tip);
    head.add(box(0.76, 0.07, 0.76, M.gold, 0, 0.84, 0)); head.add(box(0.1, 0.1, 0.04, M.gold, 0, 1.0, 0.38));
  } else if (hw === 'crown') {
    head.add(box(0.8, 0.1, 0.8, M.gold, 0, 0.86, 0));
    [[-0.3, -0.3], [0.3, -0.3], [-0.3, 0.3], [0.3, 0.3], [0, 0]].forEach(([x, z], i) => head.add(box(0.14, i === 4 ? 0.26 : 0.2, 0.14, M.gold, x, 0.98 + (i === 4 ? 0.03 : 0), z)));
    head.add(box(0.1, 0.1, 0.04, solid('#d02a2a'), 0, 0.88, 0.41));
  }
  const goggles = new THREE.Group();
  if (look.goggles) {
    goggles.add(box(0.86, 0.08, 0.84, M.dark, 0, 0, 0));
    for (const s of [-1, 1]) { goggles.add(box(0.24, 0.2, 0.07, M.dark, s * 0.17, 0, 0.42)); goggles.add(box(0.19, 0.15, 0.08, M.glass, s * 0.17, 0, 0.43)); }
    goggles.add(box(0.1, 0.07, 0.07, M.dark, 0, 0, 0.42));
    goggles.position.y = hw === 'none' || hw === 'bandana' ? 0.64 : 0.62;
    head.add(goggles);
  }
  body.add(head);

  // ---- scarf
  let scarfTail = null;
  if (look.scarf) {
    body.add(box(0.74, 0.14, 0.52, M.accent, 0, 1.17, 0));
    scarfTail = pivot(-0.22, 1.12, 0.27, box(0.17, 0.52, 0.05, M.accent, 0, -0.26, 0), box(0.17, 0.06, 0.06, M.accentDark, 0, -0.5, 0));
    body.add(scarfTail);
  }

  // ---- ground shadow + particle layer + emote
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.5, 20), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.28 }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = 0.015; shadow.userData.noOutline = true;
  root.add(shadow);
  const fx = new THREE.Group(); root.add(fx);
  const emote = makeEmote();
  emote.sp.position.set(0.5, 2.55, 0); root.add(emote.sp);
  if (look.outline) addOutline(root);

  const face = { expr: 'happy', mouth: 0, lid: 0, lookX: 0, lookY: 0, dirty: true };
  const redraw = () => { drawFace(faceCtx, look, face.expr, face.mouth, face.lid, face.lookX, face.lookY); faceTex.needsUpdate = true; face.dirty = false; };
  redraw();
  return { root, parts: { body, head, torso, armL, armR, legL, legR, goggles, cape, scarfTail, ponytail, packGroup, shadow, fx, hammer, pickaxe, paper },
    held: { hammer, pickaxe, paper }, emote, face, redraw, look, goggleY: goggles.position.y };
}

// ------------------------------------------------------------------ animation
const STATE_EXPR = { sleep: 'sleepy', stretch: 'sleepy', laugh: 'laugh', love: 'love', scared: 'scared', angry: 'angry', idea: 'excited',
  thumbsup: 'wink', victory: 'excited', cheer: 'excited', celebrate: 'excited', salute: 'determined', flex: 'smug', mine: 'determined',
  hammer: 'determined', bow: 'happy', facepalm: 'sad', sad: 'sad', dance: 'happy', disco: 'wink', robot: 'neutral', spin: 'happy',
  backflip: 'excited', moonwalk: 'smug', surprised: 'surprised', think: 'think', clap: 'happy', read: 'think', sit: 'happy' };
const EMOTES = { think: '💭', idea: '💡', surprised: '❗', love: '❤️', sleep: '💤', celebrate: '🎉', victory: '🏆', thumbsup: '👍',
  clap: '👏', scared: '😱', angry: '💢', laugh: '😂', facepalm: '🤦', cheer: '📣', dance: '🎵', disco: '🎶', robot: '🤖', search: '🔍',
  read: '📖', mine: '⛏️', hammer: '🔨', stretch: '😪', moonwalk: '🎵', flex: '💪', salute: '🎖️', bow: '🙇', sad: '😢', backflip: '🤸' };
const HELD = { build: 'hammer', hammer: 'hammer', mine: 'pickaxe', read: 'paper' };
const MOTION = { walk: 0.5, run: 1, moonwalk: 0.3, dance: 0.35, disco: 0.3, jump: 0.8, backflip: 1, spin: 0.9, celebrate: 0.6, cheer: 0.5, victory: 0.4, scared: 0.5 };
const FIDGETS = ['look', 'stretch', 'sway', 'tap', 'scratch', 'look'];
const ease = x => x * x * (3 - 2 * x);
const clamp01 = x => Math.max(0, Math.min(1, x));
const CONFETTI = ['#ff4d6d', '#ffd23f', '#3bceac', '#4ea8de', '#b983ff', '#ff9f1c'];

/** Plays named animations on a character. Call update(dt) every frame. */
export class Animator {
  constructor(ch) {
    this.ch = ch; this.t = 0; this.state = 'idle'; this.stateT = 0; this.talking = 0; this.nextBlink = 2;
    this.onceDone = null; this.levelFn = null; this.fidget = null; this.nextFidget = 6 + Math.random() * 5;
    this.particles = []; this.emoteT = 0; this.emoteMax = 0; this.sparkLast = -1;
    this.geo = new THREE.BoxGeometry(0.07, 0.07, 0.02);
    this.mats = {};
  }

  play(state, { once = false, duration = 0, then = 'idle', expr } = {}) {
    this.state = state; this.stateT = 0; this.sparkLast = -1;
    this.onceDone = once ? { at: duration || 1.6, then } : null;
    const held = HELD[state];
    for (const k of Object.keys(this.ch.held)) this.ch.held[k].visible = k === held;
    if (expr) this.express(expr); else if (STATE_EXPR[state]) this.express(STATE_EXPR[state]);
    if (EMOTES[state] && state !== 'sleep') this.emote(EMOTES[state], state === 'think' || state === 'search' || state === 'read' ? 2.6 : 1.8);
    if (state === 'sleep') this.emote('💤', 9999);
    if (state === 'celebrate' || state === 'victory') this.burst('confetti', 34);
    if (state === 'flex') this.burst('sparkle', 12);
  }

  express(expr) { if (this.ch.face.expr !== expr) { this.ch.face.expr = expr; this.ch.face.dirty = true; } }

  emote(text, secs = 1.8) {
    const e = this.ch.emote;
    if (e.text !== text) {
      const ctx = e.c.getContext('2d'); ctx.clearRect(0, 0, 128, 128);
      ctx.fillStyle = 'rgba(255,255,255,.95)'; ctx.strokeStyle = 'rgba(30,25,20,.9)'; ctx.lineWidth = 6;
      ctx.beginPath(); ctx.arc(64, 60, 52, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(28, 98); ctx.lineTo(18, 124); ctx.lineTo(52, 104); ctx.fill();
      ctx.font = '64px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = '#222'; ctx.fillText(text, 64, 64);
      e.tex.needsUpdate = true; e.text = text;
    }
    this.emoteT = secs; this.emoteMax = secs; e.sp.visible = true;
  }

  burst(kind, n = 24) {
    const fx = this.ch.parts.fx;
    for (let i = 0; i < n; i++) {
      const col = kind === 'confetti' ? CONFETTI[i % CONFETTI.length] : kind === 'spark' ? '#ffd23f' : '#fff3a0';
      const m = this.mats[col] || (this.mats[col] = new THREE.MeshBasicMaterial({ color: col, side: THREE.DoubleSide }));
      const p = new THREE.Mesh(this.geo, m);
      const a = Math.random() * Math.PI * 2, sp = kind === 'confetti' ? 1.2 + Math.random() * 1.6 : 0.8 + Math.random() * 1.4;
      p.position.set(Math.cos(a) * 0.2, kind === 'confetti' ? 2.3 : 1.0, Math.sin(a) * 0.2);
      p.userData = { v: [Math.cos(a) * sp, kind === 'confetti' ? 2.4 + Math.random() * 1.5 : 1.4 + Math.random() * 1.6, Math.sin(a) * sp],
        life: kind === 'confetti' ? 1.8 : 0.7, g: kind === 'confetti' ? 3.2 : 5, spin: (Math.random() - 0.5) * 14 };
      fx.add(p); this.particles.push(p);
    }
  }

  update(dt) {
    this.t += dt; this.stateT += dt;
    const t = this.t, s = this.stateT, P = this.ch.parts, F = this.ch.face, A = this;
    if (this.onceDone && s >= this.onceDone.at) { const n = this.onceDone.then; this.onceDone = null; this.play(n); }
    for (const k of ['armL', 'armR', 'legL', 'legR', 'head', 'body', 'torso']) { P[k].rotation.set(0, 0, 0); }
    P.body.position.set(0, 0, 0); P.torso.scale.set(1, 1, 1);
    P.armL.rotation.z = -0.07; P.armR.rotation.z = 0.07;
    P.torso.scale.y = 1 + Math.sin(t * 2.2) * 0.012;
    P.head.rotation.y = Math.sin(t * 0.5) * 0.08;
    const st = this.state, L = P.legL, R = P.legR, aL = P.armL, aR = P.armR, hd = P.head, bd = P.body, tr = P.torso;
    let hop = 0;

    const POSE = {
      idle: () => {
        aL.rotation.x = Math.sin(t * 1.1) * 0.04; aR.rotation.x = -Math.sin(t * 1.1) * 0.04;
        if (A.talking <= 0) {
          A.nextFidget -= dt;
          if (!A.fidget && A.nextFidget <= 0) { A.fidget = { name: FIDGETS[(Math.random() * FIDGETS.length) | 0], t0: t }; }
          if (A.fidget) {
            const ft = t - A.fidget.t0, n = A.fidget.name, dur = n === 'stretch' ? 2.4 : 2.2, p = Math.sin(Math.PI * clamp01(ft / dur));
            if (n === 'look') hd.rotation.y = Math.sin(ft * 2.2) * 0.7 * p;
            else if (n === 'stretch') { aR.rotation.z = 2.9 * p; aL.rotation.z = -2.9 * p; hd.rotation.x = -0.25 * p; bd.rotation.x = -0.08 * p; tr.scale.y *= 1 + 0.04 * p; }
            else if (n === 'sway') { bd.rotation.z = Math.sin(ft * 3.2) * 0.07 * p; hd.rotation.z = -Math.sin(ft * 3.2) * 0.07 * p; if (ft < 0.1) A.emote('🎵', 2); }
            else if (n === 'tap') { R.rotation.x = -Math.abs(Math.sin(ft * 9)) * 0.32 * p; aL.rotation.x += 0.15 * p; }
            else if (n === 'scratch') { aR.rotation.x = -2.2 * p; aR.rotation.z = 0.45 * p; aR.rotation.x += Math.sin(ft * 16) * 0.12 * p; hd.rotation.z = 0.12 * p; }
            if (ft > dur) { A.fidget = null; A.nextFidget = 7 + Math.random() * 7; }
          }
        } else A.fidget = null;
      },
      talk: () => {
        aR.rotation.x = -0.5 - Math.sin(s * 3) * 0.25; aR.rotation.z = 0.25 + Math.sin(s * 1.7) * 0.15;
        aL.rotation.x = -0.2 - Math.sin(s * 2.3 + 1) * 0.15; hd.rotation.x = Math.sin(s * 6) * 0.04; hd.rotation.z = Math.sin(s * 1.3) * 0.05;
        bd.rotation.y = Math.sin(s * 0.9) * 0.08;
      },
      wave: () => { aR.rotation.z = 2.6 + Math.sin(s * 10) * 0.35; hd.rotation.z = Math.sin(s * 5) * 0.06; },
      nod: () => { hd.rotation.x = Math.sin(s * 9) * 0.28 * (1 - clamp01(s / 1.4) * 0.5); },
      shake: () => { hd.rotation.y = Math.sin(s * 13) * 0.5; },
      thumbsup: () => { const p = ease(clamp01(s * 4)); aR.rotation.x = -1.3 * p; aR.rotation.z = 0.35 * p; hd.rotation.z = 0.08 * p; bd.position.y = Math.abs(Math.sin(s * 6)) * 0.03 * p; },
      salute: () => { const p = ease(clamp01(s * 5)); aR.rotation.x = -2.45 * p; aR.rotation.z = 0.55 * p; hd.rotation.x = -0.08 * p; bd.rotation.x = -0.03 * p; },
      bow: () => { const p = Math.sin(Math.PI * clamp01(s / 1.6)); bd.rotation.x = 0.5 * p; aL.rotation.x = -0.3 * p; aR.rotation.x = -0.3 * p; hd.rotation.x = -0.1 * p; bd.position.z = 0.12 * p; },
      shrug: () => { const p = ease(clamp01(s * 3)); aL.rotation.z = -0.95 * p; aR.rotation.z = 0.95 * p; aL.rotation.x = aR.rotation.x = -0.6 * p; hd.rotation.z = 0.2 * p; tr.scale.y *= 1 - 0.03 * p; },
      point: () => { aR.rotation.x = -1.5; aR.rotation.y = 0.5; hd.rotation.y = 0.45; bd.rotation.y = 0.2; },
      build: () => { const sw = Math.max(0, Math.sin(s * 9)); aR.rotation.x = -1.6 + sw * 1.3; aL.rotation.x = -0.3; bd.rotation.x = 0.08 + sw * 0.05; hd.rotation.x = 0.25; },
      hammer: () => {
        const ph = (s * 1.25) % 1, raise = ease(clamp01(ph / 0.6)), strike = ease(clamp01((ph - 0.6) / 0.12));
        aR.rotation.x = ph < 0.6 ? -0.3 - 2.5 * raise : -2.8 + 2.6 * strike;
        aR.rotation.z = 0.2; aL.rotation.x = -0.9; hd.rotation.x = 0.2;
        bd.rotation.x = ph < 0.6 ? -0.1 * raise : -0.1 + 0.3 * strike;
        bd.position.y = ph >= 0.6 ? -0.05 * strike : 0;
        const cyc = Math.floor(s * 1.25);
        if (ph >= 0.72 && cyc !== A.sparkLast) { A.sparkLast = cyc; A.burst('spark', 8); }
      },
      mine: () => {
        const ph = (s * 1.1) % 1, up = ph < 0.6, p = up ? ease(ph / 0.6) : 1, d = up ? 0 : ease(clamp01((ph - 0.6) / 0.15));
        aR.rotation.x = up ? -2.8 * p : -2.8 + 2.9 * d; aR.rotation.z = 0.15; aL.rotation.x = up ? -2.2 * p : -2.2 + 1.7 * d; aL.rotation.z = -0.1;
        bd.rotation.x = up ? -0.1 * p : -0.1 + 0.28 * d; hd.rotation.x = up ? 0.05 : -0.12; L.rotation.x = -0.15 * p; R.rotation.x = 0.1;
        const cyc = Math.floor(s * 1.1); if (!up && cyc !== A.sparkLast && d > 0.9) { A.sparkLast = cyc; A.burst('spark', 9); }
      },
      type: () => { aL.rotation.x = -1.1 + Math.sin(s * 22) * 0.12; aR.rotation.x = -1.1 + Math.cos(s * 19) * 0.12; hd.rotation.x = 0.3; bd.rotation.x = 0.06; },
      read: () => { aL.rotation.x = -1.2; aL.rotation.z = -0.1; aR.rotation.x = -0.5 - Math.abs(Math.sin(s * 0.7)) * 0.5; aR.rotation.z = 0.3; hd.rotation.x = 0.4; hd.rotation.y = Math.sin(s * 1.1) * 0.12; },
      search: () => {
        aR.rotation.x = -1.7; aR.rotation.z = 0.15; aL.rotation.x = -0.25; hd.rotation.y = Math.sin(s * 1.6) * 0.7; hd.rotation.x = -0.1;
        P.goggles.position.y = A.ch.goggleY - ease(clamp01(s * 2)) * 0.25;
      },
      think: () => { aR.rotation.x = -2.2; aR.rotation.z = 0.7; aL.rotation.x = -0.6; aL.rotation.z = -0.5; hd.rotation.z = 0.14; hd.rotation.x = -0.15 + Math.sin(s * 1.5) * 0.04; },
      idea: () => { const p = ease(clamp01(s * 5)); aR.rotation.z = 2.9 * p; aR.rotation.x = -0.2 * p; hop = Math.sin(clamp01(s * 3) * Math.PI) * 0.18; hd.rotation.x = -0.18 * p; aL.rotation.x = -0.4 * p; },
      celebrate: () => { const j = Math.abs(Math.sin(s * 6)); hop = j * 0.35; aL.rotation.z = -2.7 - Math.sin(s * 12) * 0.2; aR.rotation.z = 2.7 + Math.sin(s * 12) * 0.2; L.rotation.x = R.rotation.x = -j * 0.4; },
      victory: () => { const p = ease(clamp01(s * 5)); aR.rotation.z = 2.5 * p; aR.rotation.x = -0.4 * p + Math.sin(s * 8) * 0.2 * p; aL.rotation.z = -0.5 * p; hop = Math.abs(Math.sin(s * 5)) * 0.12; hd.rotation.x = -0.2 * p; bd.rotation.z = -0.06 * p; },
      cheer: () => { hop = Math.abs(Math.sin(s * 7)) * 0.22; aR.rotation.z = 2.7 + Math.sin(s * 14) * 0.35; aL.rotation.z = -2.7 + Math.sin(s * 14 + 2) * 0.35; hd.rotation.x = -0.15; },
      clap: () => { const c = 0.5 + 0.5 * Math.sin(s * 16); aR.rotation.x = aL.rotation.x = -1.35; aR.rotation.z = -0.04 + 0.4 * c; aL.rotation.z = 0.04 - 0.4 * c; hop = Math.abs(Math.sin(s * 8)) * 0.04; hd.rotation.x = 0.1; },
      dance: () => { bd.rotation.y = Math.sin(s * 4) * 0.5; hop = Math.abs(Math.sin(s * 8)) * 0.12; aL.rotation.z = -1.4 + Math.sin(s * 8) * 0.8; aR.rotation.z = 1.4 + Math.sin(s * 8 + Math.PI) * 0.8; L.rotation.z = Math.max(0, Math.sin(s * 8)) * 0.4; R.rotation.z = -Math.max(0, -Math.sin(s * 8)) * 0.4; hd.rotation.z = Math.sin(s * 8) * 0.15; },
      disco: () => { const b = Math.floor(s * 3) % 2; const q = ease(0.5 + 0.5 * Math.sin(s * 6)); aR.rotation.z = b ? 0.4 + 2.2 * q : 0.2; aR.rotation.x = b ? -0.3 * q : 0; aL.rotation.z = b ? -0.2 : -0.4 - 2.2 * q; bd.rotation.z = (b ? 1 : -1) * 0.1 * q; hop = Math.abs(Math.sin(s * 6)) * 0.06; hd.rotation.z = (b ? -1 : 1) * 0.12 * q; L.rotation.z = b ? 0.1 : 0; },
      robot: () => { const k = Math.floor(s * 4) % 4; const pose = [[-1.4, 0, 0, -1.4], [-1.4, 0, -1.4, 0], [0, 1.2, -1.4, 0], [-0.2, 1.3, -0.2, 1.3]][k]; aR.rotation.x = pose[0]; aR.rotation.z = Math.max(0.07, pose[1]); aL.rotation.x = pose[2]; aL.rotation.z = -Math.max(0.07, pose[3]); hd.rotation.y = [0.5, 0, -0.5, 0][k]; bd.rotation.y = [0.2, 0, -0.2, 0][k]; },
      moonwalk: () => { const w = Math.sin(s * 7); L.rotation.x = w * 0.5 + 0.2; R.rotation.x = -w * 0.5 + 0.2; bd.rotation.x = -0.08; aL.rotation.x = -w * 0.3; aR.rotation.x = w * 0.3; hd.rotation.x = -0.1; hop = Math.abs(w) * 0.03; },
      spin: () => { const p = clamp01(s / 1.2); bd.rotation.y = ease(p) * Math.PI * 4; aL.rotation.z = -1.5; aR.rotation.z = 1.5; hop = Math.sin(p * Math.PI) * 0.25; },
      jump: () => { const p = clamp01(s / 0.7), h = Math.sin(p * Math.PI); hop = h * 0.6; aL.rotation.z = -h * 1.2; aR.rotation.z = h * 1.2; L.rotation.x = R.rotation.x = -h * 0.3; },
      backflip: () => {
        const p = ease(clamp01(s / 1.0)), th = -Math.PI * 2 * p, h = Math.sin(clamp01(s / 1.0) * Math.PI) * 0.7;
        bd.rotation.x = th; bd.position.set(0, 1.0 - Math.cos(th) + h, -Math.sin(th));
        aL.rotation.z = -0.7; aR.rotation.z = 0.7; L.rotation.x = R.rotation.x = -0.4 * Math.sin(p * Math.PI);
      },
      flex: () => { const p = ease(clamp01(s * 4)), v = Math.sin(s * 14) * 0.03 * p; aR.rotation.z = 1.7 * p; aL.rotation.z = -1.7 * p; aR.rotation.x = -0.5 * p; aL.rotation.x = -0.5 * p; tr.scale.set(1 + 0.1 * p + v, 1 + 0.03 * p, 1 + 0.08 * p); hd.rotation.x = -0.12 * p; L.rotation.z = 0.12 * p; R.rotation.z = -0.12 * p; },
      laugh: () => { const sh = Math.sin(s * 18); hop = Math.abs(sh) * 0.04; hd.rotation.x = -0.28 + sh * 0.04; bd.rotation.x = -0.06; aL.rotation.x = -0.5; aL.rotation.z = -0.3; aR.rotation.x = -0.5; aR.rotation.z = 0.3; tr.scale.y *= 1 + sh * 0.02; A.talking = Math.max(A.talking, 0.2); F.mouth = Math.max(0, 0.5 + sh * 0.4); F.dirty = true; },
      love: () => { aL.rotation.x = -1.0; aL.rotation.z = 0.35; aR.rotation.x = -1.0; aR.rotation.z = -0.35; hd.rotation.z = Math.sin(s * 2.4) * 0.14; bd.rotation.z = Math.sin(s * 2.4) * 0.05; bd.position.y = Math.abs(Math.sin(s * 4.8)) * 0.03; if (Math.floor(s * 2) !== A.sparkLast) { A.sparkLast = Math.floor(s * 2); A.emote('❤️', 1.2); } },
      surprised: () => { const p = ease(clamp01(s * 6)); hop = Math.sin(clamp01(s * 3) * Math.PI) * 0.2; aL.rotation.z = -0.9 * p; aR.rotation.z = 0.9 * p; hd.rotation.x = -0.15 * p; bd.rotation.x = -0.05 * p; },
      scared: () => { const sh = Math.sin(s * 40) * 0.025; bd.position.x = sh; aL.rotation.x = aR.rotation.x = -1.9; aL.rotation.z = -0.15; aR.rotation.z = 0.15; hd.rotation.x = 0.12; bd.rotation.x = 0.1; L.rotation.z = 0.06; R.rotation.z = -0.06; },
      sad: () => { hd.rotation.x = 0.28; bd.rotation.x = 0.08; aL.rotation.z = -0.05; aR.rotation.z = 0.05; tr.scale.y *= 0.98; },
      angry: () => { const sh = Math.sin(s * 28) * 0.02; bd.position.x = sh; aL.rotation.x = aR.rotation.x = -0.25; aL.rotation.z = -0.25; aR.rotation.z = 0.25; hd.rotation.x = 0.15; bd.rotation.x = 0.06; R.rotation.x = Math.max(0, Math.sin(s * 5)) * -0.4; },
      facepalm: () => { const p = ease(clamp01(s * 3)); aR.rotation.x = -2.15 * p; aR.rotation.z = -0.1 * p; hd.rotation.x = 0.35 * p; bd.rotation.x = 0.06 * p; aL.rotation.x = -0.1; },
      walk: () => { const k = 8, a = 0.55; L.rotation.x = Math.sin(s * k) * a; R.rotation.x = -Math.sin(s * k) * a; aL.rotation.x = -Math.sin(s * k) * a * 0.9; aR.rotation.x = Math.sin(s * k) * a * 0.9; hop = Math.abs(Math.sin(s * k)) * 0.05; },
      run: () => { const k = 14, a = 0.9; L.rotation.x = Math.sin(s * k) * a; R.rotation.x = -Math.sin(s * k) * a; aL.rotation.x = -Math.sin(s * k) * a * 0.9 - 0.3; aR.rotation.x = Math.sin(s * k) * a * 0.9 - 0.3; bd.rotation.x = 0.18; hop = Math.abs(Math.sin(s * k)) * 0.09; },
      sit: () => { L.rotation.x = R.rotation.x = -1.45; L.rotation.z = 0.12; R.rotation.z = -0.12; bd.position.y = -0.42; bd.position.z = -0.05; aL.rotation.x = -0.55; aR.rotation.x = -0.5; aL.rotation.z = -0.15; aR.rotation.z = 0.15; L.rotation.x += Math.sin(s * 3) * 0.06; R.rotation.x -= Math.sin(s * 3) * 0.06; },
      stretch: () => { const p = Math.sin(Math.PI * clamp01(s / 2.6)); aR.rotation.z = 2.95 * p; aL.rotation.z = -2.95 * p; hd.rotation.x = -0.3 * p; bd.rotation.x = -0.1 * p; tr.scale.y *= 1 + 0.05 * p; if (s > 1.4 && s < 2.2) { A.talking = 0.2; F.mouth = 0.9; F.dirty = true; } },
      sleep: () => { const br = Math.sin(t * 1.4); hd.rotation.x = 0.2 + br * 0.03; hd.rotation.z = 0.14; bd.rotation.x = 0.16; aL.rotation.z = -0.02; aR.rotation.z = 0.02; aL.rotation.x = 0.1; aR.rotation.x = 0.1; tr.scale.y *= 1 + br * 0.015; bd.position.y = -0.02; },
    };
    (POSE[st] || POSE.idle)();
    if (st !== 'search') P.goggles.position.y += (A.ch.goggleY - P.goggles.position.y) * Math.min(1, dt * 6);
    bd.position.y += hop;
    P.shadow.scale.setScalar(Math.max(0.55, 1 - (hop + (st === 'backflip' ? Math.max(0, bd.position.y - 0.4) * 0.3 : 0)) * 0.6));
    P.shadow.material.opacity = 0.28 * P.shadow.scale.x;

    // secondary motion: cape, scarf and ponytail follow how much the body is moving
    const mo = MOTION[st] || 0, fl = Math.sin(t * 9) * 0.5 + 0.5;
    if (P.cape) { P.cape.rotation.x = 0.06 + Math.sin(t * 1.5) * 0.03 + mo * (0.35 + 0.25 * fl) + (st === 'sleep' ? 0.05 : 0); P.cape.rotation.z = Math.sin(t * 2) * 0.02 * (1 + mo * 4); }
    if (P.scarfTail) { P.scarfTail.rotation.x = 0.1 + Math.sin(t * 2.1) * 0.05 + mo * (0.5 + 0.3 * fl); P.scarfTail.rotation.z = Math.sin(t * 3 + 1) * (0.06 + mo * 0.2); }
    if (P.ponytail) { P.ponytail.rotation.x = 0.1 + Math.sin(t * 1.8) * 0.06 + mo * (0.4 + 0.3 * fl) - hd.rotation.x * 0.5; P.ponytail.rotation.z = Math.sin(t * 2.6) * (0.08 + mo * 0.25); }

    // face: blink, eyelids, lip sync, drifting eyes
    this.nextBlink -= dt;
    const asleep = st === 'sleep';
    let lid = asleep ? 1 : 0;
    if (!asleep && this.nextBlink <= 0) { lid = 1; if (this.nextBlink < -0.12) this.nextBlink = 2 + Math.random() * 3.5; }
    if (lid !== F.lid) { F.lid = lid; F.dirty = true; }
    if (this.talking > 0) {
      this.talking -= dt;
      const lv = this.levelFn?.();
      const m = lv != null ? Math.min(1, lv * 5) : Math.max(0, Math.sin(t * 17) * 0.6 + Math.sin(t * 9.3) * 0.5);
      if (Math.abs(m - F.mouth) > 0.2) { F.mouth = m; F.dirty = true; }
    } else if (F.mouth && st !== 'laugh' && st !== 'stretch') { F.mouth = 0; F.dirty = true; }
    const lx = Math.round(Math.sin(t * 0.7) * 0.7), ly = Math.round(Math.sin(t * 0.43) * 0.5);
    if (lx !== F.lookX || ly !== F.lookY) { F.lookX = lx; F.lookY = ly; F.dirty = true; }
    if (F.dirty) this.ch.redraw();

    // emote bubble
    const e = this.ch.emote;
    if (this.emoteT > 0) {
      this.emoteT -= dt;
      const age = this.emoteMax - this.emoteT, pop = clamp01(age / 0.22), sc = (0.55 + 0.4 * ease(pop) + (pop < 1 ? 0.18 * Math.sin(pop * Math.PI) : 0)) * (this.emoteMax > 100 ? 0.9 : 1);
      e.sp.scale.setScalar(sc * 0.85); e.sp.position.y = 2.5 + Math.sin(t * 3) * 0.04 + (this.emoteMax > 100 ? Math.sin(t * 1.2) * 0.08 : 0);
      e.sp.material.opacity = this.emoteMax > 100 ? 1 : clamp01(this.emoteT / 0.35);
      if (this.emoteT <= 0) e.sp.visible = false;
    } else if (e.sp.visible) e.sp.visible = false;
    // particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i], u = p.userData;
      u.life -= dt; u.v[1] -= u.g * dt;
      p.position.x += u.v[0] * dt; p.position.y += u.v[1] * dt; p.position.z += u.v[2] * dt;
      p.rotation.x += u.spin * dt; p.rotation.z += u.spin * 0.7 * dt;
      p.scale.setScalar(Math.max(0.01, Math.min(1, u.life * 2)));
      if (u.life <= 0) { p.parent?.remove(p); this.particles.splice(i, 1); }
    }
  }
}
