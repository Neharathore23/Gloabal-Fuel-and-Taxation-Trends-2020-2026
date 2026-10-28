/* Filter handling, chart/KPI/table loading. Charts are Plotly figures built server-side (src/charts.py). */
(() => {
  'use strict';
  const STORE = 'fuelFilters.v1';
  const form = document.getElementById('filters');
  const MULTI = ['country', 'region', 'fuel', 'income'];
  const LABEL = { date_from: 'From', date_to: 'To', country: 'Countries', region: 'Region', fuel: 'Fuel', income: 'Income' };
  const FMT = {
    usd: v => (v == null ? '–' : '$' + Number(v).toFixed(2)),
    pct: v => (v == null ? '–' : Number(v).toFixed(1) + '%'),
    int: v => (v == null ? '–' : Math.round(Number(v)).toLocaleString('en-US')),
    text: v => (v == null ? '–' : String(v)),
  };
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  let debounce = null;

  if (window.Plotly && window.FUEL && window.FUEL.topojsonURL) Plotly.setPlotConfig({ topojsonURL: window.FUEL.topojsonURL });

  // ---------------------------------------------------------------- filters <-> URL
  function filterParams() {
    const p = new URLSearchParams();
    if (!form) return p;
    ['date_from', 'date_to'].forEach(n => { const el = form.elements[n]; if (el && el.value) p.set(n, el.value); });
    MULTI.forEach(n => {
      const vals = $$(`[name="${n}"]`, form).flatMap(el =>
        el.tagName === 'SELECT' ? Array.from(el.selectedOptions).map(o => o.value) : (el.checked ? [el.value] : []));
      if (vals.length) p.set(n, vals.join(','));
    });
    return p;
  }
  function applyParams(p) {
    if (!form) return;
    ['date_from', 'date_to'].forEach(n => { if (form.elements[n]) form.elements[n].value = p.get(n) || ''; });
    MULTI.forEach(n => {
      const set = new Set((p.get(n) || '').split(',').filter(Boolean));
      $$(`[name="${n}"]`, form).forEach(el => {
        if (el.tagName === 'SELECT') Array.from(el.options).forEach(o => { o.selected = set.has(o.value); });
        else el.checked = set.has(el.value);
      });
    });
  }
  function persist(p) {
    const qs = p.toString();
    try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { /* ignore */ }
    try { qs ? localStorage.setItem(STORE, qs) : localStorage.removeItem(STORE); } catch (e) { /* storage blocked */ }
    $$('a[data-keep-filters]').forEach(a => { a.href = a.dataset.base + (qs ? '?' + qs : ''); });
  }
  function names(sel, p) {
    const opt = new Map($$('#f-country option').map(o => [o.value, o.textContent]));
    return (p.get(sel) || '').split(',').filter(Boolean).map(v => (sel === 'country' ? opt.get(v) || v : v));
  }
  function summarise(p) {
    const parts = [];
    ['fuel', 'region', 'income', 'country'].forEach(k => {
      const v = names(k, p);
      if (v.length) parts.push(`${LABEL[k]}: ${v.length > 3 ? v.slice(0, 3).join(', ') + ` +${v.length - 3}` : v.join(', ')}`);
    });
    if (p.get('date_from') || p.get('date_to')) parts.push(`${LABEL.date_from} ${p.get('date_from') || 'start'} ${LABEL.date_to.toLowerCase()} ${p.get('date_to') || 'end'}`);
    const out = document.getElementById('filter-summary');
    if (out) out.textContent = parts.length ? parts.join(' · ') : 'All countries, fuels and months';
    const badge = document.getElementById('filter-count');
    if (badge) badge.textContent = String(parts.length);
  }
  function dateProblem(p) {
    const a = p.get('date_from'), b = p.get('date_to');
    return a && b && a > b ? '“From” must not be after “To”.' : '';
  }

  // ---------------------------------------------------------------- state helpers
  function setState(card, state, msg) {
    const box = card.querySelector('.chart-state');
    if (!box) return;
    box.classList.remove('is-error');
    box.hidden = state === 'ready';
    box.replaceChildren();
    if (state === 'loading') {
      const s = document.createElement('div'); s.className = 'spinner-border spinner-border-sm'; s.setAttribute('aria-hidden', 'true');
      box.append(s, document.createTextNode('Loading…'));
    } else if (state === 'empty') {
      box.textContent = msg || 'No data matches the current filters.';
    } else if (state === 'error') {
      box.classList.add('is-error');
      const t = document.createElement('div'); t.textContent = 'Could not load this chart: ' + (msg || 'unknown error');
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-sm btn-outline-danger retry'; b.textContent = 'Retry';
      box.append(t, b);
    }
  }
  async function getJSON(url, signal) {
    const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    return body;
  }
  function query(card) {
    const p = filterParams();
    $$('[data-opt]', card).forEach(el => { if (el.value) p.set(el.dataset.opt, el.value); });
    return p;
  }
  function begin(el) { if (el._ctl) el._ctl.abort(); el._ctl = new AbortController(); return el._ctl.signal; }

  // ---------------------------------------------------------------- loaders
  async function loadChart(card) {
    const name = card.dataset.chart, area = card.querySelector('.chart-area'), note = card.querySelector('.chart-note');
    const signal = begin(card);
    setState(card, 'loading');
    try {
      if (typeof Plotly === 'undefined') throw new Error('Plotly.js did not load (offline?). Check your connection or run scripts/vendor_assets.py.');
      const body = await getJSON(`/api/chart/${encodeURIComponent(name)}?${query(card)}`, signal);
      if (body.empty) { Plotly.purge(area); note.textContent = ''; setState(card, 'empty', body.message); return; }
      await Plotly.react(area, body.figure.data, body.figure.layout,
        { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'], toImageButtonOptions: { filename: 'fuel-' + name } });
      note.textContent = body.note + (body.synthetic ? ' [Synthetic data]' : '');
      setState(card, 'ready');
    } catch (err) {
      if (err.name !== 'AbortError') setState(card, 'error', err.message);
    }
  }
  async function loadKpis() {
    const cards = $$('[data-kpi]');
    if (!cards.length) return;
    const signal = begin(document.body);
    cards.forEach(c => c.classList.add('is-loading'));
    try {
      const k = await getJSON(`/api/kpis?${filterParams()}`, signal);
      const f = { avg_price: v => FMT.usd(v), effective_tax_burden_pct: FMT.pct, subsidy_to_price_pct: FMT.pct, n_countries: FMT.int, n_records: FMT.int };
      cards.forEach(c => { c.querySelector('.kpi-value').textContent = k.empty ? '–' : (f[c.dataset.kpi] || FMT.text)(k[c.dataset.kpi]); c.classList.remove('is-loading'); });
      $$('[data-empty-banner]').forEach(b => b.classList.toggle('d-none', !k.empty));
    } catch (err) {
      if (err.name === 'AbortError') return;
      cards.forEach(c => { c.querySelector('.kpi-value').textContent = '–'; c.classList.remove('is-loading'); });
    }
  }
  async function loadTable(card) {
    const wrap = card.querySelector('.table-wrap'), signal = begin(card);
    const p = filterParams();
    $$('[data-opt]', card).forEach(el => p.set(el.dataset.opt, el.value));
    wrap.replaceChildren(Object.assign(document.createElement('div'), { className: 'table-state small text-muted p-3', textContent: 'Loading…' }));
    try {
      const t = await getJSON(`/api/data/${encodeURIComponent(card.dataset.table)}?${p}`, signal);
      if (t.empty) { wrap.firstChild.textContent = 'No data matches the current filters.'; return; }
      wrap.replaceChildren(buildTable(t));
    } catch (err) {
      if (err.name !== 'AbortError') wrap.firstChild.textContent = 'Could not load table: ' + err.message;
    }
  }
  function buildTable(t) {
    let rows = t.rows.slice(), sort = { key: null, dir: 1 };
    const table = document.createElement('table'); table.className = 'table table-sm table-hover';
    const thead = table.createTHead().insertRow(), tbody = table.createTBody();
    const draw = () => {
      tbody.replaceChildren();
      rows.forEach(r => {
        const tr = tbody.insertRow();
        t.columns.forEach(c => { const td = tr.insertCell(); td.textContent = (FMT[c.fmt] || FMT.text)(r[c.key]); if (c.fmt !== 'text') td.className = 'num'; });
      });
    };
    t.columns.forEach(c => {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = c.label; th.tabIndex = 0;
      if (c.fmt !== 'text') th.className = 'num';
      const go = () => {
        sort.dir = sort.key === c.key ? -sort.dir : (c.fmt === 'text' ? 1 : -1); sort.key = c.key;
        rows.sort((a, b) => { const x = a[c.key], y = b[c.key]; if (x == null) return 1; if (y == null) return -1;
          return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * sort.dir; });
        $$('th', thead).forEach(h => h.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', sort.dir > 0 ? 'ascending' : 'descending'); draw();
      };
      th.addEventListener('click', go); th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
      thead.appendChild(th);
    });
    draw();
    return table;
  }

  function refreshAll() {
    const p = filterParams(), problem = dateProblem(p), msg = document.getElementById('filter-msg');
    if (msg) msg.textContent = problem;
    summarise(p); persist(p);
    if (problem) return;
    loadKpis();
    $$('[data-chart]').forEach(loadChart);
    $$('[data-table]').forEach(loadTable);
  }

  // ---------------------------------------------------------------- wiring
  document.addEventListener('click', e => {
    const b = e.target.closest('.retry'); if (b) loadChart(b.closest('[data-chart]'));
  });
  document.addEventListener('change', e => {
    const opt = e.target.closest('[data-opt]');
    if (opt) { const c = opt.closest('[data-chart]'), t = opt.closest('[data-table]'); if (c) loadChart(c); if (t) loadTable(t); return; }
    if (form && form.contains(e.target)) { clearTimeout(debounce); debounce = setTimeout(refreshAll, 300); }
  });
  const reset = document.getElementById('filter-reset');
  if (reset) reset.addEventListener('click', () => { applyParams(new URLSearchParams()); refreshAll(); });

  if (form) {
    let p = new URLSearchParams(location.search);
    const has = ['date_from', 'date_to', ...MULTI].some(k => p.has(k));
    if (!has) { try { p = new URLSearchParams(localStorage.getItem(STORE) || ''); } catch (e) { p = new URLSearchParams(); } }
    applyParams(p);
    refreshAll();
  }
})();
