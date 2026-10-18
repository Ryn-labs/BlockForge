import { Viewer } from './viewer.js';
import { blockColor } from './blocks.js';
import { Guide, GUIDE_DEFAULTS } from './guide.js';
import { LOOK_DEFAULTS } from './character.js';

const $ = s => document.querySelector(s);
const api = async (path, opts = {}) => {
  const r = await fetch('/api/' + path, {
    headers: opts.body && typeof opts.body === 'string' ? { 'Content-Type': 'application/json' } : {}, ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};
const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) });

const EXAMPLES = [
  'Medieval castle on a hill with four towers, a gatehouse and banners',
  'Cozy hobbit hole built into a grassy hill with a round door and garden',
  'Japanese pagoda, five tiers, cherry trees around it',
  'Modern glass villa with a pool and a flat roof terrace',
  'Giant statue of a fox sitting',
  'Pirate ship with sails and a crow’s nest',
  'Wizard tower with a spiral staircase and floating crystals',
  'Desert temple with sandstone pillars and a hidden entrance',
];
const FORMAT_INFO = {
  schem: ['.schem', 'WorldEdit / FAWE'], litematic: ['.litematic', 'Litematica'],
  nbt: ['.nbt', 'Structure block'], mcstructure: ['.mcstructure', 'Bedrock'],
};

const state = { size: 'medium', image: null, builds: [], current: null, job: null, status: null };
const viewer = new Viewer($('#viewer'));
const guide = new Guide(document.querySelector('.stage'));
window.blockforge = { viewer, guide };   // handy for poking at things from the dev console

// ---------------------------------------------------------------- appearance (Settings > Appearance)
const ACCENTS = ['#62c44a', '#3fb3e8', '#9b6cf0', '#f0a030', '#e5534b', '#e85fa8', '#2fc4a8', '#d8c24a'];
const UI_DEFAULTS = { theme: 'system', accent: '#62c44a', corners: 'round', font: 'system', scale: 100,
  viewer_bg: '', grid: true, rotate: false, examples: true };
let ui = { ...UI_DEFAULTS };

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => Math.max(0, Math.min(255, Math.round(v * f))));
  return '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
}
function inkFor(hex) {
  const n = parseInt(hex.slice(1), 16), L = (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return L > 0.6 ? '#0b1408' : '#ffffff';
}
function effectiveTheme() {
  return ui.theme === 'system' ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : ui.theme;
}
function applyUI() {
  const root = document.documentElement, t = effectiveTheme();
  root.dataset.theme = t;
  root.dataset.corners = ui.corners;
  root.dataset.font = ui.font;
  root.style.setProperty('--accent', ui.accent);
  root.style.setProperty('--accent-2', shade(ui.accent, 0.82));
  root.style.setProperty('--accent-ink', inkFor(ui.accent));
  for (const el of document.querySelectorAll('.top, .panel, dialog')) el.style.zoom = ui.scale / 100;
  viewer.setTheme(t !== 'light', ui.viewer_bg || null);
  viewer.setGrid(ui.grid);
  viewer.setAutoRotate(ui.rotate);
  $('#examples').hidden = !ui.examples;
}
const persistUI = () => { try { localStorage.setItem('bf-ui', JSON.stringify(ui)); } catch {} };
try { ui = { ...UI_DEFAULTS, ...JSON.parse(localStorage.getItem('bf-ui') || '{}') }; } catch {}
applyUI();
matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => ui.theme === 'system' && applyUI());
$('#theme-btn').onclick = () => { ui.theme = effectiveTheme() === 'light' ? 'dark' : 'light'; applyUI(); persistUI(); saveUI(); };
const saveUI = () => post('settings', { ui }).catch(() => {});

function fillLookForm() {
  document.querySelectorAll('#set-theme button').forEach(b => b.classList.toggle('on', b.dataset.v === ui.theme));
  const sw = $('#set-accent');
  sw.innerHTML = ACCENTS.map(c => `<button type="button" data-c="${c}" style="background:${c}" class="${c === ui.accent ? 'on' : ''}" title="${c}"></button>`).join('')
    + `<input type="color" id="accent-custom" value="${ui.accent}" title="Pick any colour">`;
  sw.querySelectorAll('button').forEach(b => b.onclick = () => { ui.accent = b.dataset.c; applyUI(); fillLookForm(); });
  $('#accent-custom').oninput = e => { ui.accent = e.target.value; applyUI(); };
  $('#set-corners').value = ui.corners; $('#set-font').value = ui.font;
  $('#set-scale').value = ui.scale; $('#set-scale-val').textContent = ui.scale + '%';
  $('#set-viewer-bg').value = ui.viewer_bg || (effectiveTheme() === 'light' ? '#dfe6ee' : '#15171c');
  $('#set-grid').checked = ui.grid; $('#set-rotate').checked = ui.rotate; $('#set-examples').checked = ui.examples;
}
document.querySelectorAll('#set-theme button').forEach(b => b.onclick = () => { ui.theme = b.dataset.v; applyUI(); fillLookForm(); });
$('#set-corners').onchange = e => { ui.corners = e.target.value; applyUI(); };
$('#set-font').onchange = e => { ui.font = e.target.value; applyUI(); };
$('#set-scale').oninput = e => { ui.scale = +e.target.value; $('#set-scale-val').textContent = ui.scale + '%'; applyUI(); };
$('#set-viewer-bg').oninput = e => { ui.viewer_bg = e.target.value; applyUI(); };
$('#reset-viewer-bg').onclick = () => { ui.viewer_bg = ''; applyUI(); fillLookForm(); };
$('#set-grid').onchange = e => { ui.grid = e.target.checked; applyUI(); };
$('#set-rotate').onchange = e => { ui.rotate = e.target.checked; applyUI(); };
$('#set-examples').onchange = e => { ui.examples = e.target.checked; applyUI(); };
$('#reset-look').onclick = () => { ui = { ...UI_DEFAULTS }; applyUI(); fillLookForm(); };

