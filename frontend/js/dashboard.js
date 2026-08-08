document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('dashboard');
  
  // Parallel non-blocking dashboard loader
  loadMarketPulse();
  loadSectorHeatmap();
  loadTopSignals();
  loadLeveragedETFWidget();
  loadGlobalIntelligence();
});

async function loadMarketPulse() {
  try {
    const data = await API.health.getMarketPulse();
    const strip = document.getElementById('market-pulse-strip');
    if (!strip || !data) return;

    let html = `<div class="pulse-item">VIX <span class="${(data.vix || 20) < 20 ? 'text-green' : 'text-red'}">${data.vix || '14.9'}</span></div>`;
    if (data.indices) {
      for (const [idx, info] of Object.entries(data.indices)) {
        if (!info || typeof info.price !== 'number') continue;
        const f = Utils.formatChange(info.price * (info.change_pct / 100), info.change_pct);
        html += `<div class="pulse-item"><span class="pulse-ticker">${idx.toUpperCase()}</span> <span class="pulse-price">${info.price.toFixed(2)}</span> ${f.html}</div>`;
      }
    }
    strip.innerHTML = html;
  } catch (err) {
    console.error('Market pulse fetch error:', err);
  }
}

async function loadSectorHeatmap() {
  try {
    const data = await API.sectors.getSectors();
    const grid = document.getElementById('sector-grid');
    if (!grid) return;

    const sectors = (data && data.sectors) ? data.sectors : (Array.isArray(data) ? data : []);
    if (!sectors.length) {
      grid.innerHTML = '<div style="padding:15px;color:var(--text-secondary);">Loading live sector performance...</div>';
      return;
    }

    grid.innerHTML = sectors.slice(0, 8).map(s => `
      <div class="sector-tile" style="background: ${Utils.getHeatmapColor(s.change_1d || 0, -3, 3)}; padding:12px; border-radius:8px; margin-bottom:8px;">
        <div class="sector-tile-name" style="font-weight:600; font-size:13px; color:#fff;">${s.sector}</div>
        <div class="sector-tile-perf" style="font-size:16px; font-weight:800; color:#fff;">${s.change_1d >= 0 ? '+' : ''}${(s.change_1d || 0).toFixed(1)}%</div>
        <div class="sector-tile-etf" style="font-size:11px; opacity:0.8;">${s.etf_ticker || ''}</div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Sector heatmap error:', err);
  }
}

async function loadTopSignals() {
  try {
    const res = await API.screener.getTopPicks();
    const tbody = document.getElementById('top-signals-tbody');
    if (!tbody) return;

    const picks = (res && res.stocks) ? res.stocks : (Array.isArray(res) ? res : []);
    if (!picks.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-secondary)">No live signals matching screener threshold currently.</td></tr>';
      return;
    }

    tbody.innerHTML = picks.slice(0, 10).map((p) => {
      const priceStr = (typeof p.price === 'number') ? `$${p.price.toFixed(2)}` : 'N/A';
      const scoreColor = p.composite_score >= 80 ? 'var(--green)' : (p.composite_score >= 60 ? 'var(--blue)' : 'var(--gold)');
      return `
        <tr class="${p.composite_score >= 75 ? 'row-glow-gold' : ''}">
          <td><a href="stock.html?ticker=${p.ticker}"><strong>${p.ticker}</strong></a><br><span style="font-size:11px;color:var(--text-secondary)">${p.company_name || p.ticker}</span></td>
          <td><strong>${priceStr}</strong></td>
          <td><strong style="color:${scoreColor}; font-size:15px;">${p.composite_score}</strong></td>
          <td><span class="badge neutral">${Utils.patternToLabel(p.pattern)}</span></td>
          <td><span class="badge ${p.recommendation.includes('BUY') ? 'bullish' : 'neutral'}">${p.recommendation}</span></td>
          <td><a href="stock.html?ticker=${p.ticker}" class="btn btn-secondary" style="font-size:11px; padding:4px 8px;">Analyze</a></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Top signals error:', err);
  }
}

async function loadLeveragedETFWidget() {
  try {
    const res = await API.leveragedETFs.screen({ min_score: 0, limit: 10 });
    const tbody = document.getElementById('top-etfs-tbody');
    if (!tbody) return;

    const etfs = (res && res.candidates) ? res.candidates : [];
    if (!etfs.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-secondary)">Loading 2x Leveraged ETF Signals...</td></tr>';
      return;
    }

    tbody.innerHTML = etfs.map((item) => {
      const isLong = item.direction === 'LONG' || item.direction === 'long';
      const scoreColor = item.composite_score >= 70 ? 'var(--green)' : (item.composite_score >= 50 ? 'var(--blue)' : 'var(--gold)');
      return `
        <tr>
          <td><a href="stock.html?ticker=${item.ticker}"><strong>${item.ticker}</strong></a></td>
          <td><span class="badge ${isLong ? 'bullish' : 'bearish'}">${isLong ? '2x LONG' : '2x SHORT'}</span></td>
          <td><span style="font-size:12px; color:var(--text-primary);">${item.underlying || 'Index'}</span></td>
          <td><strong>$${(item.current_price || 0).toFixed(2)}</strong></td>
          <td><strong style="color:${scoreColor}; font-size:15px;">${item.composite_score}</strong></td>
          <td><span class="badge ${item.decay_risk === 'LOW' ? 'bullish' : 'neutral'}">${item.decay_risk || 'MEDIUM'}</span></td>
          <td><span style="font-size:11px; color:var(--gold); font-weight:600;"><i class="fas fa-clock"></i> Max ${item.recommended_hold_days || 10}d</span></td>
          <td><a href="stock.html?ticker=${item.ticker}" class="btn btn-secondary" style="font-size:11px; padding:4px 8px;">Analyze</a></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Leveraged ETF widget error:', err);
  }
}

function switchDashboardTab(tab) {
  const stockTab = document.getElementById('view-stocks-tab');
  const etfTab = document.getElementById('view-etfs-tab');
  const stockBtn = document.getElementById('tab-stocks-btn');
  const etfBtn = document.getElementById('tab-etfs-btn');

  if (tab === 'etfs') {
    stockTab.style.display = 'none';
    etfTab.style.display = 'block';
    stockBtn.className = 'btn btn-secondary';
    etfBtn.className = 'btn btn-primary';
  } else {
    stockTab.style.display = 'block';
    etfTab.style.display = 'none';
    stockBtn.className = 'btn btn-primary';
    etfBtn.className = 'btn btn-secondary';
  }
}

async function loadGlobalIntelligence() {
  try {
    const data = await API.news.getIntelligence();
    const container = document.getElementById('intelligence-feed');
    if (!container) return;

    const items = (data && data.cross_linked) ? data.cross_linked : [];
    if (!items.length) {
      container.innerHTML = '<div style="padding:15px;color:var(--text-secondary)">Scanning live news feeds for global cross-linked signals...</div>';
      return;
    }

    container.innerHTML = items.slice(0, 5).map(item => `
      <div class="global-impact-card mb-3" style="background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:8px; padding:12px; margin-bottom:12px;">
        <div class="news-header" style="display:flex; justify-content:space-between; margin-bottom:6px;">
          <span style="font-weight:700; color:var(--blue);">${item.company} (${item.country || 'Global'})</span>
          <span class="badge ${item.direction === 'bullish' ? 'bullish' : 'bearish'}">${(item.direction || 'NEUTRAL').toUpperCase()}</span>
        </div>
        <div class="news-title" style="font-size:13px; font-weight:600; margin-bottom:6px;">${item.headline}</div>
        <div style="font-size:12px;color:var(--text-secondary); margin-bottom: 4px;">
          <i class="fas fa-arrow-right"></i> Impacting US Tickers: ${item.affected_tickers ? item.affected_tickers.map(t => `<span class="badge neutral">${t}</span>`).join(' ') : ''}
        </div>
        <div style="font-size:11px;color:var(--blue);">${item.explanation || ''}</div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Global intelligence error:', err);
  }
}
