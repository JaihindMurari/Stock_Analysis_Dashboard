/* ═══════════════════════════════════════════════════════════════
   MarketPulse India — Core App JS
   Handles: theme toggle, sidebar, global search, toasts,
            market-status indicator, polling bootstrap
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── API helpers ────────────────────────────────────────────────────────────────
const API = {
  base: '/api',
  async get(path) {
    const res = await fetch(this.base + path);
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
    const json = await res.json();
    return json.data ?? json;
  },
  async post(path) {
    const res = await fetch(this.base + path, { method: 'POST' });
    if (!res.ok) throw new Error(`API POST ${path} → ${res.status}`);
    return res.json();
  }
};

// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 3500) {
  const icons = { success: 'bi-check-circle-fill', error: 'bi-x-circle-fill', info: 'bi-info-circle-fill' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<i class="bi ${icons[type] ?? icons.info}"></i><span>${msg}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── Number formatting ─────────────────────────────────────────────────────────
function fmtPrice(v) {
  if (v == null) return '—';
  return '₹' + Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtPct(v) {
  if (v == null) return '—';
  const s = Number(v).toFixed(2);
  return (v >= 0 ? '+' : '') + s + '%';
}
function fmtVol(v) {
  if (v == null) return '—';
  if (v >= 1e7) return (v / 1e7).toFixed(2) + ' Cr';
  if (v >= 1e5) return (v / 1e5).toFixed(2) + ' L';
  return Number(v).toLocaleString('en-IN');
}
function fmtCap(v) {
  if (!v) return '—';
  if (v >= 1e12) return '₹' + (v / 1e12).toFixed(2) + 'T';
  if (v >= 1e9)  return '₹' + (v / 1e9).toFixed(2) + 'B';
  return '₹' + (v / 1e6).toFixed(2) + 'M';
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

// ── Theme ──────────────────────────────────────────────────────────────────────
const THEME_KEY = 'mpulse-theme';
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
}
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem(THEME_KEY, next);
  updateThemeIcon(next);
}
function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (!icon) return;
  icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
}

// ── Sidebar ────────────────────────────────────────────────────────────────────
function initSidebar() {
  const sidebar    = document.getElementById('sidebar');
  const wrapper    = document.getElementById('mainWrapper');
  const toggle     = document.getElementById('sidebarToggle');
  const mobileBtn  = document.getElementById('mobileMenuBtn');

  const COLLAPSED_KEY = 'mpulse-sidebar-collapsed';

  function applyCollapsed(collapsed) {
    sidebar.classList.toggle('collapsed', collapsed);
    wrapper.classList.toggle('expanded', collapsed);
    localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
  }

  // Restore state
  const wasCollapsed = localStorage.getItem(COLLAPSED_KEY) === '1';
  if (wasCollapsed) applyCollapsed(true);

  toggle?.addEventListener('click', () => {
    applyCollapsed(!sidebar.classList.contains('collapsed'));
  });

  // Mobile overlay
  mobileBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('mobile-open');
  });
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 860 &&
        sidebar.classList.contains('mobile-open') &&
        !sidebar.contains(e.target) &&
        e.target !== mobileBtn) {
      sidebar.classList.remove('mobile-open');
    }
  });
}

// ── Market Status ──────────────────────────────────────────────────────────────
function updateMarketStatus() {
  const dot  = document.querySelector('.status-dot');
  const text = document.querySelector('.status-text');
  if (!dot || !text) return;

  const now = new Date();
  // Convert to IST (UTC+5:30)
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  const istMs = utcMs + (5.5 * 3600000);
  const ist   = new Date(istMs);
  const day   = ist.getDay(); // 0=Sun, 6=Sat
  const h = ist.getHours(), m = ist.getMinutes();
  const mins = h * 60 + m;
  const open = day >= 1 && day <= 5 && mins >= 9 * 60 + 15 && mins <= 15 * 60 + 35;

  dot.className  = 'status-dot ' + (open ? 'open' : 'closed');
  text.textContent = open ? 'Market Open' : 'Market Closed';
}

// ── Global Search ──────────────────────────────────────────────────────────────
let _stocksCache = [];

async function initGlobalSearch() {
  const input   = document.getElementById('globalSearch');
  const results = document.getElementById('searchResults');
  if (!input) return;

  try {
    const data = await API.get('/stocks');
    _stocksCache = data;
  } catch (e) { /* silently ignore */ }

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { results.classList.remove('visible'); return; }

    const matches = _stocksCache.filter(s =>
      s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
    ).slice(0, 8);

    if (!matches.length) { results.classList.remove('visible'); return; }

    results.innerHTML = matches.map(s => `
      <div class="search-result-item" data-symbol="${s.symbol}">
        <span class="sri-symbol">${s.symbol.replace('.NS','').replace('.BO','')}</span>
        <span class="sri-name">${s.name}</span>
      </div>
    `).join('');

    results.querySelectorAll('.search-result-item').forEach(el => {
      el.addEventListener('click', () => {
        window.location.href = `/stock/${encodeURIComponent(el.dataset.symbol)}`;
      });
    });
    results.classList.add('visible');
  });

  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !results.contains(e.target)) {
      results.classList.remove('visible');
    }
  });
}

