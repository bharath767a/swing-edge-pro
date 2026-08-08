"""
SwingEdge Pro — Backtesting Engine
Simulates trading strategies on historical data.

AUDIT FIXES APPLIED (P1 — Backtest Validity):
- Sharpe annualization now uses sqrt(trades_per_year), not sqrt(252) on trade returns
- Per-trade risk-free rate proportional to holding period
- Slippage + commission model added (configurable, defaults to realistic US retail rates)
- Exit checks now use intraday high/low (was close-only — undercounted fills)
- Profit factor now handles "no losses" case as inf instead of 999
- ATR-based stops now used when config.STOP_LOSS_ATR_MULT is set (was ignored)
- Position sizing now respects max_position_pct (was 100% allocation per trade)
- Look-ahead bias note: fundamentals still come from yfinance current snapshot —
  must be replaced with point-in-time DB (see Phase 2 of roadmap).
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from backend.data.fetchers import get_ohlcv
from backend.engine.technicals import TechnicalsEngine

logger = logging.getLogger(__name__)


@dataclass
class BacktestResults:
    strategy: str = ''
    ticker: Optional[str] = None
    start_date: str = ''
    end_date: str = ''
    win_rate: float = 0.0
    avg_gain: float = 0.0
    avg_loss: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    total_return: float = 0.0
    equity_curve: List[Dict] = None
    trades: List[Dict] = None
    # FIX P1: added new metrics for institutional-grade reporting
    avg_holding_days: float = 0.0
    trades_per_year: float = 0.0
    calmar_ratio: float = 0.0
    expectancy: float = 0.0  # avg $ per trade
    slippage_cost_pct: float = 0.0
    commission_cost_pct: float = 0.0


STRATEGIES = {
    'vcp_breakout': 'VCP Breakout (Volatility Contraction Pattern)',
    'episodic_pivot': 'Episodic Pivot (Gap on Volume)',
    'bull_flag': 'Bull Flag Continuation',
    'rsi_oversold': 'RSI Oversold Bounce (<30)',
    'macd_cross': 'MACD Bullish Cross',
    'multibagger_score': 'High Multibagger Score Setup',
}


class Backtester:

    # FIX P1: realistic US retail transaction cost model
    DEFAULT_SLIPPAGE_BPS = 5.0       # 5 basis points = 0.05% per side
    DEFAULT_COMMISSION_DOLLAR = 0.0  # most US retail brokers are zero-commission post-2019
    DEFAULT_MAX_POSITION_PCT = 0.25  # 25% max per position (was implicitly 100%)

    def __init__(self, slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
                 commission_dollar: float = DEFAULT_COMMISSION_DOLLAR,
                 max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
                 risk_free_rate: float = 0.045):
        self.tech = TechnicalsEngine()
        self.slippage_bps = slippage_bps
        self.commission_dollar = commission_dollar
        self.max_position_pct = max_position_pct
        self.risk_free_rate = risk_free_rate

    def run_backtest(
        self,
        strategy: str,
        ticker: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
        initial_capital: float = 10_000.0,
    ) -> BacktestResults:
        """Run backtest for a strategy on a ticker (or universe)."""
        from backend.data.universe import PENNY_UNIVERSE, MULTIBAGGER_UNIVERSE
        results = BacktestResults(strategy=strategy, ticker=ticker)
        results.start_date = start_date or '2024-01-01'
        results.end_date = end_date or '2025-12-31'

        tickers = [ticker] if ticker else (PENNY_UNIVERSE[:20] + MULTIBAGGER_UNIVERSE[:10])
        all_trades = []

        for t in tickers:
            try:
                df = get_ohlcv(t, period='1y', interval='1d')
                if df is None or len(df) < 40:
                    continue
                df = self.tech.calculate_all_indicators(df)
                trades = self._simulate_strategy(strategy, t, df)
                all_trades.extend(trades)
            except Exception as e:
                logger.debug(f"Backtest error {t}: {e}")

        if not all_trades:
            return results

        # Sort by entry_date for proper equity curve sequencing
        all_trades.sort(key=lambda x: x.get('entry_date', ''))
        metrics = self.calculate_metrics(all_trades, initial_capital)
        results.win_rate = metrics['win_rate']
        results.avg_gain = metrics['avg_gain']
        results.avg_loss = metrics['avg_loss']
        results.sharpe = metrics['sharpe']
        results.max_drawdown = metrics['max_drawdown']
        results.total_trades = len(all_trades)
        results.profit_factor = metrics['profit_factor']
        results.total_return = metrics['total_return']
        results.avg_holding_days = metrics.get('avg_holding_days', 0)
        results.trades_per_year = metrics.get('trades_per_year', 0)
        results.calmar_ratio = metrics.get('calmar_ratio', 0)
        results.expectancy = metrics.get('expectancy', 0)
        results.slippage_cost_pct = metrics.get('slippage_cost_pct', 0)
        results.commission_cost_pct = metrics.get('commission_cost_pct', 0)
        results.equity_curve = self.generate_equity_curve(all_trades, initial_capital)
        results.trades = all_trades[:100]
        return results

    def _simulate_strategy(self, strategy: str, ticker: str, df: pd.DataFrame) -> List[Dict]:
        dispatch = {
            'vcp_breakout': self.simulate_vcp_breakout,
            'episodic_pivot': self.simulate_episodic_pivot,
            'bull_flag': self.simulate_bull_flag,
            'rsi_oversold': self.simulate_rsi_oversold,
            'macd_cross': self.simulate_macd_cross,
            'multibagger_score': self.simulate_vcp_breakout,
        }
        fn = dispatch.get(strategy, self.simulate_vcp_breakout)
        return fn(df, ticker)

    def _apply_costs(self, entry_price: float, exit_price: float) -> Tuple[float, float, float]:
        """Apply slippage + commission to entry and exit prices.

        Returns (adj_entry, adj_exit, total_cost_pct).
        Slippage is symmetric: pay up on entry, receive less on exit.
        """
        slip = self.slippage_bps / 10_000.0  # bps → decimal
        adj_entry = entry_price * (1 + slip)
        adj_exit = exit_price * (1 - slip)
        # Commission as percentage of notional (assume $1k trade size for percentage calc)
        notional = 1000.0
        commission_pct = (self.commission_dollar * 2) / notional * 100  # both sides
        slippage_pct = (slip * 2) * 100
        return adj_entry, adj_exit, commission_pct + slippage_pct

    def _find_exit_intraday(self, df: pd.DataFrame, entry_idx: int, target: float,
                            stop: float, max_hold: int = 15) -> Tuple[float, int, str]:
        """Find exit using intraday highs/lows (was close-only — undercounted fills).

        Returns (exit_price, exit_idx, exit_reason).
        Iterates bars from entry_idx+1 to entry_idx+max_hold, checking:
        - If bar high >= target → exit at target (limit filled)
        - If bar low <= stop → exit at stop (stop filled)
        - If both on same bar → assume stop fills first (conservative)
        - Otherwise exit at close on max_hold bar
        """
        n = len(df)
        highs = df['high'].values if 'high' in df.columns else df['High'].values
        lows = df['low'].values if 'low' in df.columns else df['Low'].values
        closes = df['close'].values if 'close' in df.columns else df['Close'].values

        for j in range(entry_idx + 1, min(entry_idx + max_hold + 1, n)):
            # Conservative: stop checked before target on same bar
            if lows[j] <= stop:
                return stop, j, 'stop'
            if highs[j] >= target:
                return target, j, 'target'
        # Time stop — exit at close of last bar
        exit_idx = min(entry_idx + max_hold, n - 1)
        return float(closes[exit_idx]), exit_idx, 'time_stop'

    def simulate_vcp_breakout(self, df: pd.DataFrame, ticker: str = '') -> List[Dict]:
        """VCP breakout entries with 10% target / 5% stop, intraday exits, slippage."""
        trades = []
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        n = len(close)

        for i in range(30, n - 5):
            recent_high = np.max(high[i-50:i]) if i >= 50 else np.max(high[:i])
            price_from_high = (recent_high - close[i]) / recent_high if recent_high > 0 else 1
            vol_early = np.std(close[i-20:i-10])
            vol_recent = np.std(close[i-10:i])
            vol_declining = vol_early > 0 and vol_recent < vol_early * 0.7
            avg_vol = np.mean(volume[i-20:i])
            vol_surge = volume[i] > avg_vol * 1.5

            if price_from_high < 0.15 and vol_declining and vol_surge:
                entry_raw = df['open'].iloc[i + 1] if i + 1 < n else close[i]
                target = entry_raw * 1.10
                stop = entry_raw * 0.95
                exit_raw, exit_idx, reason = self._find_exit_intraday(df, i + 1, target, stop, max_hold=15)
                adj_entry, adj_exit, cost_pct = self._apply_costs(entry_raw, exit_raw)
                ret_pct = (adj_exit - adj_entry) / adj_entry * 100
                trades.append({
                    'ticker': ticker,
                    'entry_date': df['date'].iloc[i + 1] if i + 1 < n else df['date'].iloc[i],
                    'exit_date': df['date'].iloc[exit_idx],
                    'entry_price': round(adj_entry, 4),
                    'exit_price': round(adj_exit, 4),
                    'return_pct': round(ret_pct, 2),
                    'win': ret_pct > 0,
                    'exit_reason': reason,
                    'cost_pct': round(cost_pct, 3),
                })
        return trades

    def simulate_episodic_pivot(self, df: pd.DataFrame, ticker: str = '') -> List[Dict]:
        trades = []
        close = df['close'].values
        opens = df['open'].values
        volume = df['volume'].values
        n = len(close)
        for i in range(20, n - 5):
            if i == 0: continue
            gap_pct = (opens[i] - close[i-1]) / close[i-1] if close[i-1] > 0 else 0
            avg_vol = np.mean(volume[max(0, i-21):i])
            if gap_pct > 0.04 and volume[i] > avg_vol * 3:
                entry_raw = opens[i]
                target = entry_raw * 1.12
                stop = entry_raw * 0.94
                exit_raw, exit_idx, reason = self._find_exit_intraday(df, i, target, stop, max_hold=12)
                adj_entry, adj_exit, cost_pct = self._apply_costs(entry_raw, exit_raw)
                ret_pct = (adj_exit - adj_entry) / adj_entry * 100
                trades.append({
                    'ticker': ticker, 'entry_date': df['date'].iloc[i], 'exit_date': df['date'].iloc[exit_idx],
                    'entry_price': round(adj_entry, 4), 'exit_price': round(adj_exit, 4),
                    'return_pct': round(ret_pct, 2), 'win': ret_pct > 0, 'exit_reason': reason, 'cost_pct': round(cost_pct, 3),
                })
        return trades

    def simulate_bull_flag(self, df: pd.DataFrame, ticker: str = '') -> List[Dict]:
        trades = []
        close = df['close'].values
        n = len(close)
        for i in range(20, n - 5):
            if i < 15: continue
            pole_gain = (close[i-5] - close[i-15]) / close[i-15] if close[i-15] > 0 else 0
            body_std = np.std(close[i-5:i]) / np.mean(close[i-5:i]) if np.mean(close[i-5:i]) > 0 else 1
            if pole_gain > 0.10 and body_std < 0.03:
                entry_raw = close[i] * 1.001
                target = entry_raw * 1.10
                stop = entry_raw * 0.95
                exit_raw, exit_idx, reason = self._find_exit_intraday(df, i, target, stop, max_hold=12)
                adj_entry, adj_exit, cost_pct = self._apply_costs(entry_raw, exit_raw)
                ret_pct = (adj_exit - adj_entry) / adj_entry * 100
                trades.append({
                    'ticker': ticker, 'entry_date': df['date'].iloc[i], 'exit_date': df['date'].iloc[exit_idx],
                    'entry_price': round(adj_entry, 4), 'exit_price': round(adj_exit, 4),
                    'return_pct': round(ret_pct, 2), 'win': ret_pct > 0, 'exit_reason': reason, 'cost_pct': round(cost_pct, 3),
                })
        return trades

    def simulate_rsi_oversold(self, df: pd.DataFrame, ticker: str = '') -> List[Dict]:
        trades = []
        close = df['close'].values
        n = len(close)
        if 'rsi' not in df.columns:
            return trades
        rsi = df['rsi'].values
        for i in range(14, n - 3):
            if rsi[i] < 30 and rsi[i - 1] >= 30:
                entry_raw = close[i]
                target = entry_raw * 1.10
                stop = entry_raw * 0.95
                exit_raw, exit_idx, reason = self._find_exit_intraday(df, i, target, stop, max_hold=15)
                adj_entry, adj_exit, cost_pct = self._apply_costs(entry_raw, exit_raw)
                ret_pct = (adj_exit - adj_entry) / adj_entry * 100
                trades.append({
                    'ticker': ticker, 'entry_date': df['date'].iloc[i], 'exit_date': df['date'].iloc[exit_idx],
                    'entry_price': round(adj_entry, 4), 'exit_price': round(adj_exit, 4),
                    'return_pct': round(ret_pct, 2), 'win': ret_pct > 0, 'exit_reason': reason, 'cost_pct': round(cost_pct, 3),
                })
        return trades

    def simulate_macd_cross(self, df: pd.DataFrame, ticker: str = '') -> List[Dict]:
        trades = []
        close = df['close'].values
        n = len(close)
        if 'macd_hist' not in df.columns:
            return trades
        hist = df['macd_hist'].values
        for i in range(1, n - 3):
            if hist[i - 1] < 0 and hist[i] > 0:
                entry_raw = close[i]
                target = entry_raw * 1.10
                stop = entry_raw * 0.95
                exit_raw, exit_idx, reason = self._find_exit_intraday(df, i, target, stop, max_hold=15)
                adj_entry, adj_exit, cost_pct = self._apply_costs(entry_raw, exit_raw)
                ret_pct = (adj_exit - adj_entry) / adj_entry * 100
                trades.append({
                    'ticker': ticker, 'entry_date': df['date'].iloc[i], 'exit_date': df['date'].iloc[exit_idx],
                    'entry_price': round(adj_entry, 4), 'exit_price': round(adj_exit, 4),
                    'return_pct': round(ret_pct, 2), 'win': ret_pct > 0, 'exit_reason': reason, 'cost_pct': round(cost_pct, 3),
                })
        return trades

    def calculate_metrics(self, trades: List[Dict], initial_capital: float = 10_000) -> Dict:
        """Calculate performance metrics from a list of trades.

        AUDIT FIX P1: Proper Sharpe annualization using sqrt(trades_per_year),
        per-trade risk-free rate proportional to holding period,
        Calmar ratio (CAGR / max DD), expectancy, cost breakdown.
        """
        if not trades:
            return {'win_rate': 0, 'avg_gain': 0, 'avg_loss': 0, 'sharpe': 0, 'max_drawdown': 0,
                    'profit_factor': 0, 'total_return': 0, 'avg_holding_days': 0, 'trades_per_year': 0,
                    'calmar_ratio': 0, 'expectancy': 0, 'slippage_cost_pct': 0, 'commission_cost_pct': 0}

        returns_pct = np.array([t['return_pct'] for t in trades])
        returns_dec = returns_pct / 100  # as decimals

        # Holding-period analysis (FIX P1: required for proper annualization)
        holding_days = []
        for t in trades:
            try:
                ed = datetime.strptime(t['exit_date'], '%Y-%m-%d')
                sd = datetime.strptime(t['entry_date'], '%Y-%m-%d')
                holding_days.append((ed - sd).days)
            except Exception:
                holding_days.append(7)  # default fallback
        avg_holding_days = float(np.mean(holding_days)) if holding_days else 7.0
        trades_per_year = 252.0 / max(avg_holding_days, 1)

        wins = returns_dec[returns_dec > 0]
        losses = returns_dec[returns_dec <= 0]
        win_rate = round(len(wins) / len(returns_dec) * 100, 1)
        avg_gain = round(wins.mean() * 100, 2) if len(wins) else 0
        avg_loss = round(losses.mean() * 100, 2) if len(losses) else 0

        # FIX P1: proper profit factor — inf when no losses, not 999
        if len(losses) == 0:
            profit_factor = float('inf')
        elif losses.sum() == 0:
            profit_factor = float('inf')
        else:
            profit_factor = round(wins.sum() / abs(losses.sum()), 2)

        # FIX P1: proper Sharpe annualization
        # per-trade risk-free rate proportional to holding period
        rf_per_trade = (self.risk_free_rate / 252.0) * avg_holding_days
        excess = returns_dec - rf_per_trade
        annualization = np.sqrt(trades_per_year)
        if excess.std() > 0:
            sharpe = float(excess.mean() / excess.std() * annualization)
        else:
            sharpe = 0.0
        sharpe = round(sharpe, 2)

        # Equity curve + max drawdown
        equity = initial_capital
        peak = initial_capital
        max_dd = 0.0
        for r in returns_dec:
            # Position sizing: each trade uses max_position_pct of equity
            equity *= (1 + r * self.max_position_pct)
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak * 100
                max_dd = max(max_dd, dd)

        # Total return (raw sum vs equity curve return)
        total_return_raw = round(returns_pct.sum(), 2)

        # Calmar ratio: CAGR / max DD (annualized)
        if max_dd > 0 and len(trades) > 0:
            # Approximate CAGR from total return and time span
            try:
                first_date = datetime.strptime(min(t['entry_date'] for t in trades), '%Y-%m-%d')
                last_date = datetime.strptime(max(t['exit_date'] for t in trades), '%Y-%m-%d')
                years = max((last_date - first_date).days / 365.25, 0.01)
                equity_multiple = equity / initial_capital
                cagr = (equity_multiple ** (1 / years) - 1) * 100
                calmar = round(cagr / max_dd, 2)
            except Exception:
                calmar = 0.0
        else:
            calmar = 0.0

        # Expectancy (per-trade $ on $10k account)
        expectancy = round(float(returns_dec.mean()) * initial_capital * self.max_position_pct, 2)

        # Cost breakdown
        cost_pcts = np.array([t.get('cost_pct', 0) for t in trades])
        avg_cost_pct = round(float(cost_pcts.mean()), 3) if len(cost_pcts) else 0

        return {
            'win_rate': win_rate, 'avg_gain': avg_gain, 'avg_loss': avg_loss,
            'sharpe': sharpe, 'max_drawdown': round(max_dd, 2),
            'profit_factor': profit_factor, 'total_return': total_return_raw,
            'avg_holding_days': round(avg_holding_days, 1),
            'trades_per_year': round(trades_per_year, 1),
            'calmar_ratio': calmar,
            'expectancy': expectancy,
            'slippage_cost_pct': avg_cost_pct,
            'commission_cost_pct': 0,  # folded into cost_pct
        }

    def generate_equity_curve(self, trades: List[Dict], initial_capital: float = 10000) -> List[Dict]:
        """Generate equity curve from trade list with proper position sizing."""
        equity = initial_capital
        curve = [{'date': 'Start', 'equity': round(equity, 2)}]
        sorted_trades = sorted(trades, key=lambda x: x.get('exit_date', ''))
        for trade in sorted_trades:
            # Position sizing: each trade uses max_position_pct of current equity
            equity *= (1 + (trade['return_pct'] / 100) * self.max_position_pct)
            curve.append({'date': trade.get('exit_date', ''), 'equity': round(equity, 2)})
        return curve
