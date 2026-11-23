// BlockForge web preview: opens a build from the link (#1<packed data> or #g<user>/<gist id>) or from a
// dropped .schem / .litematic / .nbt file. Everything runs in the browser.
import { Viewer } from './viewer.js';
import { blockColor } from './blocks.js';
import { unpack, pack, LinkError } from './linkcodec.js';
import { readSchematic } from './schemread.js';

const $ = s => document.querySelector(s);
const viewer = new Viewer($('#viewer'));
viewer.setTheme(true);
viewer.setGrid(true);
let current = null;          // { data, title, fromFile }

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pretty = name => name.replace(/^minecraft:/, '').split('_').map(w => w ? w[0].toUpperCase() + w.slice(1) : w).join(' ');
const hex = c => '#' + c.toString(16).padStart(6, '0');
let toastTimer;
function toast(t) { const el = $('#toast'); el.textContent = t; el.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => el.hidden = true, 4500); }

function message(title, text, bad = false, withOpen = true) {
  $('#msg').hidden = false;
  $('#msg').innerHTML = `<div class="card${bad ? ' bad' : ''}"><h1>${esc(title)}</h1><p>${text}</p>
    ${withOpen ? '<button id="msg-open">Open a schematic file</button>' : ''}</div>`;
  $('#msg-open')?.addEventListener('click', () => $('#file').click());
}

function welcome() {
  message('BlockForge 3D preview',
    'Drop a <b>.schem</b>, <b>.litematic</b> or <b>.nbt</b> file anywhere on this page to look around it in 3D. ' +
    'The file opens in your browser and is never uploaded.<br><br>Builds made with ' +
    '<a href="https://github.com/Ryn-labs/BlockForge" target="_blank" rel="noopener" style="color:var(--accent)">BlockForge</a> come with a link that opens them here directly.');
}

function show(data, title, fromFile = false) {
  current = { data, title, fromFile };
  $('#msg').hidden = true;
  viewer.load(data);
  const [W, H, L] = data.size, n = data.blocks.length / 4;
  document.title = (title ? title + ' · ' : '') + 'BlockForge 3D preview';
  $('#title').textContent = title || 'Untitled build';
  $('#stats').textContent = `${W} × ${H} × ${L} · ${n.toLocaleString()} blocks`;
  for (const id of ['#mats-btn', '#reset', '#copy']) $(id).hidden = false;
  $('#foot').hidden = false;
  const layer = $('#layer');
  layer.max = H - 1; layer.value = H - 1; $('#layer-val').textContent = `${H}/${H}`;
  const mats = Object.entries(viewer.counts).sort((a, b) => b[1] - a[1]);
  $('#mat-list').innerHTML = mats.map(([name, c]) =>
    `<li data-block="${esc(name)}"><span class="sw" style="background:${hex(blockColor(name))}"></span>${esc(pretty(name))}<span class="n">${c.toLocaleString()}</span></li>`).join('');
  focus(null);
  if (innerWidth > 900 && mats.length) $('#mats').hidden = false;
  $('#mats-btn').classList.toggle('on', !$('#mats').hidden);
}

function focus(name) {
  if (viewer.focusName !== (name || null)) viewer.setFocus(name);
  document.querySelectorAll('#mat-list li').forEach(li => li.classList.toggle('on', li.dataset.block === name));
  const chip = $('#focus-chip');
  chip.hidden = !name;
  if (name) chip.textContent = `Showing only ${pretty(name)} (${(viewer.counts[name] || 0).toLocaleString()}) · tap to show all`;
}

async function fromHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (!h) return welcome();
  message('Loading the build…', '', false, false);
  try {
    if (h[0] === '1') {
      const d = await unpack(h.slice(1));
      show(d, d.title);
    } else if (h[0] === 'g') {
      const m = h.slice(1).match(/^([A-Za-z0-9-]+)\/([0-9a-f]+)$/);
      if (!m) throw new LinkError('This link is damaged. Ask for the link again.');
      const r = await fetch(`https://gist.githubusercontent.com/${m[1]}/${m[2]}/raw`, { cache: 'force-cache' });
      if (!r.ok) throw new LinkError(r.status === 404 ? 'This build was removed by its owner, or the link is wrong.' : `Couldn't fetch the build (GitHub said ${r.status}). Try again in a minute.`);
      const t = (await r.text()).trim();
      if (t[0] !== '1') throw new LinkError('That gist isn\'t a BlockForge build.');
      const d = await unpack(t.slice(1));
      show(d, d.title);
    } else {
      throw new LinkError('This isn\'t a BlockForge preview link.');
    }
  } catch (e) {
    message('Can\'t open this link', esc(e instanceof LinkError ? e.message : 'Something went wrong: ' + e.message), true);
  }
}