// ── Refresh button ─────────────────────────────────────────────────────────────
function initRefreshButton() {
  const btn = document.getElementById('refreshBtn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    btn.classList.add('spinning');
    try {
      await API.post('/admin/refresh');
      showToast('Background refresh started!', 'success');
    } catch (e) {
      showToast('Refresh failed — ' + e.message, 'error');
    } finally {
      setTimeout(() => btn.classList.remove('spinning'), 2000);
    }
  });
}

// ── Last Updated ───────────────────────────────────────────────────────────────
async function updateLastUpdatedTime() {
  try {
    const data = await API.get('/market-summary');
    const el = document.getElementById('lastUpdated');
    if (el && data.last_updated) {
      el.innerHTML = `<i class="bi bi-clock"></i> ${fmtDate(data.last_updated)}`;
    }
  } catch (e) { /* ignore */ }
}

// ── ECharts shared theme helper ────────────────────────────────────────────────
function getEchartsTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    isDark,
    bg:          isDark ? '#1e2130' : '#ffffff',
    textColor:   isDark ? '#8b90a8' : '#5a607a',
    textBright:  isDark ? '#e8eaf0' : '#1a1d2e',
    border:      isDark ? '#2a2d3e' : '#e2e5f0',
    green:       isDark ? '#26d07c' : '#16a34a',
    red:         isDark ? '#f05050' : '#dc2626',
    blue:        isDark ? '#4f8ef7' : '#2563eb',
    purple:      isDark ? '#a78bfa' : '#7c3aed',
    orange:      isDark ? '#f5a623' : '#d97706',
    teal:        isDark ? '#2dd4bf' : '#0d9488',
  };
}

// ── Candlestick chart builder ──────────────────────────────────────────────────
function buildCandlestickChart(containerId, prices, indicators) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  const t = getEchartsTheme();

  const dates  = prices.map(p => p.datetime.slice(0,10));
  const ohlcv  = prices.map(p => [p.open, p.close, p.low, p.high]);
  const vols   = prices.map(p => p.volume);
  const sma20  = indicators.map(i => i.sma_20  ? +i.sma_20.toFixed(2) : null);
  const sma50  = indicators.map(i => i.sma_50  ? +i.sma_50.toFixed(2) : null);
  const ema12  = indicators.map(i => i.ema_12  ? +i.ema_12.toFixed(2) : null);

  const option = {
    backgroundColor: 'transparent',
    animation: true,
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross' },
      backgroundColor: t.bg, borderColor: t.border,
      textStyle: { color: t.textBright, fontSize: 12 },
    },
    legend: {
      top: 4, right: 12,
      textStyle: { color: t.textColor, fontSize: 11 },
      data: ['OHLC', 'SMA 20', 'SMA 50', 'EMA 12'],
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 60, right: 16, top: 36, height: '60%' },
      { left: 60, right: 16, bottom: 36, height: '20%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: t.border } },
        axisLabel: { color: t.textColor, fontSize: 11 },
        splitLine: { show: false }, gridIndex: 0 },
      { type: 'category', data: dates, boundaryGap: false,
        axisLine: { lineStyle: { color: t.border } },
        axisLabel: { show: false }, gridIndex: 1 },
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: t.border, type: 'dashed' } },
        axisLabel: { color: t.textColor, fontSize: 11,
          formatter: v => '₹' + v.toLocaleString('en-IN') }, gridIndex: 0 },
      { splitLine: { lineStyle: { color: t.border, type: 'dashed' } },
        axisLabel: { color: t.textColor, fontSize: 10,
          formatter: v => fmtVol(v) }, gridIndex: 1 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 6, height: 22,
        borderColor: t.border, fillerColor: 'rgba(79,142,247,0.15)',
        handleStyle: { color: t.blue },
        textStyle: { color: t.textColor } },
    ],
    series: [
      {
        name: 'OHLC', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: ohlcv,
        itemStyle: {
          color: t.green, color0: t.red,
          borderColor: t.green, borderColor0: t.red,
        },
      },
      { name: 'SMA 20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: sma20, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: t.orange } },
      { name: 'SMA 50', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: sma50, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: t.purple } },
      { name: 'EMA 12', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ema12, smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: t.teal, type: 'dashed' } },
      {
        name: 'Volume', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: vols.map((v, i) => ({
          value: v,
          itemStyle: { color: ohlcv[i][1] >= ohlcv[i][0] ? t.green : t.red, opacity: 0.7 }
        })),
      },
    ],
  };
  chart.setOption(option);
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

