document.addEventListener('DOMContentLoaded', async () => {
  if(window.initializePage) initializePage('sectors');
  const sectors = await API.sectors.getSectors();
  
  const grid = document.getElementById('sector-grid-full');
  if(!grid) return;
  
  grid.innerHTML = sectors.map(s => `
    <div class="card" style="border-top: 3px solid ${s.change_1d >= 0 ? 'var(--green)' : 'var(--red)'}">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
          <div style="font-size:16px; font-weight:700;">${s.sector}</div>
          <div style="font-size:12px; color:var(--text-secondary)">${s.etf_ticker}</div>
        </div>
        <div style="font-size:24px; font-weight:800; color:${s.change_1d >= 0 ? 'var(--green)' : 'var(--red)'}">${s.change_1d >= 0 ? '+' : ''}${s.change_1d}%</div>
      </div>
      <div style="font-size:12px; color:var(--text-secondary); margin-bottom:8px;">1M Perf: ${Utils.formatPercent(s.change_1m)}</div>
      <div style="font-size:12px; color:var(--text-secondary);">Rel Strength: ${s.relative_strength.toFixed(2)}</div>
    </div>
  `).join('');
});
