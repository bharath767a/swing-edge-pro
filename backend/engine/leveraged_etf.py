"""
SwingEdge Pro v3 — 2x Leveraged ETF Swing Engine
NEW INTELLIGENCE: Identifies quality, high-probability 2x long/short ETF swing trades.

WHY THIS IS A SEPARATE MODULE FROM THE MAIN SCORER:
2x leveraged ETFs have unique risks that vanilla swing scoring misses:
1. **Volatility decay (beta slippage)** — in choppy markets, 2x ETFs bleed value daily
   even if the underlying is flat. Example: if underlying goes +5% then -5%, a 2x ETF
   goes +10% then -10% = net -1% (vs underlying's -0.25%).
2. **Regime dependency** — 2x longs only work in clean uptrends; 2x shorts only in
   clean downtrends. Sideways markets = guaranteed decay loss.
3. **Holding period cap** — 2x ETFs should rarely be held >15 trading days. Decay
   compounds the longer you hold.
4. **Catalyst avoidance** — must avoid FOMC, CPI, major earnings (volatility spikes
   = decay accelerates).

ENGINE OUTPUTS:
- Per-ETF swing quality score (0-100) with regime alignment
- Volatility decay risk rating (LOW/MEDIUM/HIGH) + estimated daily decay %
- ATR-based entry/stop/target with 1.5x multiplier (wider for 2x vol)
- Recommended holding period (5-15 days)
- Catalyst warnings (upcoming Fed dates, earnings)
- Direction bias (LONG candidate / SHORT candidate / NEUTRAL — avoid)

Usage:
    from backend.engine.leveraged_etf import LeveragedETFEngine
    engine = LeveragedETFEngine()
    candidates = engine.screen()  # returns ranked list
    # top candidate = candidates[0]
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.data.fetchers import get_ohlcv
from backend.data.leveraged_etf_universe import LEVERAGED_ETF_UNIVERSE
from backend.engine.technicals import TechnicalsEngine
from backend.engine.market_regime import MarketRegimeClassifier

logger = logging.getLogger(__name__)


@dataclass
class LeveragedETFSignal:
    """A ranked 2x leveraged ETF swing trade signal."""
    ticker: str = ''
    direction: str = 'LONG'              # LONG / SHORT / NEUTRAL
    underlying: str = ''
    asset_class: str = ''
    current_price: float = 0.0
    # Scores
    composite_score: float = 0.0         # 0-100, higher = better swing setup
    quality_score: float = 0.0           # trend + liquidity + spread
    pattern_score: float = 0.0           # VCP/EP/BullFlag detection
    regime_alignment_score: float = 0.0  # is the regime right for this direction?
    # Risk metrics unique to leveraged ETFs
    decay_risk: str = 'MEDIUM'           # LOW / MEDIUM / HIGH
    estimated_daily_decay_pct: float = 0.0
    volatility_drag_5d_pct: float = 0.0  # how much decay over 5-day hold
    # Trade setup
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    risk_reward: float = 0.0
    recommended_hold_days: int = 10
    # Pattern + technicals
    pattern: str = 'none'
    trend: str = 'neutral'
    rsi: float = 50.0
    adx: float = 20.0
    atr_pct: float = 0.0
    rel_volume: float = 1.0
    # Risk flags
    regime_aligned: bool = False
    catalyst_warning: str = ''
    # Human-readable explanation
    rationale: str = ''


class LeveragedETFEngine:
    """Swing screener specialized for 2x leveraged ETFs.

    KEY DIFFERENCES vs MasterScorer:
    - Strict regime filter: 2x longs only in BULLISH_EXPANSION / CAUTIOUS_BULL;
      2x shorts only in HIGH_VOLATILITY_DEFENSIVE
    - Decay-aware scoring: penalizes ETFs with high recent volatility (more decay)
    - Wider ATR stops: 2.5x ATR (vs 2.0x for non-leveraged) due to 2x vol
    - Holding period cap: 5-15 trading days max
    - Catalyst avoidance: flags upcoming FOMC/CPI dates
    - Liquidity filter: requires avg volume > 500K (else spreads eat the edge)
    """

    # Screening thresholds
    MIN_AVG_VOLUME = 500_000             # liquidity floor
    MIN_ADX_FOR_TREND = 22               # below this = no clean trend = skip
    MAX_RSI_OVERBOUGHT_LONG = 78         # don't chase 2x longs at extreme overbought
    MIN_RSI_FOR_SHORT = 50               # short setups need RSI < 50
    # Decay model — calibrated to typical 2x ETF behavior
    # Daily decay ≈ 0.5 * (daily_vol)^2 * 100 (in %)
    # At 1.5% daily vol (high-vol ETF): 0.5 * 0.0225 * 100 = 0.11%/day = 0.55%/5days
    DECAY_COEFFICIENT = 0.5
    # ATR multipliers (wider for 2x vol)
    STOP_LOSS_ATR_MULT = 2.5
    TARGET_ATR_MULT = 5.0                # 2:1 R:R minimum
    # Holding period
    MIN_HOLD_DAYS = 5
    MAX_HOLD_DAYS = 15

    def __init__(self):
        self.tech = TechnicalsEngine()
        self.regime = MarketRegimeClassifier()

    def screen(self, direction_filter: Optional[str] = None,
               asset_class_filter: Optional[str] = None,
               min_score: float = 60.0,
               limit: int = 20) -> List[LeveragedETFSignal]:
        """Screen the entire 2x leveraged ETF universe for swing candidates.

        Args:
            direction_filter: 'LONG' / 'SHORT' / None (both)
            asset_class_filter: 'equity' / 'sector' / 'commodity' / 'rates' / 'thematic' / None
            min_score: minimum composite score to include (default 60)
            limit: max number of results

        Returns:
            List of LeveragedETFSignal sorted by composite_score desc
        """
        # Get regime once (cached globally)
        regime_data = self.regime.evaluate_regime()

        # Filter universe
        universe = LEVERAGED_ETF_UNIVERSE
        if direction_filter:
            universe = [e for e in universe if e['direction'] == direction_filter.upper()]
        if asset_class_filter:
            universe = [e for e in universe if e['asset_class'] == asset_class_filter.lower()]

        signals: List[LeveragedETFSignal] = []
        for etf_meta in universe:
            try:
                signal = self._analyze_etf(etf_meta, regime_data)
                if signal and signal.composite_score >= min_score:
                    signals.append(signal)
            except Exception as e:
                logger.debug(f"ETF analyze failed {etf_meta['ticker']}: {e}")

        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals[:limit]

    def analyze_ticker(self, ticker: str) -> Optional[LeveragedETFSignal]:
        """Analyze a single ETF ticker (must be in our universe)."""
        from backend.data.leveraged_etf_universe import get_etf_by_ticker
        meta = get_etf_by_ticker(ticker)
        if not meta:
            return None
        regime_data = self.regime.evaluate_regime()
        return self._analyze_etf(meta, regime_data)

    def _analyze_etf(self, etf_meta: Dict, regime_data: Dict) -> Optional[LeveragedETFSignal]:
        """Run full analysis on a single 2x leveraged ETF."""
        ticker = etf_meta['ticker']
        direction = etf_meta['direction']

        signal = LeveragedETFSignal(
            ticker=ticker,
            direction=direction,
            underlying=etf_meta['underlying'],
            asset_class=etf_meta['asset_class'],
        )

        try:
            # ── Fetch OHLCV ───────────────────────────────────────────────
            df = get_ohlcv(ticker, period='1y', interval='1d')
            if df is None or len(df) < 60:
                return signal  # insufficient data, will be filtered out

            # ── Compute indicators ────────────────────────────────────────
            df = self.tech.calculate_all_indicators(df)
            if df is None or df.empty:
                return signal

            last = df.iloc[-1]
            close = float(last['close'])
            signal.current_price = close

            # ── Liquidity check ───────────────────────────────────────────
            avg_vol_20 = float(df['volume'].tail(20).mean())
            if avg_vol_20 < self.MIN_AVG_VOLUME:
                signal.rationale = f"Skipped: low liquidity (avg vol {avg_vol_20:,.0f} < {self.MIN_AVG_VOLUME:,})"
                signal.composite_score = 0
                return signal
            signal.rel_volume = round(float(last['volume']) / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

            # ── Technicals ────────────────────────────────────────────────
            signal.rsi = round(float(last.get('rsi', 50) or 50), 1)
            signal.adx = round(float(last.get('adx', 20) or 20), 1)
            signal.atr_pct = round(float(last.get('atr', 0) or 0) / close * 100, 2) if close > 0 else 0
            signal.pattern = self._detect_pattern(df, direction)
            signal.trend = self._determine_trend(last)

            # ── Volatility decay model ────────────────────────────────────
            # Daily returns std → estimated daily decay %
            daily_returns = df['close'].pct_change().dropna().tail(20)
            daily_vol = float(daily_returns.std()) if len(daily_returns) > 5 else 0.02
            signal.estimated_daily_decay_pct = round(
                self.DECAY_COEFFICIENT * (daily_vol ** 2) * 100, 4
            )
            # 5-day drag estimate (compounded)
            signal.volatility_drag_5d_pct = round(
                (1 - (1 - signal.estimated_daily_decay_pct / 100) ** 5) * 100, 3
            )
            # Decay risk rating
            if signal.estimated_daily_decay_pct < 0.05:
                signal.decay_risk = 'LOW'
            elif signal.estimated_daily_decay_pct < 0.15:
                signal.decay_risk = 'MEDIUM'
            else:
                signal.decay_risk = 'HIGH'

            # ── Regime alignment (CRITICAL for leveraged ETFs) ────────────
            signal.regime_aligned, signal.regime_alignment_score = self._check_regime_alignment(
                direction, regime_data
            )

            # ── Quality score (trend + liquidity + spread) ────────────────
            signal.quality_score = self._compute_quality_score(
                signal, etf_meta, avg_vol_20
            )

            # ── Pattern score ─────────────────────────────────────────────
            signal.pattern_score = self._compute_pattern_score(signal.pattern)

            # ── Composite score with decay penalty ────────────────────────
            signal.composite_score = self._compute_composite_score(signal)

            # ── Entry / Stop / Target ─────────────────────────────────────
            atr = float(last.get('atr', 0) or 0)
            if atr > 0:
                signal.entry_price = round(close, 2)
                if direction == 'LONG':
                    signal.stop_loss = round(close - (atr * self.STOP_LOSS_ATR_MULT), 2)
                    signal.target_price = round(close + (atr * self.TARGET_ATR_MULT), 2)
                else:  # SHORT
                    signal.stop_loss = round(close + (atr * self.STOP_LOSS_ATR_MULT), 2)
                    signal.target_price = round(close - (atr * self.TARGET_ATR_MULT), 2)
                # Risk:Reward
                risk = abs(signal.entry_price - signal.stop_loss)
                reward = abs(signal.target_price - signal.entry_price)
                signal.risk_reward = round(reward / risk, 2) if risk > 0 else 0

            # ── Holding period recommendation ────────────────────────────
            signal.recommended_hold_days = self._recommend_hold_days(signal)

            # ── Catalyst warnings ─────────────────────────────────────────
            signal.catalyst_warning = self._check_catalyst_warnings()

            # ── Final rationale ───────────────────────────────────────────
            signal.rationale = self._build_rationale(signal, regime_data)

            # ── Filter: regime misaligned = score 0 ───────────────────────
            if not signal.regime_aligned and not self._is_neutral_regime(regime_data):
                # Penalize heavily but don't zero — user may want to see misaligned
                signal.composite_score = round(signal.composite_score * 0.4, 1)
                signal.rationale = f"REGIME MISALIGNED — {signal.rationale}"

        except Exception as e:
            logger.warning(f"ETF analysis failed {ticker}: {e}", exc_info=True)
            signal.rationale = f"Analysis error: {e}"

        return signal

    def _determine_trend(self, last) -> str:
        """Determine trend from EMA alignment."""
        try:
            close = float(last['close'])
            ema8 = float(last.get('ema8', 0) or 0)
            ema21 = float(last.get('ema21', 0) or 0)
            ema50 = float(last.get('ema50', 0) or 0)
            ema200 = float(last.get('ema200', 0) or 0)
            if close > ema8 > ema21 > ema50 > ema200:
                return 'strong_bullish'
            elif close > ema50 > ema200:
                return 'bullish'
            elif close < ema8 < ema21 < ema50 < ema200:
                return 'strong_bearish'
            elif close < ema50 < ema200:
                return 'bearish'
            return 'neutral'
        except Exception:
            return 'neutral'

    def _detect_pattern(self, df: pd.DataFrame, direction: str) -> str:
        """Detect swing setup patterns. Reuse technicals engine logic."""
        try:
            patterns = self.tech.detect_patterns(df)
            # For short ETFs, invert the pattern interpretation
            # (a 'bull_flag' on SDS = bear_flag on S&P 500, etc.)
            if not patterns:
                return 'none'
            if direction == 'SHORT':
                # Map bullish patterns to their bearish equivalents for short ETFs
                pattern_map = {
                    'vcp': 'vcp_short',  # VCP on the short ETF = bullish for the short
                    'episodic_pivot': 'episodic_pivot_short',
                    'bull_flag': 'bear_flag_equivalent',
                    'cup_handle': 'cup_handle_short',
                }
                return pattern_map.get(patterns[0], patterns[0])
            return patterns[0]
        except Exception:
            return 'none'

    def _check_regime_alignment(self, direction: str, regime_data: Dict) -> Tuple[bool, float]:
        """Check if the market regime supports this ETF direction.

        CRITICAL: This is the #1 filter for leveraged ETFs.
        - 2x LONG ETFs only make sense in BULLISH_EXPANSION or CAUTIOUS_BULL
        - 2x SHORT ETFs only make sense in HIGH_VOLATILITY_DEFENSIVE
        - In NEUTRAL_SIDEWAYS: skip both (decay will eat you)
        - In DATA_DEGRADED: skip both (can't trust signals)
        """
        regime = regime_data.get('regime', 'NEUTRAL')
        if regime == 'DATA_DEGRADED':
            return False, 20.0  # no trades when data is bad

        if direction == 'LONG':
            if regime == 'BULLISH_EXPANSION':
                return True, 100.0
            elif regime == 'CAUTIOUS_BULL':
                return True, 75.0
            elif regime == 'NEUTRAL_SIDEWAYS':
                return False, 35.0  # decay risk, don't buy longs here
            elif regime == 'HIGH_VOLATILITY_DEFENSIVE':
                return False, 10.0  # terrible time for longs
        else:  # SHORT
            if regime == 'HIGH_VOLATILITY_DEFENSIVE':
                return True, 100.0
            elif regime == 'NEUTRAL_SIDEWAYS':
                return False, 35.0  # decay risk, don't buy shorts here either
            elif regime == 'CAUTIOUS_BULL':
                return False, 20.0  # fighting the tape
            elif regime == 'BULLISH_EXPANSION':
                return False, 5.0  # death wish — shorting in bull market

        return False, 50.0

    def _is_neutral_regime(self, regime_data: Dict) -> bool:
        """Check if regime is sideways (where both directions decay)."""
        return regime_data.get('regime') == 'NEUTRAL_SIDEWAYS'

    def _compute_quality_score(self, signal: LeveragedETFSignal,
                                etf_meta: Dict, avg_vol: float) -> float:
        """Quality = trend strength + liquidity + spread tightness."""
        score = 50.0
        # Trend strength (ADX)
        if signal.adx > 35:
            score += 20  # very strong trend
        elif signal.adx > 25:
            score += 12
        elif signal.adx > self.MIN_ADX_FOR_TREND:
            score += 5
        else:
            score -= 10  # no trend = bad for swing

        # Trend alignment with direction
        if signal.direction == 'LONG' and 'bullish' in signal.trend:
            score += 10
        elif signal.direction == 'LONG' and 'bearish' in signal.trend:
            score -= 20  # long ETF in bearish trend = wrong way
        elif signal.direction == 'SHORT' and 'bearish' in signal.trend:
            score += 10
        elif signal.direction == 'SHORT' and 'bullish' in signal.trend:
            score -= 20

        # RSI extremes (don't chase)
        if signal.direction == 'LONG':
            if signal.rsi > self.MAX_RSI_OVERBOUGHT_LONG:
                score -= 15  # overbought — wait for pullback
            elif 40 <= signal.rsi <= 65:
                score += 8  # sweet spot for swing longs
            elif signal.rsi < 30:
                score += 5  # oversold bounce potential
        else:  # SHORT
            if signal.rsi < 25:
                score -= 15  # oversold — short squeeze risk
            elif 40 <= signal.rsi <= 60:
                score += 5
            elif signal.rsi > 65:
                score += 8  # overbought — good short setup

        # Liquidity bonus
        if avg_vol > 5_000_000:
            score += 10
        elif avg_vol > 1_000_000:
            score += 5
        elif avg_vol < 200_000:
            score -= 15  # illiquid

        # Spread tightness (use ETF metadata)
        spread = etf_meta.get('typical_spread_bps', 10)
        if spread <= 3:
            score += 8
        elif spread <= 8:
            score += 4
        elif spread > 20:
            score -= 10  # wide spreads eat edge

        return round(max(0, min(100, score)), 1)

    def _compute_pattern_score(self, pattern: str) -> float:
        """Pattern detection — bonus for clean setups."""
        scores = {
            'vcp': 25, 'episodic_pivot': 25, 'bull_flag': 18, 'cup_handle': 20,
            'vcp_short': 25, 'episodic_pivot_short': 25, 'bear_flag_equivalent': 18,
            'cup_handle_short': 20, 'squeeze': 12, 'none': 0,
        }
        return scores.get(pattern, 0)

    def _compute_composite_score(self, signal: LeveragedETFSignal) -> float:
        """Final composite score with decay penalty.

        Weights:
        - Quality: 35%
        - Regime alignment: 35% (heaviest weight — regime is make-or-break for 2x ETFs)
        - Pattern: 20%
        - Decay penalty: -10% of score if HIGH decay
        """
        composite = (
            signal.quality_score * 0.35 +
            signal.regime_alignment_score * 0.35 +
            signal.pattern_score * 0.20 +
            50 * 0.10  # base
        )
        # Decay penalty
        if signal.decay_risk == 'HIGH':
            composite *= 0.85  # -15%
        elif signal.decay_risk == 'MEDIUM':
            composite *= 0.95  # -5%
        # LOW decay = no penalty
        return round(max(0, min(100, composite)), 1)

    def _recommend_hold_days(self, signal: LeveragedETFSignal) -> int:
        """Recommend holding period based on decay risk + trend strength.

        Higher decay = shorter hold. Stronger trend = can hold longer.
        Capped at 5-15 trading days for 2x ETFs.
        """
        base = 10
        # Decay adjustment
        if signal.decay_risk == 'HIGH':
            base -= 4
        elif signal.decay_risk == 'LOW':
            base += 3
        # Trend strength
        if signal.adx > 30:
            base += 2  # strong trend = hold longer
        elif signal.adx < 20:
            base -= 3  # weak trend = exit faster
        # Cap
        return max(self.MIN_HOLD_DAYS, min(self.MAX_HOLD_DAYS, base))

    def _check_catalyst_warnings(self) -> str:
        """Flag upcoming macro catalysts that 2x ETF holders should avoid.

        Checks for:
        - FOMC meetings (next 10 trading days)
        - CPI / PPI release dates
        - Major earnings (mag 7)
        Note: this is a simplified calendar — wire to FRED econ calendar for production.
        """
        today = datetime.now()
        warnings = []
        # Approximate FOMC dates (8 per year — would need real calendar)
        # For demo: warn if within 5 days of month-end (often FOMC adjacent)
        # In production, integrate with FRED or Econoday calendar
        if today.day >= 25:
            warnings.append('FOMC/meeting window approaching (verify on federalreserve.gov)')
        # CPI comes ~mid-month
        if 10 <= today.day <= 14:
            warnings.append('CPI release window (typically mid-month) — expect volatility')
        return ' | '.join(warnings)

    def _build_rationale(self, signal: LeveragedETFSignal, regime_data: Dict) -> str:
        """Human-readable explanation."""
        parts = []
        parts.append(f"Score {signal.composite_score:.0f}/100")
        parts.append(f"Regime: {regime_data.get('regime', '?')}")
        parts.append(f"Trend: {signal.trend}")
        if signal.pattern != 'none':
            parts.append(f"Pattern: {signal.pattern}")
        parts.append(f"ADX: {signal.adx}")
        parts.append(f"Decay: {signal.decay_risk} ({signal.estimated_daily_decay_pct:.3f}%/day)")
        parts.append(f"Hold: {signal.recommended_hold_days}d")
        if signal.catalyst_warning:
            parts.append(f"WARNING: {signal.catalyst_warning}")
        if not signal.regime_aligned:
            parts.append("REGIME MISALIGNED")
        return " | ".join(parts)

    # ── Convenience methods for the router ─────────────────────────────────

    def get_top_long_candidates(self, limit: int = 10) -> List[LeveragedETFSignal]:
        """Top 2x long ETF swing candidates (regime-permitting)."""
        return self.screen(direction_filter='LONG', min_score=60, limit=limit)

    def get_top_short_candidates(self, limit: int = 10) -> List[LeveragedETFSignal]:
        """Top 2x short ETF swing candidates (regime-permitting)."""
        return self.screen(direction_filter='SHORT', min_score=60, limit=limit)

    def get_universe_summary(self) -> Dict:
        """Summary stats for the leveraged ETF universe."""
        return {
            'total_etfs': len(LEVERAGED_ETF_UNIVERSE),
            'long_etfs': len([e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'LONG']),
            'short_etfs': len([e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'SHORT']),
            'by_asset_class': {
                ac: len([e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == ac])
                for ac in set(e['asset_class'] for e in LEVERAGED_ETF_UNIVERSE)
            },
        }