// ── RSI chart builder ─────────────────────────────────────────────────────────
function buildRsiChart(containerId, indicators) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  const t = getEchartsTheme();

  const dates = indicators.map(i => i.datetime.slice(0,10));
  const rsi   = indicators.map(i => i.rsi ? +i.rsi.toFixed(2) : null);

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: t.bg, borderColor: t.border,
      textStyle: { color: t.textBright, fontSize: 12 },
    },
    grid: { left: 50, right: 16, top: 20, bottom: 30 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { color: t.textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: t.border } },
    },
    yAxis: {
      min: 0, max: 100,
      splitLine: { lineStyle: { color: t.border, type: 'dashed' } },
      axisLabel: { color: t.textColor, fontSize: 11 },
    },
    visualMap: {
      show: false, dimension: 1,
      pieces: [
        { lt: 30, color: t.green },
        { gte: 30, lte: 70, color: t.blue },
        { gt: 70, color: t.red },
      ],
    },
    series: [{
      name: 'RSI', type: 'line', data: rsi,
      smooth: true, symbol: 'none',
      lineStyle: { width: 2 },
      markLine: {
        silent: true,
        lineStyle: { type: 'dashed', color: t.textColor },
        label: { color: t.textColor, fontSize: 10 },
        data: [{ yAxis: 70 }, { yAxis: 30 }],
      },
    }],
  });
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

// ── MACD chart builder ────────────────────────────────────────────────────────
function buildMacdChart(containerId, indicators) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const chart = echarts.init(el, null, { renderer: 'canvas' });
  const t = getEchartsTheme();

  const dates = indicators.map(i => i.datetime.slice(0,10));
  const macd  = indicators.map(i => i.macd        ? +i.macd.toFixed(4)        : null);
  const sig   = indicators.map(i => i.macd_signal ? +i.macd_signal.toFixed(4) : null);
  const hist  = indicators.map(i => i.macd_hist   ? +i.macd_hist.toFixed(4)   : null);

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: t.bg, borderColor: t.border,
      textStyle: { color: t.textBright, fontSize: 12 },
    },
    legend: {
      top: 4, textStyle: { color: t.textColor, fontSize: 11 },
      data: ['MACD', 'Signal'],
    },
    grid: { left: 50, right: 16, top: 30, bottom: 30 },
    xAxis: {
      type: 'category', data: dates,
      axisLabel: { color: t.textColor, fontSize: 11 },
      axisLine: { lineStyle: { color: t.border } },
    },
    yAxis: {
      splitLine: { lineStyle: { color: t.border, type: 'dashed' } },
      axisLabel: { color: t.textColor, fontSize: 11 },
    },
    series: [
      { name: 'MACD',   type: 'line', data: macd, smooth: true, symbol: 'none', lineStyle: { width: 2, color: t.blue } },
      { name: 'Signal', type: 'line', data: sig,  smooth: true, symbol: 'none', lineStyle: { width: 1.5, color: t.orange } },
      {
        name: 'Histogram', type: 'bar', data: hist,
        itemStyle: {
          color: (p) => p.value >= 0 ? t.green : t.red,
          opacity: 0.7,
        },
      },
    ],
  });
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initSidebar();
  initGlobalSearch();
  initRefreshButton();
  updateMarketStatus();
  updateLastUpdatedTime();

  document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);

  // Re-check market status every minute
  setInterval(updateMarketStatus, 60_000);
});

// Expose utilities globally for page scripts
window.API       = API;
window.showToast = showToast;
window.fmtPrice  = fmtPrice;
window.fmtPct    = fmtPct;
window.fmtVol    = fmtVol;
window.fmtCap    = fmtCap;
window.fmtDate   = fmtDate;
window.getEchartsTheme    = getEchartsTheme;
window.buildCandlestickChart = buildCandlestickChart;
window.buildRsiChart      = buildRsiChart;
window.buildMacdChart     = buildMacdChart;
