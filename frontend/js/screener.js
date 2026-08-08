let allStocks = [];

document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('screener');
  
  const tbody = document.getElementById('screener-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--text-secondary)"><i class="fas fa-spinner fa-spin"></i> Fetching live market screener analysis...</td></tr>';
  
  try {
    const res = await API.screener.getResults();
    allStocks = (res && res.stocks) ? res.stocks : (Array.isArray(res) ? res : []);
    renderTable(allStocks);
  } catch (err) {
    console.error('Screener error:', err);
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--red)">Failed to load live screener data. Ensure backend is running.</td></tr>';
  }
});

function renderTable(data) {
  const tbody = document.getElementById('screener-tbody');
  const countEl = document.getElementById('screener-count');
  if (countEl) countEl.innerText = `${data.length} Real Market Stocks Screened`;
  
  if (!tbody) return;
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:25px;color:var(--text-secondary)">No live stocks match the selected screener criteria.</td></tr>';
    return;
  }
  
  tbody.innerHTML = data.map(p => {
    const priceStr = (typeof p.price === 'number') ? `$${p.price.toFixed(2)}` : 'N/A';
    const changeStr = (typeof p.change_pct === 'number') ? Utils.formatPercent(p.change_pct) : '';
    const volStr = p.volume ? Utils.formatVolume(p.volume) : 'N/A';
    return `
      <tr>
        <td><a href="stock.html?ticker=${p.ticker}"><strong>${p.ticker}</strong></a><br><span style="font-size:11px;color:var(--text-secondary)">${p.company_name || p.ticker}</span></td>
        <td>${priceStr}<br>${changeStr}</td>
        <td>${p.sector || 'N/A'}</td>
        <td><div class="badge ${p.composite_score >= 80 ? 'gold' : (p.composite_score >= 60 ? 'bullish' : 'neutral')}">${p.composite_score || 50}</div></td>
        <td><div class="badge neutral">${Utils.patternToLabel(p.pattern)}</div></td>
        <td>${volStr}</td>
        <td><a href="stock.html?ticker=${p.ticker}" class="btn btn-secondary">Analyze</a></td>
      </tr>
    `;
  }).join('');
}

function applyFilters() {
  const searchInput = document.getElementById('filter-search');
  const search = searchInput ? searchInput.value.toLowerCase() : '';
  
  const scoreInput = document.getElementById('filter-score');
  const minScore = scoreInput ? (parseInt(scoreInput.value) || 0) : 0;
  
  const filtered = allStocks.filter(s => {
    if ((s.composite_score || 0) < minScore) return false;
    if (search && !s.ticker.toLowerCase().includes(search) && !(s.company_name || '').toLowerCase().includes(search)) return false;
    return true;
  });
  
  renderTable(filtered);
}
