const ticker = new URLSearchParams(window.location.search).get('ticker') || 'NVDA';

document.addEventListener('DOMContentLoaded', async () => {
  if (window.initializePage) initializePage('stock');
  document.title = `${ticker} - SwingEdge Pro v2`;

  try {
    const stock = await API.stock.getStock(ticker);
    renderHero(stock);
    renderConsensus(stock);
    renderWallStreet(stock);
    renderMicrostructure(stock);
    renderTechnicals(stock);
    renderFundamentals(stock);
  } catch (err) {
    console.error('Failed to load stock info:', err);
    document.getElementById('stock-ticker').innerText = ticker;
    document.getElementById('stock-company').innerText = 'Data connection error';
  }
});

function renderHero(stock) {
  if (!stock) return;
  document.getElementById('stock-ticker').innerText = stock.ticker || ticker;
  document.getElementById('stock-company').innerText = stock.company_name || stock.ticker;

  const price = stock.current_price || stock.price || 0;
  const changePct = stock.change_pct || 0;
  const priceHtml = `$${price.toFixed(2)} <span style="font-size:16px;" class="${changePct >= 0 ? 'text-green' : 'text-red'}">${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%</span>`;

  const priceEl = document.getElementById('stock-price');
  if (priceEl) priceEl.innerHTML = priceHtml;

  const gauge = document.getElementById('score-gauge');
  if (gauge) {
    gauge.innerText = `${stock.composite_score || 50}`;
    gauge.style.color = (stock.composite_score >= 75) ? 'var(--gold)' : (stock.composite_score >= 60 ? 'var(--green)' : 'var(--blue)');
  }

  const recEl = document.getElementById('stock-rec');
  if (recEl) {
    recEl.innerText = stock.recommendation || 'NEUTRAL';
    recEl.className = `badge ${(stock.recommendation || '').includes('BUY') ? 'bullish' : 'neutral'}`;
  }

  const targetEl = document.getElementById('target-price');
  if (targetEl) targetEl.innerText = stock.target_price ? `$${stock.target_price.toFixed(2)}` : 'N/A';

  const stopEl = document.getElementById('stop-loss');
  if (stopEl) stopEl.innerText = stock.stop_loss ? `$${stock.stop_loss.toFixed(2)}` : 'N/A';

  const rrEl = document.getElementById('risk-reward');
  if (rrEl) rrEl.innerText = stock.risk_reward ? `${stock.risk_reward.toFixed(1)}R` : 'N/A';

  const timeEl = document.getElementById('swing-timeframe');
  if (timeEl) timeEl.innerText = stock.swing_timeframe || '1-2 weeks';

  const signalsEl = document.getElementById('signals-list');
  if (signalsEl && stock.signals) {
    signalsEl.innerHTML = stock.signals.map(s => `
      <div style="padding: 6px 10px; background: rgba(0,255,136,0.08); border: 1px solid rgba(0,255,136,0.2); border-radius: 6px; margin-bottom: 6px; color: #fff; font-size: 12px;">
        ${s}
      </div>
    `).join('');
  }
}

function renderConsensus(stock) {
  const container = document.getElementById('tab-consensus');
  if (!container) return;

  const consensus = stock.agent_consensus || {};
  const debates = consensus.agent_debates || [];
  const action = consensus.consensus_action || 'NEUTRAL HOLD';
  const confidence = consensus.confidence_pct || 50;

  container.innerHTML = `
    <div style="background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.25); padding: 18px; border-radius: 8px; margin-bottom: 20px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 10px;">
        <div style="font-size: 18px; font-weight: 800; color: #fff;"><i class="fas fa-robot text-blue"></i> Consensus Recommendation: <span style="color:var(--gold);">${action}</span></div>
        <div class="badge bullish" style="font-size: 13px;">Agent Confidence: ${confidence}%</div>
      </div>
      <p style="font-size: 14px; color: var(--text-primary); line-height: 1.5; margin: 0;">${consensus.synthesis_summary || 'Multi-agent evaluation completed.'}</p>
    </div>

    <h3 style="margin-bottom: 16px; font-size: 15px;"><i class="fas fa-comments text-gold"></i> Specialized Agent Intelligence Debate</h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
      ${debates.map(d => `
        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border); padding: 16px; border-radius: 8px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
            <strong style="font-size: 13px; color: var(--text-primary);">${d.agent}</strong>
            <span class="badge ${d.verdict === 'BULLISH' ? 'bullish' : (d.verdict === 'BEARISH' ? 'bearish' : 'neutral')}">${d.verdict}</span>
          </div>
          <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0;">${d.comment}</p>
        </div>
      `).join('')}
    </div>
  `;
}

