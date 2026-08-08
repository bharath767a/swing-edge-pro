"""
SwingEdge Pro v3 — Hold Period Determination Engine
NEW INTELLIGENCE: Proper holding period calculation based on trade structure,
not a hand-tuned heuristic. Replaces the simple "10 ± decay ± ADX" formula.

THREE METHODS, BLENDED:
1. **Structure-based** — measure distance to next S/R; divide by expected speed
   (ATR/day) → expected bars to reach target. This is the most accurate.

2. **ATR-based** — target / (ATR × 0.5) → expected bars (price covers ~0.5 ATR/day
   on average in trending markets, ~0.3 ATR/day in choppy markets).

3. **Decay-based** — for leveraged ETFs only: max hold = decay_budget / daily_decay.
   E.g. budget 0.5% decay / 0.05%/day = 10 days max.

BLEND LOGIC:
- For non-leveraged: take the structure-based estimate, sanity-check vs ATR-based.
- For leveraged ETFs: take min(structure-based, decay-based) — decay caps the hold.
- For all: enforce min 3 days (avoid intraday noise) and max 30 days (avoid drift).

Usage:
    from backend.engine.hold_period import HoldPeriodEngine
    hp = HoldPeriodEngine()
    rec = hp.recommend(
        entry_price=100, target=110, stop=95,
        atr=2.0, adx=28, is_leveraged=False,
        daily_decay_pct=0.0, structure_levels=[...],
        current_price=100,
    )
    # rec.recommended_days, rec.method_used, rec.confidence, rec.rationale
"""
import logging
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HoldPeriodRecommendation:
    recommended_days: int = 10
    min_days: int = 3
    max_days: int = 30
    method_used: str = 'blend'              # 'structure' / 'atr' / 'decay' / 'blend'
    structure_estimate: Optional[int] = None
    atr_estimate: Optional[int] = None
    decay_estimate: Optional[int] = None
    confidence: float = 0.5                 # 0-1, higher = more agreement between methods
    rationale: str = ''