// ---------------------------------------------------------------- toast
let toastT;
function toast(msg, err = false) {
  const t = $('#toast');
  t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, err ? 7000 : 3000);
}

// ---------------------------------------------------------------- status / settings
const PALETTE_NAMES = { auto: 'Auto', medieval: 'Medieval', modern: 'Modern', fantasy: 'Fantasy', nature: 'Rustic / nature',
  desert: 'Desert', japanese: 'Japanese', nether: 'Nether', ice: 'Frozen', steampunk: 'Steampunk / copper', snapshot: 'Newest blocks' };

function fillPaletteSelects(s) {
  const custom = s.settings.custom_palettes || [];
  for (const sel of [$('#palette'), $('#default-palette')]) {
    const keep = sel.value;
    sel.innerHTML = '';
    for (const p of s.palettes) sel.add(new Option(PALETTE_NAMES[p] || p, p));
    if (custom.length) {
      const g = document.createElement('optgroup'); g.label = 'My palettes';
      for (const p of custom) g.appendChild(new Option(p.name, 'custom:' + p.name));
      sel.appendChild(g);
    }
    sel.value = keep && [...sel.options].some(o => o.value === keep) ? keep : (s.settings.default_palette || 'auto');
  }
  $('#default-palette').value = s.settings.default_palette || 'auto';
}

function paletteRow(p = { name: '', description: '' }) {
  const row = document.createElement('div');
  row.className = 'palette-row';
  row.innerHTML = `<input class="pn" placeholder="Name" maxlength="40"><input class="pd" placeholder="Blocks and style, e.g. dark oak, deepslate tiles, copper trim, lanterns" maxlength="400"><button type="button" title="Remove">×</button>`;
  row.querySelector('.pn').value = p.name; row.querySelector('.pd').value = p.description;
  row.querySelector('button').onclick = () => row.remove();
  $('#palette-list').appendChild(row);
}
$('#add-palette').onclick = () => paletteRow();

function sitesLabel(s) {
  const sites = s.settings.research_sites || s.default_sites;
  return sites.length <= 2 ? sites.join(', ') : `${sites.slice(0, 2).join(', ')} +${sites.length - 2} more`;
}

let firstStatus = true;
async function loadStatus() {
  const s = await api('status');
  state.status = s;
  const sel = $('#model'), def = $('#default-model');
  if (!sel.options.length) {
    for (const [id, label] of Object.entries(s.models)) {
      sel.add(new Option(label.split(' (')[0], id));
      def.add(new Option(label, id));
    }
  }
  sel.value = sel.dataset.touched ? sel.value : s.settings.model;
  def.value = s.settings.model;
  fillPaletteSelects(s);
  $('#research-sites').textContent = sitesLabel(s);
  if (firstStatus) {
    firstStatus = false;
    $('#research').checked = s.settings.research !== false;
    const size = s.settings.default_size || 'medium';
    document.querySelectorAll('#size-seg button').forEach(x => x.classList.toggle('on', x.dataset.v === size));
    state.size = size;
    gcfg = { ...GUIDE_DEFAULTS, ...(s.settings.guide || {}), look: { ...LOOK_DEFAULTS, ...((s.settings.guide || {}).look || {}) } };
    if ((gcfg.voice_v || 1) < 2) {            // 1.2.0: switch everyone from the robotic voice to the HD one
      if (gcfg.voice_style === 'speech' && s.hd_voice) gcfg.voice_style = 'hd';
      if (gcfg.pitch === 1.15) gcfg.pitch = 1.0;
      if (gcfg.rate === 1.05) gcfg.rate = 1.0;
      gcfg.voice_v = 2;
      if (s.settings.guide && Object.keys(s.settings.guide).length) saveGuide();
    }
    if (!s.hd_voice && gcfg.voice_style === 'hd') gcfg.voice_style = 'speech';
    $('#about-version').textContent = s.version;
    guide.apply(gcfg);
    if (!gcfg.toured && gcfg.enabled !== false) setTimeout(flintTour, 1200);
    if (s.settings.ui && Object.keys(s.settings.ui).length) { ui = { ...UI_DEFAULTS, ...s.settings.ui }; applyUI(); persistUI(); }
  }
  const pill = $('#engine-pill'), txt = $('#engine-text');
  const cc = s.claude_code;
  if (s.settings.engine === 'api') {
    pill.className = 'pill ' + (s.has_api_key ? 'ok' : 'warn');
    txt.textContent = s.has_api_key ? 'Claude · API key' : 'API key needed';
  } else {
    pill.className = 'pill ' + (cc.logged_in ? 'ok' : 'warn');
    txt.textContent = cc.logged_in ? 'Claude · your account' : cc.found ? 'Sign in to Claude' : 'Claude Code not found';
  }
  const st = $('#cc-status');
  st.className = 'status ' + (cc.logged_in ? 'ok' : 'warn');
  st.textContent = !cc.found ? 'Claude Code isn’t installed on this PC.'
    : cc.logged_in ? `Signed in${cc.account ? ' as ' + cc.account : ''} (${cc.method || 'Claude account'}).`
    : 'Found Claude Code, but it isn’t signed in yet. Click “Sign in to Claude”, finish in the window that opens, then “Check again”.';
  for (const r of document.querySelectorAll('input[name=engine]')) r.checked = r.value === s.settings.engine;
  $('#api-key').value = s.settings.api_key || '';
}

