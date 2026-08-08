"""
SwingEdge Pro — Insider Trading Intelligence
Tracks Form 4 SEC filings and scores insider sentiment.
"""
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from backend.data.fetchers import get_finnhub_insider_trades, get_form4_filings

logger = logging.getLogger(__name__)


class InsiderTracker:

    TITLE_WEIGHTS = {
        'ceo': 3.0, 'chief executive': 3.0, 'president': 2.5,
        'cfo': 2.8, 'chief financial': 2.8,
        'coo': 2.3, 'chief operating': 2.3,
        'cto': 2.0, 'chief technology': 2.0,
        'director': 1.5, 'vp': 1.3, 'vice president': 1.3,
        'officer': 1.2, '10%': 2.0,  # 10% owner
    }

    def fetch_insider_trades(self, ticker: str) -> List[Dict]:
        """Fetch insider trades from Finnhub + SEC EDGAR."""
        trades = []
        # Try Finnhub first
        finnhub_trades = get_finnhub_insider_trades(ticker)
        if finnhub_trades:
            trades.extend(finnhub_trades)
        # Also get from EDGAR
        edgar_trades = get_form4_filings(ticker)
        if edgar_trades:
            trades.extend(edgar_trades)
        # Deduplicate by (filer_name, trade_date)
        seen = set()
        unique = []
        for t in trades:
            key = (t.get('filer_name', ''), t.get('trade_date', ''))
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique

    def _get_title_weight(self, title: str) -> float:
        """Return weight based on insider's title (higher = more significant)."""
        title_lower = (title or '').lower()
        for key, weight in self.TITLE_WEIGHTS.items():
            if key in title_lower:
                return weight
        return 1.0

    def score_insider_signal(self, trades: List[Dict]) -> Optional[float]:
        """Score insider trades on a 0-100 scale.

        FIX v3.2.2: Returns None when no trades available (was returning 50.0
        which masked missing data as "neutral"). Caller should handle None.
        50.0 is still used as the BASE score when trades exist but none are
        significant — that's a real score, not fabricated.
        """
        if not trades:
            return None  # FIX: was 50.0 — don't fabricate neutral when no data

        score = 50.0
        now = datetime.now()
        cutoff_30d = now - timedelta(days=30)
        cutoff_60d = now - timedelta(days=60)

        buy_signals = []
        sell_signals = []

        for trade in trades:
            trade_date_str = trade.get('trade_date') or trade.get('filed_date', '')
            try:
                trade_date = datetime.strptime(trade_date_str[:10], '%Y-%m-%d')
            except Exception:
                continue

            trade_type = trade.get('trade_type', 'S')
            value = float(trade.get('value') or 0)
            title_weight = self._get_title_weight(trade.get('filer_title', ''))
            age_factor = 1.0
            if trade_date >= cutoff_30d:
                age_factor = 1.5  # Recent = more weight
            elif trade_date >= cutoff_60d:
                age_factor = 1.0
            else:
                age_factor = 0.5

            signal_strength = min(3.0, (value / 50_000) ** 0.5) * title_weight * age_factor

            if trade_type == 'P':  # Purchase
                buy_signals.append(signal_strength)
            elif trade_type == 'S':  # Sale (not from options exercise)
                sell_signals.append(signal_strength)

        # Score calculation
        buy_total = sum(buy_signals)
        sell_total = sum(sell_signals)

        if buy_total > 0:
            score += min(40, buy_total * 8)  # Up to +40 for buys
        if sell_total > 0:
            score -= min(30, sell_total * 5)  # Up to -30 for sells

        # Cluster bonus: 3+ insiders buying = extra signal
        if len(buy_signals) >= 3:
            score += 10

        return round(max(0.0, min(100.0, score)), 1)

    def detect_cluster_buying(self, ticker: str, trades: List[Dict]) -> Dict:
        """Detect cluster buying (3+ insiders buying within 2 weeks)."""
        if not trades:
            return {'detected': False, 'buyer_count': 0, 'total_value': 0}

        now = datetime.now()
        cutoff = now - timedelta(days=14)
        recent_buys = []

        for trade in trades:
            if trade.get('trade_type') != 'P':
                continue
            trade_date_str = trade.get('trade_date') or trade.get('filed_date', '')
            try:
                trade_date = datetime.strptime(trade_date_str[:10], '%Y-%m-%d')
                if trade_date >= cutoff:
                    recent_buys.append(trade)
            except Exception:
                continue

        unique_buyers = {t.get('filer_name', '') for t in recent_buys}
        total_value = sum(float(t.get('value') or 0) for t in recent_buys)

        detected = len(unique_buyers) >= 3
        return {
            'detected': detected,
            'buyer_count': len(unique_buyers),
            'total_value': total_value,
            'buyers': list(unique_buyers),
            'signal': '🚨 CLUSTER BUY — Multiple insiders accumulating!' if detected else '',
        }

    def get_insider_sentiment(self, ticker: str) -> Dict:
        """Get overall insider trading score and summary."""
        trades = self.fetch_insider_trades(ticker)
        score = self.score_insider_signal(trades)
        cluster = self.detect_cluster_buying(ticker, trades)

        buy_count = sum(1 for t in trades if t.get('trade_type') == 'P')
        sell_count = sum(1 for t in trades if t.get('trade_type') == 'S')

        # FIX v3.2.2: handle None score (no trades data)
        if score is None:
            summary = "No insider trades data available"
        elif score >= 75:
            summary = f"Strong insider buying — {buy_count} purchase(s) detected"
        elif score >= 60:
            summary = f"Moderate insider buying — {buy_count} purchase(s)"
        elif score <= 30:
            summary = f"Insider selling — {sell_count} sale(s) detected"
        else:
            summary = "Neutral insider activity"

        if cluster.get('detected'):
            summary = cluster.get('signal', summary)

        return {
            'score': score,  # may be None
            'data_available': score is not None,
            'summary': summary,
            'trades': trades[:10],
            'cluster_buy': cluster,
            'buy_count': buy_count,
            'sell_count': sell_count,
        }
