"""
SwingEdge Pro — Technical Analysis Engine
Comprehensive TA including VCP, Episodic Pivots, Bull Flag, Squeeze detection.

AUDIT FIXES APPLIED:
- P2: Added in-memory TTL cache (10 min) for analyze() results — eliminates duplicate yfinance fetches
- P2: Exposes `_df` on the report so downstream engines (microstructure, multibagger) can reuse it
"""
import logging
import time
from threading import RLock
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List
import ta
from backend.data.fetchers import get_ohlcv

logger = logging.getLogger(__name__)

# Module-level cache: ticker → (timestamp, TechnicalsReport)
_TECH_CACHE: dict = {}
_TECH_CACHE_TTL = 600  # 10 minutes
_TECH_CACHE_LOCK = RLock()


@dataclass
class TechnicalsReport:
    ticker: str = ''
    trend: str = 'neutral'          # bullish / bearish / neutral
    rsi: float = 50.0
    rsi_signal: str = 'neutral'    # overbought / oversold / neutral
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    macd_cross: str = 'none'       # bullish_cross / bearish_cross / none
    adx: float = 20.0
    atr: float = 0.0
    atr_pct: float = 0.0
    vwap: float = 0.0
    ema8: float = 0.0
    ema21: float = 0.0
    ema50: float = 0.0
    ema200: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    cci: float = 0.0
    obv: float = 0.0
    support: float = 0.0
    resistance: float = 0.0
    breakout_flag: bool = False
    squeeze: bool = False           # Bollinger inside Keltner
    supertrend_signal: str = 'neutral'  # bullish / bearish / neutral
    pattern: str = 'none'           # vcp / episodic_pivot / bull_flag / cup_handle / squeeze
    patterns: List[str] = field(default_factory=list)
    volume_trend: str = 'neutral'   # accumulation / distribution / neutral
    rel_volume: float = 1.0
    swing_score: float = 50.0


