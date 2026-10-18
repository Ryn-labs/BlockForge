// Flint, the guide: a little 3D character in the corner with a story-mode dialogue box and a voice.
import * as THREE from 'three';
import { createCharacter, Animator, LOOK_DEFAULTS } from './character.js';

export const GUIDE_DEFAULTS = {
  enabled: true, name: 'Flint', voice: 'auto', voice_style: 'hd', hd_voice: 'joe', pitch: 1.0, rate: 1.0, volume: 0.9,
  chatty: 'normal', in_viewer: true, look: { ...LOOK_DEFAULTS },
};

const pick = a => a[(Math.random() * a.length) | 0];

// ---------------------------------------------------------------- voice
class Voice {
  constructor() {
    this.ctx = null;
    this.voices = [];
    const load = () => { this.voices = (window.speechSynthesis?.getVoices() || []); };
    load();
    window.speechSynthesis?.addEventListener?.('voiceschanged', load);
  }

  list() { return this.voices.filter(v => /^en/i.test(v.lang)).concat(this.voices.filter(v => !/^en/i.test(v.lang))); }

  choose(pref) {
    const vs = this.list();
    if (pref && pref !== 'auto') { const v = vs.find(v => v.voiceURI === pref || v.name === pref); if (v) return v; }
    return vs.find(v => /Guy|Ryan|Davis|Andrew|Brian|Christopher|Eric|Mark/i.test(v.name) && /en-(US|GB)/i.test(v.lang))
      || vs.find(v => /en-(US|GB)/i.test(v.lang)) || vs[0] || null;
  }

  stop() {
    this.token = (this.token || 0) + 1;
    try { window.speechSynthesis?.cancel(); } catch {}
    this.blipStop = true;
    if (this.src) { try { this.src.onended = null; this.src.stop(); } catch {} this.src = null; this.analyser = null; }
  }

  /** How loud the HD voice is right now (0..1), for lip sync. */
  level() {
    if (!this.analyser) return null;
    const a = this.levelBuf || (this.levelBuf = new Uint8Array(this.analyser.fftSize));
    this.analyser.getByteTimeDomainData(a);
    let sum = 0;
    for (let i = 0; i < a.length; i++) { const v = (a[i] - 128) / 128; sum += v * v; }
    return Math.sqrt(sum / a.length);
  }

  unlock() {
    try { this.ctx = this.ctx || new AudioContext(); if (this.ctx.state === 'suspended') this.ctx.resume(); } catch {}
  }

  /** Natural offline voice made by the BlockForge app (Piper). Falls back to the Windows voice. */
  async hd(text, cfg, onStart, onEnd) {
    const token = this.token;
    try {
      const r = await fetch(`/api/tts?voice=${encodeURIComponent(cfg.hd_voice || 'joe')}&speed=${cfg.rate}&text=${encodeURIComponent(text)}`);
      if (!r.ok) throw new Error('tts ' + r.status);
      const buf = await r.arrayBuffer();
      this.unlock();
      const audio = await this.ctx.decodeAudioData(buf);
      if (token !== this.token) return;                     // a newer line started meanwhile
      const src = this.ctx.createBufferSource();
      src.buffer = audio;
      const an = this.ctx.createAnalyser(); an.fftSize = 512;
      const g = this.ctx.createGain(); g.gain.value = cfg.volume;
      src.connect(an); an.connect(g); g.connect(this.ctx.destination);
      this.src = src; this.analyser = an;
      src.onended = () => { if (this.src === src) { this.src = null; this.analyser = null; } onEnd?.(); };
      src.start();
      onStart?.();
    } catch (e) {
      if (token !== this.token) return;
      this.hdBroken = true;                                 // e.g. voice missing: use the Windows voice instead
      this.speak(text, { ...cfg, voice_style: 'speech' }, onStart, onEnd);
    }
  }

