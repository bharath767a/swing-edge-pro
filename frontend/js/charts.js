const Charts = {
  _charts: new Map(),

  formatOHLCV(records) {
    if (!Array.isArray(records)) return [];
    return records.map(d => {
      let timeVal = d.Date || d.date || d.time || d.Timestamp;
      if (typeof timeVal === 'string') {
        timeVal = Math.floor(new Date(timeVal).getTime() / 1000);
      }
      return {
        time: timeVal,
        open: Number(d.Open || d.open || 0),
        high: Number(d.High || d.high || 0),
        low: Number(d.Low || d.low || 0),
        close: Number(d.Close || d.close || 0),
        value: Number(d.Volume || d.volume || d.value || 0),
      };
    }).filter(d => !isNaN(d.time) && d.close > 0).sort((a, b) => a.time - b.time);
  },

  createCandlestickChart(containerId, rawData) {
    const container = document.getElementById(containerId);
    if (!container || !window.LightweightCharts) return null;
    container.innerHTML = '';

    const data = this.formatOHLCV(rawData);
    if (!data.length) {
      container.innerHTML = '<div style="padding:20px;color:var(--text-secondary)">No chart data available for this symbol.</div>';
      return null;
    }

    const chart = LightweightCharts.createChart(container, {
      layout: { background: { type: 'solid', color: '#0A0E1A' }, textColor: '#8B949E' },
      grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)' }
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00FF88', downColor: '#FF4757', borderDownColor: '#FF4757', borderUpColor: '#00FF88', wickDownColor: '#FF4757', wickUpColor: '#00FF88'
    });
    candleSeries.setData(data);

    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    const volData = data.map(d => ({
      time: d.time,
      value: d.value,
      color: d.close >= d.open ? 'rgba(0, 255, 136, 0.4)' : 'rgba(255, 71, 87, 0.4)'
    }));
    volumeSeries.setData(volData);

    this._charts.set(containerId, chart);
    window.addEventListener('resize', () => { chart.applyOptions({ width: container.clientWidth }); });

    // Add real EMA lines
    this.addEMALines(chart, data);

    return { chart, candleSeries, volumeSeries };
  },

  calculateEMA(data, period) {
    const k = 2 / (period + 1);
    let ema = data[0].close;
    const result = [];
    for (let i = 0; i < data.length; i++) {
      ema = data[i].close * k + ema * (1 - k);
      result.push({ time: data[i].time, value: roundTwo(ema) });
    }
    return result;
  },

  addEMALines(chart, data) {
    if (!data || data.length < 5) return;
    const lineSeries8 = chart.addLineSeries({ color: '#00D4FF', lineWidth: 1.5, title: 'EMA 8' });
    const lineSeries21 = chart.addLineSeries({ color: '#FFD700', lineWidth: 1.5, title: 'EMA 21' });

    const ema8 = this.calculateEMA(data, 8);
    const ema21 = this.calculateEMA(data, 21);

    lineSeries8.setData(ema8);
    lineSeries21.setData(ema21);
  },

  createSparkline(containerId, rawData, color = '#00D4FF') {
    const container = document.getElementById(containerId);
    if (!container || !window.LightweightCharts) return null;
    container.innerHTML = '';

    const data = this.formatOHLCV(rawData);
    if (!data.length) return null;

    const chart = LightweightCharts.createChart(container, {
      layout: { background: { type: 'solid', color: 'transparent' }, textColor: 'transparent' },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      timeScale: { visible: false },
      rightPriceScale: { visible: false },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      handleScroll: false,
      handleScale: false
    });
    const lineSeries = chart.addLineSeries({ color, lineWidth: 2, crosshairMarkerVisible: false });
    lineSeries.setData(data.map(d => ({ time: d.time, value: d.close })));
  }
};

function roundTwo(val) {
  return Math.round(val * 100) / 100;
}

window.Charts = Charts;
