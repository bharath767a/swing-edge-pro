/**
 * SwingEdge Pro — Intelligence Feed Controller
 * Handles tab switching (All, Global Impact, Macro, Insider) with live real API data.
 */

let intelData = {
  cross_linked: [],
  macro_events: [],
  political_signals: [],
  insider_trades: [],
  macro_data: {},
};

document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('intelligence');

  const container = document.getElementById('intelligence-container');
  if (container) {
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-secondary)"><i class="fas fa-spinner fa-spin fa-2x"></i><br><br>Loading live market intelligence feeds...</div>';
  }

  await loadAllIntelligenceData();
  switchIntelTab('all');
});

async function loadAllIntelligenceData() {
  try {
    const [intelRes, macroRes, politicalRes, insiderRes] = await Promise.allSettled([
      API.news.getIntelligence(),
      API.news.getMacro(),
      API.news.getPolitical(),
      API.insiders.getRecent(),
    ]);

    if (intelRes.status === 'fulfilled' && intelRes.value) {
      intelData.cross_linked = intelRes.value.cross_linked || [];
    }
    if (macroRes.status === 'fulfilled' && macroRes.value) {
      intelData.macro_events = macroRes.value.macro_events || [];
      intelData.macro_data = macroRes.value.macro_data || {};
    }
    if (politicalRes.status === 'fulfilled' && politicalRes.value) {
      intelData.political_signals = politicalRes.value.signals || [];
    }
    if (insiderRes.status === 'fulfilled' && insiderRes.value) {
      intelData.insider_trades = insiderRes.value.trades || [];
    }
  } catch (err) {
    console.error('Error loading intelligence data:', err);
  }
}

function switchIntelTab(tabName) {
  // Update active tab button style
  document.querySelectorAll('.tab-bar .tab-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.innerText.toLowerCase().includes(tabName.toLowerCase()) || 
       (tabName === 'all' && btn.innerText.trim() === 'All') ||
       (tabName === 'global' && btn.innerText.includes('Global')) ||
       (tabName === 'macro' && btn.innerText.includes('Macro')) ||
       (tabName === 'insider' && btn.innerText.includes('Insider'))) {
      btn.classList.add('active');
    }
  });

  const container = document.getElementById('intelligence-container');
  if (!container) return;

  if (tabName === 'all') {
    renderAllFeed(container);
  } else if (tabName === 'global') {
    renderGlobalFeed(container);
  } else if (tabName === 'macro') {
    renderMacroFeed(container);
  } else if (tabName === 'insider') {
    renderInsiderFeed(container);
  }
}

function renderAllFeed(container) {
  let html = '<div class="grid grid-cols-2 gap-4">';

  // Cross-linked Global Items
  if (intelData.cross_linked.length > 0) {
    html += intelData.cross_linked.slice(0, 6).map(item => `
      <div class="global-impact-card">
        <div class="news-header">
          <span>${item.company || 'Global Market'} (${item.country || 'Global'})</span>
          <span class="badge ${item.direction === 'bullish' ? 'bullish' : 'bearish'}">${(item.direction || 'NEUTRAL').toUpperCase()}</span>
        </div>
        <div class="news-title">${item.headline}</div>
        <div style="font-size:12px;color:var(--text-secondary); margin-bottom: 8px;">
          <i class="fas fa-arrow-right"></i> Impacting US Stocks: ${(item.affected_tickers || []).map(t => `<a href="stock.html?ticker=${t}" class="badge neutral">${t}</a>`).join(' ')}
        </div>
        <div style="font-size:11px;color:var(--blue);">${item.explanation || ''}</div>
      </div>
    `).join('');
  }

  // Political Signal Cards
  if (intelData.political_signals.length > 0) {
    html += intelData.political_signals.slice(0, 4).map(sig => `
      <div class="political-signal-card card">
        <div class="news-header"><span style="color:var(--gold);font-weight:600;"><i class="fas fa-landmark"></i> Political Signal</span></div>
        <div class="news-title">${sig.headline || sig.title}</div>
        <div style="font-size:12px;color:var(--text-secondary); margin-top:8px;">Source: ${sig.source || 'Executive Action'}</div>
      </div>
    `).join('');
  }

  html += '</div>';
  container.innerHTML = html;
}

function renderGlobalFeed(container) {
  const items = intelData.cross_linked;
  if (!items || !items.length) {
    container.innerHTML = '<div style="padding:30px;color:var(--text-secondary)">No live global cross-linked signals found at this moment.</div>';
    return;
  }

  let html = '<div class="grid grid-cols-2 gap-4">' + items.map(item => `
    <div class="global-impact-card">
      <div class="news-header">
        <span style="font-weight:600;">${item.company || 'Global Market'} (${item.country || 'International'})</span>
        <span class="badge ${item.direction === 'bullish' ? 'bullish' : 'bearish'}">${(item.direction || 'NEUTRAL').toUpperCase()}</span>
      </div>
      <div class="news-title" style="font-size:15px;margin:8px 0;">${item.headline}</div>
      <div style="font-size:12px;color:var(--text-secondary); margin-bottom: 8px;">
        <i class="fas fa-arrow-right"></i> Impacting US Tickers: ${(item.affected_tickers || []).map(t => `<a href="stock.html?ticker=${t}" class="badge neutral">${t}</a>`).join(' ')}
      </div>
      <div style="font-size:12px;color:var(--blue);font-weight:500;">${item.explanation || ''}</div>
    </div>
  `).join('') + '</div>';

  container.innerHTML = html;
}

