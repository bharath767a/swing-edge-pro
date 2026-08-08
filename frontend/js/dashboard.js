document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('dashboard');
  
  // Parallel non-blocking dashboard loader
  loadMarketPulse();
  loadSectorHeatmap();
  loadTopSignals();
  loadGlobalIntelligence();
});

async function loadMarketPulse() {
  try {
    const data = await API.health.getMarketPulse();
    const strip = document.getElementById('market-pulse-strip');
    if (!strip || !data) return;

    let html = `<div class="pulse-item">VIX <span class="${data.vix < 20 ? 'text-green' : 'text-red'}">${data.vix || 18.5}</span></div>`;
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
      <div class="sector-tile" style="background: ${Utils.getHeatmapColor(s.change_1d || 0, -3, 3)}">
        <div class="sector-tile-name">${s.sector}</div>
        <div class="sector-tile-perf">${s.change_1d >= 0 ? '+' : ''}${(s.change_1d || 0).toFixed(1)}%</div>
        <div class="sector-tile-etf">${s.etf_ticker || ''}</div>
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

    tbody.innerHTML = picks.map((p) => {
      const priceStr = (typeof p.price === 'number') ? `$${p.price.toFixed(2)}` : 'N/A';
      const changeStr = (typeof p.change_pct === 'number') ? Utils.formatPercent(p.change_pct) : '';
      return `
        <tr class="${p.composite_score >= 80 ? 'row-glow-gold' : ''}">
          <td><a href="stock.html?ticker=${p.ticker}"><strong>${p.ticker}</strong></a><br><span style="font-size:11px;color:var(--text-secondary)">${p.company_name || p.ticker}</span></td>
          <td>${priceStr}<br>${changeStr}</td>
          <td><div class="badge ${p.composite_score >= 80 ? 'gold' : (p.composite_score >= 60 ? 'bullish' : 'neutral')}">${p.composite_score}</div></td>
          <td><div class="badge neutral">${Utils.patternToLabel(p.pattern)}</div></td>
          <td><span class="badge ${p.recommendation === 'STRONG BUY' || p.recommendation === 'BUY' ? 'bullish' : 'neutral'}">${p.recommendation}</span></td>
          <td><a href="stock.html?ticker=${p.ticker}" class="btn btn-secondary">Analyze</a></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Top signals error:', err);
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

    container.innerHTML = items.map(item => `
      <div class="global-impact-card mb-3">
        <div class="news-header">
          <span>${item.company} (${item.country || 'Global'})</span>
          <span class="badge ${item.direction === 'bullish' ? 'bullish' : 'bearish'}">${(item.direction || 'NEUTRAL').toUpperCase()}</span>
        </div>
        <div class="news-title">${item.headline}</div>
        <div style="font-size:12px;color:var(--text-secondary); margin-bottom: 8px;">
          <i class="fas fa-arrow-right"></i> Impacting US Tickers: ${item.affected_tickers ? item.affected_tickers.map(t => `<span class="badge neutral">${t}</span>`).join(' ') : ''}
        </div>
        <div style="font-size:11px;color:var(--blue);">${item.explanation || ''}</div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Global intelligence error:', err);
  }
}
