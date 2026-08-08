"""
SwingEdge Pro — Fundamental Analysis Engine
"""
import logging
from typing import Dict, List, Optional
from backend.config import settings

logger = logging.getLogger(__name__)


class FundamentalsEngine:

    SECTOR_PE = settings.SECTOR_PE_BENCHMARKS

    def score_valuation(self, info: Dict) -> float:
        """Score valuation metrics vs sector benchmarks."""
        score = 50.0
        sector = info.get('sector', 'default')
        benchmark_pe = self.SECTOR_PE.get(sector, self.SECTOR_PE['default'])

        pe = info.get('pe_ratio')
        fpe = info.get('forward_pe')
        peg = info.get('peg')
        pb = info.get('pb')

        # P/E vs sector benchmark
        if pe and pe > 0:
            if pe < benchmark_pe * 0.7:
                score += 20  # Significantly undervalued
            elif pe < benchmark_pe:
                score += 10
            elif pe > benchmark_pe * 1.5:
                score -= 10  # Premium valued

        # Forward P/E (more predictive)
        if fpe and fpe > 0:
            if fpe < benchmark_pe * 0.6:
                score += 15
            elif fpe < benchmark_pe * 0.8:
                score += 8

        # PEG Ratio (growth-adjusted valuation)
        if peg and peg > 0:
            if peg < 1.0:
                score += 15  # Growing faster than it's priced
            elif peg < 1.5:
                score += 7
            elif peg > 2.5:
                score -= 10

        # Price/Book
        if pb and pb > 0:
            if pb < 1.0:
                score += 10  # Trading below book
            elif pb > 10:
                score -= 5

        return round(max(0, min(100, score)), 1)

    def score_growth(self, info: Dict) -> float:
        """Score growth metrics."""
        score = 50.0
        rev_growth = info.get('revenue_growth') or 0
        earn_growth = info.get('earnings_growth') or 0
        gross_margin = info.get('gross_margin') or 0

        # Revenue growth
        if rev_growth > 0.50: score += 25
        elif rev_growth > 0.25: score += 18
        elif rev_growth > 0.10: score += 10
        elif rev_growth > 0: score += 5
        elif rev_growth < -0.10: score -= 15

        # Earnings growth
        if earn_growth and earn_growth > 0.30: score += 15
        elif earn_growth and earn_growth > 0.10: score += 8

        # Gross margin quality
        if gross_margin > 0.70: score += 10
        elif gross_margin > 0.40: score += 5
        elif gross_margin < 0: score -= 10

        return round(max(0, min(100, score)), 1)

    def score_financial_health(self, info: Dict) -> float:
        """Score balance sheet and financial health."""
        score = 50.0
        debt_eq = info.get('debt_equity') or 0
        cur_ratio = info.get('current_ratio') or 1
        net_margin = info.get('net_margin') or 0

        # Debt/Equity
        if debt_eq < 0.3: score += 15
        elif debt_eq < 1.0: score += 8
        elif debt_eq > 2.0: score -= 10
        elif debt_eq > 5.0: score -= 20

        # Current Ratio
        if cur_ratio > 2.0: score += 10
        elif cur_ratio > 1.5: score += 5
        elif cur_ratio < 1.0: score -= 15  # Liquidity risk

        # Net Margin
        if net_margin > 0.20: score += 15
        elif net_margin > 0.10: score += 8
        elif net_margin > 0: score += 3
        elif net_margin < -0.10: score -= 10

        return round(max(0, min(100, score)), 1)

    def score_quality(self, info: Dict) -> float:
        """Score business quality metrics."""
        score = 50.0
        roe = info.get('roe') or 0
        roic = info.get('roic') or 0
        short_float = info.get('short_float') or 0

        # ROE
        if roe > 0.25: score += 15
        elif roe > 0.15: score += 8
        elif roe < 0: score -= 10

        # ROIC proxy (ROA)
        if roic > 0.15: score += 10
        elif roic > 0.08: score += 5
        elif roic < 0: score -= 5

        # Short interest (contrarian signal — high short = potential squeeze)
        if short_float > 0.20:
            score += 5  # High short = squeeze potential
        elif short_float > 0.30:
            score -= 5  # Too much short selling = possible reason

        return round(max(0, min(100, score)), 1)

    def composite_fundamental_score(self, ticker: str, info: Optional[Dict] = None) -> Optional[float]:
        """Compute weighted fundamental score 0-100.

        FIX v3.2.2: Returns None when no data available (was returning 50.0
        which masked missing data as "neutral"). Caller must handle None.
        """
        if info is None:
            from backend.data.fetchers import get_stock_info
            info = get_stock_info(ticker)
        if not info:
            return None  # FIX: was 50.0 — don't fabricate neutral score
        val_score = self.score_valuation(info)
        growth_score = self.score_growth(info)
        health_score = self.score_financial_health(info)
        quality_score = self.score_quality(info)
        # Weighted: growth most important for swing/multibagger trading
        composite = (growth_score * 0.35 + val_score * 0.25 + health_score * 0.20 + quality_score * 0.20)
        return round(composite, 1)

    def detect_earnings_catalyst(self, ticker: str) -> Dict:
        """Detect upcoming earnings date and expected impact."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is not None and not cal.empty:
                dates = list(cal.columns)
                next_date = str(dates[0]) if dates else 'Unknown'
                return {'has_upcoming_earnings': True, 'date': next_date, 'expected_impact': 'moderate'}
        except Exception:
            pass
        return {'has_upcoming_earnings': False, 'date': None, 'expected_impact': None}

    def parse_backlog_from_news(self, ticker: str, news_list: List[Dict]) -> Dict:
        """Detect order book/backlog mentions in news."""
        backlog_keywords = [
            'backlog', 'order book', 'contract', 'awarded', 'wins deal', 'worth',
            'million contract', 'billion contract', 'government contract',
        ]
        mentions = []
        for article in news_list:
            text = (article.get('headline', '') + ' ' + article.get('summary', '')).lower()
            for kw in backlog_keywords:
                if kw in text:
                    mentions.append({'headline': article.get('headline'), 'keyword': kw})
                    break
        return {'has_backlog_news': bool(mentions), 'mentions': mentions[:3]}