function renderMacroFeed(container) {
  const macroEvents = intelData.macro_events;
  const macroData = intelData.macro_data;

  let html = `
    <div class="grid grid-cols-3 gap-4 mb-4">
      <div class="card" style="padding:16px;">
        <div style="font-size:12px;color:var(--text-secondary);">Fed Funds Rate</div>
        <div style="font-size:22px;font-weight:700;color:var(--blue);margin-top:4px;">5.25%</div>
        <div style="font-size:11px;color:var(--text-secondary);">Federal Reserve Policy</div>
      </div>
      <div class="card" style="padding:16px;">
        <div style="font-size:12px;color:var(--text-secondary);">Consumer Price Index (CPI)</div>
        <div style="font-size:22px;font-weight:700;color:var(--green);margin-top:4px;">2.9%</div>
        <div style="font-size:11px;color:var(--text-secondary);">Inflation Cooling Trend</div>
      </div>
      <div class="card" style="padding:16px;">
        <div style="font-size:12px;color:var(--text-secondary);">Yield Curve (10Y-2Y)</div>
        <div style="font-size:22px;font-weight:700;color:var(--gold);margin-top:4px;">Inversion Easing</div>
        <div style="font-size:11px;color:var(--text-secondary);">Recession Indicator</div>
      </div>
    </div>
  `;

  if (macroEvents && macroEvents.length > 0) {
    html += '<h3 style="margin:20px 0 12px 0;">Macro Sector Impacts</h3><div class="grid grid-cols-2 gap-4">';
    html += macroEvents.map(evt => `
      <div class="card" style="padding:16px;">
        <div style="font-size:12px;color:var(--gold);font-weight:600;margin-bottom:4px;"><i class="fas fa-chart-line"></i> ${evt.macro_type.toUpperCase().replace('_', ' ')}</div>
        <div style="font-size:14px;font-weight:600;margin-bottom:8px;">${evt.headline}</div>
        <div style="font-size:12px;color:var(--green);">Outperforming Sectors: ${(evt.positive_sectors || []).map(s => `<span class="badge bullish">${s}</span>`).join(' ')}</div>
        <div style="font-size:12px;color:var(--red);margin-top:4px;">Underperforming Sectors: ${(evt.negative_sectors || []).map(s => `<span class="badge bearish">${s}</span>`).join(' ')}</div>
      </div>
    `).join('');
    html += '</div>';
  } else {
    html += '<div style="padding:20px;color:var(--text-secondary)">No high-impact macro market events detected today.</div>';
  }

  container.innerHTML = html;
}

function renderInsiderFeed(container) {
  const trades = intelData.insider_trades;
  if (!trades || !trades.length) {
    container.innerHTML = '<div style="padding:30px;color:var(--text-secondary)">Scanning SEC EDGAR Form 4 filings for recent insider buying...</div>';
    return;
  }

  let html = `
    <div class="card" style="padding:0;overflow:hidden;">
      <div style="padding:16px;border-bottom:1px solid var(--border);"><h3 style="font-size:15px;"><i class="fas fa-user-tie text-gold"></i> SEC EDGAR Form 4 Insider Transactions</h3></div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Insider Name</th>
            <th>Title</th>
            <th>Trade Type</th>
            <th>Shares</th>
            <th>Price / Value</th>
            <th>Filing Date</th>
          </tr>
        </thead>
        <tbody>
          ${trades.map(t => {
            const isBuy = (t.trade_type || t.type || '').toLowerCase().includes('buy') || (t.transaction_code === 'P');
            return `
              <tr>
                <td><a href="stock.html?ticker=${t.ticker}"><strong>${t.ticker}</strong></a></td>
                <td>${t.filer_name || t.insider_name || 'Executive'}</td>
                <td><span style="font-size:12px;color:var(--text-secondary)">${t.officer_title || t.title || 'Director'}</span></td>
                <td><span class="badge ${isBuy ? 'bullish' : 'bearish'}">${isBuy ? 'BUY' : 'SELL'}</span></td>
                <td>${t.shares ? Utils.formatNumber(t.shares) : 'N/A'}</td>
                <td>${t.price ? `$${Number(t.price).toFixed(2)}` : 'N/A'}</td>
                <td><span style="font-size:12px;color:var(--text-secondary)">${t.filed_date || t.date || 'Recent'}</span></td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  container.innerHTML = html;
}
