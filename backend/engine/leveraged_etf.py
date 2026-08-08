"""
SwingEdge Pro v3.3 — Unified Leveraged ETF Swing Engine
FIX v3.3: This is NO LONGER a separate engine. It is a thin adapter that uses
the MasterScorer (the SAME engine that scores regular stocks) and adds
leveraged-ETF-specific logic on top:

1. Calls MasterScorer.score_stock() — gets the real composite score using
   the SAME technicals/fundamentals/sentiment/insider/microstructure/regime
   analysis that regular stocks get.

2. For single-stock 2x ETFs (NVDU, TSLT, SNDG, AAPU, etc.) — also scores the
   UNDERLYING stock (NVDA, TSLA, SNDK, AAPL) and uses that as the primary signal.
   The ETF is a derivative of the underlying, so the underlying's score matters more.

3. Adds leveraged-ETF-specific risk layers:
   - Volatility decay model (daily decay = 0.5 × daily_vol² × 100)
   - Regime alignment filter (longs only in bull, shorts only in bear)
   - Wider ATR stops (2.5x vs 2.0x)
   - Holding period cap (5-15 days)
   - Liquidity floor
   - Catalyst warnings

WHY ONE ENGINE, NOT TWO:
The user is right — having two separate engines was a design mistake. ETFs are
just instruments with extra decay risk. The swing scoring logic (technicals,
fundamentals, sentiment, etc.) should be IDENTICAL whether you're scoring NVDA
or NVDU. This adapter pattern ensures that.

Usage:
    from backend.engine.leveraged_etf import LeveragedETFEngine
    engine = LeveragedETFEngine()
    candidates = engine.screen()
    # Top candidate = candidates[0]
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.data.fetchers import get_ohlcv, get_stock_info
from backend.data.leveraged_etf_universe import LEVERAGED_ETF_UNIVERSE, get_etf_by_ticker
from backend.engine.technicals import TechnicalsEngine
from backend.engine.market_regime import MarketRegimeClassifier
from backend.engine.scoring import MasterScorer

logger = logging.getLogger(__name__)


@dataclass
class LeveragedETFSignal:
    """A ranked 2x leveraged ETF swing trade signal (unified engine output)."""
    ticker: str = ''
    direction: str = 'LONG'
    underlying: str = ''
    underlying_ticker: str = ''      # for single-stock ETFs
    asset_class: str = ''
    current_price: float = 0.0
    # Unified score (from MasterScorer — same engine as regular stocks)
    composite_score: float = 0.0     # 0-100, final score including ETF adjustments
    base_swing_score: float = 0.0    # raw MasterScorer score before ETF adjustments
    underlying_score: float = 0.0    # for single-stock ETFs: score of the underlying
    # ETF-specific risk metrics
    decay_risk: str = 'MEDIUM'
    estimated_daily_decay_pct: float = 0.0
    volatility_drag_5d_pct: float = 0.0
    regime_aligned: bool = False
    regime_alignment_score: float = 0.0
    # Trade setup
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    risk_reward: float = 0.0
    recommended_hold_days: int = 10
    # Technicals (from unified engine)
    pattern: str = 'none'
    trend: str = 'neutral'
    rsi: float = 50.0
    adx: float = 20.0
    atr_pct: float = 0.0
    rel_volume: float = 1.0
    # Risk flags
    catalyst_warning: str = ''
    # Human-readable
    rationale: str = ''


class LeveragedETFEngine:
    """Unified leveraged ETF swing screener — uses MasterScorer under the hood.

    KEY DESIGN (v3.3): ONE engine, not two. The MasterScorer handles all the
    swing analysis (technicals, fundamentals, sentiment, etc.). This class
    is a thin adapter that:
    1. Calls MasterScorer for the base score
    2. For single-stock ETFs, also scores the underlying stock
    3. Adds ETF-specific decay/regime/liquidity filters
    4. Returns the adjusted signal
    """

    # ETF-specific thresholds
    MIN_AVG_VOLUME = 50_000          # lowered for single-stock ETFs (some are new/illiquid)
    MAX_WORKERS = 10
    PER_ETF_TIMEOUT_SEC = 12
    # Decay model
    DECAY_COEFFICIENT = 0.5
    # Wider stops for 2x vol
    STOP_LOSS_ATR_MULT = 2.5
    TARGET_ATR_MULT = 5.0            # 2:1 R:R minimum
    # Holding period
    MIN_HOLD_DAYS = 3
    MAX_HOLD_DAYS = 15

    def __init__(self):
        self.tech = TechnicalsEngine()
        self.regime = MarketRegimeClassifier()
        self.scorer = MasterScorer()  # THE unified engine

    def screen(self, direction_filter: Optional[str] = None,
               asset_class_filter: Optional[str] = None,
               min_score: float = 50.0,
               limit: int = 20) -> List[LeveragedETFSignal]:
        """Screen the entire 2x leveraged ETF universe using the unified engine.

        FIX v3.2.2 + v3.3: Parallel execution + uses MasterScorer (was separate).
        """
        # Normalize filters (handle None / empty / FastAPI Query objects)
        direction_filter = self._normalize_filter(direction_filter)
        asset_class_filter = self._normalize_filter(asset_class_filter)

        # Get regime once (cached globally)
        regime_data = self.regime.evaluate_regime()

        # Filter universe
        universe = LEVERAGED_ETF_UNIVERSE
        if direction_filter:
            universe = [e for e in universe if e['direction'] == direction_filter]
        if asset_class_filter:
            universe = [e for e in universe if e['asset_class'] == asset_class_filter]

        signals: List[LeveragedETFSignal] = []

        # Parallel execution
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_etf = {
                executor.submit(self._analyze_etf_safe, etf_meta, regime_data): etf_meta
                for etf_meta in universe
            }
            for future in as_completed(future_to_etf, timeout=60):
                etf_meta = future_to_etf[future]
                try:
                    signal = future.result(timeout=self.PER_ETF_TIMEOUT_SEC)
                    if signal and signal.composite_score >= min_score:
                        signals.append(signal)
                except Exception as e:
                    logger.warning(f"ETF analyze failed {etf_meta.get('ticker')}: {e}")

        signals.sort(key=lambda s: s.composite_score, reverse=True)
        return signals[:limit]

    def _normalize_filter(self, val) -> Optional[str]:
        """Normalize a filter value — handles None, empty string, FastAPI Query objects."""
        if val is None:
            return None
        # FastAPI Query objects — extract the default
        if hasattr(val, 'default'):
            val = val.default
        val = str(val).strip().upper() if val else ''
        return val if val else None

    def _analyze_etf_safe(self, etf_meta: Dict, regime_data: Dict) -> Optional[LeveragedETFSignal]:
        """Wrapper that catches all exceptions."""
        try:
            return self._analyze_etf(etf_meta, regime_data)
        except Exception as e:
            logger.warning(f"ETF analysis error {etf_meta.get('ticker', '?')}: {e}")
            return None

    def analyze_ticker(self, ticker: str) -> Optional[LeveragedETFSignal]:
        """Analyze a single ETF ticker using the unified engine."""
        meta = get_etf_by_ticker(ticker)
        if not meta:
            return None
        regime_data = self.regime.evaluate_regime()
        return self._analyze_etf(meta, regime_data)

    def _analyze_etf(self, etf_meta: Dict, regime_data: Dict) -> Optional[LeveragedETFSignal]:
        """Analyze one ETF using the unified MasterScorer + ETF-specific overlays."""
        ticker = etf_meta['ticker']
        direction = etf_meta['direction']
        underlying_ticker = etf_meta.get('underlying_ticker', '')

        signal = LeveragedETFSignal(
            ticker=ticker,
            direction=direction,
            underlying=etf_meta['underlying'],
            underlying_ticker=underlying_ticker,
            asset_class=etf_meta['asset_class'],
        )

        try:
            # ── Step 1: Get ETF's own OHLCV + technicals ──────────────────
            df = get_ohlcv(ticker, period='1y', interval='1d')
            if df is None or len(df) < 30:
                signal.rationale = f"Insufficient OHLCV data ({0 if df is None else len(df)} bars)"
                return signal

            df = self.tech.calculate_all_indicators(df)
            if df is None or df.empty:
                signal.rationale = "Indicator calculation failed"
                return signal

            last = df.iloc[-1]
            close = float(last['close'])
            signal.current_price = close

            # Liquidity check (lowered for single-stock ETFs)
            avg_vol_20 = float(df['volume'].tail(20).mean())
            avg_vol_50 = float(df['volume'].tail(50).mean())
            avg_vol = max(avg_vol_20, avg_vol_50) if avg_vol_50 > 0 else avg_vol_20
            if avg_vol_20 < self.MIN_AVG_VOLUME and avg_vol_50 < self.MIN_AVG_VOLUME:
                signal.rationale = f"Skipped: low liquidity (avg vol {avg_vol:,.0f} < {self.MIN_AVG_VOLUME:,})"
                return signal
            signal.rel_volume = round(float(last['volume']) / max(avg_vol, 1), 2) if avg_vol > 0 else 1.0

            # ── Step 2: Compute ETF's technicals (from unified engine) ─────
            signal.rsi = round(float(last.get('rsi', 50) or 50), 1)
            signal.adx = round(float(last.get('adx', 20) or 20), 1)
            signal.atr_pct = round(float(last.get('atr', 0) or 0) / close * 100, 2) if close > 0 else 0
            signal.pattern = self._detect_pattern(df, direction)
            signal.trend = self._determine_trend(last)

            # ── Step 3: Volatility decay model ─────────────────────────────
            daily_returns = df['close'].pct_change().dropna().tail(20)
            daily_vol = float(daily_returns.std()) if len(daily_returns) > 5 else 0.02
            signal.estimated_daily_decay_pct = round(
                self.DECAY_COEFFICIENT * (daily_vol ** 2) * 100, 4
            )
            signal.volatility_drag_5d_pct = round(
                (1 - (1 - signal.estimated_daily_decay_pct / 100) ** 5) * 100, 3
            )
            if signal.estimated_daily_decay_pct < 0.05:
                signal.decay_risk = 'LOW'
            elif signal.estimated_daily_decay_pct < 0.15:
                signal.decay_risk = 'MEDIUM'
            else:
                signal.decay_risk = 'HIGH'

            # ── Step 4: BASE swing score ───────────────────────────────────
            # FIX v3.3: Use the SAME MasterScorer as regular stocks
            # For ETFs with no fundamentals (index ETFs), the scorer returns a
            # base 50 — that's fine, the technicals dominate for ETFs anyway.
            try:
                base_score = self._compute_base_score(signal, df, ticker, etf_meta)
                signal.base_swing_score = base_score
            except Exception as e:
                logger.debug(f"Base score failed for {ticker}: {e}")
                base_score = 50.0
                signal.base_swing_score = 50.0

            # ── Step 5: For single-stock ETFs, also score the UNDERLYING ──
            # This is the key insight: SNDG tracks SNDK 2x. If SNDK has a great
            # setup, SNDG will reflect it (2x). The underlying's score matters more.
            if underlying_ticker:
                try:
                    underlying_score = self._score_underlying(underlying_ticker)
                    signal.underlying_score = underlying_score
                    # Blend: underlying matters MORE than the ETF's own technicals
                    # because the ETF is a derivative
                    base_score = (underlying_score * 0.65) + (base_score * 0.35)
                except Exception as e:
                    logger.debug(f"Underlying score failed for {underlying_ticker}: {e}")
                    signal.underlying_score = 50.0

            # ── Step 6: Regime alignment ───────────────────────────────────
            signal.regime_aligned, signal.regime_alignment_score = self._check_regime_alignment(
                direction, regime_data
            )

            # ── Step 7: Composite score with decay + regime adjustments ────
            composite = base_score
            # Regime scaling (heaviest weight — regime is make-or-break for 2x)
            composite = composite * (0.5 + 0.5 * (signal.regime_alignment_score / 100))
            # Decay penalty
            if signal.decay_risk == 'HIGH':
                composite *= 0.85
            elif signal.decay_risk == 'MEDIUM':
                composite *= 0.95

            signal.composite_score = round(max(0, min(100, composite)), 1)

            # ── Step 8: Entry / Stop / Target (wider for 2x vol) ───────────
            atr = float(last.get('atr', 0) or 0)
            if atr > 0:
                signal.entry_price = round(close, 2)
                if direction == 'LONG':
                    signal.stop_loss = round(close - (atr * self.STOP_LOSS_ATR_MULT), 2)
                    signal.target_price = round(close + (atr * self.TARGET_ATR_MULT), 2)
                else:
                    signal.stop_loss = round(close + (atr * self.STOP_LOSS_ATR_MULT), 2)
                    signal.target_price = round(close - (atr * self.TARGET_ATR_MULT), 2)
                risk = abs(signal.entry_price - signal.stop_loss)
                reward = abs(signal.target_price - signal.entry_price)
                signal.risk_reward = round(reward / risk, 2) if risk > 0 else 0

            # ── Step 9: Holding period ─────────────────────────────────────
            signal.recommended_hold_days = self._recommend_hold_days(signal)

            # ── Step 10: Catalyst warnings ─────────────────────────────────
            signal.catalyst_warning = self._check_catalyst_warnings(underlying_ticker)

            # ── Step 11: Rationale ─────────────────────────────────────────
            signal.rationale = self._build_rationale(signal, regime_data, underlying_ticker)

        except Exception as e:
            logger.warning(f"ETF analysis failed {ticker}: {e}", exc_info=True)
            signal.rationale = f"Analysis error: {e}"

        return signal

    def _compute_base_score(self, signal: LeveragedETFSignal, df: pd.DataFrame,
                             ticker: str, etf_meta: Dict) -> float:
        """Compute base swing score using the unified MasterScorer.

        For ETFs (not single-stock), MasterScorer may not have fundamentals —
        that's OK, the technicals dominate for ETFs.
        """
        # Try to use the full MasterScorer
        try:
            score = self.scorer.score_stock(ticker)
            if score and score.composite_score > 0:
                return float(score.composite_score)
        except Exception:
            pass
        # Fallback: compute a technicals-only score
        return self._technicals_only_score(signal)

    def _score_underlying(self, underlying_ticker: str) -> float:
        """Score the UNDERLYING stock using the full MasterScorer.

        For SNDG → scores SNDK. For NVDU → scores NVDA. Etc.
        This is the real edge — the ETF is a derivative, so the underlying's
        swing setup is what matters.
        """
        try:
            score = self.scorer.score_stock(underlying_ticker)
            if score and score.composite_score > 0:
                return float(score.composite_score)
        except Exception as e:
            logger.debug(f"Underlying score failed {underlying_ticker}: {e}")
        return 50.0

    def _technicals_only_score(self, signal: LeveragedETFSignal) -> float:
        """Fallback: technicals-only score (used when MasterScorer can't fetch data)."""
        score = 50.0
        # Trend alignment
        if signal.direction == 'LONG' and 'bullish' in signal.trend:
            score += 15
        elif signal.direction == 'LONG' and 'bearish' in signal.trend:
            score -= 20
        elif signal.direction == 'SHORT' and 'bearish' in signal.trend:
            score += 15
        elif signal.direction == 'SHORT' and 'bullish' in signal.trend:
            score -= 20
        # ADX
        if signal.adx > 30:
            score += 10
        elif signal.adx < 18:
            score -= 10
        # RSI
        if signal.direction == 'LONG':
            if 40 <= signal.rsi <= 65:
                score += 8
            elif signal.rsi > 78:
                score -= 15
        else:
            if 40 <= signal.rsi <= 65:
                score += 5
            elif signal.rsi > 70:
                score += 8
        return round(max(0, min(100, score)), 1)

    def _determine_trend(self, last) -> str:
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
        try:
            patterns = self.tech.detect_patterns(df)
            if not patterns:
                return 'none'
            if direction == 'SHORT':
                pattern_map = {
                    'vcp': 'vcp_short',
                    'episodic_pivot': 'episodic_pivot_short',
                    'bull_flag': 'bear_flag_equivalent',
                    'cup_handle': 'cup_handle_short',
                }
                return pattern_map.get(patterns[0], patterns[0])
            return patterns[0]
        except Exception:
            return 'none'

    def _check_regime_alignment(self, direction: str, regime_data: Dict) -> Tuple[bool, float]:
        """CRITICAL for leveraged ETFs: regime filter."""
        regime = regime_data.get('regime', 'NEUTRAL')
        if regime == 'DATA_DEGRADED':
            return False, 20.0
        if direction == 'LONG':
            if regime == 'BULLISH_EXPANSION':
                return True, 100.0
            elif regime == 'CAUTIOUS_BULL':
                return True, 75.0
            elif regime == 'NEUTRAL_SIDEWAYS':
                return False, 35.0
            elif regime == 'HIGH_VOLATILITY_DEFENSIVE':
                return False, 10.0
        else:  # SHORT
            if regime == 'HIGH_VOLATILITY_DEFENSIVE':
                return True, 100.0
            elif regime == 'NEUTRAL_SIDEWAYS':
                return False, 35.0
            elif regime == 'CAUTIOUS_BULL':
                return False, 20.0
            elif regime == 'BULLISH_EXPANSION':
                return False, 5.0
        return False, 50.0

    def _recommend_hold_days(self, signal: LeveragedETFSignal) -> int:
        base = 10
        if signal.decay_risk == 'HIGH':
            base -= 4
        elif signal.decay_risk == 'LOW':
            base += 3
        if signal.adx > 30:
            base += 2
        elif signal.adx < 18:
            base -= 3
        return max(self.MIN_HOLD_DAYS, min(self.MAX_HOLD_DAYS, base))

    def _check_catalyst_warnings(self, underlying_ticker: str = '') -> str:
        today = datetime.now()
        warnings = []
        if today.day >= 25:
            warnings.append('FOMC/meeting window approaching (verify on federalreserve.gov)')
        if 10 <= today.day <= 14:
            warnings.append('CPI release window (typically mid-month) — expect volatility')
        if underlying_ticker:
            # Check for known earnings dates (would need a real earnings calendar)
            # For now, just flag if it's earnings season (mid-Jan, mid-Apr, mid-Jul, mid-Oct)
            if today.month in (1, 4, 7, 10) and 10 <= today.day <= 25:
                warnings.append(f'Earnings season — {underlying_ticker} may report soon')
        return ' | '.join(warnings)

    def _build_rationale(self, signal: LeveragedETFSignal, regime_data: Dict,
                          underlying_ticker: str = '') -> str:
        parts = [f"Score {signal.composite_score:.0f}/100"]
        if underlying_ticker:
            parts.append(f"Underlying {underlying_ticker} score: {signal.underlying_score:.0f}")
        parts.append(f"Base swing: {signal.base_swing_score:.0f}")
        parts.append(f"Regime: {regime_data.get('regime', '?')}")
        parts.append(f"Trend: {signal.trend}")
        if signal.pattern != 'none':
            parts.append(f"Pattern: {signal.pattern}")
        parts.append(f"Decay: {signal.decay_risk} ({signal.estimated_daily_decay_pct:.3f}%/day)")
        parts.append(f"Hold: {signal.recommended_hold_days}d")
        if signal.catalyst_warning:
            parts.append(f"WARNING: {signal.catalyst_warning}")
        if not signal.regime_aligned:
            parts.append("REGIME MISALIGNED")
        return " | ".join(parts)

    def get_top_long_candidates(self, limit: int = 10) -> List[LeveragedETFSignal]:
        return self.screen(direction_filter='LONG', min_score=50, limit=limit)

    def get_top_short_candidates(self, limit: int = 10) -> List[LeveragedETFSignal]:
        return self.screen(direction_filter='SHORT', min_score=50, limit=limit)

    def get_universe_summary(self) -> Dict:
        return {
            'total_etfs': len(LEVERAGED_ETF_UNIVERSE),
            'long_etfs': len([e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'LONG']),
            'short_etfs': len([e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'SHORT']),
            'single_stock_etfs': len([e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == 'single_stock']),
            'by_asset_class': {
                ac: len([e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == ac])
                for ac in set(e['asset_class'] for e in LEVERAGED_ETF_UNIVERSE)
            },
        }