  /** Speak text. Returns a promise that resolves when done. onWord fires as words are spoken. */
  speak(text, cfg, onStart, onEnd) {
    this.stop();
    const clean = text.replace(/[*_`#]/g, '').replace(/\s+/g, ' ');
    if (cfg.voice_style === 'off' || !clean.trim()) { onEnd?.(); return; }
    if (cfg.voice_style === 'hd' && !this.hdBroken) return this.hd(clean, cfg, onStart, onEnd);
    if (cfg.voice_style === 'blips' || !window.speechSynthesis || !this.list().length) return this.blips(clean, cfg, onStart, onEnd);
    const u = new SpeechSynthesisUtterance(clean);
    const v = this.choose(cfg.voice);
    if (v) u.voice = v;
    u.pitch = cfg.pitch; u.rate = cfg.rate; u.volume = cfg.volume;
    u.onstart = () => onStart?.();
    u.onend = u.onerror = () => onEnd?.();
    speechSynthesis.speak(u);
  }

  /** Story-game style "blip" voice made with WebAudio (works with no TTS voices installed). */
  blips(text, cfg, onStart, onEnd) {
    try { this.ctx = this.ctx || new AudioContext(); } catch { onEnd?.(); return; }
    const ctx = this.ctx;
    this.blipStop = false;
    onStart?.();
    const chars = [...text];
    let i = 0;
    const base = 180 * cfg.pitch;
    const tick = () => {
      if (this.blipStop || i >= chars.length) { onEnd?.(); return; }
      const c = chars[i++];
      if (/[a-z0-9]/i.test(c) && i % 2) {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'square';
        o.frequency.value = base * (1 + ((c.charCodeAt(0) * 7) % 12) / 24);
        g.gain.setValueAtTime(0.0001, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.05 * cfg.volume, ctx.currentTime + 0.01);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.06);
        o.connect(g).connect(ctx.destination);
        o.start(); o.stop(ctx.currentTime + 0.07);
      }
      setTimeout(tick, /[.,!?]/.test(c) ? 140 / cfg.rate : 38 / cfg.rate);
    };
    tick();
  }
}

// ---------------------------------------------------------------- guide
export class Guide {
  constructor(stageEl, opts = {}) {
    this.cfg = { ...GUIDE_DEFAULTS, ...opts };
    this.voice = new Voice();
    // browsers only allow sound after the first click, so unlock audio then
    const unlock = () => { this.voice.unlock(); removeEventListener('pointerdown', unlock); };
    addEventListener('pointerdown', unlock);
    this.queue = [];
    this.current = null;
    this.lastLine = 0;
    this.el = document.createElement('div');
    this.el.className = 'guide';
    this.el.innerHTML = `
      <div class="guide-stage"><canvas></canvas><button class="guide-min" title="Hide ${this.cfg.name}">–</button></div>
      <div class="guide-box" hidden>
        <div class="guide-name"></div>
        <div class="guide-text"></div>
        <div class="guide-choices"></div>
        <div class="guide-next">▼</div>
      </div>
      <button class="guide-mini" hidden title="Show ${this.cfg.name}"></button>`;
    stageEl.appendChild(this.el);
    this.canvas = this.el.querySelector('canvas');
    this.box = this.el.querySelector('.guide-box');
    this.textEl = this.el.querySelector('.guide-text');
    this.choicesEl = this.el.querySelector('.guide-choices');
    this.el.querySelector('.guide-min').onclick = e => { e.stopPropagation(); this.minimize(true); };
    this.el.querySelector('.guide-mini').onclick = () => { this.minimize(false); this.say(pick(['I’m back!', 'Missed me?', 'Ready to build!']), { anim: 'wave', expr: 'happy' }); };
    this.box.onclick = () => this.advance();
    this.canvas.onclick = () => this.poke();
    this.setupScene();
    this.apply(this.cfg);
  }

  setupScene() {
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setSize(190, 240, false);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, 190 / 240, 0.1, 50);
    this.camera.position.set(0.9, 1.75, 5.4);
    this.camera.lookAt(0, 1.15, 0);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667080, 1.7));
    const key = new THREE.DirectionalLight(0xfff2dd, 1.6); key.position.set(2, 3, 4); this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x9fd0ff, 0.8); rim.position.set(-3, 2, -2); this.scene.add(rim);
    // a grass block to stand on
    const top = new THREE.MeshLambertMaterial({ color: 0x6a9b3e }), side = new THREE.MeshLambertMaterial({ color: 0x866043 });
    const ground = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.5, 1.5), [side, side, top, side, side, side]);
    ground.position.y = -0.25;
    this.scene.add(ground);
    this.clock = new THREE.Clock();
    const loop = () => {
      const dt = Math.min(0.05, this.clock.getDelta());
      if (this.anim && !this.hiddenNow) {
        this.anim.update(dt);
        this.ch.root.rotation.y += ((this.turn || 0.25) - this.ch.root.rotation.y) * Math.min(1, dt * 4);
        this.renderer.render(this.scene, this.camera);
      }
      requestAnimationFrame(loop);
    };
    loop();
    setInterval(() => this.idleTick(), 9000);
  }

  apply(cfg) {
    this.cfg = { ...GUIDE_DEFAULTS, ...cfg, look: { ...LOOK_DEFAULTS, ...(cfg.look || {}) } };
    if (this.ch) this.scene.remove(this.ch.root);
    this.ch = createCharacter(this.cfg.look);
    this.anim = new Animator(this.ch);
    this.anim.levelFn = () => this.voice.level();
    this.scene.add(this.ch.root);
    this.el.querySelector('.guide-name').textContent = this.cfg.name;
    this.el.querySelector('.guide-mini').textContent = this.cfg.name[0] || 'F';
    this.el.hidden = !this.cfg.enabled;
    if (!this.cfg.enabled) this.voice.stop();
  }

  minimize(on) {
    this.hiddenNow = on;
    this.el.querySelector('.guide-stage').hidden = on;
    this.el.querySelector('.guide-mini').hidden = !on;
    if (on) { this.box.hidden = true; this.voice.stop(); this.queue = []; this.current = null; }
  }

  get active() { return this.cfg.enabled && !this.hiddenNow; }

  /** Queue a line. opts: anim, expr, choices [{label, value}], hold (ms), important, turn */
  say(text, opts = {}) {
    if (!this.active) return Promise.resolve(null);
    if (opts.chatter && this.cfg.chatty === 'quiet') return Promise.resolve(null);
    return new Promise(res => {
      const line = { text, ...opts, res };
      if (opts.interrupt) { this.queue = []; if (this.current) this.finish(null); }
      if (this.queue.length > 3 && !opts.important) this.queue.splice(1, this.queue.length - 3);
      this.queue.push(line);
      if (!this.current) this.next();
    });
  }

  next() {
    const line = this.queue.shift();
    this.current = line || null;
    if (!line) {
      this.box.classList.add('fade');
      clearTimeout(this.hideT);
      this.hideT = setTimeout(() => { if (!this.current) this.box.hidden = true; }, 2500);
      this.anim.play(this.restAnim || 'idle');
      return;
    }
    clearTimeout(this.hideT);
    this.lastLine = Date.now();
    this.box.hidden = false; this.box.classList.remove('fade');
    this.anim.express(line.expr || 'happy');
    this.anim.play(line.anim || 'talk', line.animOnce ? { once: true, duration: line.animOnce, then: 'talk' } : {});
    this.turn = line.turn ?? 0.25;
    this.choicesEl.innerHTML = '';
    this.el.querySelector('.guide-next').hidden = !!line.choices;
    // typewriter
    clearInterval(this.typeT);
    const full = line.text;
    let i = 0;
    this.textEl.textContent = '';
    this.typing = true;
    this.typeT = setInterval(() => {
      i += 2;
      this.textEl.textContent = full.slice(0, i);
      if (i >= full.length) { clearInterval(this.typeT); this.typing = false; this.showChoices(line); }
    }, 22);
    // voice + lip sync
    this.anim.talking = full.length * 0.055;
    this.voice.speak(full, this.cfg, () => { this.anim.talking = Infinity; }, () => {
      this.anim.talking = 0;
      if (this.current === line && !line.choices) {
        clearTimeout(this.advT);
        this.advT = setTimeout(() => { if (this.current === line) this.finish(null); }, line.hold ?? 1400);
      }
    });
    if (this.cfg.voice_style === 'off') {
      clearTimeout(this.advT);
      if (!line.choices) this.advT = setTimeout(() => { if (this.current === line) this.finish(null); }, (line.hold ?? 1200) + full.length * 45);
    }
  }

  showChoices(line) {
    if (!line.choices) return;
    this.choicesEl.innerHTML = '';
    for (const c of line.choices) {
      const b = document.createElement('button');
      b.textContent = c.label;
      b.onclick = e => { e.stopPropagation(); this.finish(c.value ?? c.label); };
      this.choicesEl.appendChild(b);
    }
  }

  finish(value) {
    const line = this.current;
    if (!line) return;
    clearTimeout(this.advT); clearInterval(this.typeT);
    this.anim.talking = 0;
    line.res(value);
    this.current = null;
    this.next();
  }

  advance() {
    if (!this.current) return;
    if (this.typing) {               // first click finishes the typewriter
      clearInterval(this.typeT); this.typing = false;
      this.textEl.textContent = this.current.text; this.showChoices(this.current);
      return;
    }
    if (this.current.choices) return;
    this.voice.stop();
    this.finish(null);
  }

  /** Play an animation without talking. */
  act(anim, expr, seconds = 2) {
    if (!this.active) return;
    if (expr) this.anim.express(expr);
    this.anim.play(anim, { once: true, duration: seconds, then: this.restAnim || 'idle' });
  }

  setRest(anim) { this.restAnim = anim; if (!this.current) this.anim.play(anim); }

  poke() {
    const lines = [
      ['Hey! That tickles.', 'surprised', 'jump'], ['Need a hand? I’ve got two blocky ones.', 'happy', 'wave'],
      ['Fun fact: I once built a dirt house. Never again.', 'wink', 'shrug'], ['Watch this!', 'excited', 'dance'],
      ['Hmm... what should we build next?', 'think', 'think'], ['Type an idea on the left and I’ll get to work.', 'happy', 'point'],
      ['Ahh, the smell of fresh planks.', 'happy', 'idle'], ['Did you know you can drop in a picture? I can build from that too.', 'excited', 'talk'],
    ];
    const [t, e, a] = pick(lines);
    this.say(t, { expr: e, anim: a, interrupt: true });
  }

  idleTick() {
    if (!this.active || this.current || this.busy || Date.now() - this.lastLine < 45000) return;
    if (this.cfg.chatty !== 'chatty' && Math.random() < 0.6) { this.act(pick(['dance', 'shrug', 'think', 'wave', 'jump']), pick(['happy', 'wink', 'think']), 2.5); return; }
    this.say(pick([
      'Tip: Layers slider lets you peek inside a build, floor by floor.',
      'Tip: The Materials tab tells you how many stacks you’ll need.',
      'Tip: “Change it with Claude” remixes a build without starting over.',
      'Tip: Turn on research and I’ll study real schematics first.',
      'Tip: You can make your own palettes in Settings.',
    ]), { expr: 'happy', anim: 'talk', chatter: true });
  }
}