function openSettings(tab = 'claude') {
  const s = state.status;
  if (s) {
    $('#set-research').checked = s.settings.research !== false;
    $('#set-sites').value = (s.settings.research_sites || s.default_sites).join('\n');
    $('#default-size').value = s.settings.default_size || 'medium';
    $('#palette-list').innerHTML = '';
    for (const p of s.settings.custom_palettes || []) paletteRow(p);
  }
  savedUI = { ...ui };
  savedGuide = { ...gcfg, look: { ...gcfg.look } };
  fillLookForm();
  fillGuideForm();
  showSettingsTab(tab);
  $('#settings').showModal();
}
function showSettingsTab(tab) {
  document.querySelectorAll('.set-tabs button').forEach(b => b.classList.toggle('on', b.dataset.stab === tab));
  document.querySelectorAll('.stab').forEach(el => el.hidden = el.id !== 'stab-' + tab);
}
document.querySelectorAll('.set-tabs button').forEach(b => b.onclick = () => showSettingsTab(b.dataset.stab));
$('#reset-sites').onclick = () => { $('#set-sites').value = state.status.default_sites.join('\n'); };
$('#settings-btn').onclick = () => loadStatus().then(() => openSettings());
$('#engine-pill').onclick = () => loadStatus().then(() => openSettings('claude'));
$('#research-sites').onclick = e => { e.preventDefault(); openSettings('research'); };
$('#cc-login').onclick = async () => { try { await post('login', {}); toast('A sign-in window opened. Finish signing in there, then click “Check again”.'); } catch (e) { toast(e.message, true); } };
$('#cc-refresh').onclick = () => loadStatus();
let savedUI = null;
$('#settings').addEventListener('close', () => { if (savedUI) { ui = savedUI; savedUI = null; applyUI(); } });
$('#save-settings').onclick = async e => {
  e.preventDefault();
  const engine = document.querySelector('input[name=engine]:checked')?.value || 'claude_code';
  const sites = $('#set-sites').value.split(/\n|,/).map(x => x.trim()).filter(Boolean);
  const custom_palettes = [...document.querySelectorAll('.palette-row')].map(r => ({
    name: r.querySelector('.pn').value.trim(), description: r.querySelector('.pd').value.trim() })).filter(p => p.name && p.description);
  const research = $('#set-research').checked;
  await post('settings', { engine, api_key: $('#api-key').value.trim(), model: $('#default-model').value,
    research, research_sites: sites, default_size: $('#default-size').value, default_palette: $('#default-palette').value,
    custom_palettes, ui, guide: (gcfg = readGuideForm()) });
  $('#research').checked = research;
  savedUI = null; savedGuide = null;
  guide.apply(gcfg);
  persistUI();
  $('#settings').close();
  $('#model').dataset.touched = '';
  await loadStatus();
  toast('Settings saved');
};

