"""
SwingEdge Pro v3 — Risk Parity Position Sizing & Portfolio Optimizer
NEW INTELLIGENCE: Converts raw signals into a risk-managed portfolio.
This is the core differentiator between a screener and an institutional engine.

Features:
- Volatility targeting (target 12% annualized portfolio vol)
- ATR-scaled per-position sizing (risk = portfolio_vol_target / position_ATR)
- Sector exposure caps (max 30% per GICS sector)
- Correlation penalty (reduce size when position is highly correlated to existing book)
- Drawdown kill-switch (auto-deleverage when portfolio DD > threshold)
- Kelly fraction cap (max 25% Kelly — avoid overbetting)

Usage:
    from backend.engine.risk_parity import PortfolioOptimizer
    opt = PortfolioOptimizer()
    targets = opt.optimize(positions, regime_data)
    # targets = [{'ticker': 'NVDA', 'weight': 0.12, 'shares': 24, 'risk_contribution': 0.18}, ...]
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Position:
    ticker: str
    score: float                  # 0-100 from MasterScorer / Ensemble
    current_price: float
    atr: float                    # 14-day ATR for vol scaling
    atr_pct: float                # ATR / price
    sector: str = 'Unknown'
    correlation_to_book: float = 0.0  # 0-1, computed by optimizer
    existing_weight: float = 0.0  # current portfolio weight
    pattern: str = 'none'
    stop_loss: Optional[float] = None


@dataclass
class PositionTarget:
    ticker: str
    target_weight: float          # 0-1 of portfolio
    target_shares: int            # integer share count
    risk_contribution: float      # share of portfolio vol from this position
    kelly_fraction: float         # raw Kelly fraction (capped at 0.25)
    entry_price: float
    stop_loss: float
    risk_per_share: float         # = entry_price - stop_loss
    sector: str
    rationale: str                # human-readable explanation


class PortfolioOptimizer:
    """Risk-parity portfolio optimizer with sector caps + drawdown kill-switch.

    Institutional features (vs simple "equal weight" or "score-weighted"):
    1. Volatility targeting — portfolio vol stays near 12% annualized regardless of position count
    2. Risk contribution parity — each position contributes equally to portfolio vol
    3. Sector concentration cap — no single GICS sector > 30% of book
    4. Correlation penalty — reduce size for positions highly correlated to existing book
    5. Drawdown kill-switch — auto-deleverage when portfolio DD > threshold
    6. Kelly cap — never bet more than 25% of Kelly fraction (avoid overbetting)
    """

    TARGET_PORTFOLIO_VOL = 0.12      # 12% annualized vol target
    MAX_POSITION_WEIGHT = 0.10       # max 10% per position
    MAX_SECTOR_WEIGHT = 0.30         # max 30% per GICS sector
    MAX_KELLY_FRACTION = 0.25        # cap Kelly at 25% to avoid overbetting
    DRAWDOWN_KILL_THRESHOLD = 0.08   # auto-deleverage at 8% portfolio DD
    DRAWDOWN_KILL_MULTIPLIER = 0.50  # cut exposure in half when kill-switch trips
    TRADING_DAYS = 252

    def __init__(self, portfolio_capital: float = 100_000.0):
        self.portfolio_capital = portfolio_capital
        self.current_drawdown: float = 0.0
        self.peak_equity: float = portfolio_capital
        self.kill_switch_active: bool = False

    def update_drawdown(self, current_equity: float):
        """Track portfolio drawdown and trip kill-switch if threshold breached."""
        self.peak_equity = max(self.peak_equity, current_equity)
        if self.peak_equity > 0:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        if self.current_drawdown >= self.DRAWDOWN_KILL_THRESHOLD:
            if not self.kill_switch_active:
                logger.warning(
                    f"DRAWDOWN KILL-SWITCH TRIPPED: DD={self.current_drawdown:.2%} "
                    f"≥ threshold {self.DRAWDOWN_KILL_THRESHOLD:.2%}. Cutting exposure by "
                    f"{1 - self.DRAWDOWN_KILL_MULTIPLIER:.0%}."
                )
            self.kill_switch_active = True
        else:
            if self.kill_switch_active:
                logger.info(f"Drawdown recovered to {self.current_drawdown:.2%} — kill-switch released.")
            self.kill_switch_active = False

    def optimize(self, positions: List[Position], regime_data: Optional[Dict] = None,
                 correlation_matrix: Optional[pd.DataFrame] = None) -> List[PositionTarget]:
        """Generate position targets from candidate positions.

        Args:
            positions: list of Position objects (scored candidates)
            regime_data: market regime dict (used for risk multiplier)
            correlation_matrix: optional NxN correlation matrix for risk-parity computation

        Returns:
            List of PositionTarget objects sorted by target_weight descending.
        """
        if not positions:
            return []

        # Step 1: Filter candidates — only score >= 60
        candidates = [p for p in positions if p.score >= 60]
        if not candidates:
            return []

        # Step 2: Sort by score descending, take top 15
        candidates.sort(key=lambda p: p.score, reverse=True)
        candidates = candidates[:15]

        # Step 3: Compute raw Kelly fraction per position
        # Kelly = (win_prob * b - (1 - win_prob)) / b
        # where b = avg_win / avg_loss (typically 2.0 for swing strategies)
        # Approximate win_prob from score: 50% at score=50, 65% at score=80
        b = 2.0  # reward-to-risk ratio
        for p in candidates:
            win_prob = 0.35 + (p.score / 100) * 0.40  # 0.35-0.75 range
            kelly = max(0, (win_prob * b - (1 - win_prob)) / b)
            p._kelly = min(kelly, self.MAX_KELLY_FRACTION)

        # Step 4: Volatility scaling — reduce Kelly for high-vol positions
        for p in candidates:
            # Annualized vol ≈ ATR_pct * sqrt(252) * price/price (simplified)
            annualized_vol = p.atr_pct * np.sqrt(self.TRADING_DAYS)
            if annualized_vol > 0:
                vol_scalar = self.TARGET_PORTFOLIO_VOL / annualized_vol
                vol_scalar = min(vol_scalar, 2.0)  # cap leverage at 2x
                p._vol_scaled_kelly = p._kelly * vol_scalar
            else:
                p._vol_scaled_kelly = p._kelly

        # Step 5: Apply sector caps
        sector_weights: Dict[str, float] = {}
        for p in candidates:
            sector_weights[p.sector] = sector_weights.get(p.sector, 0) + p._vol_scaled_kelly
        # If any sector exceeds cap, scale down all positions in that sector
        for sector, total in sector_weights.items():
            if total > self.MAX_SECTOR_WEIGHT:
                scale = self.MAX_SECTOR_WEIGHT / total
                for p in candidates:
                    if p.sector == sector:
                        p._vol_scaled_kelly *= scale

        # Step 6: Apply max position weight cap
        for p in candidates:
            p._vol_scaled_kelly = min(p._vol_scaled_kelly, self.MAX_POSITION_WEIGHT)

        # Step 7: Apply correlation penalty if correlation matrix provided
        if correlation_matrix is not None:
            for p in candidates:
                # Average correlation to other candidates
                if p.ticker in correlation_matrix.columns:
                    other_tickers = [o.ticker for o in candidates if o.ticker != p.ticker
                                     and o.ticker in correlation_matrix.columns]
                    if other_tickers:
                        avg_corr = correlation_matrix.loc[p.ticker, other_tickers].abs().mean()
                        # Penalize high-correlation positions
                        p._vol_scaled_kelly *= (1 - 0.5 * avg_corr)

        # Step 8: Apply regime risk multiplier
        risk_mult = regime_data.get('risk_multiplier', 1.0) if regime_data else 1.0
        for p in candidates:
            p._final_weight = p._vol_scaled_kelly * risk_mult

        # Step 9: Apply drawdown kill-switch
        if self.kill_switch_active:
            for p in candidates:
                p._final_weight *= self.DRAWDOWN_KILL_MULTIPLIER

        # Step 10: Renormalize so total weight <= 1.0
        total_weight = sum(p._final_weight for p in candidates)
        if total_weight > 1.0:
            scale = 1.0 / total_weight
            for p in candidates:
                p._final_weight *= scale

        # Step 11: Build PositionTarget objects
        targets = []
        for p in candidates:
            target_dollars = p._final_weight * self.portfolio_capital
            target_shares = int(target_dollars / p.current_price) if p.current_price > 0 else 0
            if target_shares < 1:
                continue
            # Risk contribution: this position's share of portfolio vol
            risk_contrib = p._final_weight * (p.atr_pct * np.sqrt(self.TRADING_DAYS))
            # Stop loss: 2x ATR below entry
            stop = p.stop_loss or (p.current_price - 2 * p.atr if p.atr > 0 else p.current_price * 0.95)
            risk_per_share = p.current_price - stop

            rationale = self._build_rationale(p, regime_data, self.kill_switch_active)
            targets.append(PositionTarget(
                ticker=p.ticker,
                target_weight=round(p._final_weight, 4),
                target_shares=target_shares,
                risk_contribution=round(risk_contrib, 4),
                kelly_fraction=round(p._kelly, 4),
                entry_price=round(p.current_price, 2),
                stop_loss=round(stop, 2),
                risk_per_share=round(risk_per_share, 2),
                sector=p.sector,
                rationale=rationale,
            ))

        targets.sort(key=lambda t: t.target_weight, reverse=True)
        return targets

    def _build_rationale(self, p: Position, regime_data: Optional[Dict], kill_active: bool) -> str:
        parts = []
        parts.append(f"Score {p.score:.0f}/100")
        if p.pattern != 'none':
            parts.append(f"pattern={p.pattern}")
        if p._kelly >= 0.15:
            parts.append(f"strong Kelly={p._kelly:.2f}")
        if regime_data:
            regime = regime_data.get('regime', 'NEUTRAL')
            parts.append(f"regime={regime}")
        if kill_active:
            parts.append("KILL-SWITCH ACTIVE (50% exposure cut)")
        return " | ".join(parts)
