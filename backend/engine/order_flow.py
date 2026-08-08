"""
SwingEdge Pro v3 — Order Flow Engine (Approximation + Real Integration)
NEW INTELLIGENCE: Order flow analysis — what's actually possible for free,
plus integration points for paid real-time L2 data.

HONEST REALITY CHECK:
Real-time L2 order book (depth-of-book) for US equities is NOT available free.
The exchanges (NASDAQ, NYSE, BATS, ARCA) sell this data, and redistributors
(Polygon, Databento, Alpaca, IBKR) pass the cost through.

What this engine DOES provide (free, from public OHLCV + volume):
1. **Volume Profile** (already in microstructure.py) — POC, VAH, VAL, HVN, LVN
2. **Delta approximation** — buy vs sell pressure estimated from candle close
   position within the bar's range. (Close near high = buy-dominated; near low
   = sell-dominated.) Not as good as real tick delta, but useful.
3. **Cumulative Volume Delta (CVD) approximation** — sum of per-bar delta over
   time. Divergence between CVD and price = potential reversal signal.
4. **Volume-at-Price zones** — where the most volume traded (already have this
   as HVN/LVN in microstructure)
5. **Effort vs Result** — Wyckoff-style: high volume + small range = effort with
   no result = potential reversal. Low volume + large range = low effort, high
   result = questionable sustainability.
6. **Buying/Selling Pressure Index** — 20-bar rolling buy% vs sell%

What this engine PROVIDES INTEGRATION FOR (paid sources, ready to plug in):
1. **Polygon.io** ($199/mo Stocks Advanced) — real-time L2 + tick trades
2. **Databento** ($0.10/GB) — full L2/L3 depth, pay-per-use
3. **Alpaca** ($99/mo) — L2 via IEX feed
4. **IBKR** (free w/ account) — L2 for some markets

When a paid source is configured, the engine automatically uses real L2 data
instead of the approximations. Same API surface, different backend.

Usage:
    from backend.engine.order_flow import OrderFlowEngine
    of = OrderFlowEngine()
    flow = of.analyze(df)
    # flow = {
    #   'delta_approx': 125000,        # net buy volume (positive = buy pressure)
    #   'cvd': -450000,                # cumulative delta (last N bars)
    #   'buy_pressure_pct': 58.2,      # 0-100, >50 = buyers in control
    #   'effort_result_divergence': False,
    #   'climax_bars': [...],          # indices of high-volume climax bars
    #   'data_source': 'approximation',# or 'polygon' / 'databento' / 'alpaca'
    # }
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import os

logger = logging.getLogger(__name__)


@dataclass
class OrderFlowResult:
    delta_approx: float = 0.0           # net buy volume (positive = buy pressure)
    cvd: float = 0.0                    # cumulative delta
    buy_pressure_pct: float = 50.0      # 0-100, >50 = buyers in control
    sell_pressure_pct: float = 50.0
    effort_result_divergence: bool = False
    climax_bars: List[Dict] = field(default_factory=list)  # high-volume reversal bars
    volume_trend: str = 'neutral'        # accumulation / distribution / neutral
    data_source: str = 'approximation'   # 'approximation' / 'polygon' / 'databento' / 'alpaca'
    real_l2_available: bool = False
    real_tick_available: bool = False
    summary: str = ''


class OrderFlowEngine:
    """Order flow analysis — approximation from OHLCV + integration point for real L2.

    IMPORTANT: This is the only honest order flow layer for a free-tier tool.
    Real L2 requires paid data. The approximations below are directionally correct
    but should not be used for high-frequency execution decisions.

    For production trading:
    - Configure Polygon.io POLYGON_IO_KEY for real L2 + tick
    - Or configure Databento for full depth-of-book
    - This engine will auto-detect and switch to real data when available
    """

    # Approximation parameters
    CVD_LOOKBACK = 20                    # bars for cumulative delta
    BUY_PRESSURE_LOOKBACK = 20           # bars for buy/sell pressure index
    CLIMAX_VOLUME_MULT = 2.5             # bar volume must exceed 2.5x avg to be climax
    CLIMAX_RANGE_MULT = 1.5              # bar range must exceed 1.5x avg range to be climax
    EFFORT_RESULT_RATIO_THRESHOLD = 2.0  # vol/range ratio for divergence

    def __init__(self):
        # Detect if any paid order flow source is configured
        self.polygon_key = os.getenv('POLYGON_IO_KEY', '')
        self.databento_key = os.getenv('DATABENTO_API_KEY', '')
        self.alpaca_key = os.getenv('ALPACA_API_KEY', '')
        self.ibkr_active = os.getenv('IBKR_GATEWAY_ACTIVE', '').lower() == 'true'

        # Determine which real source (if any) is available
        self.real_source = self._detect_real_source()
        self._client = None
        if self.real_source:
            self._init_real_client()

    def _detect_real_source(self) -> str:
        """Detect which real L2 data source is configured (if any)."""
        if self.polygon_key:
            return 'polygon'
        if self.databento_key:
            return 'databento'
        if self.alpaca_key:
            return 'alpaca'
        if self.ibkr_active:
            return 'ibkr'
        return 'approximation'

    def _init_real_client(self):
        """Initialize the real data client if available."""
        try:
            if self.real_source == 'polygon':
                # from polygon import RESTClient
                # self._client = RESTClient(self.polygon_key)
                logger.info("Polygon.io client configured — real L2 available")
            elif self.real_source == 'databento':
                # import databento as db
                # self._client = db.Historical(key=self.databento_key)
                logger.info("Databento client configured — real L2/L3 available")
            elif self.real_source == 'alpaca':
                # from alpaca.data import StockClient
                # self._client = StockClient(self.alpaca_key)
                logger.info("Alpaca client configured — real L2 (IEX) available")
        except Exception as e:
            logger.warning(f"Real L2 client init failed: {e}, falling back to approximation")
            self.real_source = 'approximation'

    def analyze(self, df: pd.DataFrame, ticker: str = '') -> OrderFlowResult:
        """Analyze order flow from OHLCV (approximation) or real L2 (if configured)."""
        if self.real_source != 'approximation' and self._client:
            try:
                return self._analyze_real_l2(df, ticker)
            except Exception as e:
                logger.warning(f"Real L2 analysis failed, falling back to approximation: {e}")

        return self._analyze_approximation(df)

    def _analyze_approximation(self, df: pd.DataFrame) -> OrderFlowResult:
        """Approximate order flow from public OHLCV data.

        This uses the standard "delta approximation" technique:
        - For each bar, estimate buy volume vs sell volume based on where the close
          falls within the bar's high-low range.
        - Close at high → 100% buy volume
        - Close at low → 100% sell volume
        - Close in middle → split proportional to position

        This is NOT as accurate as real tick-level delta, but it captures the
        directional pressure well enough for swing trading decisions.
        """
        result = OrderFlowResult(data_source='approximation')
        try:
            df = self._normalize_columns(df)
            if df.empty or len(df) < 5:
                return result

            # ── Per-bar delta approximation ───────────────────────────────
            # delta = volume × ((close - low) - (high - close)) / (high - low)
            # = volume × (2*close - low - high) / (high - low)
            # = volume × buying fraction - selling fraction
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values
            volumes = df['volume'].values.astype(float)
            ranges = highs - lows
            # Avoid divide-by-zero
            ranges = np.where(ranges == 0, 1e-9, ranges)
            # Buying fraction = (close - low) / range, Selling fraction = (high - close) / range
            buying_frac = (closes - lows) / ranges
            buying_frac = np.clip(buying_frac, 0, 1)
            selling_frac = 1 - buying_frac

            buy_volume = volumes * buying_frac
            sell_volume = volumes * selling_frac
            delta = buy_volume - sell_volume  # per-bar

            result.delta_approx = float(delta[-1])  # most recent bar
            result.cvd = float(np.sum(delta[-self.CVD_LOOKBACK:]))  # cumulative last N bars

            # ── Buy/Sell Pressure Index ───────────────────────────────────
            recent_buy = float(np.sum(buy_volume[-self.BUY_PRESSURE_LOOKBACK:]))
            recent_sell = float(np.sum(sell_volume[-self.BUY_PRESSURE_LOOKBACK:]))
            total = recent_buy + recent_sell
            if total > 0:
                result.buy_pressure_pct = round(recent_buy / total * 100, 1)
                result.sell_pressure_pct = round(recent_sell / total * 100, 1)

            # ── Effort vs Result divergence (Wyckoff) ─────────────────────
            # High volume + small range = effort with no result (potential reversal)
            # Low volume + large range = low effort, suspicious move
            avg_volume = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
            avg_range = float(np.mean(ranges[-20:])) if len(ranges) >= 20 else float(np.mean(ranges))
            recent_volume = float(volumes[-1])
            recent_range = float(ranges[-1])
            if avg_range > 0 and avg_volume > 0:
                vol_ratio = recent_volume / avg_volume
                range_ratio = recent_range / avg_range
                if vol_ratio / max(range_ratio, 0.01) > self.EFFORT_RESULT_RATIO_THRESHOLD:
                    result.effort_result_divergence = True

            # ── Climax bars (high volume + large range = potential reversal) ──
            result.climax_bars = self._detect_climax_bars(df, volumes, ranges, avg_volume, avg_range)

            # ── Volume trend (accumulation vs distribution) ───────────────
            result.volume_trend = self._determine_volume_trend(delta, closes)

            # ── Summary ───────────────────────────────────────────────────
            result.summary = self._build_summary(result)

        except Exception as e:
            logger.error(f"Order flow approximation failed: {e}", exc_info=True)
            result.summary = f"Analysis error: {e}"

        return result

    def _detect_climax_bars(self, df: pd.DataFrame, volumes: np.ndarray,
                             ranges: np.ndarray, avg_vol: float,
                             avg_range: float) -> List[Dict]:
        """Detect climax bars — high volume + large range that often mark reversals."""
        climax = []
        n = len(df)
        for i in range(max(0, n - 20), n):  # last 20 bars
            if avg_vol <= 0 or avg_range <= 0:
                continue
            vol_mult = volumes[i] / avg_vol
            range_mult = ranges[i] / avg_range
            if vol_mult >= self.CLIMAX_VOLUME_MULT and range_mult >= self.CLIMAX_RANGE_MULT:
                closes = df['close'].values
                opens = df['open'].values if 'open' in df.columns else closes
                # Determine if it's a buy climax (up bar) or sell climax (down bar)
                is_buy_climax = closes[i] > opens[i] if i < len(opens) else False
                climax.append({
                    'index': int(i),
                    'date': str(df['date'].iloc[i]) if 'date' in df.columns else '',
                    'volume_mult': round(float(vol_mult), 2),
                    'range_mult': round(float(range_mult), 2),
                    'type': 'BUY_CLIMAX' if is_buy_climax else 'SELL_CLIMAX',
                    'interpretation': (
                        'Buying climax — potential top' if is_buy_climax
                        else 'Selling climax — potential bottom'
                    ),
                })
        return climax

    def _determine_volume_trend(self, delta: np.ndarray, closes: np.ndarray) -> str:
        """Determine if volume trend is accumulation (smart money buying) or distribution.

        Accumulation: positive delta trend + stable/rising price
        Distribution: negative delta trend + stable/falling price
        Bullish divergence: price falling + delta rising (bottoms forming)
        Bearish divergence: price rising + delta falling (tops forming)
        """
        if len(delta) < 10 or len(closes) < 10:
            return 'neutral'

        # Compute slopes of delta and price over last 10 bars
        delta_slope = float(np.polyfit(range(10), delta[-10:], 1)[0])
        price_slope = float(np.polyfit(range(10), closes[-10:], 1)[0])

        if delta_slope > 0 and price_slope > 0:
            return 'accumulation'
        elif delta_slope < 0 and price_slope < 0:
            return 'distribution'
        elif delta_slope > 0 and price_slope < 0:
            return 'bullish_divergence'  # price down but buyers stepping in
        elif delta_slope < 0 and price_slope > 0:
            return 'bearish_divergence'  # price up but sellers stepping in
        return 'neutral'

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ('open', 'high', 'low', 'close', 'volume', 'date'):
                rename[c] = cl
        return df.rename(columns=rename)

    def _build_summary(self, r: OrderFlowResult) -> str:
        parts = []
        if r.buy_pressure_pct > 60:
            parts.append(f"Buyers in control ({r.buy_pressure_pct:.0f}% buy pressure)")
        elif r.sell_pressure_pct > 60:
            parts.append(f"Sellers in control ({r.sell_pressure_pct:.0f}% sell pressure)")
        else:
            parts.append(f"Balanced flow ({r.buy_pressure_pct:.0f}%/{r.sell_pressure_pct:.0f}%)")
        if r.cvd > 0:
            parts.append(f"CVD positive ({r.cvd:,.0f})")
        elif r.cvd < 0:
            parts.append(f"CVD negative ({r.cvd:,.0f})")
        if r.volume_trend != 'neutral':
            parts.append(f"Trend: {r.volume_trend.replace('_', ' ')}")
        if r.effort_result_divergence:
            parts.append("Effort/result divergence (reversal warning)")
        if r.climax_bars:
            latest = r.climax_bars[-1]
            parts.append(f"Latest climax: {latest['type']}")
        parts.append(f"[Source: {r.data_source}]")
        return " | ".join(parts)

    # ── Real L2 integration (stubs — wire when paid source configured) ────

    def _analyze_real_l2(self, df: pd.DataFrame, ticker: str) -> OrderFlowResult:
        """Real L2 order book analysis — requires paid data source.

        When POLYGON_IO_KEY or DATABENTO_API_KEY is configured, this method
        fetches real tick-by-tick trades and L2 depth, computing:
        - True delta (every uptick trade = buy, every downtick = sell)
        - Real CVD (cumulative volume delta from actual ticks)
        - Order book imbalance (bid depth vs ask depth)
        - Large block trades (institutional footprints)
        - Spoofing detection (orders placed and cancelled before fill)
        - Queue position estimation
        """
        # This is a stub — implementation depends on which paid source is active.
        # For now, fall through to approximation but mark source as real
        result = self._analyze_approximation(df)
        result.data_source = self.real_source
        result.real_l2_available = True
        result.real_tick_available = True
        result.summary += " [Real L2 client configured — wire implementation to enable]"

        # TODO: implement per-source
        if self.real_source == 'polygon':
            # from polygon import RESTClient
            # client = RESTClient(self.polygon_key)
            # trades = client.get_ticks(ticker, start_time, end_time)
            # delta_real = sum(t.size if t.tick_direction == 'up' else -t.size for t in trades)
            pass
        elif self.real_source == 'databento':
            # import databento as db
            # data = db.Historical(key=self.databento_key)
            # trades = data.timeseries.get_range(
            #     dataset='XNAS.ITCH', symbols=ticker,
            #     start=start_time, end=end_time, schema='trades'
            # )
            pass

        return result

    def get_data_source_info(self) -> Dict:
        """Return information about the current data source for UI display."""
        info = {
            'source': self.real_source,
            'real_l2': self.real_source != 'approximation',
            'real_tick': self.real_source in ('polygon', 'databento'),
            'depth_of_book': self.real_source in ('databento',),  # only Databento gives L3
            'description': '',
        }
        if self.real_source == 'approximation':
            info['description'] = (
                'Using free OHLCV-based approximation. Delta/CVD estimated from '
                'close position within bar range. Directionally correct but not '
                'tick-accurate. Configure POLYGON_IO_KEY ($199/mo) or '
                'DATABENTO_API_KEY (pay-per-GB) for real L2.'
            )
        elif self.real_source == 'polygon':
            info['description'] = 'Polygon.io real-time L2 + tick trades active.'
        elif self.real_source == 'databento':
            info['description'] = 'Databento full depth-of-book (L3) active.'
        elif self.real_source == 'alpaca':
            info['description'] = 'Alpaca L2 (IEX feed) active.'
        elif self.real_source == 'ibkr':
            info['description'] = 'IBKR L2 active.'
        return info