class TechnicalsEngine:
    """Full technical analysis engine for swing trading."""

    def analyze(self, ticker: str, df: Optional[pd.DataFrame] = None, ttl: int = _TECH_CACHE_TTL) -> TechnicalsReport:
        """Run full technical analysis on a ticker.

        AUDIT FIX P2: Caches results for `ttl` seconds (default 10 min).
        When `df` is None, fetches OHLCV and caches the result + the underlying DataFrame
        on `report._df` so downstream engines (microstructure, multibagger) can reuse it.
        """
        # Cache hit only when caller did not pass a custom df
        if df is None:
            with _TECH_CACHE_LOCK:
                cached = _TECH_CACHE.get(ticker)
                if cached and (time.time() - cached[0]) < ttl:
                    return cached[1]

        report = self._compute(ticker, df)

        if df is None:
            with _TECH_CACHE_LOCK:
                _TECH_CACHE[ticker] = (time.time(), report)
        return report

    def _compute(self, ticker: str, df: Optional[pd.DataFrame]) -> TechnicalsReport:
        """Original analyze() body — renamed to _compute so analyze() can wrap with cache."""
        report = TechnicalsReport(ticker=ticker)
        try:
            if df is None:
                df = get_ohlcv(ticker, period='1y', interval='1d')
            if df is None or len(df) < 30:
                return report
            df = self.calculate_all_indicators(df)
            if df is None or df.empty:
                return report
            # Expose the df on the report for downstream consumers
            report._df = df  # FIX P2: microstructure/multibagger can reuse this
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last

            # ── Price / EMA relationships ────────────────────────────────
            report.ema8 = self._safe(last, 'ema8')
            report.ema21 = self._safe(last, 'ema21')
            report.ema50 = self._safe(last, 'ema50')
            report.ema200 = self._safe(last, 'ema200')
            close = last['close']

            if close > report.ema8 > report.ema21 > report.ema50:
                report.trend = 'bullish'
            elif close > report.ema50 > report.ema200:
                report.trend = 'bullish'
            elif close < report.ema21 < report.ema50:
                report.trend = 'bearish'
            else:
                report.trend = 'neutral'

            # ── RSI ──────────────────────────────────────────────────────
            report.rsi = round(self._safe(last, 'rsi', 50.0), 1)
            if report.rsi > 70:
                report.rsi_signal = 'overbought'
            elif report.rsi < 30:
                report.rsi_signal = 'oversold'
            else:
                report.rsi_signal = 'neutral'

            # ── MACD ─────────────────────────────────────────────────────
            report.macd = round(self._safe(last, 'macd'), 4)
            report.macd_signal = round(self._safe(last, 'macd_signal'), 4)
            report.macd_hist = round(self._safe(last, 'macd_hist'), 4)
            prev_hist = self._safe(prev, 'macd_hist')
            if prev_hist < 0 and report.macd_hist > 0:
                report.macd_cross = 'bullish_cross'
            elif prev_hist > 0 and report.macd_hist < 0:
                report.macd_cross = 'bearish_cross'

            # ── ADX / ATR ────────────────────────────────────────────────
            report.adx = round(self._safe(last, 'adx', 20.0), 1)
            report.atr = round(self._safe(last, 'atr'), 4)
            report.atr_pct = round(report.atr / close * 100, 2) if close > 0 else 0

            # ── Bollinger Bands ──────────────────────────────────────────
            report.bb_upper = round(self._safe(last, 'bb_upper'), 4)
            report.bb_lower = round(self._safe(last, 'bb_lower'), 4)
            band_range = report.bb_upper - report.bb_lower
            report.bb_width = round(band_range / close * 100, 2) if close > 0 else 0

            # ── Keltner / Squeeze ────────────────────────────────────────
            kelt_upper = self._safe(last, 'kelt_upper')
            kelt_lower = self._safe(last, 'kelt_lower')
            if kelt_upper and kelt_lower:
                report.squeeze = (report.bb_upper < kelt_upper and report.bb_lower > kelt_lower)

            # ── Stochastic ───────────────────────────────────────────────
            report.stoch_k = round(self._safe(last, 'stoch_k', 50.0), 1)
            report.stoch_d = round(self._safe(last, 'stoch_d', 50.0), 1)

            # ── CCI ──────────────────────────────────────────────────────
            report.cci = round(self._safe(last, 'cci', 0.0), 1)

            # ── OBV ──────────────────────────────────────────────────────
            report.obv = self._safe(last, 'obv')

            # ── VWAP ─────────────────────────────────────────────────────
            report.vwap = round(self._safe(last, 'vwap', close), 4)

            # ── Supertrend ───────────────────────────────────────────────
            st_signal = self._calc_supertrend(df)
            report.supertrend_signal = st_signal

            # ── Support / Resistance ─────────────────────────────────────
            support, resistance = self.find_support_resistance(df)
            report.support = round(support, 4)
            report.resistance = round(resistance, 4)

            # ── Volume Analysis ──────────────────────────────────────────
            avg_vol = df['volume'].tail(20).mean()
            cur_vol = last['volume']
            report.rel_volume = round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
            # OBV trend: rising = accumulation
            obv_series = df['obv'].tail(10)
            if len(obv_series) > 5:
                slope = np.polyfit(range(len(obv_series)), obv_series.values, 1)[0]
                report.volume_trend = 'accumulation' if slope > 0 else 'distribution'

            # ── Breakout Detection ───────────────────────────────────────
            report.breakout_flag = self.detect_breakout(df, close, resistance)

            # ── Pattern Detection ────────────────────────────────────────
            patterns = self.detect_patterns(df)
            report.patterns = patterns
            report.pattern = patterns[0] if patterns else 'none'
            if report.squeeze:
                report.patterns.append('squeeze')

            # ── Swing Score ──────────────────────────────────────────────
            report.swing_score = self._calculate_swing_score(report)

        except Exception as e:
            logger.error(f"Technicals analysis error {ticker}: {e}", exc_info=True)

        return report

    def _safe(self, row, key: str, default: float = 0.0) -> float:
        val = row.get(key) if hasattr(row, 'get') else getattr(row, key, default)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to the DataFrame."""
        try:
            df = df.copy()
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            df.dropna(subset=['close', 'high', 'low', 'volume'], inplace=True)

            if len(df) < 20:
                return df

            # EMAs
            df['ema8']   = ta.trend.ema_indicator(df['close'], window=8)
            df['ema21']  = ta.trend.ema_indicator(df['close'], window=21)
            df['ema50']  = ta.trend.ema_indicator(df['close'], window=50)
            df['ema200'] = ta.trend.ema_indicator(df['close'], window=200)

            # MACD
            macd_obj = ta.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
            df['macd']        = macd_obj.macd()
            df['macd_signal'] = macd_obj.macd_signal()
            df['macd_hist']   = macd_obj.macd_diff()

            # RSI
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)

            # Stochastic
            stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
            df['stoch_k'] = stoch.stoch()
            df['stoch_d'] = stoch.stoch_signal()

            # CCI
            df['cci'] = ta.trend.cci(df['high'], df['low'], df['close'], window=20)

            # Williams %R
            df['williams_r'] = ta.momentum.williams_r(df['high'], df['low'], df['close'], lbp=14)

            # ADX
            adx_obj = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
            df['adx'] = adx_obj.adx()

            # ATR
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_lower'] = bb.bollinger_lband()
            df['bb_mid']   = bb.bollinger_mavg()

            # Keltner Channels (for squeeze detection)
            kc = ta.volatility.KeltnerChannel(df['high'], df['low'], df['close'], window=20)
            df['kelt_upper'] = kc.keltner_channel_hband()
            df['kelt_lower'] = kc.keltner_channel_lband()

            # OBV
            df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])

            # VWAP (cumulative within window)
            df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()

            return df
        except Exception as e:
            logger.error(f"Indicator calculation error: {e}")
            return df

    def _calc_supertrend(self, df: pd.DataFrame, multiplier: float = 3.0, period: int = 10) -> str:
        """Calculate Supertrend indicator direction."""
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            atr = df['atr'].values

            n = len(close)
            if n < period + 5:
                return 'neutral'

            upper_band = ((high + low) / 2) + (multiplier * atr)
            lower_band = ((high + low) / 2) - (multiplier * atr)

            supertrend = np.zeros(n)
            direction = np.ones(n)  # 1 = bullish, -1 = bearish

            supertrend[0] = lower_band[0]
            direction[0] = 1

            for i in range(1, n):
                if close[i] > upper_band[i - 1]:
                    direction[i] = 1
                elif close[i] < lower_band[i - 1]:
                    direction[i] = -1
                else:
                    direction[i] = direction[i - 1]

                if direction[i] == 1:
                    supertrend[i] = max(lower_band[i], supertrend[i - 1]) if direction[i - 1] == 1 else lower_band[i]
                else:
                    supertrend[i] = min(upper_band[i], supertrend[i - 1]) if direction[i - 1] == -1 else upper_band[i]

            final_dir = direction[-1]
            return 'bullish' if final_dir == 1 else 'bearish'
        except Exception:
            return 'neutral'

    def detect_patterns(self, df: pd.DataFrame) -> List[str]:
        """Detect technical chart patterns."""
        patterns = []
        try:
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            n = len(close)

            if n < 20:
                return patterns

            # ── VCP (Volatility Contraction Pattern) ─────────────────────
            # Characteristics: price near 52wk high, declining volatility, declining volume
            recent_high = np.max(high[-50:]) if n >= 50 else np.max(high)
            current = close[-1]
            price_from_high = (recent_high - current) / recent_high if recent_high > 0 else 1

            vol_early = np.std(close[-20:-10]) if n >= 20 else 999
            vol_recent = np.std(close[-10:]) if n >= 10 else 999
            vol_contracting = vol_recent < vol_early * 0.7

            vol_trend_early = np.mean(volume[-20:-10]) if n >= 20 else 999
            vol_trend_recent = np.mean(volume[-10:]) if n >= 10 else 999
            volume_declining = vol_trend_recent < vol_trend_early * 0.8

            if price_from_high < 0.15 and vol_contracting and volume_declining:
                patterns.append('vcp')

            # ── Episodic Pivot (EP) — Gap on Volume ──────────────────────
            # Large gap up or down on 3x+ volume in last 5 sessions
            for i in range(max(0, n - 5), n):
                if i == 0:
                    continue
                gap_pct = (df['open'].iloc[i] - close[i - 1]) / close[i - 1] if close[i - 1] > 0 else 0
                avg_vol_20 = np.mean(volume[max(0, i - 21):i])
                if abs(gap_pct) > 0.04 and volume[i] > avg_vol_20 * 3:
                    patterns.append('episodic_pivot')
                    break

            # ── Bull Flag ────────────────────────────────────────────────
            # Strong move up (>10% in 5-10 days) followed by tight consolidation
            if n >= 20:
                flag_pole = close[-15:-10] if n >= 15 else close[-10:-5]
                flag_body = close[-10:]
                if len(flag_pole) > 0 and len(flag_body) > 0:
                    pole_gain = (flag_pole[-1] - flag_pole[0]) / flag_pole[0] if flag_pole[0] > 0 else 0
                    body_std = np.std(flag_body) / np.mean(flag_body) if np.mean(flag_body) > 0 else 1
                    if pole_gain > 0.10 and body_std < 0.03:
                        patterns.append('bull_flag')

            # ── Cup & Handle ─────────────────────────────────────────────
            # U-shaped base with a small pullback handle
            if n >= 60:
                left = close[-60:-40]
                base = close[-40:-20]
                handle = close[-20:]
                if len(left) > 0 and len(base) > 0 and len(handle) > 0:
                    left_high = np.max(left)
                    base_low = np.min(base)
                    right_high = np.max(handle)
                    cup_depth = (left_high - base_low) / left_high if left_high > 0 else 1
                    # Cup: depth 15-50%, right side near left_high, handle tight
                    handle_pullback = (np.max(handle) - np.min(handle)) / np.max(handle) if np.max(handle) > 0 else 1
                    if 0.15 < cup_depth < 0.50 and right_high > left_high * 0.9 and handle_pullback < 0.12:
                        patterns.append('cup_handle')

        except Exception as e:
            logger.debug(f"Pattern detection error: {e}")

        return patterns

    def find_support_resistance(self, df: pd.DataFrame, window: int = 20) -> tuple:
        """Find key support and resistance levels."""
        try:
            highs = df['high'].tail(window * 2).values
            lows = df['low'].tail(window * 2).values
            close = df['close'].iloc[-1]

            # Pivot-based S/R
            resistance = np.percentile(highs, 80)
            support = np.percentile(lows, 20)

            # Ensure support < close < resistance
            if support >= close:
                support = np.min(lows)
            if resistance <= close:
                resistance = np.max(highs)

            return support, resistance
        except Exception:
            close = df['close'].iloc[-1] if not df.empty else 0
            return close * 0.95, close * 1.10

    def detect_breakout(self, df: pd.DataFrame, current_price: float, resistance: float) -> bool:
        """Check if price is breaking above resistance on volume."""
        try:
            last_vol = df['volume'].iloc[-1]
            avg_vol = df['volume'].tail(20).mean()
            price_above_resistance = current_price >= resistance * 0.99
            volume_confirms = last_vol > avg_vol * 1.5
            return price_above_resistance and volume_confirms
        except Exception:
            return False

    def _calculate_swing_score(self, report: TechnicalsReport) -> float:
        """Calculate composite 0-100 technical swing score."""
        score = 50.0
        try:
            # Trend alignment: +15
            if report.trend == 'bullish':
                score += 15
            elif report.trend == 'bearish':
                score -= 15

            # RSI: +10 if 40-65 (swing sweet spot), -10 if >75 (overbought)
            if 40 <= report.rsi <= 65:
                score += 10
            elif report.rsi > 75:
                score -= 10
            elif report.rsi < 30:
                score += 8  # oversold bounce opportunity

            # MACD: +8 for bullish cross
            if report.macd_cross == 'bullish_cross':
                score += 8
            elif report.macd_cross == 'bearish_cross':
                score -= 8
            elif report.macd_hist > 0 and report.macd > report.macd_signal:
                score += 4

            # ADX (trend strength): +5 if ADX > 25 (trending)
            if report.adx > 25:
                score += 5

            # Supertrend: +8
            if report.supertrend_signal == 'bullish':
                score += 8
            elif report.supertrend_signal == 'bearish':
                score -= 8

            # Breakout: +15
            if report.breakout_flag:
                score += 15

            # Pattern bonus
            pattern_scores = {'vcp': 12, 'episodic_pivot': 15, 'bull_flag': 10, 'cup_handle': 12, 'squeeze': 8}
            for pat in report.patterns:
                score += pattern_scores.get(pat, 0)

            # Volume confirmation: +5 if rel volume > 1.5
            if report.rel_volume > 2.0:
                score += 8
            elif report.rel_volume > 1.5:
                score += 5

            # Volume trend: +5
            if report.volume_trend == 'accumulation':
                score += 5
            elif report.volume_trend == 'distribution':
                score -= 5

        except Exception as e:
            logger.debug(f"Swing score error: {e}")

        return round(max(0.0, min(100.0, score)), 1)

    def swing_score(self, ticker: str) -> float:
        """Quick API: return just the swing score for a ticker."""
        report = self.analyze(ticker)
        return report.swing_score

    def multi_timeframe_score(self, ticker: str) -> dict:
        """Check trend alignment across daily and weekly timeframes."""
        from typing import Dict as D
        daily_df = get_ohlcv(ticker, period='1y', interval='1d')
        weekly_df = get_ohlcv(ticker, period='2y', interval='1wk')

        daily_report = self.analyze(ticker, daily_df)
        weekly_report = self.analyze(ticker, weekly_df)

        # Alignment bonus: both bullish = high conviction
        aligned = (daily_report.trend == weekly_report.trend)
        both_bullish = (daily_report.trend == 'bullish' and weekly_report.trend == 'bullish')

        return {
            'daily_trend': daily_report.trend,
            'weekly_trend': weekly_report.trend,
            'daily_score': daily_report.swing_score,
            'weekly_score': weekly_report.swing_score,
            'aligned': aligned,
            'both_bullish': both_bullish,
            'conviction': 'high' if both_bullish else ('medium' if aligned else 'low'),
        }
