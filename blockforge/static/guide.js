// Flint, the guide: a little 3D character in the corner with a story-mode dialogue box and a voice.
import * as THREE from 'three';
import { createCharacter, Animator, LOOK_DEFAULTS, ANIMATIONS } from './character.js';

export const GUIDE_DEFAULTS = {
  enabled: true, name: 'Flint', voice: 'auto', voice_style: 'hd', hd_voice: 'joe', pitch: 1.0, rate: 1.0, volume: 0.9,
  chatty: 'normal', in_viewer: true, eleven_save: true, look: { ...LOOK_DEFAULTS },
};

const pick = a => a[(Math.random() * a.length) | 0];
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const ONCE_LEN = { sleep: 5, stretch: 2.8, backflip: 1.3, bow: 1.9, spin: 1.4, jump: 0.9, nod: 1.4, shake: 1.2, salute: 1.6,
  thumbsup: 1.8, surprised: 1.6, idea: 2, facepalm: 2.2, scared: 2.4, victory: 2.6, hammer: 3.2, mine: 3.2, walk: 3, run: 3, sit: 3.5 };

// ---------------------------------------------------------------- voice
class Voice {
  constructor() {
    this.ctx = null; this.token = 0; this.voices = [];
    this.elevenBroken = false; this.hdBroken = false;
    const load = () => { this.voices = window.speechSynthesis?.getVoices() || []; };
    load();
    window.speechSynthesis?.addEventListener?.('voiceschanged', load);
  }

  list() { return this.voices.filter(v => /^en/i.test(v.lang)).concat(this.voices.filter(v => !/^en/i.test(v.lang))); }

  choose(pref) {
    const vs = this.list();
    if (pref && pref !== 'auto') { const v = vs.find(v => v.voiceURI === pref || v.name === pref); if (v) return v; }
    return vs.find(v => /Guy|Ryan|Davis|Andrew|Brian|Christopher|Eric|Mark|George/i.test(v.name) && /en-(US|GB)/i.test(v.lang))
      || vs.find(v => /en-(US|GB)/i.test(v.lang)) || vs[0] || null;
  }

  stop() {
    this.token++;
    try { window.speechSynthesis?.cancel(); } catch {}
    this.blipStop = true;
    if (this.src) { try { this.src.onended = null; this.src.stop(); } catch {} this.src = null; this.analyser = null; }
  }

  /** Loudness of what's playing right now (0..1), for lip sync. */
  level() {
    if (!this.analyser) return null;
    const a = this.levelBuf || (this.levelBuf = new Uint8Array(this.analyser.fftSize));
    this.analyser.getByteTimeDomainData(a);
    let sum = 0;
    for (let i = 0; i < a.length; i++) { const v = (a[i] - 128) / 128; sum += v * v; }
    return Math.sqrt(sum / a.length);
  }

  unlock() { try { this.ctx = this.ctx || new AudioContext(); if (this.ctx.state === 'suspended') this.ctx.resume(); } catch {} }

  async play(url, cfg, rate, onStart, onEnd, token) {
    const r = await fetch(url);
    if (!r.ok) {
      let msg = 'voice ' + r.status;
      try { msg = (await r.json()).error || msg; } catch {}
      throw new Error(msg);
    }
    const buf = await r.arrayBuffer();
    this.unlock();
    const audio = await this.ctx.decodeAudioData(buf);
    if (token !== this.token) return;                      // a newer line started meanwhile
    const src = this.ctx.createBufferSource();
    src.buffer = audio; src.playbackRate.value = rate;
    const an = this.ctx.createAnalyser(); an.fftSize = 512;
    const g = this.ctx.createGain(); g.gain.value = cfg.volume;
    src.connect(an); an.connect(g); g.connect(this.ctx.destination);
    this.src = src; this.analyser = an;
    src.onended = () => { if (this.src === src) { this.src = null; this.analyser = null; } onEnd?.(); };
    src.start();
    onStart?.();
  }