function renderWallStreet(stock) {
  const container = document.getElementById('tab-wallstreet');
  if (!container) return;

  const ws = stock.wallstreet_intelligence || {};
  const buffettScore = ws.buffett_score || 50;

  const aiLayerBadge = ws.ai_layer_name ? `<div style="background:rgba(0,212,255,0.15); border:1px solid var(--blue); padding:12px; border-radius:6px; margin-bottom:12px; color:var(--blue); font-weight:600;"><i class="fas fa-microchip"></i> ${ws.ai_layer_name}</div>` : '';
  const itLayerBadge = ws.it_layer_name ? `<div style="background:rgba(168,85,247,0.15); border:1px solid var(--purple); padding:12px; border-radius:6px; margin-bottom:12px; color:var(--purple); font-weight:600;"><i class="fas fa-network-wired"></i> ${ws.it_layer_name}</div>` : '';

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px;">
      <div style="background: rgba(255,215,0,0.05); padding: 18px; border-radius: 8px; border: 1px solid rgba(255,215,0,0.3);">
        <div style="color: var(--gold); font-size: 12px; font-weight:600; text-transform:uppercase;">Warren Buffett Moat Rating</div>
        <div style="font-size: 22px; font-weight: 800; color: #fff; margin: 4px 0;">${ws.economic_moat || 'WIDE MOAT'}</div>
        <div style="font-size: 12px; color: var(--text-secondary);">Berkshire Quality Score: <strong style="color:var(--gold);">${buffettScore}/100</strong></div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; text-transform:uppercase;">Return on Invested Capital (ROIC)</div>
        <div style="font-size: 22px; font-weight: 800; color: var(--green); margin: 4px 0;">${ws.roic || 15.0}%</div>
        <div style="font-size: 12px; color: var(--text-secondary);">FCF Yield: <strong>${ws.fcf_yield || 4.2}%</strong></div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; text-transform:uppercase;">Balance Sheet Safety</div>
        <div style="font-size: 16px; font-weight: 700; color: var(--blue); margin: 4px 0;">${ws.debt_safety || 'Fortress Balance Sheet'}</div>
        <div style="font-size: 12px; color: var(--text-secondary);">Institutional Verdict: <span class="badge bullish">${ws.institutional_verdict || 'ACCUMULATION'}</span></div>
      </div>
    </div>

    ${aiLayerBadge}
    ${itLayerBadge}

    <div style="background: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
      <div style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;"><i class="fas fa-file-contract text-gold"></i> Wall Street Analyst Thesis & Value Chain Mapping</div>
      <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 0;">${ws.thesis || 'Classified within supply chain stack hierarchy.'}</p>
    </div>
  `;
}

function renderMicrostructure(stock) {
  const container = document.getElementById('tab-micro');
  if (!container) return;

  const micro = stock.microstructure || {};
  const price = stock.current_price || stock.price || 0;
  const avwap = micro.avwap_earnings || price;
  const poc = micro.poc_price || price;
  const confluenceScore = micro.confluence_score || 50;

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px;">
      <div style="background: rgba(168,85,247,0.05); padding: 18px; border-radius: 8px; border: 1px solid rgba(168,85,247,0.3);">
        <div style="color: var(--purple); font-size: 12px; font-weight:600;">Earnings Anchored VWAP (AVWAP)</div>
        <div style="font-size: 24px; font-weight: 800; color: #fff; margin: 4px 0;">$${avwap.toFixed(2)}</div>
        <div style="font-size: 12px; color: var(--text-secondary);">Distance to AVWAP: <strong style="color:${micro.avwap_dist_pct >= 0 ? 'var(--green)' : 'var(--red)'}">${micro.avwap_dist_pct || 0}%</strong></div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px;">Volume Profile Point of Control (POC)</div>
        <div style="font-size: 24px; font-weight: 800; color: var(--blue); margin: 4px 0;">$${poc.toFixed(2)}</div>
        <div style="font-size: 12px; color: var(--text-secondary);">Value Area: <strong>$${(micro.val_price || price*0.95).toFixed(2)} - $${(micro.vah_price || price*1.05).toFixed(2)}</strong></div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px;">Institutional Confluence Score</div>
        <div style="font-size: 24px; font-weight: 800; color: var(--gold); margin: 4px 0;">${confluenceScore}/100</div>
        <div style="font-size: 12px; color: var(--text-secondary);">Confluence Status: <span class="badge bullish">${micro.confluence_status || 'NEUTRAL'}</span></div>
      </div>
    </div>
  `;
}

