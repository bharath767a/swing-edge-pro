"""
SwingEdge Pro — Sector Rotation Engine
Detects money flow between GICS sectors and assesses risk on/off.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List
from backend.config import settings
from backend.data.fetchers import get_ohlcv, get_stock_info

logger = logging.getLogger(__name__)


class SectorRotationEngine:

    SECTORS = settings.SECTORS
    GLOBAL_ETFS = {'Nikkei': 'EWJ', 'DAX': 'EWG', 'KOSPI': 'EWY', 'FTSE': 'EWU', 'EEM': 'EEM'}

    def get_sector_performance(self) -> Dict:
        """Get 1D / 5D / 1M performance for each GICS sector ETF."""
        results = {}
        for sector, etf in self.SECTORS.items():
            try:
                df = get_ohlcv(etf, period='3mo', interval='1d')
                if df is None or len(df) < 5:
                    results[sector] = self._empty_sector(sector, etf)
                    continue
                closes = df['close'].values
                c_1d = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0
                c_5d = round((closes[-1] - closes[-6]) / closes[-6] * 100, 2) if len(closes) >= 6 else 0
                c_1m = round((closes[-1] - closes[-22]) / closes[-22] * 100, 2) if len(closes) >= 22 else 0
                c_3m = round((closes[-1] - closes[0]) / closes[0] * 100, 2)

                # Relative strength vs SPY
                spy_df = get_ohlcv('SPY', period='3mo', interval='1d')
                rs = 0
                if spy_df is not None and len(spy_df) >= 22:
                    spy_closes = spy_df['close'].values
                    spy_1m = (spy_closes[-1] - spy_closes[-22]) / spy_closes[-22] * 100
                    rs = round(c_1m - spy_1m, 2)

                results[sector] = {
                    'sector': sector,
                    'etf_ticker': etf,
                    'price': round(closes[-1], 2),
                    'change_1d': c_1d,
                    'change_5d': c_5d,
                    'change_1m': c_1m,
                    'change_3m': c_3m,
                    'relative_strength': rs,
                    'momentum_score': round((c_1d * 3 + c_5d * 2 + c_1m) / 6, 2),
                    'rotation_signal': 'inflow' if rs > 1 else ('outflow' if rs < -1 else 'neutral'),
                }
            except Exception as e:
                logger.warning(f"Sector perf error {sector}: {e}")
                results[sector] = self._empty_sector(sector, etf)
        return results

    def _empty_sector(self, sector, etf):
        return {'sector': sector, 'etf_ticker': etf, 'price': 0, 'change_1d': 0, 'change_5d': 0,
                'change_1m': 0, 'change_3m': 0, 'relative_strength': 0, 'momentum_score': 0, 'rotation_signal': 'neutral'}

    def detect_rotation_signal(self) -> Dict:
        """Detect which sectors money is flowing into/out of."""
        performance = self.get_sector_performance()
        inflows = [(s, d['relative_strength']) for s, d in performance.items() if d['rotation_signal'] == 'inflow']
        outflows = [(s, d['relative_strength']) for s, d in performance.items() if d['rotation_signal'] == 'outflow']
        inflows.sort(key=lambda x: x[1], reverse=True)
        outflows.sort(key=lambda x: x[1])
        return {
            'top_inflow_sectors': [s for s, _ in inflows[:3]],
            'top_outflow_sectors': [s for s, _ in outflows[:3]],
            'rotation_strength': round(sum(v for _, v in inflows[:3]) / 3, 2) if inflows else 0,
        }

    def detect_risk_on_off(self) -> Dict:
        """Determine if market is in risk-on or risk-off mode."""
        try:
            risk_on_etfs = ['XLK', 'XLY', 'XLI']   # Tech, Discretionary, Industrials
            risk_off_etfs = ['XLU', 'XLP', 'GLD']   # Utilities, Staples, Gold

            def avg_perf(etfs: List[str]) -> float:
                perfs = []
                for etf in etfs:
                    df = get_ohlcv(etf, period='1mo', interval='1d')
                    if df is not None and len(df) >= 2:
                        c = df['close'].values
                        perfs.append((c[-1] - c[-6]) / c[-6] * 100 if len(c) >= 6 else 0)
                return sum(perfs) / len(perfs) if perfs else 0

            risk_on_perf = avg_perf(risk_on_etfs)
            risk_off_perf = avg_perf(risk_off_etfs)
            diff = risk_on_perf - risk_off_perf

            if diff > 2:
                signal = 'risk-on'
                explanation = 'Tech & cyclicals outperforming defensives — market in risk-on mode'
            elif diff < -2:
                signal = 'risk-off'
                explanation = 'Defensives outperforming cyclicals — market in risk-off / defensive mode'
            else:
                signal = 'neutral'
                explanation = 'Mixed sector performance — no clear risk-on or risk-off bias'

            return {'signal': signal, 'diff': round(diff, 2), 'explanation': explanation,
                    'risk_on_perf': round(risk_on_perf, 2), 'risk_off_perf': round(risk_off_perf, 2)}
        except Exception as e:
            logger.warning(f"Risk on/off error: {e}")
            return {'signal': 'neutral', 'diff': 0, 'explanation': 'Could not determine risk mode'}

    def get_correlation_matrix(self, tickers: List[str], period: int = 60) -> Dict:
        """Compute Pearson correlation matrix for a list of tickers."""
        returns = {}
        for ticker in tickers:
            try:
                df = get_ohlcv(ticker, period='6mo', interval='1d')
                if df is not None and len(df) >= period:
                    closes = pd.Series(df['close'].values[-period:])
                    returns[ticker] = closes.pct_change().dropna()
            except Exception:
                pass
        if len(returns) < 2:
            return {}
        ret_df = pd.DataFrame(returns)
        corr_matrix = ret_df.corr().round(3)
        return corr_matrix.to_dict()

    def get_global_market_correlation(self) -> Dict:
        """Correlation between US sectors and global market ETFs."""
        global_etfs = list(self.GLOBAL_ETFS.values())
        sector_etfs = list(self.SECTORS.values())
        all_etfs = global_etfs + sector_etfs
        corr = self.get_correlation_matrix(all_etfs)
        return {
            'global_etfs': self.GLOBAL_ETFS,
            'correlation': corr,
        }

    def get_sector_for_ticker(self, ticker: str) -> str:
        """Return GICS sector name for a ticker."""
        try:
            info = get_stock_info(ticker)
            if info:
                return info.get('sector', 'Unknown')
        except Exception:
            pass
        return 'Unknown'

    def get_sector_leaders(self, sector: str, n: int = 5) -> List[Dict]:
        """Get top N performing stocks in a sector."""
        # Mapping common sectors to sample tickers
        sector_stocks = {
            'Technology': ['NVDA', 'AMD', 'MSFT', 'AAPL', 'CRWD', 'ANET', 'SMCI', 'MRVL'],
            'Healthcare': ['LLY', 'UNH', 'ISRG', 'DXCM', 'VRTX', 'ABBV', 'MRNA', 'RXRX'],
            'Financials': ['JPM', 'GS', 'MS', 'BLK', 'V', 'MA', 'COIN', 'SOFI'],
            'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'MPC', 'VLO', 'DINO', 'HES'],
            'Industrials': ['CAT', 'DE', 'RTX', 'LMT', 'GE', 'HON', 'KTOS', 'AVAV'],
            'Consumer Discretionary': ['TSLA', 'AMZN', 'LULU', 'RH', 'WYNN', 'MGM', 'CMG'],
            'Materials': ['FCX', 'NEM', 'ALB', 'MP', 'UUUU', 'CCJ', 'CLF'],
        }
        tickers = sector_stocks.get(sector, [])
        if not tickers:
            return []
        leaders = []
        for ticker in tickers[:n + 3]:
            try:
                info = get_stock_info(ticker)
                if info:
                    leaders.append({'ticker': ticker, 'price': info.get('price'), 'change_pct': info.get('change_pct', 0)})
            except Exception:
                pass
        leaders.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
        return leaders[:n]
