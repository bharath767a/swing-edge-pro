"""
SwingEdge Pro v3 — Market Structure Engine (Simplified)
Identifies fractal swing highs/lows and aggregates them into key support/resistance
levels. Replaces the old percentile-based S/R in technicals.py with actual market
pivot points.

WHAT THIS MODULE DOES:
1. **Fractal swing high/low detection** — Bill Williams-style fractals with
   configurable window (default 2 bars on each side = 5-bar fractal).
   A swing high at bar i means high[i] > high[i-2], high[i-1], high[i+1], high[i+2].
   A swing low is the mirror.

2. **Key levels aggregation** — All unbroken swing highs (resistance) and
   unbroken swing lows (support) are collected, deduplicated, sorted by
   distance from current price. Each level includes strength and tested status.

3. **Trend bias** — derived from the relative position of recent swing highs
   vs recent swing lows (higher highs + higher lows = bullish, etc.)

WHY THIS MATTERS:
The old percentile-based S/R (np.percentile(highs, 80)) was a statistical proxy
with no concept of where actual buyers/sellers entered. Real swing points are
where price reversed — those are the levels where future reactions are likely.

Usage:
    from backend.engine.market_structure import MarketStructureEngine
    ms = MarketStructureEngine()
    structure = ms.analyze(df)
    # structure.swing_highs, structure.swing_lows, structure.key_levels
    # structure.trend_bias
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SwingPoint:
    index: int                 # bar index in the DataFrame
    price: float               # the swing high or low price
    type: str                  # 'HIGH' or 'LOW'
    date: str = ''             # bar date if available
    strength: int = 1          # how many bars confirmed (1=weak, 2=medium, 3+=strong)
    tested: bool = False       # has price returned to test this level?
    broken: bool = False       # has price broken through this level?


@dataclass
class MarketStructure:
    swing_highs: List[SwingPoint] = field(default_factory=list)
    swing_lows: List[SwingPoint] = field(default_factory=list)
    key_levels: List[Dict] = field(default_factory=list)  # aggregated, sorted by distance
    trend_bias: str = 'NEUTRAL'  # BULLISH / BEARISH / NEUTRAL


class MarketStructureEngine:
    """Fractal-based swing point detection and S/R aggregation.

    Simple, robust, trader-friendly. No ICT/SMC complexity (no BOS/CHoCH/order
    blocks/liquidity pools/FVGs) — just clean swing highs/lows that any chartist
    would recognize.
    """

    def __init__(self, fractal_window: int = 2, min_swing_strength: int = 1):
        """
        Args:
            fractal_window: bars on each side for swing detection (2 = 5-bar fractal)
            min_swing_strength: minimum confirmations to keep a swing point
        """
        self.fractal_window = fractal_window
        self.min_swing_strength = min_swing_strength

    def analyze(self, df: pd.DataFrame) -> MarketStructure:
        """Run market structure analysis on an OHLCV DataFrame."""
        structure = MarketStructure()
        try:
            df = self._normalize_columns(df)
            if len(df) < 3 * self.fractal_window + 1:
                return structure

            # 1. Fractal swing points
            structure.swing_highs, structure.swing_lows = self._detect_swings(df)

            # 2. Aggregate key levels (sorted by distance from current price)
            structure.key_levels = self._aggregate_key_levels(structure, df)

            # 3. Trend bias from swing sequence
            structure.trend_bias = self._determine_bias(structure)

        except Exception as e:
            logger.error(f"Market structure analysis failed: {e}", exc_info=True)
        return structure

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to lowercase."""
        rename = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ('open', 'high', 'low', 'close', 'volume', 'date'):
                rename[c] = cl
        return df.rename(columns=rename)

    def _detect_swings(self, df: pd.DataFrame) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """Detect fractal swing highs and lows.

        A swing high at bar i (with window=2) means:
            high[i] > high[i-2], high[i-1], high[i+1], high[i+2]
        A swing low is the mirror.

        Stronger swings: also check if high[i] > high[i-3], high[i+3] etc. for strength 2+.
        """
        highs = df['high'].values
        lows = df['low'].values
        dates = df['date'].values if 'date' in df.columns else [str(i) for i in range(len(df))]
        n = len(df)
        w = self.fractal_window

        swing_highs: List[SwingPoint] = []
        swing_lows: List[SwingPoint] = []

        for i in range(w, n - w):
            # Swing high check
            is_high = True
            for k in range(1, w + 1):
                if highs[i] <= highs[i - k] or highs[i] <= highs[i + k]:
                    is_high = False
                    break
            if is_high:
                # Compute strength: how many bars on each side confirm
                strength = w
                for k in range(w + 1, min(w + 3, n - i, i + 1)):
                    if highs[i] > highs[i - k] and highs[i] > highs[i + k]:
                        strength += 1
                    else:
                        break
                swing_highs.append(SwingPoint(
                    index=i, price=float(highs[i]), type='HIGH',
                    date=str(dates[i]), strength=strength,
                ))

            # Swing low check
            is_low = True
            for k in range(1, w + 1):
                if lows[i] >= lows[i - k] or lows[i] >= lows[i + k]:
                    is_low = False
                    break
            if is_low:
                strength = w
                for k in range(w + 1, min(w + 3, n - i, i + 1)):
                    if lows[i] < lows[i - k] and lows[i] < lows[i + k]:
                        strength += 1
                    else:
                        break
                swing_lows.append(SwingPoint(
                    index=i, price=float(lows[i]), type='LOW',
                    date=str(dates[i]), strength=strength,
                ))

        # Mark tested + broken
        self._mark_tested_broken(swing_highs, df, 'high')
        self._mark_tested_broken(swing_lows, df, 'low')

        # Filter by minimum strength
        swing_highs = [s for s in swing_highs if s.strength >= self.min_swing_strength]
        swing_lows = [s for s in swing_lows if s.strength >= self.min_swing_strength]

        return swing_highs, swing_lows

    def _mark_tested_broken(self, swings: List[SwingPoint], df: pd.DataFrame, kind: str):
        """Mark each swing point as tested (price returned) or broken (price broke through)."""
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        for sw in swings:
            # Look at bars AFTER the swing
            for i in range(sw.index + 1, len(df)):
                if kind == 'high':
                    # Tested: a later low came back up near this high (within 0.5%)
                    if abs(lows[i] - sw.price) / sw.price < 0.005:
                        sw.tested = True
                    # Broken: a later close above this high
                    if closes[i] > sw.price:
                        sw.broken = True
                        break
                else:  # low
                    if abs(highs[i] - sw.price) / sw.price < 0.005:
                        sw.tested = True
                    if closes[i] < sw.price:
                        sw.broken = True
                        break

    def _aggregate_key_levels(self, structure: MarketStructure, df: pd.DataFrame) -> List[Dict]:
        """Aggregate all swing points into a sorted list of key levels.

        Each level gets:
        - price
        - type (swing_high / swing_low)
        - direction (BULLISH/BEARISH/NEUTRAL relative to current price)
        - strength (1-5)
        - distance_pct from current price
        - tested/broken status
        - date
        """
        current_price = float(df['close'].iloc[-1])
        levels: List[Dict] = []

        # Swing highs (resistance above price)
        for sw in structure.swing_highs[-20:]:  # last 20
            if not sw.broken:
                levels.append({
                    'price': round(sw.price, 4),
                    'type': 'swing_high',
                    'direction': 'BEARISH' if sw.price > current_price else 'NEUTRAL',
                    'strength': min(5, sw.strength + 1),
                    'tested': sw.tested,
                    'distance_pct': round((sw.price - current_price) / current_price * 100, 2),
                    'date': sw.date,
                })

        # Swing lows (support below price)
        for sw in structure.swing_lows[-20:]:
            if not sw.broken:
                levels.append({
                    'price': round(sw.price, 4),
                    'type': 'swing_low',
                    'direction': 'BULLISH' if sw.price < current_price else 'NEUTRAL',
                    'strength': min(5, sw.strength + 1),
                    'tested': sw.tested,
                    'distance_pct': round((sw.price - current_price) / current_price * 100, 2),
                    'date': sw.date,
                })

        # Dedupe: levels within 0.1% of each other = same level (keep stronger)
        unique: List[Dict] = []
        for lvl in sorted(levels, key=lambda x: x['strength'], reverse=True):
            if not any(abs(lvl['price'] - u['price']) / lvl['price'] < 0.001 for u in unique):
                unique.append(lvl)

        # Sort by distance from current price (closest first)
        unique.sort(key=lambda x: abs(x['distance_pct']))
        return unique[:20]  # top 20 most relevant

    def _determine_bias(self, structure: MarketStructure) -> str:
        """Determine trend bias from the sequence of recent swing highs/lows.

        Higher highs + higher lows = BULLISH
        Lower highs + lower lows = BEARISH
        Mixed = NEUTRAL
        """
        recent_highs = structure.swing_highs[-3:] if len(structure.swing_highs) >= 3 else structure.swing_highs
        recent_lows = structure.swing_lows[-3:] if len(structure.swing_lows) >= 3 else structure.swing_lows

        if len(recent_highs) < 2 or len(recent_lows) < 2:
            return 'NEUTRAL'

        # Check higher highs
        hh = recent_highs[-1].price > recent_highs[-2].price
        # Check higher lows
        hl = recent_lows[-1].price > recent_lows[-2].price
        # Check lower highs
        lh = recent_highs[-1].price < recent_highs[-2].price
        # Check lower lows
        ll = recent_lows[-1].price < recent_lows[-2].price

        if hh and hl:
            return 'BULLISH'
        elif lh and ll:
            return 'BEARISH'
        return 'NEUTRAL'

    def get_structure_summary(self, structure: MarketStructure, current_price: float) -> Dict:
        """Human-readable summary for UI display."""
        # Find nearest support and resistance
        supports = [s for s in structure.swing_lows if not s.broken and s.price < current_price]
        resistances = [s for s in structure.swing_highs if not s.broken and s.price > current_price]
        nearest_support = max(supports, key=lambda s: s.price) if supports else None
        nearest_resistance = min(resistances, key=lambda s: s.price) if resistances else None

        return {
            'trend_bias': structure.trend_bias,
            'nearest_support': nearest_support.price if nearest_support else None,
            'nearest_support_distance_pct': round((nearest_support.price - current_price) / current_price * 100, 2) if nearest_support else None,
            'nearest_resistance': nearest_resistance.price if nearest_resistance else None,
            'nearest_resistance_distance_pct': round((nearest_resistance.price - current_price) / current_price * 100, 2) if nearest_resistance else None,
            'swing_high_count': len(structure.swing_highs),
            'swing_low_count': len(structure.swing_lows),
            'total_key_levels': len(structure.key_levels),
        }
