"""
SwingEdge Pro — Multibagger Detection Engine
Identifies stocks with potential for 2x-10x returns.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from backend.config import settings
from backend.data.fetchers import get_stock_info, get_earnings_surprise, get_institutional_holders

logger = logging.getLogger(__name__)


@dataclass
class MultibaggerScore:
    ticker: str = ''
    composite_score: float = 0.0
    revenue_inflection: float = 0.0
    margin_expansion: float = 0.0
    tam_ratio: float = 0.0
    insider_ownership_score: float = 0.0
    institutional_accumulation: float = 0.0
    float_score: float = 0.0
    breakout_score: float = 0.0
    sector_tailwind: float = 0.0
    explanation: str = ''


class MultibaggerEngine:

    CRITERIA_WEIGHTS = {
        'revenue_inflection': 0.20,
        'margin_expansion': 0.12,
        'tam_ratio': 0.10,
        'insider_ownership_score': 0.15,
        'institutional_accumulation': 0.10,
        'float_score': 0.10,
        'breakout_score': 0.13,
        'sector_tailwind': 0.10,
    }

    HOT_THEMES = settings.HOT_THEMES

    def score_stock(self, ticker: str, tech_report=None, info: Optional[Dict] = None) -> MultibaggerScore:
        """Score a stock for multibagger potential (0-100).

        AUDIT FIX P2: Accepts optional pre-computed tech_report and info
        to avoid duplicate yfinance fetches (was making 2 extra calls per ticker).
        """
        result = MultibaggerScore(ticker=ticker)
        try:
            if info is None:
                info = get_stock_info(ticker)
            if not info:
                return result

            # 1. Revenue inflection
            rev_growth = info.get('revenue_growth') or 0
            result.revenue_inflection = self.score_revenue_inflection(rev_growth)

            # 2. Margin expansion
            gross_margin = info.get('gross_margin') or 0
            op_margin = info.get('operating_margin') or 0
            result.margin_expansion = self.score_margin_expansion(gross_margin, op_margin)

            # 3. TAM ratio (market cap vs estimated TAM)
            market_cap = info.get('market_cap') or 0
            sector = info.get('sector', '')
            description = info.get('description', '')
            result.tam_ratio = self.score_tam_ratio(market_cap, sector, description)

            # 4. Insider ownership
            insider_pct = info.get('insider_ownership') or 0
            result.insider_ownership_score = self.score_insider_ownership(insider_pct)

            # 5. Institutional accumulation
            inst_pct = info.get('institutional_ownership') or 0
            result.institutional_accumulation = self.score_institutional_accumulation(ticker, inst_pct)

            # 6. Float & volume (low float + high rel volume = potential for explosive move)
            float_shares = info.get('float_shares') or 0
            avg_volume = info.get('avg_volume') or 1
            rel_volume = info.get('rel_volume') or 1
            result.float_score = self.score_float_and_volume(float_shares, avg_volume, rel_volume)

            # 7. Technical breakout — FIX P2: reuse tech_report if provided
            if tech_report is None:
                from backend.engine.technicals import TechnicalsEngine
                tech_engine = TechnicalsEngine()
                tech_report = tech_engine.analyze(ticker)
            result.breakout_score = min(100, tech_report.swing_score * 1.2 if tech_report.breakout_flag else tech_report.swing_score * 0.6)

            # 8. Sector tailwind
            result.sector_tailwind = self.score_sector_tailwind(sector, description)

            # Compute composite
            scores = {
                'revenue_inflection': result.revenue_inflection,
                'margin_expansion': result.margin_expansion,
                'tam_ratio': result.tam_ratio,
                'insider_ownership_score': result.insider_ownership_score,
                'institutional_accumulation': result.institutional_accumulation,
                'float_score': result.float_score,
                'breakout_score': result.breakout_score,
                'sector_tailwind': result.sector_tailwind,
            }
            result.composite_score = round(
                sum(scores[k] * self.CRITERIA_WEIGHTS[k] for k in self.CRITERIA_WEIGHTS), 1
            )
            result.explanation = self.get_multibagger_explanation(ticker, scores)

        except Exception as e:
            logger.error(f"Multibagger score error {ticker}: {e}")

        return result

    def score_revenue_inflection(self, rev_growth: float) -> float:
        """Score revenue acceleration. Higher growth = higher score."""
        if rev_growth <= 0:
            return max(0, 30 + rev_growth * 100)  # Declining revenue penalised
        elif rev_growth < 0.10:
            return 40.0
        elif rev_growth < 0.25:
            return 55.0
        elif rev_growth < 0.50:
            return 70.0
        elif rev_growth < 1.0:
            return 85.0
        else:
            return 100.0  # Hyper-growth (>100% YoY)

    def score_margin_expansion(self, gross_margin: float, op_margin: float) -> float:
        """Score margin levels and expected expansion."""
        score = 50.0
        if gross_margin > 0.70:
            score += 25  # Software-like margins
        elif gross_margin > 0.40:
            score += 15
        elif gross_margin > 0.20:
            score += 5
        elif gross_margin < 0:
            score -= 20  # Negative gross margin = concerning

        if op_margin > 0.20:
            score += 15
        elif op_margin > 0.10:
            score += 8
        elif op_margin < 0:
            score -= 10

        return round(max(0, min(100, score)), 1)

    def score_tam_ratio(self, market_cap: float, sector: str, description: str) -> float:
        """Estimate how underpenetrated the company is vs its TAM."""
        if not market_cap or market_cap <= 0:
            return 50.0
        # Approximate TAM by sector
        sector_tams = {
            'Technology': 5e12, 'Healthcare': 4e12, 'Financials': 3e12,
            'Energy': 2e12, 'Consumer Discretionary': 2e12, 'Industrials': 1.5e12,
            'Communications': 1e12, 'Materials': 800e9, 'default': 1e12,
        }
        tam = sector_tams.get(sector, sector_tams['default'])
        # Boost TAM for hot themes
        desc_lower = description.lower()
        for theme in self.HOT_THEMES:
            if theme in desc_lower:
                tam *= 1.5
                break
        penetration = market_cap / tam
        if penetration < 0.001:  # <0.1% penetration = massive room to grow
            return 100.0
        elif penetration < 0.01:
            return 85.0
        elif penetration < 0.05:
            return 65.0
        elif penetration < 0.10:
            return 45.0
        else:
            return 25.0

    def score_insider_ownership(self, insider_pct: float) -> float:
        """Score insider ownership level."""
        if insider_pct >= 0.30:
            return 100.0  # >30% insider = very aligned
        elif insider_pct >= 0.20:
            return 85.0
        elif insider_pct >= 0.10:
            return 65.0
        elif insider_pct >= 0.05:
            return 50.0
        else:
            return 30.0

    def score_institutional_accumulation(self, ticker: str, inst_pct: float) -> float:
        """Score institutional ownership (moderate = good, too much = crowded)."""
        # Ideal: 30-70% institutional ownership and rising
        if 0.30 <= inst_pct <= 0.70:
            return 80.0
        elif 0.10 <= inst_pct < 0.30:
            return 65.0  # Early stage institutional discovery
        elif inst_pct > 0.80:
            return 40.0  # Too crowded
        else:
            return 45.0

    def score_float_and_volume(self, float_shares: float, avg_volume: float, rel_volume: float) -> float:
        """Score low float + high relative volume (explosive move potential)."""
        score = 50.0
        # Low float bonus
        if float_shares < 5e6:  # <5M shares float
            score += 35
        elif float_shares < 20e6:
            score += 25
        elif float_shares < 50e6:
            score += 15
        elif float_shares < 100e6:
            score += 5
        # Relative volume bonus
        if rel_volume > 3.0:
            score += 20
        elif rel_volume > 2.0:
            score += 12
        elif rel_volume > 1.5:
            score += 6
        return round(min(100, score), 1)

    def score_sector_tailwind(self, sector: str, description: str) -> float:
        """Score how aligned the company is with hot market themes."""
        desc_lower = (description + ' ' + sector).lower()
        matches = [theme for theme in self.HOT_THEMES if theme in desc_lower]
        if not matches:
            return 40.0
        return min(100.0, 40.0 + len(matches) * 20.0)

    def get_multibagger_explanation(self, ticker: str, scores: Dict) -> str:
        """Generate human-readable explanation of multibagger potential."""
        top_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        parts = []
        for factor, score in top_factors:
            if score >= 70:
                label = factor.replace('_', ' ').title()
                parts.append(f"Strong {label} ({score:.0f}/100)")
        if not parts:
            return f"Moderate multibagger potential across multiple criteria"
        return f"Key drivers: {' | '.join(parts)}"

    def get_top_multibagger_candidates(self, n: int = 20) -> List[Dict]:
        """Screen universe for top multibagger candidates."""
        from backend.data.universe import MULTIBAGGER_UNIVERSE
        results = []
        for ticker in MULTIBAGGER_UNIVERSE[:40]:  # Limit for speed
            try:
                score = self.score_stock(ticker)
                if score.composite_score > 0:
                    results.append({
                        'ticker': ticker,
                        'composite_score': score.composite_score,
                        'revenue_inflection': score.revenue_inflection,
                        'sector_tailwind': score.sector_tailwind,
                        'float_score': score.float_score,
                        'breakout_score': score.breakout_score,
                        'explanation': score.explanation,
                    })
            except Exception as e:
                logger.debug(f"Multibagger score error {ticker}: {e}")
        results.sort(key=lambda x: x['composite_score'], reverse=True)
        return results[:n]
