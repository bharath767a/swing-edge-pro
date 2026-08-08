const BASE_URL = 'http://localhost:8000/api';

/**
 * SwingEdge Pro — Strictly Real-Data API Client
 * NO SIMULATED DATA. Directly connects to the backend real market intelligence engine.
 */

async function apiFetch(endpoint, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}/${endpoint}`, options);
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`[API Error] ${endpoint}:`, err);
    throw err;
  }
}

const API = {
  screener: {
    getResults: (params = {}) => {
      const query = new URLSearchParams(params).toString();
      return apiFetch(`screener?${query}`);
    },
    getTopPicks: () => apiFetch('screener/top-picks'),
    getMultibaggers: () => apiFetch('screener/multibagger'),
    refresh: () => apiFetch('screener/refresh', { method: 'POST' }),
  },

  stock: {
    getStock: (ticker) => apiFetch(`stock/${ticker}`),
    getChart: (ticker, period = '6mo', interval = '1d') =>
      apiFetch(`stock/${ticker}/chart?period=${period}&interval=${interval}`),
    getNews: (ticker) => apiFetch(`stock/${ticker}/news`),
    getInsiders: (ticker) => apiFetch(`stock/${ticker}/insiders`),
    getSimilar: (ticker) => apiFetch(`stock/${ticker}/similar`),
    getIntelligence: (ticker) => apiFetch(`stock/${ticker}/intelligence`),
  },

  news: {
    getAll: (type = '', ticker = '') => apiFetch(`news?type=${type}&ticker=${ticker}`),
    getIntelligence: () => apiFetch('news/intelligence'),
    getPolitical: () => apiFetch('news/political'),
    getAnalysts: () => apiFetch('news/analysts'),
    getMacro: () => apiFetch('news/macro'),
  },

  sectors: {
    getSectors: () => apiFetch('sectors'),
    getLeaders: (sector) => apiFetch(`sectors/${encodeURIComponent(sector)}/leaders`),
    getRotation: () => apiFetch('sectors/rotation'),
    getCorrelation: () => apiFetch('sectors/correlation'),
    getGlobal: () => apiFetch('sectors/global'),
  },

  insiders: {
    getRecent: () => apiFetch('insiders/recent'),
    getCluster: () => apiFetch('insiders/cluster'),
    getTicker: (ticker) => apiFetch(`insiders/${ticker}`),
  },

  backtest: {
    run: (data) => apiFetch('backtest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
    getStrategies: () => apiFetch('backtest/strategies'),
    getResults: () => apiFetch('backtest/results'),
  },

  alerts: {
    getAll: () => apiFetch('alerts'),
    create: (data) => apiFetch('alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
    markRead: (id) => apiFetch(`alerts/${id}/read`, { method: 'PATCH' }),
  },

  watchlist: {
    getAll: () => apiFetch('watchlist'),
    add: (ticker, data = {}) => apiFetch('watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, ...data }),
    }),
    remove: (ticker) => apiFetch(`watchlist/${ticker}`, { method: 'DELETE' }),
  },

  health: {
    check: () => apiFetch('health'),
    getMarketPulse: () => apiFetch('market-pulse'),
  },

  leveragedETFs: {
    getSummary: () => apiFetch('leveraged-etfs/universe/summary'),
    screen: (params = {}) => {
      const query = new URLSearchParams(params).toString();
      return apiFetch(`leveraged-etfs?${query}`);
    },
    getTicker: (ticker) => apiFetch(`leveraged-etfs/${ticker}`),
  },
};

window.API = API;
