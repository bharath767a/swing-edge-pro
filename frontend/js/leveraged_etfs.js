/**
 * SwingEdge Pro v3.2 — 2x Leveraged ETF Screener Controller
 */

let etfData = [];

document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('leveraged_etfs');
  await loadETFData();
});

async function loadETFData() {
  const tbody = document.getElementById('etf-table-body');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:40px; color:var(--text-secondary);"><i class="fas fa-spinner fa-spin fa-2x"></i><br><br>Analyzing 2x Leveraged ETF Volatility Decay & Regimes...</td></tr>';
  }

  try {
    const summaryRes = await API.leveragedETFs.getSummary();
    if (summaryRes) {
      const elTotal = document.getElementById('stat-total');
      if (elTotal) elTotal.innerText = summaryRes.total_etfs || 47;
      const elLongs = document.getElementById('stat-longs');
      if (elLongs) elLongs.innerText = summaryRes.long_etfs || 24;
      const elShorts = document.getElementById('stat-shorts');
      if (elShorts) elShorts.innerText = summaryRes.short_etfs || 23;
    }

    const screenRes = await API.leveragedETFs.screen({ min_score: 0, limit: 50 });
    if (screenRes && screenRes.candidates) {
      etfData = screenRes.candidates;
      renderETFTable(etfData);
    }
  } catch (err) {
    console.error('Error loading ETF data:', err);
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:40px; color:var(--red);">Error loading 2x Leveraged ETF screen. Please check server status.</td></tr>';
    }
  }
}

function filterETFs() {
  const dir = document.getElementById('filter-direction').value;
  const assetClass = document.getElementById('filter-asset-class').value;
  const minScore = parseFloat(document.getElementById('filter-min-score').value) || 0;

  const filtered = etfData.filter(item => {
    if (dir && item.direction !== dir) return false;
    if (assetClass && item.asset_class !== assetClass) return false;
    if (item.composite_score < minScore) return false;
    return true;
  });

  renderETFTable(filtered);
}

function renderETFTable(list) {
  const tbody = document.getElementById('etf-table-body');
  if (!tbody) return;

  if (!list || !list.length) {
    tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:30px; color:var(--text-secondary);">No 2x Leveraged ETFs meet the selected filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(item => {
    const isLong = item.direction === 'long';
    const scoreColor = item.composite_score >= 70 ? 'var(--green)' : (item.composite_score >= 50 ? 'var(--blue)' : 'var(--gold)');
    
    return `
      <tr>
        <td>
          <a href="stock.html?ticker=${item.ticker}" style="font-weight:700; font-size:15px;">${item.ticker}</a>
        </td>
        <td>
          <span class="badge ${isLong ? 'bullish' : 'bearish'}">${isLong ? '2x LONG' : '2x SHORT'}</span>
        </td>
        <td><span style="font-size:13px; color:var(--text-primary);">${item.underlying || 'Index'}</span></td>
        <td><span class="badge neutral">${(item.asset_class || 'equity').toUpperCase()}</span></td>
        <td><strong>$${(item.current_price || 0).toFixed(2)}</strong></td>
        <td><strong style="color:${scoreColor}; font-size:15px;">${item.composite_score}</strong></td>
        <td><span class="badge ${item.decay_risk === 'LOW' ? 'bullish' : 'neutral'}">${item.decay_risk || 'MODERATE'}</span></td>
        <td><span style="font-size:12px; color:var(--red); font-weight:600;">-${(item.volatility_drag_5d_pct || 0.5).toFixed(2)}%</span></td>
        <td>
          <div style="font-size:12px; color:var(--green);">Target: $${(item.target_price || 0).toFixed(2)}</div>
          <div style="font-size:12px; color:var(--red);">Stop: $${(item.stop_loss || 0).toFixed(2)}</div>
        </td>
        <td><span style="font-size:12px; color:var(--gold); font-weight:600;"><i class="fas fa-clock"></i> Max ${item.recommended_hold_days || 10}d</span></td>
        <td>
          <a href="stock.html?ticker=${item.ticker}" class="btn btn-secondary" style="font-size:11px; padding:4px 8px;">Analyze</a>
        </td>
      </tr>
    `;
  }).join('');
}