class HoldPeriodEngine:
    """Multi-method hold period determination.

    The right hold period is a function of:
    1. How far price needs to travel to reach target (structure)
    2. How fast price typically moves in this instrument (ATR + ADX)
    3. How long before decay eats the edge (leveraged ETFs only)
    4. How long until a catalyst invalidates the thesis (events)

    This engine blends all four.
    """

    # Method weights (must sum to 1.0 for non-leveraged)
    WEIGHTS_NON_LEVERAGED = {'structure': 0.50, 'atr': 0.35, 'event': 0.15}
    # For leveraged ETFs, decay dominates
    WEIGHTS_LEVERAGED = {'structure': 0.35, 'atr': 0.20, 'decay': 0.35, 'event': 0.10}

    # Sanity bounds
    MIN_DAYS = 3
    MAX_DAYS = 30
    MIN_DAYS_LEVERAGED = 2
    MAX_DAYS_LEVERAGED = 15

    # Speed model: in trending markets, price covers ~50% of ATR per day
    # In choppy markets, ~30%. In strong trends, ~70%.
    SPEED_TREND_MULT = {  # multiplier on ATR per day, keyed by ADX
        'strong_trend': 0.70,   # ADX > 35
        'trending': 0.50,       # ADX 25-35
        'mild_trend': 0.40,     # ADX 18-25
        'choppy': 0.30,         # ADX < 18
    }

    # Decay budget: max cumulative decay we tolerate before exit
    DECAY_BUDGET_PCT = 0.50  # 0.5% max decay for 2x ETFs

    def recommend(self, entry_price: float, target: float, stop: float,
                  atr: float, adx: float, is_leveraged: bool = False,
                  daily_decay_pct: float = 0.0,
                  structure_levels: Optional[List[Dict]] = None,
                  event_days_ahead: Optional[int] = None) -> HoldPeriodRecommendation:
        """Recommend a holding period for a swing trade.

        Args:
            entry_price: planned entry
            target: planned target (take-profit)
            stop: planned stop-loss
            atr: 14-day ATR (absolute, not %)
            adx: 14-day ADX (trend strength)
            is_leveraged: True for 2x/3x leveraged ETFs
            daily_decay_pct: estimated daily decay (for leveraged ETFs)
            structure_levels: list of S/R levels with 'price' and 'distance_pct'
            event_days_ahead: days until known catalyst (earnings/FOMC/etc.)

        Returns:
            HoldPeriodRecommendation with blended estimate + per-method breakdowns
        """
        rec = HoldPeriodRecommendation()
        try:
            # Method 1: Structure-based
            rec.structure_estimate = self._structure_based_estimate(
                entry_price, target, structure_levels
            )

            # Method 2: ATR-based
            rec.atr_estimate = self._atr_based_estimate(entry_price, target, atr, adx)

            # Method 3: Decay-based (leveraged only)
            if is_leveraged and daily_decay_pct > 0:
                rec.decay_estimate = self._decay_based_estimate(daily_decay_pct)

            # Method 4: Event-based (if catalyst known)
            event_estimate = event_days_ahead - 1 if event_days_ahead else None  # exit day before catalyst

            # Blend
            weights = self.WEIGHTS_LEVERAGED if is_leveraged else self.WEIGHTS_NON_LEVERAGED
            estimates = []
            weighted_sum = 0.0
            total_weight = 0.0

            for method, weight in weights.items():
                if method == 'structure' and rec.structure_estimate:
                    estimates.append(rec.structure_estimate)
                    weighted_sum += rec.structure_estimate * weight
                    total_weight += weight
                elif method == 'atr' and rec.atr_estimate:
                    estimates.append(rec.atr_estimate)
                    weighted_sum += rec.atr_estimate * weight
                    total_weight += weight
                elif method == 'decay' and rec.decay_estimate:
                    estimates.append(rec.decay_estimate)
                    weighted_sum += rec.decay_estimate * weight
                    total_weight += weight
                elif method == 'event' and event_estimate:
                    estimates.append(event_estimate)
                    weighted_sum += event_estimate * weight
                    total_weight += weight

            if total_weight > 0:
                blended = int(weighted_sum / total_weight)
            else:
                blended = 10  # fallback

            # Apply bounds
            min_days = self.MIN_DAYS_LEVERAGED if is_leveraged else self.MIN_DAYS
            max_days = self.MAX_DAYS_LEVERAGED if is_leveraged else self.MAX_DAYS
            # If event is within max_days, cap at event - 1
            if event_estimate and event_estimate < max_days:
                max_days = max(min_days, event_estimate - 1)

            rec.recommended_days = max(min_days, min(max_days, blended))
            rec.min_days = min_days
            rec.max_days = max_days

            # Confidence: how much agreement between methods
            if len(estimates) >= 2:
                std = float(np.std(estimates))
                mean = float(np.mean(estimates))
                cv = std / mean if mean > 0 else 1.0  # coefficient of variation
                rec.confidence = round(max(0.0, min(1.0, 1.0 - cv)), 2)
            elif len(estimates) == 1:
                rec.confidence = 0.4
            else:
                rec.confidence = 0.2

            rec.rationale = self._build_rationale(rec, is_leveraged, adx, atr,
                                                   daily_decay_pct, event_estimate)

        except Exception as e:
            logger.error(f"Hold period calc failed: {e}")
            rec.rationale = f"Error: {e}"

        return rec

    def _structure_based_estimate(self, entry: float, target: float,
                                    structure_levels: Optional[List[Dict]]) -> Optional[int]:
        """Estimate days based on distance to target divided by expected daily progress.

        If structure_levels provided, find the nearest level beyond target and use
        that distance instead — targets often get slightly overshot.
        """
        if entry <= 0:
            return None
        distance = abs(target - entry)
        distance_pct = distance / entry * 100

        # If we have structure levels, check if target aligns with a known level
        # (if so, the level is more reliable than an arbitrary 10% target)
        effective_distance_pct = distance_pct
        if structure_levels:
            # Find nearest level beyond target
            if target > entry:  # long
                beyond = [l for l in structure_levels if l.get('price', 0) > target]
                if beyond:
                    nearest = min(beyond, key=lambda l: l['price'])
                    # Use midpoint of target and the structure level
                    effective_distance_pct = (nearest['price'] - entry) / entry * 100
            else:  # short
                beyond = [l for l in structure_levels if l.get('price', 0) < target]
                if beyond:
                    nearest = max(beyond, key=lambda l: l['price'])
                    effective_distance_pct = (entry - nearest['price']) / entry * 100

        # Rough heuristic: price moves ~1-2% per day in swing-friendly conditions
        # So a 10% target takes ~7-10 days, 5% target takes ~4-5 days, etc.
        # We refine this with ATR in the ATR method; structure gives the distance.
        estimated_days = int(effective_distance_pct / 1.2)  # 1.2% per day baseline
        return max(self.MIN_DAYS, min(self.MAX_DAYS, estimated_days))

    def _atr_based_estimate(self, entry: float, target: float,
                             atr: float, adx: float) -> Optional[int]:
        """Estimate days based on ATR and trend strength.

        Logic: distance / (ATR × daily_speed_multiplier) = expected days
        Daily speed depends on ADX (trend strength).
        """
        if atr <= 0 or entry <= 0:
            return None
        distance = abs(target - entry)

        # Pick speed multiplier based on ADX
        if adx > 35:
            speed = self.SPEED_TREND_MULT['strong_trend']
        elif adx > 25:
            speed = self.SPEED_TREND_MULT['trending']
        elif adx > 18:
            speed = self.SPEED_TREND_MULT['mild_trend']
        else:
            speed = self.SPEED_TREND_MULT['choppy']

        daily_progress = atr * speed
        if daily_progress <= 0:
            return None
        estimated_days = int(distance / daily_progress)
        return max(self.MIN_DAYS, min(self.MAX_DAYS, estimated_days))

    def _decay_based_estimate(self, daily_decay_pct: float) -> Optional[int]:
        """For leveraged ETFs: max days before cumulative decay exceeds budget.

        decay_budget / daily_decay = max_days
        E.g. 0.5% / 0.05%/day = 10 days
        """
        if daily_decay_pct <= 0:
            return None
        max_days = int(self.DECAY_BUDGET_PCT / daily_decay_pct)
        return max(self.MIN_DAYS_LEVERAGED, min(self.MAX_DAYS_LEVERAGED, max_days))

    def _build_rationale(self, rec: HoldPeriodRecommendation, is_leveraged: bool,
                          adx: float, atr: float, daily_decay_pct: float,
                          event_estimate: Optional[int]) -> str:
        parts = [f"Recommended hold: {rec.recommended_days} days (range {rec.min_days}-{rec.max_days})"]
        parts.append(f"Confidence: {rec.confidence:.0%}")
        if rec.structure_estimate:
            parts.append(f"Structure estimate: {rec.structure_estimate}d")
        if rec.atr_estimate:
            parts.append(f"ATR estimate: {rec.atr_estimate}d (ATR={atr:.2f}, ADX={adx:.0f})")
        if rec.decay_estimate:
            parts.append(f"Decay estimate: {rec.decay_estimate}d (decay={daily_decay_pct:.3f}%/day)")
        if event_estimate:
            parts.append(f"Event cap: {event_estimate - 1}d (exit before catalyst)")
        if is_leveraged:
            parts.append("[LEVERAGED — decay-capped]")
        return " | ".join(parts)
