"""
SwingEdge Pro v3 — Market Structure Engine
NEW INTELLIGENCE: Proper market structure analysis — replaces the percentile-based
"support/resistance" in technicals.py (which was a statistical proxy, not real structure).

WHAT THIS MODULE DOES:
1. **Fractal swing high/low detection** — Bill Williams-style fractals with configurable
   window (default 5 bars: a swing high is a bar whose high is higher than 2 bars
   on each side). Identifies actual market pivot points, not statistical percentiles.

2. **Break of Structure (BOS)** — when price closes above the most recent swing high
   (in an uptrend) or below the most recent swing low (in a downtrend). Confirms
   trend continuation.

3. **Change of Character (CHoCH)** — when price breaks the most recent opposite-side
   swing, signaling potential trend reversal. E.g. in an uptrend, breaking below
   the last swing low = bearish CHoCH.

4. **Order Block detection** — the last down-candle before a strong up-move (bullish OB)
   or the last up-candle before a strong down-move (bearish OB). These are institutional
   accumulation/distribution zones. Price often retraces to these.

5. **Equal Highs / Equal Lows (liquidity pools)** — when two swing highs/lows are
   within 0.2% of each other, that's a liquidity pool. Stop-losses cluster there.
   Price often sweeps these before reversing.

6. **Fair Value Gap (FVG) / Imbalance** — a 3-bar pattern where bar 1's high doesn't
   overlap bar 3's low (bullish FVG) or bar 1's low doesn't overlap bar 3's high
   (bearish FVG). These are unfilled gaps that price tends to revisit.

WHY THIS MATTERS:
The old percentile-based S/R was statistically valid but had no concept of WHERE
actual buyers/sellers entered. Real market structure — swing points, order blocks,
liquidity pools — tells you where institutions are trapped and where price will
react. This is the difference between a screener and a real trading tool.

Usage:
    from backend.engine.market_structure import MarketStructureEngine
    ms = MarketStructureEngine()
    structure = ms.analyze(df)
    # structure.swing_highs, structure.swing_lows, structure.bos_events,
    # structure.choc_events, structure.order_blocks, structure.liquidity_pools,
    # structure.fair_value_gaps, structure.key_levels
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SwingPoint:
    index: int                   # bar index in the DataFrame
    price: float                 # the swing high or low price
    type: str                    # 'HIGH' or 'LOW'
    date: str = ''               # bar date if available
    strength: int = 1            # how many bars confirmed (1=weak, 2=medium, 3+=strong)
    tested: bool = False         # has price returned to test this level?
    broken: bool = False         # has price broken through this level?


@dataclass
class OrderBlock:
    index: int                   # bar index of the order block candle
    high: float
    low: float
    close: float
    type: str                    # 'BULLISH' or 'BEARISH'
    mitigation_count: int = 0    # how many times price has returned to it
    last_mitigation_index: Optional[int] = None
    strength: float = 1.0        # based on the move that followed


@dataclass
class LiquidityPool:
    """Equal highs/lows where stops cluster — magnet for price."""
    level: float
    type: str                    # 'BUY_SIDE' (equal highs) or 'SELL_SIDE' (equal lows)
    swing_indices: List[int] = field(default_factory=list)
    swept: bool = False          # has price spiked through it (stop hunt)?
    sweep_index: Optional[int] = None


@dataclass
class FairValueGap:
    """3-bar imbalance — unfilled gap price tends to revisit."""
    index: int                   # starting bar index
    top: float                   # upper boundary
    bottom: float                # lower boundary
    type: str                    # 'BULLISH' (gap up) or 'BEARISH' (gap down)
    filled: bool = False
    fill_pct: float = 0.0        # how much of the gap has been filled


@dataclass
class StructureEvent:
    """BOS or CHoCH event."""
    index: int
    type: str                    # 'BOS' or 'CHoCH'
    direction: str               # 'BULLISH' or 'BEARISH'
    broken_level: float          # the swing level that was broken
    close: float                 # the close that confirmed the break
    date: str = ''


@dataclass
class MarketStructure:
    swing_highs: List[SwingPoint] = field(default_factory=list)
    swing_lows: List[SwingPoint] = field(default_factory=list)
    bos_events: List[StructureEvent] = field(default_factory=list)
    choc_events: List[StructureEvent] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    liquidity_pools: List[LiquidityPool] = field(default_factory=list)
    fair_value_gaps: List[FairValueGap] = field(default_factory=list)
    # Aggregated levels for the current chart
    key_levels: List[Dict] = field(default_factory=list)  # sorted by significance
    trend_bias: str = 'NEUTRAL'  # BULLISH / BEARISH / NEUTRAL
    last_bos: Optional[StructureEvent] = None
    last_choc: Optional[StructureEvent] = None


class MarketStructureEngine:
    """Proper market structure analysis — ICT/SMC concepts.

    This replaces the percentile-based S/R in technicals.py with actual market
    structure: swing points, BOS, CHoCH, order blocks, liquidity pools, FVGs.
    """

    def __init__(self, fractal_window: int = 2, min_swing_strength: int = 1,
                 liquidity_tolerance_pct: float = 0.20,
                 fvg_min_size_pct: float = 0.10):
        """
        Args:
            fractal_window: bars on each side for swing detection (2 = 5-bar fractal)
            min_swing_strength: minimum confirmations to keep a swing point
            liquidity_tolerance_pct: equal H/L tolerance (0.20 = within 0.20%)
            fvg_min_size_pct: minimum gap size to qualify as FVG (0.10% of price)
        """
        self.fractal_window = fractal_window
        self.min_swing_strength = min_swing_strength
        self.liquidity_tolerance_pct = liquidity_tolerance_pct
        self.fvg_min_size_pct = fvg_min_size_pct

    def analyze(self, df: pd.DataFrame) -> MarketStructure:
        """Run full market structure analysis on an OHLCV DataFrame."""
        structure = MarketStructure()
        try:
            # Ensure column names
            df = self._normalize_columns(df)
            if len(df) < 3 * self.fractal_window + 1:
                return structure

            # 1. Fractal swing points
            structure.swing_highs, structure.swing_lows = self._detect_swings(df)

            # 2. BOS + CHoCH events
            structure.bos_events, structure.choc_events = self._detect_structure_breaks(
                df, structure.swing_highs, structure.swing_lows
            )
            if structure.bos_events:
                structure.last_bos = structure.bos_events[-1]
            if structure.choc_events:
                structure.last_choc = structure.choc_events[-1]

            # 3. Order blocks
            structure.order_blocks = self._detect_order_blocks(df)

            # 4. Liquidity pools (equal highs/lows)
            structure.liquidity_pools = self._detect_liquidity_pools(
                structure.swing_highs, structure.swing_lows
            )

            # 5. Fair value gaps
            structure.fair_value_gaps = self._detect_fvgs(df)

            # 6. Aggregate key levels
            structure.key_levels = self._aggregate_key_levels(structure, df)

            # 7. Trend bias from last BOS/CHoCH
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
        for sw in swings:
            # Look at bars AFTER the swing
            for i in range(sw.index + 1, len(df)):
                if kind == 'high':
                    # Tested: a later low came back up near this high (within 0.5%)
                    if abs(lows[i] - sw.price) / sw.price < 0.005:
                        sw.tested = True
                    # Broken: a later close above this high
                    if df['close'].values[i] > sw.price:
                        sw.broken = True
                        break
                else:  # low
                    if abs(highs[i] - sw.price) / sw.price < 0.005:
                        sw.tested = True
                    if df['close'].values[i] < sw.price:
                        sw.broken = True
                        break

    def _detect_structure_breaks(self, df: pd.DataFrame,
                                  swing_highs: List[SwingPoint],
                                  swing_lows: List[SwingPoint]) -> Tuple[List[StructureEvent], List[StructureEvent]]:
        """Detect Break of Structure (BOS) and Change of Character (CHoCH).

        BOS = price closes above the most recent swing high (in uptrend) — continuation.
        CHoCH = price closes below the most recent swing low (in uptrend) — reversal.
        (And vice versa for downtrends.)
        """
        bos_events: List[StructureEvent] = []
        choc_events: List[StructureEvent] = []
        closes = df['close'].values
        dates = df['date'].values if 'date' in df.columns else [str(i) for i in range(len(df))]

        # Track current trend bias based on last BOS direction
        current_bias = 'NEUTRAL'  # 'BULLISH' or 'BEARISH'

        # Track the most recent unbroken swing high and low
        last_high_idx = 0
        last_low_idx = 0

        all_swings = sorted(
            [(s, 'HIGH') for s in swing_highs] + [(s, 'LOW') for s in swing_lows],
            key=lambda x: x[0].index
        )

        for sw, sw_type in all_swings:
            # For each swing, check if a later close breaks it
            for i in range(sw.index + 1, len(df)):
                if sw_type == 'HIGH' and closes[i] > sw.price:
                    # Price closed above a swing high
                    if current_bias == 'BULLISH' or current_bias == 'NEUTRAL':
                        # Continuation of uptrend → BOS
                        event = StructureEvent(
                            index=i, type='BOS', direction='BULLISH',
                            broken_level=sw.price, close=float(closes[i]),
                            date=str(dates[i]),
                        )
                        bos_events.append(event)
                        current_bias = 'BULLISH'
                    else:  # current_bias == 'BEARISH'
                        # Was bearish, now breaking up → CHoCH (reversal)
                        event = StructureEvent(
                            index=i, type='CHoCH', direction='BULLISH',
                            broken_level=sw.price, close=float(closes[i]),
                            date=str(dates[i]),
                        )
                        choc_events.append(event)
                        current_bias = 'BULLISH'
                    break
                elif sw_type == 'LOW' and closes[i] < sw.price:
                    # Price closed below a swing low
                    if current_bias == 'BEARISH' or current_bias == 'NEUTRAL':
                        # Continuation of downtrend → BOS
                        event = StructureEvent(
                            index=i, type='BOS', direction='BEARISH',
                            broken_level=sw.price, close=float(closes[i]),
                            date=str(dates[i]),
                        )
                        bos_events.append(event)
                        current_bias = 'BEARISH'
                    else:  # current_bias == 'BULLISH'
                        # Was bullish, now breaking down → CHoCH
                        event = StructureEvent(
                            index=i, type='CHoCH', direction='BEARISH',
                            broken_level=sw.price, close=float(closes[i]),
                            date=str(dates[i]),
                        )
                        choc_events.append(event)
                        current_bias = 'BEARISH'
                    break

        return bos_events, choc_events

    def _detect_order_blocks(self, df: pd.DataFrame, lookback: int = 50,
                              min_move_pct: float = 1.5) -> List[OrderBlock]:
        """Detect order blocks — last opposite-color candle before a strong move.

        Bullish OB: last down-candle before a strong up-move (≥ min_move_pct in next 3 bars).
        Bearish OB: last up-candle before a strong down-move.

        These are institutional accumulation zones — price often retraces to them.
        """
        obs: List[OrderBlock] = []
        opens = df['open'].values
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        n = len(df)

        for i in range(1, n - 3):
            # Look at bars in lookback window only (most recent)
            if i < n - lookback - 3:
                continue
            # Bullish OB: down candle at i, strong up-move in i+1..i+3
            if closes[i] < opens[i]:  # down candle
                move_pct = (max(closes[i+1:i+4]) - closes[i]) / closes[i] * 100
                if move_pct >= min_move_pct:
                    obs.append(OrderBlock(
                        index=i, high=float(highs[i]), low=float(lows[i]),
                        close=float(closes[i]), type='BULLISH',
                        strength=round(move_pct / min_move_pct, 2),
                    ))
            # Bearish OB: up candle at i, strong down-move in i+1..i+3
            elif closes[i] > opens[i]:  # up candle
                move_pct = (closes[i] - min(closes[i+1:i+4])) / closes[i] * 100
                if move_pct >= min_move_pct:
                    obs.append(OrderBlock(
                        index=i, high=float(highs[i]), low=float(lows[i]),
                        close=float(closes[i]), type='BEARISH',
                        strength=round(move_pct / min_move_pct, 2),
                    ))

        # Mark mitigation: how many times price returned to the OB zone
        for ob in obs:
            for i in range(ob.index + 4, n):
                if ob.type == 'BULLISH' and lows[i] <= ob.high and lows[i] >= ob.low:
                    ob.mitigation_count += 1
                    ob.last_mitigation_index = i
                elif ob.type == 'BEARISH' and highs[i] >= ob.low and highs[i] <= ob.high:
                    ob.mitigation_count += 1
                    ob.last_mitigation_index = i

        # Sort by recency and keep most relevant
        obs.sort(key=lambda o: o.index, reverse=True)
        return obs[:10]  # top 10 most recent

    def _detect_liquidity_pools(self, swing_highs: List[SwingPoint],
                                 swing_lows: List[SwingPoint]) -> List[LiquidityPool]:
        """Detect equal highs/lows — where stops cluster and price sweeps.

        Two swing highs within 0.2% of each other = buy-side liquidity pool.
        Two swing lows within 0.2% = sell-side liquidity pool.
        Price often spikes through these to grab stops before reversing.
        """
        pools: List[LiquidityPool] = []

        # Buy-side (equal highs)
        for i in range(len(swing_highs)):
            for j in range(i + 1, len(swing_highs)):
                p1, p2 = swing_highs[i].price, swing_highs[j].price
                if p1 <= 0 or p2 <= 0:
                    continue
                diff_pct = abs(p1 - p2) / min(p1, p2) * 100
                if diff_pct <= self.liquidity_tolerance_pct:
                    level = (p1 + p2) / 2
                    pools.append(LiquidityPool(
                        level=round(level, 4), type='BUY_SIDE',
                        swing_indices=[swing_highs[i].index, swing_highs[j].index],
                    ))

        # Sell-side (equal lows)
        for i in range(len(swing_lows)):
            for j in range(i + 1, len(swing_lows)):
                p1, p2 = swing_lows[i].price, swing_lows[j].price
                if p1 <= 0 or p2 <= 0:
                    continue
                diff_pct = abs(p1 - p2) / min(p1, p2) * 100
                if diff_pct <= self.liquidity_tolerance_pct:
                    level = (p1 + p2) / 2
                    pools.append(LiquidityPool(
                        level=round(level, 4), type='SELL_SIDE',
                        swing_indices=[swing_lows[i].index, swing_lows[j].index],
                    ))

        # Dedupe: pools at very similar levels
        unique_pools: List[LiquidityPool] = []
        for p in pools:
            if not any(abs(p.level - up.level) / p.level < 0.001 for up in unique_pools):
                unique_pools.append(p)

        return unique_pools[:8]  # top 8

    def _detect_fvgs(self, df: pd.DataFrame) -> List[FairValueGap]:
        """Detect Fair Value Gaps (3-bar imbalances).

        Bullish FVG: bar[i-1].high < bar[i+1].low (gap up, never filled)
        Bearish FVG: bar[i-1].low > bar[i+1].high (gap down, never filled)
        """
        fvgs: List[FairValueGap] = []
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        n = len(df)

        for i in range(1, n - 1):
            # Bullish FVG: high[i-1] < low[i+1]
            if highs[i - 1] < lows[i + 1]:
                gap_top = float(lows[i + 1])
                gap_bottom = float(highs[i - 1])
                gap_size_pct = (gap_top - gap_bottom) / closes[i] * 100
                if gap_size_pct >= self.fvg_min_size_pct:
                    # Check if filled by later price action
                    filled = False
                    fill_pct = 0.0
                    for j in range(i + 2, n):
                        if lows[j] <= gap_top:
                            # Partial or full fill
                            fill_amount = gap_top - max(lows[j], gap_bottom)
                            fill_pct = max(fill_pct, fill_amount / (gap_top - gap_bottom) * 100)
                            if lows[j] <= gap_bottom:
                                filled = True
                                break
                    fvgs.append(FairValueGap(
                        index=i, top=gap_top, bottom=gap_bottom,
                        type='BULLISH', filled=filled, fill_pct=round(fill_pct, 1),
                    ))
            # Bearish FVG: low[i-1] > high[i+1]
            elif lows[i - 1] > highs[i + 1]:
                gap_top = float(lows[i - 1])
                gap_bottom = float(highs[i + 1])
                gap_size_pct = (gap_top - gap_bottom) / closes[i] * 100
                if gap_size_pct >= self.fvg_min_size_pct:
                    filled = False
                    fill_pct = 0.0
                    for j in range(i + 2, n):
                        if highs[j] >= gap_bottom:
                            fill_amount = min(highs[j], gap_top) - gap_bottom
                            fill_pct = max(fill_pct, fill_amount / (gap_top - gap_bottom) * 100)
                            if highs[j] >= gap_top:
                                filled = True
                                break
                    fvgs.append(FairValueGap(
                        index=i, top=gap_top, bottom=gap_bottom,
                        type='BEARISH', filled=filled, fill_pct=round(fill_pct, 1),
                    ))

        # Return most recent unfilled FVGs first
        unfilled = [f for f in fvgs if not f.filled]
        unfilled.sort(key=lambda f: f.index, reverse=True)
        return unfilled[:5] + [f for f in fvgs if f.filled][-3:]  # 5 unfilled + 3 filled

    def _aggregate_key_levels(self, structure: MarketStructure, df: pd.DataFrame) -> List[Dict]:
        """Aggregate all structure points into a sorted list of key levels.

        Each level gets:
        - price
        - type (swing_high, swing_low, order_block, liquidity_pool, fvg)
        - direction (BULLISH/BEARISH/NEUTRAL)
        - strength (1-5)
        - distance_pct from current price
        - tested/broken status
        """
        current_price = float(df['close'].iloc[-1])
        levels: List[Dict] = []

        # Swing highs (resistance)
        for sw in structure.swing_highs[-15:]:  # last 15
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

        # Swing lows (support)
        for sw in structure.swing_lows[-15:]:
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

        # Order blocks
        for ob in structure.order_blocks[:5]:
            levels.append({
                'price': round((ob.high + ob.low) / 2, 4),
                'type': f'order_block_{ob.type.lower()}',
                'direction': ob.type,
                'strength': min(5, int(ob.strength) + 1),
                'tested': ob.mitigation_count > 0,
                'distance_pct': round(((ob.high + ob.low) / 2 - current_price) / current_price * 100, 2),
                'mitigation_count': ob.mitigation_count,
                'zone_high': round(ob.high, 4),
                'zone_low': round(ob.low, 4),
            })

        # Liquidity pools (high significance — magnet for price)
        for lp in structure.liquidity_pools[:4]:
            levels.append({
                'price': lp.level,
                'type': f'liquidity_pool_{lp.type.lower()}',
                'direction': 'NEUTRAL',  # magnet, not directional
                'strength': 5,  # highest — these are stop hunts
                'tested': lp.swept,
                'distance_pct': round((lp.level - current_price) / current_price * 100, 2),
            })

        # Sort by distance from current price (closest first)
        levels.sort(key=lambda x: abs(x['distance_pct']))
        return levels[:20]  # top 20 most relevant

    def _determine_bias(self, structure: MarketStructure) -> str:
        """Determine overall trend bias from BOS/CHoCH sequence.

        Most recent event wins. If last CHoCH is more recent than last BOS, that's the bias.
        """
        last_bos_idx = structure.bos_events[-1].index if structure.bos_events else -1
        last_choc_idx = structure.choc_events[-1].index if structure.choc_events else -1

        if last_choc_idx > last_bos_idx and last_choc_idx >= 0:
            return structure.choc_events[-1].direction
        elif last_bos_idx >= 0:
            return structure.bos_events[-1].direction
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
            'last_event_type': structure.last_bos.type if structure.last_bos and (not structure.last_choc or structure.last_bos.index > structure.last_choc.index) else (structure.last_choc.type if structure.last_choc else None),
            'last_event_direction': (structure.last_bos.direction if structure.last_bos and (not structure.last_choc or structure.last_bos.index > structure.last_choc.index) else (structure.last_choc.direction if structure.last_choc else None)),
            'order_block_count': len(structure.order_blocks),
            'liquidity_pool_count': len(structure.liquidity_pools),
            'unfilled_fvg_count': len([f for f in structure.fair_value_gaps if not f.filled]),
            'total_key_levels': len(structure.key_levels),
        }