async function openFile(file) {
  if (!file) return;
  message('Opening ' + file.name + '…', '', false, false);
  try {
    const d = await readSchematic(new Uint8Array(await file.arrayBuffer()), file.name);
    history.replaceState(null, '', location.pathname);
    show(d, file.name.replace(/\.[^.]+$/, ''), true);
  } catch (e) {
    message('Can\'t open ' + file.name, esc(e.message), true);
  }
}

// ---------------------------------------------------------------- controls
$('#open').onclick = () => $('#file').click();
$('#file').onchange = e => { openFile(e.target.files[0]); e.target.value = ''; };
$('#reset').onclick = () => viewer.frame();
$('#mats-btn').onclick = () => { $('#mats').hidden = !$('#mats').hidden; $('#mats-btn').classList.toggle('on', !$('#mats').hidden); };
$('#mat-list').onclick = e => { const li = e.target.closest('li'); if (li) focus(viewer.focusName === li.dataset.block ? null : li.dataset.block); };
$('#focus-chip').onclick = () => focus(null);
$('#layer').oninput = e => { const v = +e.target.value; viewer.setCut(v); $('#layer-val').textContent = `${v + 1}/${+e.target.max + 1}`; };
$('#copy').onclick = async () => {
  if (!current) return;
  let url = location.href;
  if (current.fromFile || !location.hash) url = location.origin + location.pathname + '#1' + await pack(current.data, current.title || '');
  try { await navigator.clipboard.writeText(url); } catch { prompt('Copy this link:', url); return; }
  toast(url.length > 8000 ? `Link copied. It's long (${url.length.toLocaleString()} characters), so some chat apps may cut it off; sharing the file works too.` : 'Link copied. Anyone can open it to see this build in 3D.');
};
addEventListener('hashchange', fromHash);
addEventListener('keydown', e => { if (e.key === 'Escape') focus(null); });

// drag and drop anywhere
let depth = 0;
addEventListener('dragenter', e => { if (e.dataTransfer?.types?.includes('Files')) { depth++; document.body.classList.add('dragging'); e.preventDefault(); } });
addEventListener('dragleave', () => { if (--depth <= 0) { depth = 0; document.body.classList.remove('dragging'); } });
addEventListener('dragover', e => e.preventDefault());
addEventListener('drop', e => { e.preventDefault(); depth = 0; document.body.classList.remove('dragging'); openFile(e.dataTransfer.files[0]); });

// hover / tap to see what a block is; click highlights every block of that kind
viewer.enablePicking({
  onHover(info, cx, cy) {
    const tip = $('#tip');
    if (!info) { tip.hidden = true; return; }
    tip.innerHTML = `<div style="display:flex;gap:7px;align-items:center"><span class="sw" style="background:${hex(blockColor(info.name))}"></span><b>${esc(pretty(info.name))}</b></div>
      <div class="id">${esc(info.state.replace(/^minecraft:/, ''))}</div><div class="id">x ${info.x}, y ${info.y}, z ${info.z} · ${info.count.toLocaleString()} in this build</div>`;
    tip.hidden = false;
    const r = $('#viewer').getBoundingClientRect();
    let x = cx - r.left + 14, y = cy - r.top + 14;
    if (x + tip.offsetWidth > r.width - 6) x = cx - r.left - tip.offsetWidth - 12;
    if (y + tip.offsetHeight > r.height - 6) y = cy - r.top - tip.offsetHeight - 12;
    tip.style.left = Math.max(6, x) + 'px'; tip.style.top = Math.max(6, y) + 'px';
  },
  onPick(info) {
    if (!info) { if (viewer.focusName) focus(null); return; }
    focus(viewer.focusName === info.name ? null : info.name);
  },
});

window.bfView = { viewer, show, readSchematic, unpack, pack };   // for checks from the console
fromHash();
