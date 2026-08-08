// Utility Functions
const Utils = {
  formatPrice(price) { return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price); },
  
  formatChange(change, pct) {
    const isPos = pct >= 0;
    const sign = isPos ? '+' : '';
    const colorClass = isPos ? 'text-green' : 'text-red';
    return {
      html: `<span class="${colorClass}">${sign}${change.toFixed(2)} (${sign}${pct.toFixed(2)}%)</span>`,
      class: colorClass
    };
  },
  
  formatVolume(vol) {
    if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
    if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
    if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
    return vol.toString();
  },
  
  formatMarketCap(mc) { return '$' + this.formatVolume(mc); },
  
  formatDate(dateStr) {
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 3600) return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  },
  
  formatPercent(val, decimals = 1) {
    const isPos = val >= 0;
    const sign = isPos ? '+' : '';
    return `<span class="${isPos ? 'text-green' : 'text-red'}">${sign}${val.toFixed(decimals)}%</span>`;
  },
  
  formatNumber(n) { return new Intl.NumberFormat('en-US').format(n); },

  scoreToColor(score) {
    if (score >= 85) return 'var(--gold)';
    if (score >= 70) return 'var(--green)';
    if (score >= 40) return 'var(--text-secondary)';
    return 'var(--red)';
  },
  
  scoreToLabel(score) {
    if (score >= 85) return 'STRONG BUY';
    if (score >= 70) return 'BUY';
    if (score >= 50) return 'WATCH';
    if (score >= 35) return 'NEUTRAL';
    return 'AVOID';
  },

  patternToLabel(pattern) { return pattern.replace(/_/g, ' ').toUpperCase(); },
  patternToColor(pattern) {
    const map = { vcp: 'blue', episodic_pivot: 'purple', bull_flag: 'green', cup_handle: 'gold', squeeze: 'orange' };
    return map[pattern.toLowerCase()] || 'neutral';
  },

  createSkeletonLoader(rows, cols) {
    let html = '';
    for(let i=0; i<rows; i++) {
      html += '<tr>';
      for(let j=0; j<cols; j++) html += `<td><div class="skeleton skeleton-text"></div></td>`;
      html += '</tr>';
    }
    return html;
  },

  createScoreGauge(containerId, score, label) {
    const container = document.getElementById(containerId);
    if(!container) return;
    const color = this.scoreToColor(score);
    const dasharray = 2 * Math.PI * 26;
    const dashoffset = dasharray - (dasharray * score) / 100;
    container.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; gap:8px;">
        <div class="score-circle">
          <svg viewBox="0 0 60 60">
            <circle class="bg" cx="30" cy="30" r="26"></circle>
            <circle class="progress" cx="30" cy="30" r="26" style="stroke:${color}; stroke-dasharray:${dasharray}; stroke-dashoffset:${dashoffset};"></circle>
          </svg>
          <div class="score-circle-text">${score}</div>
        </div>
        ${label ? `<div class="badge" style="color:${color}; border-color:${color}; background:rgba(255,255,255,0.05)">${label}</div>` : ''}
      </div>
    `;
  },

  getHeatmapColor(value, min, max) {
    if (value > 0) return `rgba(0, 255, 136, ${Math.min(0.8, 0.2 + (value/max)*0.6)})`;
    if (value < 0) return `rgba(255, 71, 87, ${Math.min(0.8, 0.2 + (value/min)*0.6)})`;
    return 'var(--bg-card)';
  }
};

function initializePage(pageName) {
  // Set active nav
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const activeNav = document.getElementById(`nav-${pageName}`);
  if(activeNav) activeNav.classList.add('active');
}
window.Utils = Utils;
window.initializePage = initializePage;
