/* Samrudhi Control Room — vanilla JS, no external libraries. Every number comes from the API. */
(() => {
'use strict';

/* ======================================================================
   helpers
   ====================================================================== */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  sget(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
  sset(k, v) { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch (e) {} },
};
const pad = n => String(n).padStart(2, '0');
function clock(s) { if (s == null) return ''; s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`; }
function dur(s) {
  if (s == null) return 'unavailable';
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60); if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}
const time = iso => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
const date = iso => iso ? new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '';
const since = iso => iso ? (Date.now() - new Date(iso).getTime()) / 1000 : null;
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.style.display = 'block'; clearTimeout(toast.t); toast.t = setTimeout(() => { t.style.display = 'none'; }, 3200); }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

const STAGES = { 'P0-1A': 'Stage 1A', 'P0-1B': 'Stage 1B', 'P0-1C': 'Stage 1C', 'P1-P1': 'Phase 1', 'P1-P2': 'Phase 2', 'P1-P3': 'Phase 3' };
const STATE_META = {
  active: { label: 'Active', dot: 'green', tile: 'c-green' },
  awaiting_approval: { label: 'Awaiting approval', dot: 'amber', tile: 'c-amber' },
  on_standby: { label: 'On standby', dot: 'standby', tile: 'c-standby' },
  not_deployed: { label: 'Not deployed', dot: '', tile: 'c-grey' },
};
const PSTATUS = {
  draft: 'Ready to start', running: 'Running', paused: 'Paused', needs_attention: 'Needs attention',
  completed: 'Completed', stopped: 'Stopped',
};

/* ======================================================================
   icons + status symbols (identical everywhere)
   ====================================================================== */
const svg = (p, size = 18, extra = '') => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${p}</svg>`;
const I = {
  logo: `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 21 19H3Z" fill="none" stroke="#2ED573" stroke-width="2.6" stroke-linejoin="round"/></svg>`,
  folder: svg('<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>'),
  users: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>', 16),
  clock: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', 16),
  chev: svg('<path d="m9 6 6 6-6 6"/>', 16),
  chevDown: svg('<path d="m6 9 6 6 6-6"/>', 16),
  pause: svg('<path d="M9 5v14M15 5v14"/>', 16),
  play: svg('<path d="M7 5l12 7-12 7Z"/>', 16),
  stop: svg('<rect x="6" y="6" width="12" height="12" rx="1.5"/>', 16),
  send: svg('<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/>', 16),
  check: svg('<path d="M20 6 9 17l-5-5"/>', 16),
  x: svg('<path d="M18 6 6 18M6 6l12 12"/>', 16),
  pencil: svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>', 16),
  retry: svg('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>', 16),
  ext: svg('<path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>', 14),
};
const SYM = {
  completed: (c = 'var(--green)') => `<svg class="sym" viewBox="0 0 24 24" role="img" aria-label="Completed"><circle cx="12" cy="12" r="9" fill="none" stroke="${c}" stroke-width="2"/><path d="m8 12.5 2.7 2.7L16.5 9.5" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  in_progress: (c = 'var(--sky)') => `<svg class="sym spin" viewBox="0 0 24 24" role="img" aria-label="In progress"><path d="M12 3a9 9 0 1 1-9 9" fill="none" stroke="${c}" stroke-width="2.4" stroke-linecap="round"/></svg>`,
  needs_attention: (c = 'var(--amber)') => `<svg class="sym" viewBox="0 0 24 24" role="img" aria-label="Needs attention"><path d="M12 3.5 22 20H2Z" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/><path d="M12 10v4.5M12 17.2v.3" stroke="${c}" stroke-width="2" stroke-linecap="round"/></svg>`,
  queued: (c = 'var(--indigo)') => `<svg class="sym" viewBox="0 0 24 24" role="img" aria-label="Queued"><circle cx="12" cy="12" r="8.5" fill="none" stroke="${c}" stroke-width="2" stroke-dasharray="3 3.2"/></svg>`,
  skipped: () => SYM.queued('var(--grey)').replace('aria-label="Queued"', 'aria-label="Skipped"'),
};
function stepSym(st, pendingIds) {
  if (st.status === 'needs_attention') {
    const awaiting = st.approval_id && pendingIds.has(st.approval_id);
    return SYM.needs_attention(awaiting ? 'var(--amber)' : 'var(--red)');
  }
  return (SYM[st.status] || SYM.queued)();
}

/* ======================================================================
   API + auth
   ====================================================================== */
const S = {
  auth: store.get('samrudhi.auth'),
  wf: null, wfError: false, open: [], live: 'connecting',
  view: null, cleanup: null, project: null,
  ui: { expanded: new Set(), fullReq: new Set(), notes: {}, composer: {}, agents: { q: '', stage: '', state: '', dept: '', prio: '', type: '', sort: 'canonical_id', dir: 1 }, histQ: '' },
  busy: new Set(),
};

async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  if (S.auth && S.auth.token) headers.Authorization = 'Bearer ' + S.auth.token;
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(opts.json); }
  let res;
  try { res = await fetch(path, Object.assign({}, opts, { headers })); }
  catch (e) { const err = new Error('The backend is not reachable.'); err.status = 0; throw err; }
  let body = null; try { body = await res.json(); } catch (e) {}
  if (res.status === 401 && S.auth) { setAuth(null); }
  if (!res.ok) {
    const d = body && body.detail;
    const err = new Error(typeof d === 'string' ? d : (d && d.message) || res.statusText || 'Request failed');
    err.status = res.status; err.detail = d; throw err;
  }
  return body;
}

function setAuth(a) { S.auth = a; store.set('samrudhi.auth', a); renderSidebar(); }
let loginWaiter = null;
function requireAuth() {
  if (S.auth && S.auth.token) return Promise.resolve(true);
  const dlg = $('#login'); $('#login-error').textContent = ''; $('#login-form').reset();
  dlg.showModal(); setTimeout(() => $('#login-form [name=username]').focus(), 30);
  return new Promise(res => { loginWaiter = res; });
}
$('#login-cancel').addEventListener('click', () => { $('#login').close(); if (loginWaiter) { loginWaiter(false); loginWaiter = null; } });
$('#login').addEventListener('cancel', () => { if (loginWaiter) { loginWaiter(false); loginWaiter = null; } });
$('#login-form').addEventListener('submit', async ev => {
  ev.preventDefault();
  const fd = new FormData(ev.target), btn = $('#login-submit');
  btn.disabled = true; $('#login-error').textContent = '';
  try {
    const body = new URLSearchParams({ username: fd.get('username').trim(), password: fd.get('password') });
    const r = await api('/api/auth/login', { method: 'POST', body });
    setAuth({ token: r.access_token, role: r.role, username: fd.get('username').trim() });
    $('#login').close(); toast('Signed in as ' + fd.get('username').trim());
    if (loginWaiter) { loginWaiter(true); loginWaiter = null; }
  } catch (e) { $('#login-error').textContent = e.message; }
  finally { btn.disabled = false; }
});
async function act(fn) { if (!(await requireAuth())) return null; return fn(); }

/* ======================================================================
   live feed: Server-Sent Events, falling back to polling every 5 s
   ====================================================================== */
class Live {
  constructor(url, onUpdate, onMode) { this.url = url; this.onUpdate = debounce(onUpdate, 250); this.onMode = onMode || (() => {}); this.es = null; this.poll = null; this.retry = null; this.stopped = false; }
  start() {
    if (this.stopped) return;
    // Lifecycle changes made through the existing agent endpoints publish no live event,
    // so a slow safety refresh runs even while the live feed is connected.
    if (!this.safety) this.safety = setInterval(() => { if (!this.poll) this.onUpdate(); }, 20000);
    try { this.es = new EventSource(this.url); } catch (e) { return this.fallback(); }
    this.es.addEventListener('ready', () => { this.onMode('live'); this.clearPoll(); this.onUpdate(); });
    this.es.addEventListener('update', () => this.onUpdate());
    this.es.onerror = () => { if (this.es) { this.es.close(); this.es = null; } this.fallback(); };
  }
  fallback() {
    if (this.stopped) return;
    this.onMode('offline');
    if (!this.poll) this.poll = setInterval(() => this.onUpdate(), 5000);
    clearTimeout(this.retry); this.retry = setTimeout(() => this.start(), 30000);
  }
  clearPoll() { clearInterval(this.poll); this.poll = null; }
  stop() { this.stopped = true; if (this.es) this.es.close(); this.clearPoll(); clearTimeout(this.retry); clearInterval(this.safety); }
}

/* ======================================================================
   components
   ====================================================================== */
function tile(value, label, cls, big) {
  const na = value == null;
  return `<div class="tile ${cls}${big ? ' big' : ''}"><div class="num${na ? ' na' : ''}">${na ? 'unavailable' : esc(value)}</div><div class="lbl">${esc(label)}</div></div>`;
}
function navBtn(href, icon, label, active, chev) {
  return `<a class="nav-btn${active ? ' active' : ''}" href="${href}" aria-label="${esc(label)}"${active ? ' aria-current="page"' : ''}><span class="icon-box" aria-hidden="true">${icon}</span><span>${esc(label)}</span>${chev ? `<span class="chev" aria-hidden="true">${I.chev}</span>` : ''}</a>`;
}
function statusChip(p, pending) {
  if (p.status === 'running' && pending) return `<span class="status-chip st-awaiting">Awaiting your decision</span>`;
  return `<span class="status-chip st-${esc(p.status)}">${esc(PSTATUS[p.status] || p.status)}</span>`;
}
function stateView(kind, title, text, retry) {
  if (kind === 'loading') return `<div class="state" aria-busy="true"><div class="skeleton" style="width:260px;height:14px"></div><div class="skeleton" style="width:200px;height:14px"></div><span class="sr-only">Loading</span></div>`;
  return `<div class="state" role="${kind === 'error' ? 'alert' : 'status'}">
    ${kind === 'error' ? SYM.needs_attention('var(--red)') : ''}
    <h2>${esc(title)}</h2>${text ? `<p>${text}</p>` : ''}
    ${retry ? `<button class="btn" data-retry>${I.retry} Retry</button>` : ''}</div>`;
}
function liveBanner() { return S.live === 'offline' ? `<div class="banner" role="status">${SYM.needs_attention('var(--amber)')} Live updates offline, refreshing every few seconds.</div>` : ''; }

/* ======================================================================
   sidebar
   ====================================================================== */
function renderSidebar() {
  const wf = S.wf, c = wf && wf.available ? wf.counts : null;
  const v = S.view || {};
  const onProject = v.name === 'project' && S.project && S.project.project.status !== 'draft';
  const pc = onProject ? S.project.counts : null;
  const projectsActive = ['projects', 'new', 'project', 'history'].includes(v.name);
  const running = S.open.filter(p => ['running', 'paused', 'needs_attention'].includes(p.status)).slice(0, 3);
  const h = wf ? wf.health : null;
  const healthItems = h ? [['API', h.api], ['Database', h.db], ['Redis', h.redis], ['Ollama', h.ollama]] : [['API', S.wfError ? 'down' : '…']];
  const allUp = h && healthItems.every(([, s]) => s === 'up');
  const mon = wf && wf.monitoring && wf.monitoring.length ? wf.monitoring : null;
  const ae = document.activeElement, sb = $('#sidebar');
  const keepFocus = ae && sb.contains(ae) ? (ae.getAttribute('href') || ae.id) : null;

  sb.innerHTML = `
    <a class="brand" href="#/projects/new" aria-label="Samrudhi Control Room home">
      <span class="brand-logo">${I.logo}</span>
      <span><div class="brand-name">Samrudhi</div><div class="brand-sub">Agentic OS · Control Room</div></span>
    </a>
    <p class="section-label">Workforce · ${c ? esc(wf.total) + ' agents' : 'unavailable'}</p>
    <div class="tiles">
      ${tile(c ? c.active : null, 'Active', 'c-green')}
      ${tile(c ? c.awaiting_approval : null, 'Awaiting approval', 'c-amber')}
      ${pc ? tile(pc.completed, 'Completed', 'c-sky') + tile(pc.queued, 'Queued', 'c-indigo') : ''}
      ${tile(c ? c.on_standby : null, 'On standby', 'c-standby')}
      ${tile(c ? c.not_deployed : null, 'Not deployed', 'c-grey')}
    </div>
    <nav aria-label="Main" style="display:flex;flex-direction:column;gap:10px">
      ${navBtn('#/projects', I.folder, 'Projects', projectsActive, true)}
      <div class="sub-nav">
        <a class="sub-link${v.name === 'new' ? ' active' : ' green'}" href="#/projects/new">${I.plus} New project</a>
        <a class="sub-link${v.name === 'history' ? ' active' : ''}" href="#/history">${I.clock} History</a>
        ${running.map(p => `<a class="sub-link${v.name === 'project' && v.id === p.id ? ' active' : ''}" href="#/projects/${esc(p.id)}" title="${esc(p.name)}">
          <span class="dot ${p.status === 'running' ? 'sky' : p.status === 'paused' ? 'standby' : 'red'}"></span><span class="ellipsis">${esc(p.name)}</span></a>`).join('')}
      </div>
      ${navBtn('#/agents', I.users, 'Agents', v.name === 'agents', false)}
    </nav>
    <div class="monitor-card">
      <p class="section-label">Monitoring</p>
      ${mon ? mon.map(m => `<div class="monitor-row" title="${esc(m.name)}: ${esc(m.detail)}"><span class="dot ${m.level === 'ok' ? 'green' : m.level === 'down' ? 'red' : ''}"></span><span class="ellipsis">${esc(m.name)} · ${esc(m.role)}</span><span class="sr-only">${esc(m.detail)}</span></div>`).join('') +
          (mon.some(m => m.level !== 'ok') ? `<div class="faint small">${[mon.filter(m => m.level === 'idle').length ? mon.filter(m => m.level === 'idle').length + ' not deployed' : '', mon.filter(m => m.level === 'down').length ? mon.filter(m => m.level === 'down').length + ' with a system down' : ''].filter(Boolean).join(' · ')}</div>` : '')
        : `<div class="muted small">unavailable</div>`}
    </div>
    <div class="side-bottom">
      <div class="row" style="gap:8px"><span class="dot ${allUp ? 'green' : h ? 'amber' : 'red'}"></span>${allUp ? 'All systems running' : h ? 'Some systems need attention' : 'Backend not reachable'}</div>
      <div class="health-grid">${healthItems.map(([k, s]) => `<span class="health-item" title="${esc(k)}: ${esc(s)}"><span class="dot ${s === 'up' ? 'green' : s === '…' ? '' : 'red'}"></span><span class="ellipsis">${esc(k)}${s === 'up' ? '' : ': ' + esc(s)}</span></span>`).join('')}</div>
      <div class="user-line">${S.auth ? `Signed in as ${esc(S.auth.username)} (${esc(S.auth.role.replace(/_/g, ' '))}) <button class="linklike" id="signout">Sign out</button>` : `Not signed in · <button class="linklike" id="signin">Sign in</button>`}</div>
    </div>`;
  const so = $('#signout'); if (so) so.onclick = () => { setAuth(null); toast('Signed out'); };
  const si = $('#signin'); if (si) si.onclick = () => requireAuth();
  if (keepFocus) { const el = $$('a,button', sb).find(x => x.getAttribute('href') === keepFocus || x.id === keepFocus); if (el) el.focus({ preventScroll: true }); }
}

let wfSig = null;
async function loadWorkforce() {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const [wf, open] = await Promise.all([api('/api/workforce'), api('/api/projects?status=running,paused,needs_attention')]);
      S.wf = wf; S.open = open; S.wfError = false;
      break;
    } catch (e) {
      if (attempt === 2) { S.wfError = true; S.wf = null; }
      else await new Promise(r => setTimeout(r, 1200));
    }
  }
  const sig = JSON.stringify([S.wf, S.open && S.open.map(p => [p.id, p.name, p.status]), S.wfError]);
  if (sig === wfSig) return; // nothing changed: keep the DOM (and focus) as it is
  wfSig = sig;
  renderSidebar();
  if (S.view && S.view.onWorkforce) S.view.onWorkforce();
}
const wfLive = new Live('/api/workforce/stream', loadWorkforce, mode => { S.live = mode; const b = $('#live-banner'); if (b) b.innerHTML = liveBanner(); });

/* ======================================================================
   router
   ====================================================================== */
function route() {
  const h = location.hash.replace(/^#\/?/, '');
  const parts = h.split('/').filter(Boolean).map(decodeURIComponent);
  if (S.cleanup) { try { S.cleanup(); } catch (e) {} S.cleanup = null; }
  S.project = null;
  $('#shell').classList.remove('with-right'); $('#rightpanel').hidden = true; $('#rightpanel').innerHTML = '';
  if (parts[0] === 'projects' && parts[1] === 'new') S.view = { name: 'new' }, viewNew();
  else if (parts[0] === 'projects' && parts[1]) S.view = { name: 'project', id: parts[1] }, viewProject(parts[1]);
  else if (parts[0] === 'projects') S.view = { name: 'projects' }, viewProjects();
  else if (parts[0] === 'history') S.view = { name: 'history', id: parts[1] || null }, viewHistory(parts[1] || null);
  else if (parts[0] === 'agents') S.view = { name: 'agents' }, viewAgents();
  else { location.replace('#/projects/new'); return; }
  renderSidebar();
  $('#main').focus({ preventScroll: true });
}
window.addEventListener('hashchange', route);
function main(html) { $('#main').innerHTML = `<div id="live-banner">${liveBanner()}</div>` + html; }

/* ======================================================================
   Projects overview
   ====================================================================== */
async function viewProjects() {
  main(`<header class="page-head"><h1>Projects</h1><p>Projects that are running, paused, need attention, or are ready to start.</p></header><div class="page" id="pl">${stateView('loading')}</div>`);
  const load = async () => {
    const box = $('#pl'); if (!box) return;
    try {
      const all = await api('/api/projects');
      const open = all.filter(p => !['completed', 'stopped'].includes(p.status));
      box.innerHTML = open.length ? `<div class="hist-list" style="max-width:760px">${open.map(p => `
          <a class="hist-item" href="#/projects/${esc(p.id)}" style="text-decoration:none;color:inherit">
            <div class="row" style="justify-content:space-between;flex-wrap:nowrap"><span class="ellipsis" style="font-weight:600" title="${esc(p.name)}">${esc(p.name)}</span>${statusChip(p)}</div>
            <div class="muted small">Created ${esc(date(p.created_at))} by ${esc(p.created_by)}${p.started_at ? ' · started ' + esc(time(p.started_at)) : ''}</div>
          </a>`).join('')}</div>
          <div><a class="btn btn-primary" href="#/projects/new">${I.plus} New project</a> <a class="btn" href="#/history">${I.clock} History</a></div>`
        : stateView('empty', 'No open projects', 'Create a project to put the team to work. Finished and stopped projects are in History.') +
          `<div class="row" style="justify-content:center"><a class="btn btn-primary" href="#/projects/new">${I.plus} New project</a></div>`;
    } catch (e) { box.innerHTML = stateView('error', 'Could not load projects', esc(e.message), true); box.querySelector('[data-retry]').onclick = load; }
  };
  S.view.onWorkforce = load;
  load();
}

/* ======================================================================
   Screen 1 — New project
   ====================================================================== */
async function viewNew() {
  main(`<div class="center"><form class="card np-card" id="np" novalidate>
      <div class="step-of">Step 1 of 2</div>
      <h1>Name your project</h1>
      <p class="muted" style="margin:0 0 18px">Choose a clear name so you can find it later in History.</p>
      <label class="field" for="np-name">Project name</label>
      <input class="input" id="np-name" maxlength="200" placeholder="e.g. Diabetes awareness – Demo Clinic" autocomplete="off">
      <p class="form-error" id="np-err" role="alert"></p>
      <div class="row" style="justify-content:space-between;margin-top:14px">
        <span class="muted small" id="np-client">Client: …</span>
        <button class="btn btn-primary" id="np-next" type="submit" disabled>Next ${I.chev}</button>
      </div></form></div>`);
  const inp = $('#np-name'), btn = $('#np-next');
  inp.addEventListener('input', () => { btn.disabled = !inp.value.trim(); });
  setTimeout(() => inp.focus(), 30);
  api('/api/projects/flow').then(f => { $('#np-client').textContent = 'Client: ' + (f.client_id || 'unavailable'); })
    .catch(() => { $('#np-client').textContent = 'Client: unavailable'; });
  $('#np').addEventListener('submit', async ev => {
    ev.preventDefault();
    const name = inp.value.trim(); if (!name || btn.disabled) return;
    btn.disabled = true; $('#np-err').textContent = '';
    try {
      const p = await act(() => api('/api/projects', { method: 'POST', json: { name } }));
      if (p) { location.hash = '#/projects/' + encodeURIComponent(p.id); loadWorkforce(); return; }
    } catch (e) { $('#np-err').textContent = e.message; }
    btn.disabled = !inp.value.trim();
  });
}

/* ======================================================================
   Project page: Screen 2 (draft) / Screen 3 (running and after)
   ====================================================================== */
async function viewProject(pid) {
  main(stateView('loading'));
  let live = null, tick = null, startBusy = false, ready = null, readyErr = null, startKey = null, runSig = null;

  async function load() {
    try {
      const st = await api('/api/projects/' + encodeURIComponent(pid));
      const wasDraft = S.project && S.project.project.status === 'draft';
      S.project = st;
      if (st.project.status === 'draft') {
        await loadReady();
        const key = JSON.stringify([st.project.name, ready, readyErr, startBusy]);
        if (key !== startKey || !$('#start')) { startKey = key; renderStart(); }
      }
      else {
        if (wasDraft) $('#main').innerHTML = '';
        // elapsed_s changes on every fetch; timers tick client-side, so ignore it here
        const sig = JSON.stringify(st, (k, v) => k === 'elapsed_s' || k === 'duration_s' ? undefined : v) + S.live + (S.auth ? S.auth.username : '');
        if (sig !== runSig || !$('#convo')) { runSig = sig; renderRunning(); }
      }
      renderSidebar();
    } catch (e) {
      if (!S.project) {
        main(stateView('error', e.status === 404 ? 'Project not found' : 'Could not load this project', esc(e.message), e.status !== 404));
        const r = $('[data-retry]'); if (r) r.onclick = load;
      } else toast('Refresh failed: ' + e.message);
    }
  }
  async function loadReady() {
    try { ready = await api('/api/projects/flow'); readyErr = null; } catch (e) { readyErr = e.message; }
  }

  /* ---------- Screen 2 ---------- */
  function renderStart() {
    const p = S.project.project;
    const draft = $('#start-msg') ? $('#start-msg').value : (store.sget('prefill:' + pid) || '');
    const notReady = ready && !ready.ready;
    main(`<header class="page-head"><h1 class="ellipsis" title="${esc(p.name)}">${esc(p.name)}</h1><p>New project · ready to start</p></header>
      <div class="start-page">
        <div><div class="step-of">Step 2 of 2</div><h2>Ready when you are</h2>
        <p class="muted" style="margin:6px 0 0">Press Start. The team begins and you will see every step live.</p></div>
        ${readyErr ? `<div class="notready" role="alert">Could not check the team: ${esc(readyErr)} <button class="btn btn-sm" id="ready-retry">${I.retry} Retry</button></div>` : ''}
        ${notReady ? `<div class="notready" role="alert" id="notready"><strong>${SYM.needs_attention('var(--red)')} Some agents this project needs are not deployed yet.</strong>
            <div class="muted small" style="margin-top:4px">The project cannot start until every agent below is Active. Activate each one on its agent page (activation gate, then lifecycle transition).</div>
            <ul>${ready.not_active.map(a => `<li><a href="/legacy/?agent=${encodeURIComponent(a.canonical_id)}" target="_blank" rel="noopener">${esc(a.name)} (${esc(a.canonical_id)})</a> — ${esc(a.state)} ${I.ext}</li>`).join('')}</ul></div>` : ''}
        <div class="start-wrap"><button class="start-btn" id="start" ${notReady || startBusy || readyErr ? 'disabled' : ''} aria-describedby="start-help">START</button></div>
        <div class="card instr-card">
          <label class="field" for="start-msg">Instructions for the team (optional)</label>
          <textarea class="input" id="start-msg" maxlength="10000" placeholder="e.g. Make 3 simple posts about Type 2 diabetes for adults 35 to 60. Keep the language easy.">${esc(draft)}</textarea>
          <div class="row">
            ${['Create 3 social posts', 'Plan this month’s content calendar', 'Research a health topic'].map(c => `<button type="button" class="chip" data-chip="${esc(c)}">${esc(c)}</button>`).join('')}
          </div>
          <div class="muted small" id="start-help">Leave this empty and press Start: the agents will begin on their own.</div>
          <p class="form-error" id="start-err" role="alert"></p>
        </div>
      </div>`);
    $$('[data-chip]').forEach(b => b.onclick = () => { const t = $('#start-msg'); t.value = b.dataset.chip; t.focus(); });
    const rr = $('#ready-retry'); if (rr) rr.onclick = async () => { await loadReady(); renderStart(); };
    $('#start').onclick = async () => {
      if (startBusy) return;
      startBusy = true; $('#start').disabled = true; $('#start-err').textContent = '';
      try {
        const st = await act(() => api(`/api/projects/${encodeURIComponent(pid)}/start`, { method: 'POST', json: { message: $('#start-msg').value } }));
        if (st) { store.sset('prefill:' + pid, null); S.project = st; $('#main').innerHTML = ''; renderRunning(); loadWorkforce(); }
        else { startBusy = false; $('#start').disabled = false; }
      } catch (e) {
        startBusy = false;
        if (e.status === 409 && e.detail && e.detail.not_active) { ready = { ready: false, not_active: e.detail.not_active }; renderStart(); }
        else { await load(); const er = $('#start-err'); if (er) er.textContent = e.message; }
      }
    };
  }

  /* ---------- Screen 3 ---------- */
  function renderRunning() {
    const st = S.project, p = st.project;
    const pending = st.pending_approval;
    const ended = ['completed', 'stopped'].includes(p.status);
    const pendingIds = new Set(st.approvals.filter(a => a.pending).map(a => a.request_id));
    const stepsById = Object.fromEntries(st.steps.map(s => [s.id, s]));
    const keyCount = st.steps.reduce((m, s) => (m[s.step_key] = (m[s.step_key] || 0) + 1, m), {});
    const roundLabel = s => keyCount[s.step_key] > 1 ? ` · round ${s.round}` : '';

    // preserve UI state across re-renders
    const convo = $('#convo'), sc = $('#main');
    const nearBottom = !convo || (sc.scrollHeight - sc.scrollTop - sc.clientHeight < 140);
    const prevScroll = convo ? sc.scrollTop : null;
    const focusId = document.activeElement && document.activeElement.id;
    const selStart = document.activeElement && document.activeElement.selectionStart;
    if ($('#composer-text')) S.ui.composer[pid] = $('#composer-text').value;
    $$('[data-note]').forEach(t => { S.ui.notes[t.dataset.note] = t.value; });

    const canRetry = s => s.status === 'needs_attention' && !s.superseded && !ended && !(s.approval_id && pendingIds.has(s.approval_id));
    const actions = s => canRetry(s) ? `<div class="row" style="margin-top:10px">
        <button class="btn btn-sm" data-retry-step="${s.id}">${I.retry} Retry</button>
        <button class="btn btn-sm btn-ghost" data-stop>${I.stop} Stop project</button></div>` : '';

    const items = [];
    for (const m of st.messages) {
      if (m.kind === 'decision') continue; // shown inside the approval card
      if (m.author_type === 'human') {
        items.push(`<div class="bubble wrap"><div class="who">${esc(m.author)} · ${esc(time(m.created_at))}</div>${esc(m.text)}</div>`);
      } else if (m.author_type === 'agent') {
        const s = stepsById[m.step_id] || {};
        const long = m.text.length > 700 || m.text.split('\n').length > 10;
        const open = S.ui.expanded.has(m.id);
        items.push(`<article class="acard" aria-label="${esc(m.agent_name)} update">
          <div class="acard-head">${s.id ? stepSym(s, pendingIds) : SYM.completed()}<span class="name">${esc(m.agent_name || m.agent_id)}</span>
            <span class="tag">${esc(m.step_tag || 'Update')}${s.id ? esc(roundLabel(s)) : ''}</span><span class="faint small" style="margin-left:auto">${esc(time(m.created_at))}</span></div>
          <div class="body${long && !open ? ' clamp' : ''}">${esc(m.text)}</div>
          ${long ? `<button class="more" data-expand="${m.id}" aria-expanded="${open}">${open ? 'Show less' : 'Show more'}</button>` : ''}
        </article>`);
        for (const a of st.approvals.filter(a => a.step_id === m.step_id)) items.push(approvalCard(a, s, m));
      } else if (m.kind === 'error') {
        const s = stepsById[m.step_id];
        if (s && s.approval_id) continue;
        items.push(`<div class="errcard" role="alert"><div class="title">${SYM.needs_attention('var(--red)')}${s ? esc(s.agent_name) + ' · ' + esc(s.tag) + esc(roundLabel(s)) : 'Project'}</div>
          <div class="wrap" style="margin-top:4px">${esc(m.text)}</div>${s ? actions(s) : ''}</div>`);
      } else {
        items.push(`<div class="sysnote wrap">${esc(m.text)} · ${esc(time(m.created_at))}</div>`);
      }
    }
    for (const s of st.steps.filter(s => s.status === 'in_progress')) {
      items.push(`<div class="working" role="status">${SYM.in_progress()}<span><strong>${esc(s.agent_name)}</strong> is working on ${esc(s.tag.toLowerCase())}${esc(roundLabel(s))}… <span data-since="${esc(s.started_at)}">${clock(since(s.started_at))}</span></span></div>`);
    }
    if (p.status === 'running' && !pending && !st.steps.some(s => s.status === 'in_progress') && st.steps.some(s => s.status === 'queued')) {
      items.push(`<div class="working">${SYM.queued()}<span>Starting the next step…</span></div>`);
    }

    function approvalCard(a, s, m) {
      if (a.pending) {
        const showFull = S.ui.fullReq.has(a.request_id), note = S.ui.notes[a.request_id] || '';
        const busy = S.busy.has(a.request_id) || ended;
        return `<section class="decision" aria-label="Your decision is needed">
          <div class="title">${SYM.needs_attention()} Your decision is needed <span class="asked">Asked by ${esc(a.agent_name)}</span></div>
          <div class="wrap">${esc(a.question || 'Can the team continue?')}</div>
          <button class="toggle" data-fullreq="${esc(a.request_id)}" aria-expanded="${showFull}">${showFull ? I.chevDown : I.chev} Read the full request</button>
          ${showFull ? `<div class="full-req">${esc(m.text)}</div>` : ''}
          <div class="row">
            <button class="btn btn-primary" data-decide="approve" data-req="${esc(a.request_id)}" ${busy ? 'disabled' : ''}>${I.check} Approve</button>
            <button class="btn btn-reject" data-decide="reject" data-req="${esc(a.request_id)}" ${busy ? 'disabled' : ''}>${I.x} Reject</button>
            <button class="btn btn-changes" data-decide="approve_with_changes" data-req="${esc(a.request_id)}" ${busy || !note.trim() ? 'disabled' : ''}>${I.pencil} Approve with changes</button>
          </div>
          <label class="field" for="note-${esc(a.request_id)}">Your changes or reason (the agents will read this and update the work; required for Approve with changes)</label>
          <textarea class="input" id="note-${esc(a.request_id)}" data-note="${esc(a.request_id)}" maxlength="10000" placeholder="e.g. Keep the idea, remove the word naturally, and add a line to visit the clinic.">${esc(note)}</textarea>
          <p class="form-error" id="err-${esc(a.request_id)}" role="alert"></p>
        </section>`;
      }
      const label = { approve: 'Approved', reject: 'Rejected', approve_with_changes: 'Approved with changes' }[a.decision] || a.decision;
      const sym = a.decision === 'reject' ? SYM.needs_attention('var(--red)') : a.decision === 'approve' ? SYM.completed() : `<span style="color:var(--sky)">${I.pencil}</span>`;
      return `<section class="decision resolved"><div class="title">${sym} ${esc(label)} by ${esc(a.decided_by)} <span class="faint small">${esc(time(a.decided_at))}</span> <span class="asked" style="color:var(--muted);border-color:var(--border)">Asked by ${esc(a.agent_name)}</span></div>
        <div class="muted wrap">${esc(a.question || '')}</div>${a.note ? `<div class="wrap">“${esc(a.note)}”</div>` : ''}${a.decision === 'reject' ? actions(s) : ''}</section>`;
    }

    const started = p.started_at ? `Started ${time(p.started_at)} · ${PSTATUS[p.status] || p.status}` : PSTATUS[p.status];
    const canPause = p.status === 'running', canResume = p.status === 'paused';
    const composerDisabled = ended;
    $('#main').innerHTML = `<div id="live-banner">${liveBanner()}</div>
      <header class="proj-head">
        <div class="titles"><h1 class="ellipsis" title="${esc(p.name)}">${esc(p.name)}</h1><div class="muted small">${esc(started)} · Client: ${esc(p.client_id)}</div></div>
        ${statusChip(p, pending)}
        ${canPause ? `<button class="btn btn-pause" id="pause">${I.pause} Pause</button>` : ''}
        ${canResume ? `<button class="btn btn-pause resume" id="resume">${I.play} Resume</button>` : ''}
        ${!ended ? `<button class="btn btn-sm btn-ghost" data-stop title="Stop this project">${I.stop}<span class="sr-only">Stop project</span></button>` : `<a class="btn btn-sm" href="#/history/${esc(p.id)}">View in History</a>`}
      </header>
      <div class="convo" id="convo" aria-live="polite">${items.join('') || stateView('empty', 'Nothing yet', 'The first agent update will appear here.')}</div>
      <form class="composer" id="composer">
        <label class="sr-only" for="composer-text">Message the team</label>
        <textarea class="input" id="composer-text" maxlength="10000" ${composerDisabled ? 'disabled' : ''} placeholder="${composerDisabled ? 'This project has ended.' : 'Message the team… (leave empty and the agents continue on their own)'}">${esc(S.ui.composer[pid] || '')}</textarea>
        <button class="btn btn-primary" id="send" type="submit" ${composerDisabled || !(S.ui.composer[pid] || '').trim() ? 'disabled' : ''}>${I.send} Send</button>
      </form>`;

    // right panel
    const visible = st.steps.filter(s => s.status !== 'skipped' || true);
    const done = st.counts.completed;
    $('#shell').classList.add('with-right'); const rp = $('#rightpanel'); rp.hidden = false;
    rp.innerHTML = `<div><div class="rp-title">Agents on this project</div><div class="muted small">${done} of ${st.counts.total} steps finished</div></div>
      <div class="rp-steps">${visible.map(s => {
        const awaiting = s.approval_id && pendingIds.has(s.approval_id);
        let line;
        if (s.status === 'completed') line = `<span class="muted">Completed · ${clock(s.elapsed_s)}</span>`;
        else if (s.status === 'in_progress') line = `<span style="color:var(--sky)">In progress… <span data-since="${esc(s.started_at)}">${clock(since(s.started_at))}</span></span>`;
        else if (s.status === 'needs_attention') line = awaiting ? `<span style="color:var(--amber)">Waiting for your decision</span>`
          : s.superseded ? `<span class="muted">Retried in a new round</span>` : `<span style="color:#ff8a9b" title="${esc(s.error || '')}">${esc((s.error || 'Needs attention').slice(0, 90))}${(s.error || '').length > 90 ? '…' : ''}</span>`;
        else if (s.status === 'skipped') line = `<span class="faint">Skipped</span>`;
        else line = `<span class="muted">${s.source_approval_id ? 'Queued · uses your note' : 'Queued'}</span>`;
        return `<div class="rp-step${s.status === 'in_progress' ? ' cur' : ''}${s.status === 'needs_attention' && !s.superseded ? ' att' : ''}">${stepSym(s, pendingIds)}
          <div><div class="n">${esc(s.agent_name)}${esc(roundLabel(s))}</div><div class="r">${esc(s.responsibility)}</div><div class="s">${line}</div></div></div>`;
      }).join('') || '<div class="muted small">No steps yet.</div>'}</div>
      <div class="legend" aria-label="Legend"><div>${SYM.completed()} Completed</div><div>${SYM.in_progress()} In progress</div><div>${SYM.needs_attention()} Needs attention</div><div>${SYM.queued()} Queued</div></div>`;

    // wire up
    const scroller = $('#main');
    if (nearBottom) { scroller.scrollTop = scroller.scrollHeight; requestAnimationFrame(() => { scroller.scrollTop = scroller.scrollHeight; }); }
    else if (prevScroll != null) scroller.scrollTop = prevScroll;
    if (focusId && $('#' + CSS.escape(focusId))) { const el = $('#' + CSS.escape(focusId)); el.focus({ preventScroll: true }); if (selStart != null && el.setSelectionRange) try { el.setSelectionRange(selStart, selStart); } catch (e) {} }
    $$('[data-expand]').forEach(b => b.onclick = () => { const id = +b.dataset.expand; S.ui.expanded.has(id) ? S.ui.expanded.delete(id) : S.ui.expanded.add(id); renderRunning(); });
    $$('[data-fullreq]').forEach(b => b.onclick = () => { const id = b.dataset.fullreq; S.ui.fullReq.has(id) ? S.ui.fullReq.delete(id) : S.ui.fullReq.add(id); renderRunning(); });
    $$('[data-note]').forEach(t => t.addEventListener('input', () => {
      S.ui.notes[t.dataset.note] = t.value;
      const b = $(`[data-decide="approve_with_changes"][data-req="${CSS.escape(t.dataset.note)}"]`); if (b) b.disabled = !t.value.trim() || S.busy.has(t.dataset.note);
    }));
    $$('[data-decide]').forEach(b => b.onclick = () => decide(b.dataset.req, b.dataset.decide));
    $$('[data-retry-step]').forEach(b => b.onclick = () => post(`/steps/${b.dataset.retryStep}/retry`, b, 'Retry started'));
    $$('[data-stop]').forEach(b => b.onclick = async () => { if (confirm('Stop this project? Steps that have not started will be skipped.')) post('/stop', b, 'Project stopped'); });
    const pb = $('#pause'); if (pb) pb.onclick = () => post('/pause', pb, 'Paused');
    const rb = $('#resume'); if (rb) rb.onclick = () => post('/resume', rb, 'Resumed');
    const ct = $('#composer-text');
    ct.addEventListener('input', () => { S.ui.composer[pid] = ct.value; $('#send').disabled = !ct.value.trim(); ct.style.height = 'auto'; ct.style.height = Math.min(160, ct.scrollHeight) + 'px'; });
    ct.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#composer').requestSubmit(); } });
    $('#composer').onsubmit = async e => {
      e.preventDefault();
      const text = ct.value.trim(); if (!text) return;
      $('#send').disabled = true;
      try { const r = await act(() => api(`/api/projects/${encodeURIComponent(pid)}/messages`, { method: 'POST', json: { text } }));
        if (r) { S.ui.composer[pid] = ''; ct.value = ''; await load(); } }
      catch (er) { toast(er.message); }
      finally { const sb = $('#send'); if (sb) sb.disabled = !($('#composer-text').value || '').trim(); }
    };
  }

  async function post(path, btn, okMsg) {
    if (btn) btn.disabled = true;
    try { const r = await act(() => api(`/api/projects/${encodeURIComponent(pid)}${path}`, { method: 'POST' })); if (r) toast(okMsg); }
    catch (e) { toast(e.message); }
    await load(); loadWorkforce();
  }
  async function decide(req, decision) {
    if (S.busy.has(req)) return; // ignore double clicks
    const note = (S.ui.notes[req] || '').trim();
    if (decision === 'approve_with_changes' && !note) { const er = $('#err-' + CSS.escape(req)); if (er) er.textContent = 'Write your changes first.'; return; }
    S.busy.add(req); $$(`[data-req="${CSS.escape(req)}"]`).forEach(b => b.disabled = true);
    try {
      const r = await act(() => api(`/api/projects/${encodeURIComponent(pid)}/approvals/${encodeURIComponent(req)}/decision`, { method: 'POST', json: { decision, note: note || null } }));
      if (r) { delete S.ui.notes[req]; toast('Decision recorded'); }
    } catch (e) { toast(e.status === 409 ? 'Already decided: ' + e.message : e.message); }
    S.busy.delete(req);
    await load(); loadWorkforce();
  }

  live = new Live('/api/projects/' + encodeURIComponent(pid) + '/stream', () => { load(); }, mode => { S.live = mode; const b = $('#live-banner'); if (b) b.innerHTML = liveBanner(); });
  S.view.onWorkforce = () => { if (S.project && S.project.project.status === 'draft' && ready && !ready.ready) load(); };
  tick = setInterval(() => { $$('[data-since]').forEach(el => { el.textContent = clock(since(el.dataset.since)); }); }, 1000);
  S.cleanup = () => { live.stop(); clearInterval(tick); };
  await load();
  live.start();
}

/* ======================================================================
   Screen 5 — History
   ====================================================================== */
async function viewHistory(selId) {
  main(`<header class="page-head"><h1>History</h1><p>Every earlier project, with who did what and what you decided</p></header>
    <div class="hist"><div class="hist-list"><label class="sr-only" for="hq">Search projects</label>
      <input class="input" id="hq" type="search" placeholder="Search projects" value="${esc(S.ui.histQ)}">
      <div id="hl">${stateView('loading')}</div></div>
      <div class="card hist-detail" id="hd">${selId ? stateView('loading') : stateView('empty', 'Select a project', 'Pick a project on the left to see what happened.')}</div></div>`);
  let list = null;
  const renderList = () => {
    const q = S.ui.histQ.toLowerCase();
    const items = (list || []).filter(p => !q || p.name.toLowerCase().includes(q));
    $('#hl').innerHTML = !list.length ? stateView('empty', 'No earlier projects yet', 'Completed and stopped projects appear here.')
      : !items.length ? `<p class="muted">No projects match “${esc(S.ui.histQ)}”.</p>`
      : `<div class="hist-list">${items.map(p => `<button class="hist-item${p.id === selId ? ' active' : ''}" data-id="${esc(p.id)}">
          <div class="row" style="justify-content:space-between;flex-wrap:nowrap"><span class="t ellipsis" title="${esc(p.name)}">${esc(p.name)}</span>
          <span class="status-chip st-${esc(p.status)}">${p.status === 'stopped' ? 'Stopped' : 'Completed'}</span></div>
          <div class="muted small">${esc(date(p.started_at || p.created_at))} · ${esc(dur(p.duration_s))} · ${esc(p.agents_used)} agent${p.agents_used === 1 ? '' : 's'}</div></button>`).join('')}</div>`;
    $$('#hl [data-id]').forEach(b => b.onclick = () => { location.hash = '#/history/' + encodeURIComponent(b.dataset.id); });
  };
  const loadList = async () => {
    try { list = await api('/api/projects/history'); renderList(); }
    catch (e) { $('#hl').innerHTML = stateView('error', 'Could not load history', esc(e.message), true); $('#hl [data-retry]').onclick = loadList; }
  };
  $('#hq').addEventListener('input', e => { S.ui.histQ = e.target.value; if (list) renderList(); });

  const loadDetail = async () => {
    if (!selId) return;
    const box = $('#hd');
    try {
      const d = await api(`/api/projects/${encodeURIComponent(selId)}/summary`);
      const p = d.project, t = d.tiles;
      const icon = it => it.type === 'human' || it.type === 'decision'
        ? (it.decision === 'reject' ? SYM.needs_attention('var(--red)') : `<span style="color:var(--sky)">${I.pencil}</span>`)
        : it.type === 'step' ? (it.status === 'completed' ? SYM.completed() : it.status === 'in_progress' ? SYM.in_progress() : SYM.needs_attention(it.status === 'needs_attention' ? 'var(--amber)' : 'var(--red)'))
        : SYM.queued('var(--grey)');
      box.innerHTML = `<div class="row" style="justify-content:space-between;flex-wrap:nowrap;align-items:flex-start">
          <div style="min-width:0"><h2 style="margin:0;font-size:20px" class="wrap">${esc(p.name)}</h2><div class="muted small">${esc(date(p.started_at || p.created_at))} · Client: ${esc(p.client_id)} · created by ${esc(p.created_by)}</div></div>
          <span class="status-chip st-${esc(p.status)}">${esc(PSTATUS[p.status] || p.status)}</span></div>
        <div class="tiles4">${tile(t.duration_s == null ? null : dur(t.duration_s), 'Duration', 'c-sky', true)}${tile(t.agents_used, 'Agents used', 'c-green', true)}${tile(t.human_approvals, 'Human decisions', 'c-amber', true)}${tile(t.deliverables, 'Deliverables', 'c-indigo', true)}</div>
        <div><p class="section-label" style="margin-bottom:12px">What happened</p>
          <div class="timeline">${d.timeline.length ? d.timeline.map(it => `<div class="tl">${icon(it)}<div><div class="wrap">${esc(it.title)}</div>${it.detail ? `<div class="d">${it.type === 'human' || it.type === 'decision' ? '“' + esc(it.detail) + '”' : esc(it.detail)}</div>` : ''}</div><div class="when">${esc(time(it.at))}</div></div>`).join('') : '<p class="muted">Nothing was recorded for this project.</p>'}</div></div>
        <div><p class="section-label" style="margin-bottom:8px">Deliverables</p>
          ${d.deliverables.length ? `<ul style="margin:0;padding-left:18px">${d.deliverables.map(x => `<li><strong>${esc(x.name)}</strong> — ${esc(x.agent_name)}${x.round > 1 ? ' · round ' + x.round : ''}${x.summary ? `<div class="muted small wrap">${esc(x.summary)}</div>` : ''}</li>`).join('')}</ul>` : '<p class="muted" style="margin:0">No deliverables were completed.</p>'}</div>
        <div class="row"><a class="btn btn-primary" href="#/projects/${esc(p.id)}">Open full conversation</a><button class="btn" id="again">Run again</button></div>
        <p class="form-error" id="again-err" role="alert"></p>`;
      $('#again').onclick = async () => {
        const b = $('#again'); b.disabled = true;
        try {
          const st = await api(`/api/projects/${encodeURIComponent(selId)}`);
          const first = st.messages.find(m => m.author_type === 'human' && m.kind === 'start');
          const np = await act(() => api('/api/projects', { method: 'POST', json: { name: p.name, rerun_of: p.id } }));
          if (np) { if (first) store.sset('prefill:' + np.id, first.text); location.hash = '#/projects/' + encodeURIComponent(np.id); return; }
        } catch (e) { $('#again-err').textContent = e.message; }
        b.disabled = false;
      };
    } catch (e) {
      box.innerHTML = stateView('error', 'Could not load this project', esc(e.message), true);
      box.querySelector('[data-retry]').onclick = loadDetail;
    }
  };
  S.view.onWorkforce = () => { loadList(); };
  loadList(); loadDetail();
}

/* ======================================================================
   Screen 6 — Agents
   ====================================================================== */
function viewAgents() {
  main(`<header class="page-head"><h1>Agents</h1><p>Your whole team: what each one does and whether it is working</p></header><div class="page" id="ag">${stateView('loading')}</div>`);
  S.view.onWorkforce = render;
  function render() {
    const box = $('#ag'); if (!box) return;
    const wf = S.wf;
    if (!wf) { box.innerHTML = S.wfError ? stateView('error', 'Could not load the agents', 'The backend did not answer.', true) : stateView('loading'); const r = box.querySelector('[data-retry]'); if (r) r.onclick = loadWorkforce; return; }
    if (!wf.available) { box.innerHTML = stateView('error', 'Agent data unavailable', 'The database is not reachable.', true); box.querySelector('[data-retry]').onclick = loadWorkforce; return; }
    const f = S.ui.agents, c = wf.counts;
    const focusId = document.activeElement && document.activeElement.id;
    const uniq = k => [...new Set(wf.agents.map(a => a[k]))].sort();
    const stateLabel = a => a.state === 'on_standby' && a.lifecycle_status === 'monitored' ? 'Monitoring' : STATE_META[a.state].label;
    let rows = wf.agents.filter(a =>
      (!f.stage || a.stage === f.stage) && (!f.dept || a.department === f.dept) && (!f.prio || a.priority === f.prio) && (!f.type || a.agent_type === f.type) &&
      (!f.state || (f.state === 'needs_attention' ? a.needs_attention : a.state === f.state)) &&
      (!f.q || [a.canonical_id, a.name, a.designation, a.department].join(' ').toLowerCase().includes(f.q.toLowerCase())));
    const key = { canonical_id: a => a.canonical_id, name: a => a.name, department: a => a.department, stage: a => a.stage, state: a => stateLabel(a), last: a => a.last_activity ? a.last_activity.at || '' : '' }[f.sort] || (a => a.canonical_id);
    rows.sort((x, y) => String(key(x)).localeCompare(String(key(y)), undefined, { numeric: true }) * f.dir);
    const sel = (id, label, opts, cur) => `<label class="sr-only" for="${id}">${label}</label><select class="chip-select${cur ? ' on' : ''}" id="${id}">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    const th = (k, l) => `<th aria-sort="${f.sort === k ? (f.dir > 0 ? 'ascending' : 'descending') : 'none'}"><button data-sort="${k}">${l}${f.sort === k ? (f.dir > 0 ? ' ▲' : ' ▼') : ''}</button></th>`;
    box.innerHTML = `
      <div class="tiles5">${tile(c.active, 'Active', 'c-green', true)}${tile(c.awaiting_approval, 'Awaiting approval', 'c-amber', true)}${tile(c.on_standby, 'On standby', 'c-standby', true)}${tile(c.not_deployed, 'Not deployed', 'c-grey', true)}${tile(c.needs_attention, 'Needs attention', 'c-red', true)}</div>
      <div class="filters">
        <label class="sr-only" for="aq">Search agents</label><input class="input" id="aq" type="search" placeholder="Search name, ID or role" value="${esc(f.q)}">
        ${sel('f-stage', 'Stage', [['', 'All stages'], ...uniq('stage').map(s => [s, STAGES[s] || s])], f.stage)}
        ${sel('f-state', 'State', [['', 'All states'], ['active', 'Active'], ['awaiting_approval', 'Awaiting approval'], ['on_standby', 'On standby'], ['not_deployed', 'Not deployed'], ['needs_attention', 'Needs attention']], f.state)}
        ${sel('f-dept', 'Department', [['', 'All departments'], ...uniq('department').map(s => [s, s])], f.dept)}
        ${sel('f-prio', 'Priority', [['', 'All priorities'], ...uniq('priority').map(s => [s, s])], f.prio)}
        ${sel('f-type', 'Type', [['', 'All types'], ...uniq('agent_type').map(s => [s, s])], f.type)}
        <span class="muted small" style="margin-left:auto">${rows.length} of ${wf.total} agents</span>
      </div>
      <div class="table-wrap"><table><thead><tr>${th('canonical_id', 'ID')}${th('name', 'Agent and role')}${th('department', 'Department')}${th('stage', 'Stage')}${th('state', 'State')}${th('last', 'Last activity')}</tr></thead>
        <tbody>${rows.length ? rows.map(a => {
          const meta = STATE_META[a.state], la = a.last_activity;
          const dot = a.state === 'on_standby' && a.lifecycle_status === 'monitored' ? 'green' : meta.dot;
          return `<tr tabindex="0" data-agent="${esc(a.canonical_id)}" aria-label="Open ${esc(a.name)}">
            <td class="mono">${esc(a.canonical_id)}</td>
            <td><div class="agent-name">${esc(a.name)}</div><div class="agent-role">${esc(a.designation)}</div></td>
            <td>${esc(a.department)}</td><td><span class="tag">${esc(STAGES[a.stage] || a.stage)}</span></td>
            <td><span class="state-cell"><span class="dot ${dot}"></span>${esc(stateLabel(a))}${a.needs_attention ? ` <span title="Needs attention">${SYM.needs_attention('var(--red)')}</span>` : ''}</span>
              <div class="faint small">${esc(a.lifecycle_status)}</div></td>
            <td class="muted">${la ? `<div class="wrap">${esc(la.text)}</div><div class="faint small">${esc(la.status)}${la.at ? ' · ' + esc(date(la.at)) + ' ' + esc(time(la.at)) : ''}</div>` : (a.state === 'not_deployed' ? 'Not yet activated' : 'No runs yet')}</td></tr>`;
        }).join('') : `<tr><td colspan="6">${stateView('empty', 'No agents match these filters', '')}</td></tr>`}</tbody></table></div>
      <p class="muted small">Click an agent to open its page: job, limits, activation gate and lifecycle (the existing agent page).</p>`;
    $('#aq').addEventListener('input', e => { f.q = e.target.value; render(); });
    [['f-stage', 'stage'], ['f-state', 'state'], ['f-dept', 'dept'], ['f-prio', 'prio'], ['f-type', 'type']].forEach(([id, k]) => $('#' + id).onchange = e => { f[k] = e.target.value; render(); });
    $$('[data-sort]').forEach(b => b.onclick = () => { if (f.sort === b.dataset.sort) f.dir = -f.dir; else { f.sort = b.dataset.sort; f.dir = 1; } render(); });
    $$('tr[data-agent]').forEach(tr => {
      const go = () => { location.href = '/legacy/?agent=' + encodeURIComponent(tr.dataset.agent); };
      tr.onclick = go; tr.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } };
    });
    if (focusId === 'aq') { const q = $('#aq'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
    else if (focusId && $('#' + focusId)) $('#' + focusId).focus();
  }
  render();
}

/* ======================================================================
   boot
   ====================================================================== */
renderSidebar();
loadWorkforce();
wfLive.start();
route();
})();
