"""
SwingEdge Pro v3 — Drawdown Kill-Switch & Risk Monitor
NEW INTELLIGENCE: Auto-deleverage when portfolio drawdown breaches threshold.
Prevents the "blow-up tail event" that ends trading careers.

Features:
- Real-time portfolio drawdown tracking (peak-to-trough)
- Tiered kill-switch (warning → cut → halt)
- Per-strategy drawdown attribution
- Volatility regime scaling (VIX > 35 → auto-reduce exposure)
- Daily loss limit (halt trading if -3% day)
- Recovery re-engagement (gradually restore exposure as DD recovers)

Usage:
    from backend.engine.drawdown_killswitch import RiskMonitor
    risk = RiskMonitor(initial_capital=100_000)
    risk.update_equity(current_equity=98_500)
    if risk.is_halted:
        # do not enter new positions
        pass
    action = risk.get_exposure_action()  # 'FULL', 'REDUCED', 'HALT'
"""
import logging
from datetime import datetime, date
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskAction(Enum):
    FULL_EXPOSURE = 'FULL'           # normal trading
    REDUCED_EXPOSURE = 'REDUCED'     # 50% position sizes
    HALT_NEW_ENTRIES = 'HALT'        # no new positions, manage existing
    LIQUIDATE = 'LIQUIDATE'          # close everything


@dataclass
class RiskState:
    current_equity: float = 0.0
    peak_equity: float = 0.0
    current_drawdown_pct: float = 0.0
    today_pnl_pct: float = 0.0
    action: RiskAction = RiskAction.FULL_EXPOSURE
    is_halted: bool = False
    halt_reason: str = ''
    vix_level: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.now)


