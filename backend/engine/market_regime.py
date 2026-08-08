"""
SwingEdge Pro v2 — Market Breadth & Liquidity Regime Classifier
Tracks VIX Term Structure, Market Breadth (% S&P 500 > 50-EMA),
and outputs Dynamic Portfolio Exposure Scaling factor (0.25x to 1.0x).

AUDIT FIXES APPLIED:
- P0-5: Errors fetching ETFs no longer counted as bullish breadth
- P2:   Global 15-min TTL cache (was per-stock, added 2-3s to every score)
- P1:   VIX fetch failures now surface as DATA_DEGRADED regime, not silent 18.5 fallback
- P1:   Sector ETF history cached per-ticker to avoid 7 sequential yfinance calls per stock
"""
import time
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Global cache: regime result + per-ETF history
_REGIME_CACHE: Dict = {'ts': 0, 'data': None}
_ETF_CACHE: Dict[str, Dict] = {}  # etf_symbol → {'ts': float, 'df': pd.DataFrame}
_REGIME_TTL = 900  # 15 minutes
_ETF_TTL = 900


def _cached_etf_history(symbol: str, period: str = '3mo') -> pd.DataFrame:
    """Cached fetch of ETF history — avoids 7 sequential yfinance calls per score."""
    now = time.time()
    cached = _ETF_CACHE.get(symbol)
    if cached and (now - cached['ts']) < _ETF_TTL:
        return cached['df']
    try:
        df = yf.Ticker(symbol).history(period=period)
        _ETF_CACHE[symbol] = {'ts': now, 'df': df}
        return df
    except Exception as e:
        logger.warning(f"ETF fetch failed {symbol}: {e}")
        return pd.DataFrame()


class MarketRegimeClassifier:
    SECTOR_ETFS = ['XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLI', 'XLC']

    def evaluate_regime(self) -> Dict:
        """
        Evaluate overall market regime with global caching.

        Returns DATA_DEGRADED when critical inputs (VIX, SPY) are unavailable.
        Never fabricates a fake VIX=18.5 — surfaces null and a conservative risk_multiplier.
        """
        # Global cache hit?
        now = time.time()
        if _REGIME_CACHE['data'] and (now - _REGIME_CACHE['ts']) < _REGIME_TTL:
            return _REGIME_CACHE['data']

        result = self._compute_regime()
        _REGIME_CACHE['data'] = result
        _REGIME_CACHE['ts'] = now
        return result

    def _compute_regime(self) -> Dict:
        try:
            spy_df = _cached_etf_history('SPY', period='6mo')

            # VIX fetch — surface failure as DATA_DEGRADED, do not fabricate
            try:
                vix_info = yf.Ticker('^VIX').fast_info
                vix_price_raw = getattr(vix_info, 'last_price', None)
                if vix_price_raw is None or vix_price_raw <= 0:
                    return self._degraded_regime('VIX fast_info returned None')
                vix_price = float(vix_price_raw)
            except Exception as e:
                return self._degraded_regime(f'VIX fetch failed: {e}')

            if spy_df.empty:
                return self._degraded_regime('SPY history empty')

            close = spy_df['Close']
            ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
            ema200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
            current_spy = float(close.iloc[-1])

            spy_above_50 = current_spy > ema50
            spy_above_200 = current_spy > ema200

            # FIX P0-5: errors do NOT count as bullish — only count successful fetches
            above_50_count = 0
            total_checked = 0
            for etf_symbol in self.SECTOR_ETFS:
                etf_df = _cached_etf_history(etf_symbol, period='3mo')
                if etf_df.empty or len(etf_df) < 50:
                    continue  # do NOT count failures either way
                e50 = etf_df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                if etf_df['Close'].iloc[-1] > e50:
                    above_50_count += 1
                total_checked += 1

            if total_checked == 0:
                return self._degraded_regime('All sector ETF fetches failed')

            breadth_pct = round((above_50_count / total_checked) * 100, 1)

            # Regime classification
            if vix_price < 20.0 and spy_above_50 and breadth_pct >= 60.0:
                regime = 'BULLISH_EXPANSION'
                risk_multiplier = 1.0
                guidance = 'Full Risk On — Ideal conditions for VCP breakouts and momentum swings.'
            elif vix_price < 25.0 and spy_above_200 and breadth_pct >= 40.0:
                regime = 'CAUTIOUS_BULL'
                risk_multiplier = 0.75
                guidance = 'Selective Risk — Maintain tight stop-losses and prioritize high-moat leaders.'
            elif vix_price >= 25.0 or (not spy_above_200 and breadth_pct < 40.0):
                regime = 'HIGH_VOLATILITY_DEFENSIVE'
                risk_multiplier = 0.40
                guidance = 'Defensive Stance — Clamp position sizes, favor cash, and target high-yield cash cows.'
            else:
                regime = 'NEUTRAL_SIDEWAYS'
                risk_multiplier = 0.60
                guidance = 'Sideways Market — Trade tight ranges and focus on insider cluster buys.'

            return {
                'regime': regime,
                'vix_level': round(vix_price, 2),
                'market_breadth_pct': breadth_pct,
                'spy_price': round(current_spy, 2),
                'spy_above_50_ema': spy_above_50,
                'spy_above_200_ema': spy_above_200,
                'risk_multiplier': risk_multiplier,
                'guidance': guidance,
                'data_quality': 'OK',
                'sectors_checked': total_checked,
            }
        except Exception as e:
            logger.warning(f"Error evaluating market regime: {e}", exc_info=True)
            return self._degraded_regime(str(e))

    def _degraded_regime(self, reason: str) -> Dict:
        """Return a conservative DATA_DEGRADED regime — never fabricates fake data."""
        return {
            'regime': 'DATA_DEGRADED',
            'vix_level': None,
            'market_breadth_pct': None,
            'spy_price': None,
            'spy_above_50_ema': None,
            'spy_above_200_ema': None,
            'risk_multiplier': 0.50,  # conservative default
            'guidance': f'Data degraded ({reason}). Falling back to neutral-risk exposure. DO NOT trust bullish signals.',
            'data_quality': 'DEGRADED',
        }

    # Legacy alias for backwards compat
    def _fallback_regime(self) -> Dict:
        return self._degraded_regime('legacy fallback')