// ---------------------------------------------------------------- usage dashboard
const fmtN = n => (n || 0).toLocaleString();
const fmtTok = n => n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n || 0);
const fmtUsd = n => '$' + (n || 0).toFixed(n >= 10 ? 2 : 3);
const fmtSec = s => s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.round(s || 0)}s`;
const modelName = m => (state.status?.models?.[m] || m || '').split(' (')[0].replace(/^\w+ - /, '');

function usageKV(u) {
  if (!u) return '<p class="muted small">No Claude usage was recorded for this build (it was imported, hand-edited or made from a chat).</p>';
  const rows = [
    ['Model', modelName(u.model)], ['Total tokens', fmtN(u.total_tokens)], ['Input (new)', fmtN(u.input_tokens)],
    ['Input (from cache)', fmtN(u.cache_read_tokens)], ['Input (written to cache)', fmtN(u.cache_write_tokens)],
    ['Output', fmtN(u.output_tokens)], ['Web searches', fmtN(u.web_searches)], ['Pages read', fmtN(u.web_fetches)],
    ['Claude turns', fmtN(u.turns)], ['Claude time', fmtSec(u.seconds)], ['Estimated cost', fmtUsd(u.cost_usd)],
  ];
  return `<div class="kv">${rows.map(([k, v]) => `<span>${k}</span><span>${esc(v)}</span>`).join('')}</div>
    <p class="muted small">${esc(u.billing || '')}</p>`;
}

async function openUsage() {
  let u;
  try { u = await api('usage'); } catch (e) { return toast(e.message, true); }
  const plan = state.status?.settings.engine !== 'api';
  $('#usage-note').textContent = plan
    ? 'You use your Claude account, so these builds come out of your Claude plan’s usage limits, not your wallet. Costs are shown at API list prices so you can compare builds.'
    : 'You use an API key, so these costs are what your Anthropic account is charged (estimated from list prices).';
  const card = (name, t) => `<div class="u-card"><h4>${name}</h4><div class="big">${fmtTok(t.total_tokens)} <span class="sub">tokens</span></div>
    <div class="sub">${t.builds} build${t.builds === 1 ? '' : 's'}${t.failed ? ` · ${t.failed} failed` : ''} · ${fmtN(t.web_searches)} searches · ${fmtSec(t.seconds)}</div>
    <div class="sub">≈ ${fmtUsd(t.cost_usd)}</div></div>`;
  $('#usage-cards').innerHTML = card('Today', u.today) + card('Last 7 days', u.week) + card('All time', u.all);
  const maxT = Math.max(1, ...Object.values(u.by_model).map(t => t.total_tokens));
  $('#usage-models').innerHTML = Object.keys(u.by_model).length ? Object.entries(u.by_model).map(([m, t]) =>
    `<div class="kv"><span>${esc(modelName(m))} · ${t.builds} builds</span><span>${fmtTok(t.total_tokens)} · ${fmtUsd(t.cost_usd)}</span></div>
     <div class="bar"><i style="width:${(100 * t.total_tokens / maxT).toFixed(1)}%"></i></div>`).join('')
    : '<p class="muted small">Nothing yet. Generate a build and its usage shows up here.</p>';
  $('#usage-table').innerHTML = `<tr><th>When</th><th>Build</th><th>Model</th><th>Research</th><th>Tokens</th><th>Searches</th><th>Time</th><th>Cost</th></tr>` +
    u.recent.map(r => `<tr class="${r.status === 'done' ? '' : 'fail'}" ${r.build_id ? `data-id="${r.build_id}" style="cursor:pointer"` : ''}>
      <td>${new Date(r.time * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
      <td class="t">${esc(r.title || r.prompt || '')}${r.status === 'done' ? '' : ' (failed)'}${r.parent ? ' · edit' : ''}</td>
      <td>${esc(modelName(r.model))}</td><td>${r.researched ? 'yes' : '-'}</td>
      <td class="num">${fmtTok(r.total_tokens)}</td><td class="num">${r.web_searches || 0}</td>
      <td class="num">${fmtSec(r.wall_seconds || r.seconds)}</td><td class="num">${fmtUsd(r.cost_usd)}</td></tr>`).join('');
  $('#usage-table').querySelectorAll('tr[data-id]').forEach(tr => tr.onclick = () => { $('#usage').close(); openBuild(tr.dataset.id).catch(() => toast('That build was deleted', true)); });
  $('#usage').showModal();
}
$('#usage-btn').onclick = openUsage;
$('#usage-close').onclick = () => $('#usage').close();

// ---------------------------------------------------------------- create form
for (const b of document.querySelectorAll('#size-seg button')) b.onclick = () => {
  document.querySelectorAll('#size-seg button').forEach(x => x.classList.toggle('on', x === b));
  state.size = b.dataset.v;
};
$('#model').onchange = () => $('#model').dataset.touched = '1';
for (const ex of EXAMPLES.sort(() => Math.random() - .5).slice(0, 4)) {
  const b = document.createElement('button'); b.textContent = ex;
  b.onclick = () => { $('#prompt').value = ex; $('#prompt').focus(); };
  $('#examples').appendChild(b);
}

function setImage(file) {
  if (!file || !file.type.startsWith('image/')) return;
  if (file.size > 8 * 1024 * 1024) return toast('That image is over 8 MB', true);
  const rd = new FileReader();
  rd.onload = () => { state.image = rd.result; $('#image-preview').src = rd.result; $('#image-chip').hidden = false; };
  rd.readAsDataURL(file);
}
$('#image-input').onchange = e => setImage(e.target.files[0]);
$('#image-clear').onclick = () => { state.image = null; $('#image-chip').hidden = true; $('#image-input').value = ''; };
const dz = $('#drop-zone');
dz.ondragover = e => { e.preventDefault(); dz.classList.add('drag'); };
dz.ondragleave = () => dz.classList.remove('drag');
dz.ondrop = e => { e.preventDefault(); dz.classList.remove('drag'); setImage(e.dataTransfer.files[0]); };
$('#prompt').onpaste = e => { const f = [...e.clipboardData.files].find(f => f.type.startsWith('image/')); if (f) { e.preventDefault(); setImage(f); } };
$('#prompt').onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generate(); };

async function generate() {
  const prompt = $('#prompt').value.trim();
  if (!prompt && !state.image) return toast('Describe a build or add an image first', true);
  if (state.job) return toast('Already building, hang on');
  try {
    const { job } = await post('generate', { prompt, image: state.image, size: state.size, palette: $('#palette').value, model: $('#model').value, research: $('#research').checked });
    watchJob(job, 'Generating your build…', prompt || 'your picture');
  } catch (e) { toast(e.message, true); }
}
$('#generate').onclick = generate;

// ---------------------------------------------------------------- jobs
function watchJob(id, title, about = '') {
  state.job = id;
  flintStart(title, about);
  let seen = 0;
  $('#progress').hidden = false; $('#empty').hidden = true;
  $('#progress-title').textContent = title;
  $('#progress-log').innerHTML = '';
  document.querySelectorAll('#generate, #edit-btn, #run-code').forEach(b => b.disabled = true);
  const t0 = Date.now();
  const tick = setInterval(() => $('#progress-time').textContent = Math.round((Date.now() - t0) / 1000) + 's', 500);
  const poll = async () => {
    let j;
    try { j = await api('jobs/' + id); } catch { return setTimeout(poll, 1500); }
    $('#progress-log').innerHTML = j.log.map(l => `<li>${esc(l.msg)}</li>`).join('') + (j.error ? `<li class="err">${esc(j.error)}</li>` : '');
    for (; seen < j.log.length; seen++) flintNarrate(j.log[seen].msg);
    if (j.status === 'running') return setTimeout(poll, 1000);
    clearInterval(tick);
    state.job = null;
    document.querySelectorAll('#generate, #edit-btn, #run-code').forEach(b => b.disabled = false);
    flintStop();
    if (j.status === 'done') {
      $('#progress').hidden = true;
      await refreshGallery();
      await openBuild(j.build.id, true);
      $('#edit-prompt').value = '';
      toast(`Built “${j.build.title}”`);
    } else {
      flintFail(j.error || 'Generation failed');
      $('#progress-title').textContent = 'That didn’t work';
      setTimeout(() => { if (!state.job) { $('#progress').hidden = true; if (!state.current) $('#empty').hidden = false; } }, 9000);
      toast(j.error || 'Generation failed', true);
    }
  };
  poll();
}

// ---------------------------------------------------------------- gallery
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
async function refreshGallery() {
  try { state.builds = await api('builds'); } catch { return; }
  renderGallery();
}
function renderGallery() {
  const q = $('#search').value.toLowerCase();
  const list = state.builds.filter(b => !q || (b.title + ' ' + b.prompt).toLowerCase().includes(q));
  $('#count').textContent = state.builds.length ? `(${state.builds.length})` : '';
  const g = $('#gallery');
  if (!list.length) { g.innerHTML = `<div class="empty-gallery">${q ? 'No matches' : 'Your builds will show up here.'}</div>`; return; }
  g.innerHTML = list.map(b => `
    <div class="g-item ${state.current?.id === b.id ? 'on' : ''}" data-id="${b.id}" title="${esc(b.prompt || b.title)}">
      ${b.source === 'claude_chat' ? '<span class="badge">from chat</span>' : b.source === 'import' ? '<span class="badge">imported</span>' : ''}
      <div class="g-thumb" style="${b.has_thumb ? `background-image:url('/api/builds/${b.id}/file/thumb.jpg?v=${b.thumb_v || 0}')` : ''}">${b.has_thumb ? '' : '▣'}</div>
      <button class="g-dl" data-dl="${b.id}" title="Download .schem">⬇</button>
      <div class="g-meta"><div class="g-title">${esc(b.title)}</div><div class="g-sub">${b.size.join('×')} · ${b.block_count.toLocaleString()} blocks</div></div>
    </div>`).join('');
  for (const el of g.querySelectorAll('.g-item')) el.onclick = () => openBuild(el.dataset.id);
  for (const el of g.querySelectorAll('.g-dl')) el.onclick = e => { e.stopPropagation(); downloadBuild(el.dataset.dl, 'schem'); };
}
$('#search').oninput = renderGallery;

$('#import-input').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const r = await fetch('/api/import', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(f.name) }, body: await f.arrayBuffer() });
    const j = await r.json(); if (!r.ok) throw new Error(j.error);
    await refreshGallery(); await openBuild(j.id, true); toast('Imported ' + f.name);
  } catch (err) { toast(err.message, true); }
  e.target.value = '';
};

// ---------------------------------------------------------------- open build
window.blockforge.openBuild = (...a) => openBuild(...a);
async function openBuild(id, fresh = false) {
  const [meta, data, code] = await Promise.all([api('builds/' + id), api(`builds/${id}/blocks`), api(`builds/${id}/code`)]);
  state.current = meta;
  $('#details').scrollTop = 0;              // always start at the top so Download is in view
  $('#empty').hidden = true; $('#toolbar').hidden = false; $('#details').hidden = false;
  document.querySelector('.layout').classList.remove('no-details');
  viewer.load(data);
  const L = $('#layer'); L.max = data.size[1] - 1; L.value = L.max; $('#layer-val').textContent = `${L.max}/${L.max}`;
  $('#title').value = meta.title;
  const date = new Date(meta.created * 1000).toLocaleString();
  const srcName = { claude_code: 'Claude (your account)', api: 'Claude API', script: 'Edited script', import: 'Imported file', claude_chat: 'Claude Code chat' }[meta.source] || meta.source;
  $('#stats').innerHTML = [
    [meta.size.join(' × '), 'W × H × L'], [meta.block_count.toLocaleString(), 'blocks'],
    [srcName, (meta.model || '').replace('claude-', '') || 'source'], [date.split(',')[0], 'created'],
  ].map(([b, s]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join('');
  $('#prompt-text').textContent = meta.prompt || meta.description || '';
  const parent = meta.parent && state.builds.find(b => b.id === meta.parent);
  $('#parent-link').innerHTML = parent ? `Edited from <a href="#" class="link-btn small" data-p="${parent.id}">${esc(parent.title)}</a>` : '';
  $('#parent-link').querySelector('a')?.addEventListener('click', e => { e.preventDefault(); openBuild(parent.id); });
  $('#downloads').innerHTML = Object.entries(FORMAT_INFO).map(([f, [ext, who]]) =>
    `<a href="/api/builds/${id}/export/${f}" download><b>${ext}</b><span>${who}</span></a>`).join('');
  for (const a of $('#downloads').querySelectorAll('a')) a.onclick = e => { e.preventDefault(); downloadBuild(id, a.href.split('/').pop()); };
  $('#materials').innerHTML = (meta.materials || []).map(([n, c]) => {
    const col = '#' + blockColor(n).toString(16).padStart(6, '0');
    const stacks = c >= 64 ? `${Math.floor(c / 64)}×64${c % 64 ? ' + ' + (c % 64) : ''}` : '';
    return `<li><span class="sw" style="background:${col}"></span><span class="nm">${esc(n.replace(/_/g, ' '))}</span><span class="ct">${c.toLocaleString()}${stacks ? '<br>' + stacks : ''}</span></li>`;
  }).join('');
  $('#code').value = code.code || '# This build was imported from a file, so it has no script.';
  $('#edit-card').hidden = !code.code;
  const refs = meta.references || [];
  $('#sources').innerHTML = refs.length ? `<p class="muted small">Real builds Claude studied before designing this one. Click one to open it in your browser.</p>` +
    refs.map(r => `<div class="src"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title || r.url)}</a>
      <span class="site">${esc(r.site || new URL(r.url).hostname)}${r.size && r.size !== 'unknown' ? ' · ' + esc(r.size) : ''}</span>
      ${r.takeaways ? `<p>${esc(r.takeaways)}</p>` : ''}</div>`).join('')
    : `<p class="muted small">${meta.researched ? 'Claude searched but found no close matches, so this one is designed from scratch.' : 'Online research was off for this build. Turn on “Research real builds online” before generating to have Claude study real schematics first.'}</p>`;
  $('#build-usage').innerHTML = usageKV(meta.usage);
  renderGallery();
  if (fresh && flintCfg().in_viewer && flintCfg().enabled !== false) {
    flintBuild(meta).then(() => setTimeout(() => saveThumb(id), 300));
  } else if (!meta.has_thumb || fresh) setTimeout(() => saveThumb(id), 400);
}

async function saveThumb(id) {
  if (state.current?.id !== id) return;
  try {
    const r = await post(`builds/${id}/thumb`, { image: viewer.snapshot() });
    const b = state.builds.find(b => b.id === id);
    if (b) { b.has_thumb = true; b.thumb_v = r.thumb_v; renderGallery(); }
  } catch {}
}

$('#layer').oninput = e => { const v = +e.target.value; viewer.setCut(v); $('#layer-val').textContent = `${v}/${e.target.max}`; };
$('#reset-view').onclick = () => viewer.frame();
$('#shot').onclick = async () => {
  const url = viewer.screenshotFull(), name = (state.current?.title || 'build').replace(/[^\w]+/g, '_') + '.png';
  if (window.pywebview?.api) { const p = await window.pywebview.api.save_image(name, url); if (p) toast('Saved to ' + p); return; }
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
};
$('#title').onchange = async () => {
  if (!state.current) return;
  const m = await post(`builds/${state.current.id}/rename`, { title: $('#title').value });
  state.current.title = m.title; await refreshGallery();
};
$('#reveal').onclick = async () => { if (state.current) await post(`builds/${state.current.id}/reveal`, { format: 'schem' }); };
$('#delete').onclick = async () => {
  if (!state.current || !confirm(`Delete “${state.current.title}”? This can’t be undone.`)) return;
  await api('builds/' + state.current.id, { method: 'DELETE' });
  state.current = null; viewer.clear();
  $('#details').hidden = true; $('#toolbar').hidden = true; $('#empty').hidden = false;
  document.querySelector('.layout').classList.add('no-details');
  refreshGallery();
};
$('#edit-btn').onclick = async () => {
  const p = $('#edit-prompt').value.trim();
  if (!p || !state.current) return toast('Say what to change first', true);
  try {
    const { job } = await post('generate', { prompt: p, parent_id: state.current.id, model: $('#model').value });
    watchJob(job, 'Applying your change…', p);
  } catch (e) { toast(e.message, true); }
};
$('#run-code').onclick = async () => {
  if (!state.current) return;
  try {
    const { job } = await post('run', { code: $('#code').value, title: state.current.title + ' (edited)', parent_id: state.current.id });
    watchJob(job, 'Running your script…');
  } catch (e) { toast(e.message, true); }
};
for (const t of document.querySelectorAll('#details .tabs button')) t.onclick = () => {
  document.querySelectorAll('#details .tabs button').forEach(x => x.classList.toggle('on', x === t));
  document.querySelectorAll('#details .tab').forEach(el => el.hidden = el.id !== 'tab-' + t.dataset.tab);
};
$('#code').onkeydown = e => {
  if (e.key === 'Tab') { e.preventDefault(); const el = e.target, s = el.selectionStart; el.setRangeText('    ', s, el.selectionEnd, 'end'); }
};

// ---------------------------------------------------------------- Flint (the guide)
let gcfg = { ...GUIDE_DEFAULTS };
const flintCfg = () => gcfg;
const saveGuide = () => post('settings', { guide: gcfg }).catch(() => {});
const pickOne = a => a[(Math.random() * a.length) | 0];
let waitTimer = null, lastNarrate = 0, researching = false, reads = 0;

function siteName(s) { return s.replace(/^www\./, '').split('/')[0]; }

function flintStart(title, about) {
  guide.busy = true; researching = false; reads = 0; lastNarrate = Date.now();
  const short = about.length > 60 ? about.slice(0, 57) + '…' : about;
  const editing = /change/i.test(title);
  guide.say(editing ? pickOne([`A remix! Let me work in “${short}”.`, `On it. Changing it so it’s ${short}.`])
                    : pickOne([`Ooh, ${short}! Let’s make it.`, `${short}? Great idea. Let’s go!`, `Alright, ${short}, coming right up.`]),
    { anim: 'wave', animOnce: 1.2, expr: 'excited', interrupt: true });
  guide.setRest('think');
  clearInterval(waitTimer);
  waitTimer = setInterval(() => {
    if (Date.now() - lastNarrate < 28000 || guide.current) return;
    lastNarrate = Date.now();
    guide.say(pickOne([
      'Still working on it. Good builds take a little time!', 'Hmm, where should the windows go…', 'Measuring twice, placing once.',
      'Picking the perfect blocks…', 'This is the fun part. Almost there!', 'Making sure nothing floats. Unless it’s supposed to.',
    ]), { anim: pickOne(['think', 'type', 'talk']), expr: pickOne(['think', 'determined', 'happy']), chatter: true });
  }, 6000);
}

function flintNarrate(msg) {
  lastNarrate = Date.now();
  let m;
  if (/^Researching/.test(msg)) {
    researching = true;
    guide.say('Before I build, let me see what real builders have made. The best ideas come from the pros!', { anim: 'search', expr: 'think' });
    guide.setRest('search');
  } else if (/^Asking Claude/.test(msg)) {
    if (!researching) { guide.say(pickOne(['Let me sketch this out…', 'Thinking up a design…', 'Planning time!']), { anim: 'think', expr: 'think', chatter: true }); }
  } else if ((m = msg.match(/^Searching (.+?) for "(.*)"/))) {
    guide.say(`Searching ${m[1]} for “${m[2]}”…`, { anim: 'search', expr: 'think', hold: 500 });
  } else if ((m = msg.match(/^Reading (.+)/))) {
    reads++;
    const site = siteName(m[1]);
    guide.say(pickOne([`Ooh, this one on ${site} looks good.`, `Taking notes from ${site}…`, `Let me look closer at this one on ${site}.`,
      `Nice details on this ${site} build!`]), { anim: reads % 2 ? 'search' : 'point', expr: 'excited', hold: 500 });
  } else if (/^Writing the build script/.test(msg)) {
    guide.say(researching && reads ? `Got it! I studied ${reads} build${reads === 1 ? '' : 's'}. Now I’m drawing up the plans, which takes a minute.`
                                   : 'Got it! Drawing up the plans now. This part takes a minute.', { anim: 'type', expr: 'determined' });
    guide.setRest('type');
  } else if (/^Script error/.test(msg)) {
    guide.say(pickOne(['Whoops, a little mistake in my plans. Fixing it!', 'Hmm, that didn’t fit. Let me redo that part.']), { anim: 'shrug', expr: 'surprised' });
  } else if (/^Building the blocks/.test(msg)) {
    guide.say('Plans done. Time to place some blocks!', { anim: 'build', expr: 'determined', hold: 300 });
    guide.setRest('build');
  }
}

function flintStop() { guide.busy = false; clearInterval(waitTimer); guide.setRest('idle'); }

function flintFail(err) {
  const short = err.length > 140 ? err.slice(0, 137) + '…' : err;
  guide.say(`Oof. That one didn’t work: ${short}`, { anim: 'sad', expr: 'sad', interrupt: true,
    choices: [{ label: 'Try again', value: 'retry' }, { label: 'Okay', value: 'ok' }] })
    .then(v => { if (v === 'retry') generate(); });
}

async function flintBuild(meta) {
  const banner = $('#build-banner');
  banner.hidden = false;
  $('#build-banner-text').textContent = `${gcfg.name} is building…`;
  $('#build-banner-bar').style.width = '0%';
  $('#skip-build').onclick = () => viewer.stopBuild();
  if (guide.active) guide.say(pickOne(['Watch this!', 'Here we go, block by block!', 'Hard hat on. Building!']), { anim: 'build', expr: 'determined', interrupt: true, hold: 200 });
  guide.setRest('build');
  await viewer.playBuild({ look: gcfg.look, showBuilder: true,
    onLayer: (y, H) => {
      $('#build-banner-bar').style.width = `${Math.round(100 * (y + 1) / H)}%`;
      $('#layer').value = y; $('#layer-val').textContent = `${y}/${H - 1}`;
    } });
  $('#layer').value = $('#layer').max; $('#layer-val').textContent = `${$('#layer').max}/${$('#layer').max}`;
  banner.hidden = true;
  guide.setRest('idle');
  if (!guide.active) return;
  const refs = (meta.references || []).length;
  const v = await guide.say(`Ta-da! “${meta.title}”: ${meta.block_count.toLocaleString()} blocks${refs ? `, inspired by ${refs} real build${refs === 1 ? '' : 's'}` : ''}. What next?`,
    { anim: 'celebrate', animOnce: 2.2, expr: 'excited', interrupt: true,
      choices: [{ label: 'Download .schem', value: 'dl' }, { label: 'Change something', value: 'edit' }, { label: 'Looks great!', value: 'ok' }] });
  if (v === 'dl') downloadBuild(meta.id, 'schem');
  else if (v === 'edit') { $('#edit-prompt').focus(); guide.say('Tell me what to change in the box on the right, then hit “Apply change”.', { anim: 'point', turn: -0.5 }); }
  else if (v === 'ok') guide.act('dance', 'happy', 2.5);
}

async function flintTour() {
  const name = gcfg.name;
  const v = await guide.say(`Hey there! I’m ${name}. I build Minecraft schematics with Claude. Want a quick tour?`,
    { anim: 'wave', animOnce: 2, expr: 'happy', important: true, choices: [{ label: 'Show me around', value: 'yes' }, { label: 'I’ll explore myself', value: 'no' }] });
  gcfg.toured = true; saveGuide();
  if (v !== 'yes') { guide.say('No problem! Click me any time if you want to chat.', { anim: 'shrug', expr: 'wink' }); return; }
  const steps = [
    ['Describe a build on the left, like “a cozy cottage by a river”. You can drop in a picture too!', 'point', 'happy'],
    ['Pick a size and palette, and choose a model. Pro gives the most detail.', 'point', 'think'],
    ['Leave “Research real builds online” on and I’ll study builds on the best schematic sites before I design yours.', 'search', 'excited'],
    ['When it’s done, I build it right in front of you. Then you can download it for WorldEdit, Litematica or Bedrock.', 'build', 'determined'],
    ['Usage, at the top, shows how much Claude used for each build. Settings lets you restyle the whole app, and even me!', 'talk', 'happy'],
    ['That’s it. Let’s build something awesome!', 'celebrate', 'excited'],
  ];
  for (const [t, a, e] of steps) await guide.say(t, { anim: a, expr: e, important: true, hold: 700 });
}

// Settings > Guide
function fillGuideForm() {
  $('#g-enabled').checked = gcfg.enabled !== false;
  $('#g-name').value = gcfg.name; $('#g-chatty').value = gcfg.chatty; $('#g-style').value = gcfg.voice_style;
  fillVoiceList(gcfg.voice_style);
  $('#g-pitch').value = gcfg.pitch; $('#g-pitch-val').textContent = (+gcfg.pitch).toFixed(2);
  $('#g-rate').value = gcfg.rate; $('#g-rate-val').textContent = (+gcfg.rate).toFixed(2);
  for (const k of Object.keys(LOOK_DEFAULTS)) { const el = $('#g-' + k); if (el) el.value = gcfg.look[k] || LOOK_DEFAULTS[k]; }
  $('#g-viewer').checked = gcfg.in_viewer !== false;
}
function readGuideForm() {
  const look = {};
  for (const k of Object.keys(LOOK_DEFAULTS)) { const el = $('#g-' + k); look[k] = el ? el.value : LOOK_DEFAULTS[k]; }
  return { ...gcfg, enabled: $('#g-enabled').checked, name: $('#g-name').value.trim() || 'Flint', chatty: $('#g-chatty').value,
    voice_style: $('#g-style').value,
    ...($('#g-style').value === 'hd' ? { hd_voice: $('#g-voice').value } : { voice: $('#g-voice').value }), pitch: +$('#g-pitch').value, rate: +$('#g-rate').value,
    in_viewer: $('#g-viewer').checked, look };
}
function fillVoiceList(style) {
  const sel = $('#g-voice');
  if (style === 'hd') {
    const hv = state.status?.hd_voices || {};
    sel.innerHTML = Object.entries(hv).map(([k, l]) => `<option value="${esc(k)}">${esc(l)}</option>`).join('') || '<option value="joe">Joe</option>';
    sel.value = gcfg.hd_voice in hv ? gcfg.hd_voice : (Object.keys(hv)[0] || 'joe');
  } else {
    const vs = guide.voice.list();
    sel.innerHTML = '<option value="auto">Automatic</option>' + vs.map(v => `<option value="${esc(v.voiceURI)}">${esc(v.name)} (${esc(v.lang)})</option>`).join('');
    sel.value = [...sel.options].some(o => o.value === gcfg.voice) ? gcfg.voice : 'auto';
  }
  sel.disabled = style === 'blips' || style === 'off';
  $('#g-pitch').disabled = style !== 'speech' && style !== 'blips';
  $('#g-pitch-note').textContent = style === 'hd' ? '(not used by the HD voice)' : '';
}
$('#g-style').addEventListener('change', e => fillVoiceList(e.target.value));
let savedGuide = null;
const previewGuide = () => { guide.apply(readGuideForm()); if (guide.hiddenNow) guide.minimize(false); };
for (const id of ['g-enabled', 'g-name', 'g-chatty', 'g-style', 'g-voice', 'g-viewer', ...Object.keys(LOOK_DEFAULTS).map(k => 'g-' + k)])
  $('#' + id).addEventListener('input', previewGuide);
$('#g-pitch').oninput = e => { $('#g-pitch-val').textContent = (+e.target.value).toFixed(2); previewGuide(); };
$('#g-rate').oninput = e => { $('#g-rate-val').textContent = (+e.target.value).toFixed(2); previewGuide(); };
$('#g-test').onclick = () => { previewGuide(); guide.say(`Hi, I’m ${guide.cfg.name}! This is what I sound like. Let’s build something cool.`, { anim: 'wave', animOnce: 1.5, expr: 'happy', interrupt: true }); };
$('#g-tour').onclick = () => { $('#settings').close(); setTimeout(flintTour, 300); };
$('#g-reset').onclick = () => { gcfg = { ...GUIDE_DEFAULTS, toured: true }; fillGuideForm(); previewGuide(); };
$('#settings').addEventListener('close', () => { if (savedGuide) { gcfg = savedGuide; savedGuide = null; guide.apply(gcfg); } });


// ---------------------------------------------------------------- downloads (always reachable)
async function downloadBuild(id, fmt = 'schem') {
  if (!id) return toast('Open a build first', true);
  if (window.pywebview?.api) {                // installed app: native Save As dialog
    try { const p = await window.pywebview.api.save_export(id, fmt); if (p) toast('Saved to ' + p); }
    catch (err) { toast(String(err), true); }
    return;
  }
  const a = document.createElement('a'); a.href = `/api/builds/${id}/export/${fmt}`; a.download = ''; a.click();
}
$('#dl-main').onclick = () => downloadBuild(state.current?.id, 'schem');
$('#dl-menu').innerHTML = Object.entries(FORMAT_INFO).map(([f, [ext, who]]) => `<button data-f="${f}"><b>${ext}</b><span>${who}</span></button>`).join('');
$('#dl-more').onclick = e => { e.stopPropagation(); $('#dl-menu').hidden = !$('#dl-menu').hidden; };
$('#dl-menu').onclick = e => { const b = e.target.closest('button'); if (b) { $('#dl-menu').hidden = true; downloadBuild(state.current?.id, b.dataset.f); } };
document.addEventListener('click', () => { $('#dl-menu').hidden = true; });

// ---------------------------------------------------------------- updates from GitHub
let updateInfo = null, updateAnnounced = false;
async function checkUpdate(force = false, quiet = true) {
  try { updateInfo = await api('update' + (force ? '?force=1' : '')); }
  catch (e) { if (!quiet) toast(e.message, true); $('#about-update').textContent = 'Couldn’t check for updates.'; return; }
  const u = updateInfo;
  $('#update-btn').hidden = !u.available;
  $('#update-btn').textContent = `⬆ Update to ${u.latest}`;
  $('#about-update').textContent = u.available ? `Version ${u.latest} is available.` : `You’re up to date (latest is ${u.latest || u.current}).`;
  if (!quiet && !u.available) toast('BlockForge is up to date');
  if (u.available && !updateAnnounced && guide.active && !state.job) {
    updateAnnounced = true;
    guide.say(`Psst! There’s a new version of BlockForge (${u.latest}). Want me to update?`,
      { anim: 'wave', animOnce: 1.4, expr: 'excited', choices: [{ label: 'Update now', value: 'go' }, { label: 'Later', value: 'no' }] })
      .then(v => { if (v === 'go') openUpdate(); });
  }
}
function openUpdate() {
  const u = updateInfo; if (!u) return;
  $('#update-title').textContent = u.available ? `Update to BlockForge ${u.latest}` : 'BlockForge is up to date';
  $('#update-sub').textContent = u.available
    ? `You have ${u.current}. BlockForge downloads the new installer from GitHub (${(u.asset.size / 1e6).toFixed(0)} MB), checks it, then closes and reopens itself. Your builds and settings are kept. Windows will ask for permission once.`
    : `You have ${u.current}.`;
  $('#update-notes').textContent = u.notes || '';
  $('#update-log').innerHTML = '';
  $('#update-go').hidden = !u.available; $('#update-go').disabled = false;
  if (!u.installed_app && u.available) $('#update-sub').textContent += ' (You’re running from source, so get the update from the release page instead.)';
  $('#update-dlg').showModal();
}
$('#update-btn').onclick = openUpdate;
$('#update-later').onclick = () => $('#update-dlg').close();
$('#check-update').onclick = () => checkUpdate(true, false);
$('#update-go').onclick = async () => {
  $('#update-go').disabled = true;
  let job;
  try { ({ job } = await post('update', {})); } catch (e) { $('#update-log').innerHTML = `<li class="err">${esc(e.message)}</li>`; $('#update-go').disabled = false; return; }
  const poll = async () => {
    let j; try { j = await api('jobs/' + job); } catch { $('#update-log').innerHTML += '<li>BlockForge is closing to install the update…</li>'; return; }
    $('#update-log').innerHTML = j.log.map(l => `<li>${esc(l.msg)}</li>`).join('') + (j.error ? `<li class="err">${esc(j.error)}</li>` : '');
    if (j.status === 'running') return setTimeout(poll, 700);
    if (j.status === 'error') { $('#update-go').disabled = false; return; }
    guide.say('See you on the other side of the update!', { anim: 'wave', expr: 'happy', interrupt: true });
  };
  poll();
};

// ---------------------------------------------------------------- start
document.querySelector('.layout').classList.add('no-details');
loadStatus().catch(e => toast('Couldn’t reach BlockForge: ' + e.message, true));
setTimeout(() => checkUpdate(), 4000);
setInterval(() => checkUpdate(), 6 * 3600 * 1000);
await refreshGallery();
// builds made from a Claude Code chat appear without a reload
let known = new Set(state.builds.map(b => b.id));
setInterval(async () => {
  if (document.hidden) return;
  await refreshGallery();
  const fresh = state.builds.filter(b => !known.has(b.id));
  known = new Set(state.builds.map(b => b.id));
  const fromChat = fresh.find(b => b.source === 'claude_chat');
  if (fromChat && !state.job) { toast(`New build from Claude: “${fromChat.title}”`); openBuild(fromChat.id); }
}, 4000);