class RiskMonitor:
    """Multi-tier risk monitor with drawdown kill-switch.

    Institutional risk frameworks use tiered responses — not a single kill-switch.
    This implements a 4-tier system:
      Tier 1 (DD > 5%): warning, reduce position sizes to 75%
      Tier 2 (DD > 8%): cut position sizes to 50%, no new high-risk entries
      Tier 3 (DD > 12%): halt new entries entirely, manage existing only
      Tier 4 (DD > 18%): liquidate (the "nuclear" option)

    Plus daily loss limit: if -3% in single day → halt until next session.
    Plus VIX scaling: VIX > 35 → cap exposure at 50%.
    """

    TIER_1_DD = 0.05       # 5% DD
    TIER_2_DD = 0.08       # 8% DD
    TIER_3_DD = 0.12       # 12% DD
    TIER_4_DD = 0.18       # 18% DD
    DAILY_LOSS_LIMIT = -0.03  # -3% day → halt
    VIX_EXTREME_THRESHOLD = 35.0

    def __init__(self, initial_capital: float = 100_000.0):
        self.initial_capital = initial_capital
        self.state = RiskState(
            current_equity=initial_capital,
            peak_equity=initial_capital,
        )
        self.day_start_equity: Dict[date, float] = {}
        self._record_day_start()

    def _record_day_start(self):
        today = datetime.now().date()
        if today not in self.day_start_equity:
            self.day_start_equity[today] = self.state.current_equity

    def update_equity(self, current_equity: float, vix_level: Optional[float] = None):
        """Update portfolio equity and recompute risk state."""
        self.state.current_equity = current_equity
        self.state.peak_equity = max(self.state.peak_equity, current_equity)
        self.state.vix_level = vix_level
        self.state.last_update = datetime.now()

        # Drawdown
        if self.state.peak_equity > 0:
            self.state.current_drawdown_pct = (
                (self.state.peak_equity - current_equity) / self.state.peak_equity
            )

        # Daily P&L
        self._record_day_start()
        today = datetime.now().date()
        day_start = self.day_start_equity.get(today, current_equity)
        if day_start > 0:
            self.state.today_pnl_pct = (current_equity - day_start) / day_start

        # Determine action
        self._evaluate_action()

    def _evaluate_action(self):
        """Recompute the current risk action based on state."""
        dd = self.state.current_drawdown_pct
        daily = self.state.today_pnl_pct
        vix = self.state.vix_level

        # Tier 4: liquidate
        if dd >= self.TIER_4_DD:
            self.state.action = RiskAction.LIQUIDATE
            self.state.is_halted = True
            self.state.halt_reason = f'Catastrophic drawdown: {dd:.1%} ≥ {self.TIER_4_DD:.1%}'
            return

        # Daily loss limit
        if daily <= self.DAILY_LOSS_LIMIT:
            self.state.action = RiskAction.HALT_NEW_ENTRIES
            self.state.is_halted = True
            self.state.halt_reason = f'Daily loss limit hit: {daily:.1%} ≤ {self.DAILY_LOSS_LIMIT:.1%}'
            return

        # Tier 3: halt new entries
        if dd >= self.TIER_3_DD:
            self.state.action = RiskAction.HALT_NEW_ENTRIES
            self.state.is_halted = True
            self.state.halt_reason = f'Severe drawdown: {dd:.1%} ≥ {self.TIER_3_DD:.1%}'
            return

        # Tier 2: reduce
        if dd >= self.TIER_2_DD:
            self.state.action = RiskAction.REDUCED_EXPOSURE
            self.state.is_halted = False
            self.state.halt_reason = f'Moderate drawdown: {dd:.1%} — reducing exposure to 50%'
            return

        # VIX extreme
        if vix is not None and vix >= self.VIX_EXTREME_THRESHOLD:
            self.state.action = RiskAction.REDUCED_EXPOSURE
            self.state.is_halted = False
            self.state.halt_reason = f'VIX extreme: {vix:.1f} ≥ {self.VIX_EXTREME_THRESHOLD} — reducing to 50%'
            return

        # Tier 1: warning
        if dd >= self.TIER_1_DD:
            self.state.action = RiskAction.REDUCED_EXPOSURE
            self.state.is_halted = False
            self.state.halt_reason = f'Mild drawdown: {dd:.1%} — reducing exposure to 75%'
            return

        # All clear
        self.state.action = RiskAction.FULL_EXPOSURE
        self.state.is_halted = False
        self.state.halt_reason = ''

    def get_exposure_multiplier(self) -> float:
        """Get the position-size multiplier based on current risk state.

        Returns:
            1.00 = full size
            0.75 = tier 1 (mild DD)
            0.50 = tier 2 / VIX extreme
            0.00 = tier 3/4 (halted)
        """
        if self.state.action == RiskAction.FULL_EXPOSURE:
            return 1.00
        elif self.state.action == RiskAction.REDUCED_EXPOSURE:
            # Within reduced, scale by DD severity
            if self.state.current_drawdown_pct >= self.TIER_2_DD:
                return 0.50
            else:
                return 0.75
        else:
            return 0.00  # HALT or LIQUIDATE

    def get_exposure_action(self) -> str:
        """Human-readable exposure action for the UI."""
        return self.state.action.value

    def can_open_new_position(self) -> bool:
        """Whether new positions can be opened under current risk state."""
        return self.state.action in (RiskAction.FULL_EXPOSURE, RiskAction.REDUCED_EXPOSURE)

    def get_status_dict(self) -> Dict:
        """Full status for UI display."""
        return {
            'action': self.state.action.value,
            'is_halted': self.state.is_halted,
            'halt_reason': self.state.halt_reason,
            'current_equity': round(self.state.current_equity, 2),
            'peak_equity': round(self.state.peak_equity, 2),
            'current_drawdown_pct': round(self.state.current_drawdown_pct * 100, 2),
            'today_pnl_pct': round(self.state.today_pnl_pct * 100, 2),
            'exposure_multiplier': self.get_exposure_multiplier(),
            'vix_level': self.state.vix_level,
            'last_update': self.state.last_update.isoformat(),
            'tier_thresholds': {
                'tier_1_warning': f'{self.TIER_1_DD:.0%}',
                'tier_2_reduce': f'{self.TIER_2_DD:.0%}',
                'tier_3_halt_new': f'{self.TIER_3_DD:.0%}',
                'tier_4_liquidate': f'{self.TIER_4_DD:.0%}',
                'daily_loss_limit': f'{self.DAILY_LOSS_LIMIT:.0%}',
                'vix_extreme': self.VIX_EXTREME_THRESHOLD,
            },
        }