  /** Speak text with the voice type in cfg.voice_style. Falls back to the next best voice on any problem. */
  async speak(text, cfg, onStart, onEnd) {
    this.stop();
    const token = this.token;
    const clean = text.replace(/[*_`#]/g, '').replace(/\s+/g, ' ').trim();
    let style = cfg.voice_style;
    if (style === 'off' || !clean) { onEnd?.(); return; }
    if (style === 'eleven' && (this.elevenBroken || !cfg.eleven_ready)) style = 'hd';
    if (style === 'hd' && (this.hdBroken || !cfg.hd_ready)) style = 'speech';
    try {
      if (style === 'eleven') {
        const q = `/api/eleven/tts?speed=${clamp(cfg.rate, 0.7, 1.2)}&text=${encodeURIComponent(clean)}`;
        return await this.play(q, cfg, 1, onStart, onEnd, token);
      }
      if (style === 'hd') {
        const pitch = clamp(cfg.pitch || 1, 0.6, 1.6);                  // pitch = playback speed, compensated in the request
        const q = `/api/tts?voice=${encodeURIComponent(cfg.hd_voice || 'joe')}&speed=${clamp(cfg.rate / pitch, 0.5, 1.6).toFixed(2)}&text=${encodeURIComponent(clean)}`;
        return await this.play(q, cfg, pitch, onStart, onEnd, token);
      }
    } catch (e) {
      if (token !== this.token) return;
      const msg = String(e.message || e);
      if (style === 'eleven') {
        if (!/busy|too many/i.test(msg)) this.elevenBroken = true;
        window.dispatchEvent(new CustomEvent('guide-voice-error', { detail: msg }));
      } else this.hdBroken = true;
      return this.speak(text, { ...cfg, voice_style: style === 'eleven' ? 'hd' : 'speech' }, onStart, onEnd);
    }
    if (style === 'blips' || !window.speechSynthesis || !this.list().length) return this.blips(clean, cfg, onStart, onEnd);
    const u = new SpeechSynthesisUtterance(clean);
    const v = this.choose(cfg.voice);
    if (v) u.voice = v;
    u.pitch = cfg.pitch; u.rate = cfg.rate; u.volume = cfg.volume;
    u.onstart = () => onStart?.();
    u.onend = u.onerror = () => onEnd?.();
    speechSynthesis.speak(u);
  }

  /** Story-game style "blip" voice made with WebAudio (works with no voices installed). */
  blips(text, cfg, onStart, onEnd) {
    try { this.unlock(); } catch { onEnd?.(); return; }
    const ctx = this.ctx;
    this.blipStop = false;
    onStart?.();
    const chars = [...text];
    let i = 0;
    const base = 180 * (cfg.pitch || 1);
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
    this.queue = [];
    this.current = null;
    this.lastLine = Date.now();
    this.asleep = false;
    const unlock = () => { this.voice.unlock(); removeEventListener('pointerdown', unlock); };
    addEventListener('pointerdown', unlock);
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
    this.camera.position.set(0.8, 1.6, 5.7);
    this.camera.lookAt(0, 1.3, 0);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667080, 1.7));
    const key = new THREE.DirectionalLight(0xfff2dd, 1.6); key.position.set(2, 3, 4); this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x9fd0ff, 0.9); rim.position.set(-3, 2, -2); this.scene.add(rim);
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
    this.voice.elevenBroken = false; this.voice.hdBroken = false;
    if (this.ch) this.scene.remove(this.ch.root);
    this.ch = createCharacter(this.cfg.look);
    this.anim = new Animator(this.ch);
    this.anim.levelFn = () => this.voice.level();
    this.scene.add(this.ch.root);
    if (this.asleep) this.anim.play('sleep');
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

  wake() {
    if (!this.asleep) return;
    this.asleep = false; this.restAnim = 'idle';
    this.anim.emote('❗', 1.2);
  }

  /** Queue a line. opts: anim, expr, choices [{label, value}], hold (ms), important, interrupt, turn */
  say(text, opts = {}) {
    if (!this.active) return Promise.resolve(null);
    if (opts.chatter && this.cfg.chatty === 'quiet') return Promise.resolve(null);
    this.wake();
    return new Promise(res => {
      const line = { text, ...opts, res, big: !!(opts.choices || opts.important || opts.big) };
      if (opts.interrupt) { this.queue = []; if (this.current) this.finish(null); }
      if (this.queue.length > 3 && !opts.important) this.queue.splice(1, this.queue.length - 3);
      this.queue.push(line);
      if (!this.current) this.next();
    });
  }

  /** Which voice this line uses. ElevenLabs credits are saved for the big moments when eleven_save is on. */
  lineCfg(line) {
    const c = this.cfg;
    if (c.voice_style === 'eleven' && c.eleven_save && !line.big && !line.test) return { ...c, voice_style: 'hd' };
    return c;
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
    this.anim.play(line.anim || 'talk', { ...(line.animOnce ? { once: true, duration: line.animOnce, then: 'talk' } : {}), expr: line.expr || 'happy' });
    this.turn = line.turn ?? 0.25;
    this.choicesEl.innerHTML = '';
    this.el.querySelector('.guide-next').hidden = !!line.choices;
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
    this.anim.talking = full.length * 0.055;
    const cfg = this.lineCfg(line);
    this.voice.speak(full, cfg, () => { this.anim.talking = Infinity; }, () => {
      this.anim.talking = 0;
      if (this.current === line && !line.choices) {
        clearTimeout(this.advT);
        this.advT = setTimeout(() => { if (this.current === line) this.finish(null); }, line.hold ?? 1400);
      }
    });
    if (cfg.voice_style === 'off') {
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
    if (this.typing) {
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
    this.wake();
    this.lastLine = Date.now();
    this.anim.play(anim, { once: true, duration: seconds, then: this.restAnim || 'idle', ...(expr ? { expr } : {}) });
  }

  /** For the animation gallery in Settings. */
  preview(anim) {
    if (!this.active) { this.minimize(false); }
    this.asleep = false; this.restAnim = 'idle';
    this.queue = []; if (this.current) this.finish(null);
    this.box.hidden = true;
    this.lastLine = Date.now();
    this.anim.play(anim, { once: true, duration: ONCE_LEN[anim] || 2.8, then: 'idle' });
  }

  setRest(anim) { if (this.asleep && anim === 'idle') return; this.restAnim = anim; if (!this.current) this.anim.play(anim); }

  poke() {
    this.lastLine = Date.now();
    if (this.asleep) { this.say('Huh? I wasn’t sleeping! I was just resting my eyes.', { anim: 'surprised', expr: 'surprised', interrupt: true }); return; }
    const lines = [
      ['Hey! That tickles.', 'surprised', 'jump'], ['Need a hand? I’ve got two blocky ones.', 'happy', 'wave'],
      ['Fun fact: I once built a dirt house. Never again.', 'wink', 'shrug'], ['Watch this!', 'excited', 'backflip'],
      ['Hmm... what should we build next?', 'think', 'think'], ['Type an idea on the left and I’ll get to work.', 'happy', 'point'],
      ['Ahh, the smell of fresh planks.', 'happy', 'stretch'], ['Did you know you can drop in a picture? I can build from that too.', 'excited', 'talk'],
      ['Look at these muscles. Strong enough to carry a whole stack of stone.', 'smug', 'flex'], ['Boogie time!', 'wink', 'disco'],
      ['Beep boop. I am totally a robot.', 'neutral', 'robot'], ['You’re doing great! Keep it up.', 'happy', 'thumbsup'],
      ['Ugh, I stepped on a Lego. Wrong game.', 'angry', 'angry'], ['Aww, thanks for stopping by!', 'love', 'love'],
      ['Reporting for duty!', 'determined', 'salute'], ['Hee hee, that was a good one.', 'laugh', 'laugh'],
    ];
    const [t, e, a] = pick(lines);
    this.say(t, { expr: e, anim: a, interrupt: true });
  }

  idleTick() {
    if (!this.active || this.current || this.busy) return;
    const idle = Date.now() - this.lastLine;
    if (idle > 150000 && !this.asleep && this.cfg.chatty !== 'quiet') {
      this.asleep = true; this.restAnim = 'sleep'; this.anim.play('sleep'); return;
    }
    if (this.asleep || idle < 45000) return;
    if (this.cfg.chatty !== 'chatty' && Math.random() < 0.6) {
      this.act(pick(['dance', 'shrug', 'think', 'wave', 'jump', 'stretch', 'flex', 'robot', 'disco', 'sit', 'clap', 'spin']), null, 3);
      return;
    }
    this.say(pick([
      'Tip: Layers slider lets you peek inside a build, floor by floor.',
      'Tip: The Materials tab tells you how many stacks you’ll need.',
      'Tip: “Change it with Claude” remixes a build without starting over.',
      'Tip: Turn on research and I’ll study real schematics first.',
      'Tip: You can make your own palettes in Settings.',
      'Tip: Need a door or a farm? Ask for redstone and I’ll wire it up.',
    ]), { expr: 'happy', anim: 'talk', chatter: true });
  }
}

export { ANIMATIONS };
