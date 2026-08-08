"""
SwingEdge Pro v3 — Pivot Points & S/R Engine
NEW INTELLIGENCE: Proper pivot point calculations — Classic/Floor, Fibonacci, Camarilla,
and Woodie pivots. Replaces ad-hoc percentile S/R with trader-standard levels.

PIVOT TYPES:
1. **Classic / Floor** — Standard pit-trader pivots (most widely used)
   P = (H + L + C) / 3
   R1 = 2P - L, S1 = 2P - H
   R2 = P + (H - L), S2 = P - (H - L)
   R3 = H + 2(P - L), S3 = L - 2(H - P)

2. **Fibonacci** — Fibonacci retracement extensions of the range
   P = (H + L + C) / 3
   R1 = P + 0.382(H - L), S1 = P - 0.382(H - L)
   R2 = P + 0.618(H - L), S2 = P - 0.618(H - L)
   R3 = P + 1.000(H - L), S3 = P - 1.000(H - L)
   R4 = P + 1.618(H - L), S4 = P - 1.618(H - L)

3. **Camarilla** — Tight S/R for intraday (works on daily too)
   P = (H + L + C) / 3
   R1 = C + 1.1(H - L)/12, S1 = C - 1.1(H - L)/12
   R2 = C + 1.1(H - L)/6,  S2 = C - 1.1(H - L)/6
   R3 = C + 1.1(H - L)/4,  S3 = C - 1.1(H - L)/4
   R4 = C + 1.1(H - L)/2,  S4 = C - 1.1(H - L)/2

4. **Woodie** — Gives more weight to close
   P = (H + L + 2C) / 4
   R1 = 2P - L, S1 = 2P - H
   R2 = P + (H - L), S2 = P - (H - L)

WHY THIS MATTERS:
Pivots are the most-watched S/R levels in the world. Every trading desk, every
algo, every screen has them. If you don't have pivots, you're ignoring the
levels where 80% of order flow reacts. The old percentile S/R was statistical;
pivots are structural and trader-aware.

Usage:
    from backend.engine.pivots import PivotEngine
    pivots = PivotEngine()
    levels = pivots.calculate(df, pivot_type='classic')
    # levels = {'P': 450.5, 'R1': 458, 'S1': 443, ...}
    confluence = pivots.find_confluence(pivot_levels, structure_levels)
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PivotLevels:
    """Pivot point S/R levels for a single period."""
    pivot_type: str = 'classic'
    period_high: float = 0.0
    period_low: float = 0.0
    period_close: float = 0.0
    P: float = 0.0  # central pivot
    R1: float = 0.0
    R2: float = 0.0
    R3: float = 0.0
    R4: float = 0.0  # only Fibonacci + Camarilla
    S1: float = 0.0
    S2: float = 0.0
    S3: float = 0.0
    S4: float = 0.0
    period_label: str = ''  # 'DAILY' / 'WEEKLY' / 'MONTHLY'


class PivotEngine:
    """Calculate pivot points using standard trader methodologies.

    Pivot points are self-fulfilling because everyone uses them. The R1/S1 levels
    are the most reliable intraday reversal zones. R2/S2 are trend-continuation
    targets. R3/S3 are exhaustion extremes.
    """

    def calculate(self, df: pd.DataFrame, pivot_type: str = 'classic',
                  timeframe: str = 'daily') -> PivotLevels:
        """Calculate pivot points for the most recent completed period.

        Args:
            df: OHLCV DataFrame (must have 'high', 'low', 'close' columns)
            pivot_type: 'classic' / 'fibonacci' / 'camarilla' / 'woodie'
            timeframe: 'daily' (uses yesterday's H/L/C) / 'weekly' / 'monthly'

        Returns:
            PivotLevels dataclass with P, R1-R4, S1-S4
        """
        try:
            # Normalize columns
            df = self._normalize_columns(df)
            if df.empty or len(df) < 2:
                return PivotLevels()

            # Get the previous period's H/L/C based on timeframe
            high, low, close, label = self._get_previous_period_hlc(df, timeframe)

            return self._compute_pivots(high, low, close, pivot_type, label)
        except Exception as e:
            logger.error(f"Pivot calculation failed: {e}")
            return PivotLevels()

    def calculate_multiple_timeframes(self, df: pd.DataFrame,
                                       pivot_type: str = 'classic') -> Dict[str, PivotLevels]:
        """Calculate daily + weekly + monthly pivots and return all three.

        Confluence between timeframes = strongest S/R.
        """
        return {
            'daily': self.calculate(df, pivot_type, 'daily'),
            'weekly': self.calculate(df, pivot_type, 'weekly'),
            'monthly': self.calculate(df, pivot_type, 'monthly'),
        }

    def _get_previous_period_hlc(self, df: pd.DataFrame, timeframe: str) -> Tuple[float, float, float, str]:
        """Extract the previous period's high/low/close from the DataFrame.

        For 'daily': yesterday's H/L/C (last completed trading day)
        For 'weekly': the most recent completed week's H/L/C
        For 'monthly': the most recent completed month's H/L/C
        """
        df = df.copy()
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

        if timeframe == 'daily':
            # Use yesterday's data (last complete day)
            if len(df) < 2:
                return 0, 0, 0, 'DAILY'
            yesterday = df.iloc[-2]
            return float(yesterday['high']), float(yesterday['low']), float(yesterday['close']), 'DAILY'

        elif timeframe == 'weekly':
            # Resample to weekly, take last complete week
            weekly = df.resample('W').agg({'high': 'max', 'low': 'min', 'close': 'last'})
            if len(weekly) < 2:
                # Fall back to last 5 days
                recent = df.tail(5)
                return float(recent['high'].max()), float(recent['low'].min()), float(recent['close'].iloc[-1]), 'WEEKLY'
            last_week = weekly.iloc[-2]
            return float(last_week['high']), float(last_week['low']), float(last_week['close']), 'WEEKLY'

        elif timeframe == 'monthly':
            # Resample to monthly, take last complete month
            monthly = df.resample('ME').agg({'high': 'max', 'low': 'min', 'close': 'last'})
            if len(monthly) < 2:
                recent = df.tail(22)
                return float(recent['high'].max()), float(recent['low'].min()), float(recent['close'].iloc[-1]), 'MONTHLY'
            last_month = monthly.iloc[-2]
            return float(last_month['high']), float(last_month['low']), float(last_month['close']), 'MONTHLY'

        return 0, 0, 0, 'DAILY'

    def _compute_pivots(self, H: float, L: float, C: float, pivot_type: str, label: str) -> PivotLevels:
        """Compute pivot levels using the specified methodology."""
        if H == 0 or L == 0 or C == 0:
            return PivotLevels()

        result = PivotLevels(
            pivot_type=pivot_type, period_high=H, period_low=L, period_close=C,
            period_label=label,
        )
        rng = H - L  # the period range

        if pivot_type == 'classic' or pivot_type == 'floor':
            result.P = (H + L + C) / 3
            result.R1 = 2 * result.P - L
            result.S1 = 2 * result.P - H
            result.R2 = result.P + rng
            result.S2 = result.P - rng
            result.R3 = H + 2 * (result.P - L)
            result.S3 = L - 2 * (H - result.P)

        elif pivot_type == 'fibonacci':
            result.P = (H + L + C) / 3
            result.R1 = result.P + 0.382 * rng
            result.S1 = result.P - 0.382 * rng
            result.R2 = result.P + 0.618 * rng
            result.S2 = result.P - 0.618 * rng
            result.R3 = result.P + 1.000 * rng
            result.S3 = result.P - 1.000 * rng
            result.R4 = result.P + 1.618 * rng
            result.S4 = result.P - 1.618 * rng

        elif pivot_type == 'camarilla':
            result.P = (H + L + C) / 3
            result.R1 = C + 1.1 * rng / 12
            result.S1 = C - 1.1 * rng / 12
            result.R2 = C + 1.1 * rng / 6
            result.S2 = C - 1.1 * rng / 6
            result.R3 = C + 1.1 * rng / 4
            result.S3 = C - 1.1 * rng / 4
            result.R4 = C + 1.1 * rng / 2
            result.S4 = C - 1.1 * rng / 2

        elif pivot_type == 'woodie':
            result.P = (H + L + 2 * C) / 4
            result.R1 = 2 * result.P - L
            result.S1 = 2 * result.P - H
            result.R2 = result.P + rng
            result.S2 = result.P - rng
            result.R3 = H + 2 * (result.P - L)
            result.S3 = L - 2 * (H - result.P)

        else:
            # Default to classic
            return self._compute_pivots(H, L, C, 'classic', label)

        return result

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename = {}
        for c in df.columns:
            cl = c.lower()
            if cl in ('open', 'high', 'low', 'close', 'volume', 'date'):
                rename[c] = cl
        return df.rename(columns=rename)

    def find_confluence(self, pivot_levels: Dict[str, PivotLevels],
                        structure_levels: List[Dict],
                        tolerance_pct: float = 0.15) -> List[Dict]:
        """Find confluence zones where pivots + market structure align.

        Args:
            pivot_levels: dict from calculate_multiple_timeframes()
            structure_levels: list of structure levels from MarketStructureEngine
            tolerance_pct: levels within this % of each other = confluence (default 0.15%)

        Returns:
            List of confluence zones sorted by strength (number of overlapping levels)
        """
        all_pivot_prices = []
        for tf, piv in pivot_levels.items():
            for level_name in ('S4', 'S3', 'S2', 'S1', 'P', 'R1', 'R2', 'R3', 'R4'):
                price = getattr(piv, level_name, 0)
                if price > 0:
                    all_pivot_prices.append({
                        'price': price,
                        'source': f'{tf}_{piv.pivot_type}_{level_name}',
                        'type': 'pivot',
                    })

        # Combine with structure levels
        all_levels = all_pivot_prices + [
            {'price': sl['price'], 'source': f'structure_{sl["type"]}', 'type': 'structure',
             'direction': sl.get('direction', 'NEUTRAL')}
            for sl in structure_levels
        ]

        # Cluster levels by price proximity
        all_levels.sort(key=lambda x: x['price'])
        confluences: List[Dict] = []
        i = 0
        while i < len(all_levels):
            cluster = [all_levels[i]]
            j = i + 1
            while j < len(all_levels):
                if abs(all_levels[j]['price'] - cluster[0]['price']) / cluster[0]['price'] * 100 <= tolerance_pct:
                    cluster.append(all_levels[j])
                    j += 1
                else:
                    break
            if len(cluster) >= 2:
                avg_price = sum(c['price'] for c in cluster) / len(cluster)
                confluences.append({
                    'price': round(avg_price, 4),
                    'level_count': len(cluster),
                    'sources': [c['source'] for c in cluster],
                    'strength': min(5, len(cluster)),
                    'types_present': list(set(c['type'] for c in cluster)),
                })
            i = j

        confluences.sort(key=lambda x: x['strength'], reverse=True)
        return confluences

    def get_pivot_summary(self, levels: PivotLevels, current_price: float) -> Dict:
        """Human-readable pivot summary for UI."""
        # Where is price relative to pivot?
        if current_price > levels.R3:
            position = 'ABOVE R3 (extreme overbought)'
        elif current_price > levels.R2:
            position = 'Between R2-R3 (strong bullish)'
        elif current_price > levels.R1:
            position = 'Between R1-R2 (bullish)'
        elif current_price > levels.P:
            position = 'Between P-R1 (mildly bullish)'
        elif current_price > levels.S1:
            position = 'Between S1-P (mildly bearish)'
        elif current_price > levels.S2:
            position = 'Between S2-S1 (bearish)'
        elif current_price > levels.S3:
            position = 'Between S3-S2 (strong bearish)'
        else:
            position = 'BELOW S3 (extreme oversold)'

        return {
            'pivot_type': levels.pivot_type,
            'period': levels.period_label,
            'central_pivot': round(levels.P, 2),
            'current_price': round(current_price, 2),
            'position_vs_pivot': position,
            'distance_to_R1_pct': round((levels.R1 - current_price) / current_price * 100, 2) if levels.R1 else None,
            'distance_to_S1_pct': round((levels.S1 - current_price) / current_price * 100, 2) if levels.S1 else None,
            'all_levels': {
                'R4': round(levels.R4, 2) if levels.R4 else None,
                'R3': round(levels.R3, 2) if levels.R3 else None,
                'R2': round(levels.R2, 2) if levels.R2 else None,
                'R1': round(levels.R1, 2) if levels.R1 else None,
                'P': round(levels.P, 2) if levels.P else None,
                'S1': round(levels.S1, 2) if levels.S1 else None,
                'S2': round(levels.S2, 2) if levels.S2 else None,
                'S3': round(levels.S3, 2) if levels.S3 else None,
                'S4': round(levels.S4, 2) if levels.S4 else None,
            },
        }