function renderTechnicals(stock) {
  const container = document.getElementById('tab-tech');
  if (!container) return;

  const tech = stock.technicals || {};
  const price = stock.current_price || stock.price || 0;

  const rsi = tech.rsi || 50;
  const rsiClass = rsi > 70 ? 'text-red' : (rsi < 30 ? 'text-green' : 'text-blue');
  const trendClass = tech.trend === 'bullish' ? 'text-green' : (tech.trend === 'bearish' ? 'text-red' : 'text-secondary');

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">RSI (14)</div>
        <div style="font-size: 20px; font-weight: 700;" class="${rsiClass}">${rsi}</div>
        <div style="font-size: 11px; color: var(--text-secondary); font-weight: 500;">Status: ${(tech.rsi_signal || 'NEUTRAL').toUpperCase()}</div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">MACD Signal</div>
        <div style="font-size: 20px; font-weight: 700; color: var(--text-primary);">${tech.macd || 0}</div>
        <div style="font-size: 11px; color: var(--text-secondary);">Cross: ${(tech.macd_cross || 'NONE').replace('_', ' ').toUpperCase()}</div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">Trend Structure</div>
        <div style="font-size: 20px; font-weight: 700;" class="${trendClass}">${(tech.trend || 'NEUTRAL').toUpperCase()}</div>
        <div style="font-size: 11px; color: var(--text-secondary);">ADX Strength: ${tech.adx || 20}</div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">Support / Resistance</div>
        <div style="font-size: 14px; font-weight: 600; color: var(--green);">Supp: $${(tech.support || price * 0.95).toFixed(2)}</div>
        <div style="font-size: 14px; font-weight: 600; color: var(--red);">Res: $${(tech.resistance || price * 1.10).toFixed(2)}</div>
      </div>
    </div>
  `;
}

function renderFundamentals(stock) {
  const container = document.getElementById('tab-fund');
  if (!container) return;

  const fund = stock.fundamentals || {};
  const pe = fund.pe_ratio ? fund.pe_ratio.toFixed(2) : 'N/A';
  const fpe = fund.forward_pe ? fund.forward_pe.toFixed(2) : 'N/A';
  const mc = fund.market_cap ? Utils.formatMarketCap(fund.market_cap) : 'N/A';

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">Valuation</div>
        <div style="font-size: 14px; font-weight: 600;">P/E: <span style="color:var(--text-primary);">${pe}</span></div>
        <div style="font-size: 14px; font-weight: 600;">Forward P/E: <span style="color:var(--green);">${fpe}</span></div>
      </div>

      <div style="background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 4px;">Market Size</div>
        <div style="font-size: 18px; font-weight: 700; color: var(--blue);">${mc}</div>
      </div>
    </div>
  `;
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');

  if (event && event.target) {
    const btn = event.target.closest('.tab-btn');
    if (btn) btn.classList.add('active');
  }
  const content = document.getElementById(`tab-${tabId}`);
  if (content) content.style.display = 'block';
}
