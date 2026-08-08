"""
SwingEdge Pro — Global News Cross-Linking Engine
Maps international news events to US stock impacts.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CrossLinkResult:
    source_headline: str = ''
    source_company: str = ''
    source_country: str = ''
    affected_us_tickers: List[str] = field(default_factory=list)
    impact_direction: str = 'neutral'  # bullish / bearish / neutral
    explanation: str = ''
    confidence: float = 0.0
    category: str = 'global'  # global / macro / political / analyst
    event_type: str = ''      # earnings / merger / regulatory / geopolitical / macro


COUNTRY_REGIONS = {
    'south korea': ['samsung', 'sk hynix', 'hyundai', 'lg', 'kia'],
    'korea': ['samsung', 'sk hynix', 'hyundai', 'lg', 'kia'],
    'japan': ['toyota', 'honda', 'sony', 'softbank', 'nintendo', 'panasonic'],
    'china': ['alibaba', 'tencent', 'baidu', 'byd', 'catl'],
    'taiwan': ['tsmc', 'foxconn', 'asus', 'acer'],
    'europe': ['asml', 'volkswagen', 'bmw', 'mercedes', 'shell', 'bp', 'roche', 'novartis', 'astrazeneca'],
    'germany': ['volkswagen', 'bmw', 'mercedes', 'siemens', 'bayer'],
    'netherlands': ['asml', 'shell'],
    'uk': ['shell', 'bp', 'astrazeneca'],
    'saudi': ['saudi aramco'],
    'middle east': ['saudi aramco', 'petrobras'],
    'australia': ['bhp', 'rio tinto'],
    'brazil': ['vale', 'petrobras'],
}

# Event type keywords
EVENT_KEYWORDS = {
    'earnings_beat': ['beat', 'beats', 'surpassed', 'record profit', 'record revenue', 'blowout', 'smashed estimates', 'q1 beat', 'q2 beat', 'q3 beat', 'q4 beat', 'eps surprise', 'guidance raise'],
    'earnings_miss': ['missed', 'miss', 'disappoints', 'fell short', 'below estimates', 'weak earnings', 'guidance cut', 'profit warning'],
    'merger_acquisition': ['acquires', 'acquisition', 'merger', 'takeover', 'buyout', 'tender offer', 'deal worth', 'cash premium', 'buying target'],
    'regulatory_approval': ['approved', 'approval', 'fda', 'eu approved', 'green light', 'clears'],
    'regulatory_block': ['blocked', 'rejected', 'denied', 'ban', 'antitrust'],
    'supply_chain': ['supply chain', 'chip shortage', 'shortage', 'disruption', 'delay', 'bottleneck'],
    'geopolitical': ['war', 'conflict', 'sanction', 'tariff', 'trade war', 'invasion', 'missile'],
    'macro_fed': ['fed', 'federal reserve', 'rate hike', 'rate cut', 'interest rate', 'powell', 'fomc'],
    'macro_inflation': ['inflation', 'cpi', 'ppi', 'consumer price'],
    'macro_jobs': ['jobs', 'unemployment', 'payroll', 'nonfarm'],
    'macro_gdp': ['gdp', 'growth rate', 'economic growth', 'recession'],
    'opec': ['opec', 'oil production', 'oil cut', 'crude'],
    'ai_tech': ['ai', 'artificial intelligence', 'chatgpt', 'machine learning', 'language model', 'gpu', 'data center', 'hbm', 'liquid cooling', 'llm'],
    'ai_vs_legacy_it': ['it budget reallocation', 'legacy it slowdown', 'it consulting weakness', 'ai capex shift', 'ai hardware surge'],
}


class CrossLinkEngine:
    """Maps global news events to US stock impacts."""

    def __init__(self):
        self.company_map = {k.lower(): v for k, v in settings.GLOBAL_COMPANY_MAP.items()}
        self.macro_map = settings.MACRO_EVENT_MAP

    def process_news_article(self, article: Dict) -> Optional[CrossLinkResult]:
        """Process a single news article for cross-link signals."""
        headline = article.get('headline', '')
        summary = article.get('summary', '') or ''
        full_text = (headline + ' ' + summary).lower()

        result = CrossLinkResult(source_headline=headline)

        # 1. Find foreign companies mentioned
        affected_tickers = []
        source_company = ''
        for company_name, us_tickers in self.company_map.items():
            if company_name in full_text:
                affected_tickers.extend(us_tickers)
                if not source_company:
                    source_company = company_name.title()

        # 2. Find country regions (broader mapping)
        source_country = ''
        for country, companies in COUNTRY_REGIONS.items():
            if country in full_text:
                source_country = country.title()
                for co in companies:
                    if co in self.company_map:
                        affected_tickers.extend(self.company_map[co])

        # Deduplicate
        affected_tickers = list(dict.fromkeys(affected_tickers))[:8]

        if not affected_tickers:
            return None  # No cross-link found

        result.source_company = source_company
        result.source_country = source_country
        result.affected_us_tickers = affected_tickers

        # 3. Detect event type and direction
        event_type, direction = self._classify_event(full_text)
        result.event_type = event_type
        result.impact_direction = direction

        # 4. Confidence (more company mentions = higher confidence)
        result.confidence = min(0.95, 0.5 + len([c for c in self.company_map if c in full_text]) * 0.15)

        # 5. Generate explanation
        result.explanation = self._generate_explanation(
            source_company or source_country, event_type, direction, affected_tickers
        )

        return result

    def _classify_event(self, text: str):
        """Classify the event type and determine impact direction."""
        # Check for specific event types
        for event_type, keywords in EVENT_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    if 'beat' in event_type or 'approval' in event_type or 'merger' in event_type or 'ai' in event_type:
                        return event_type, 'bullish'
                    elif 'miss' in event_type or 'block' in event_type:
                        return event_type, 'bearish'
                    elif 'geo' in event_type:
                        return event_type, 'bearish'
                    elif 'supply_chain' in event_type:
                        return event_type, 'bearish'
                    else:
                        return event_type, 'neutral'

        # Generic positive/negative keywords
        positive = ['surge', 'jump', 'soar', 'record', 'profit', 'growth', 'rise', 'gain', 'rally']
        negative = ['fall', 'drop', 'decline', 'loss', 'miss', 'cut', 'warn', 'trouble', 'probe']
        pos_count = sum(1 for w in positive if w in text)
        neg_count = sum(1 for w in negative if w in text)
        if pos_count > neg_count:
            return 'news_event', 'bullish'
        elif neg_count > pos_count:
            return 'news_event', 'bearish'
        return 'news_event', 'neutral'

    def _generate_explanation(self, source: str, event_type: str, direction: str, tickers: List[str]) -> str:
        """Generate human-readable impact explanation."""
        ticker_str = ', '.join(tickers[:4])
        direction_word = {'bullish': '📈 bullish', 'bearish': '📉 bearish', 'neutral': '➡️ neutral'}[direction]

        event_descriptions = {
            'earnings_beat': 'earnings beat',
            'earnings_miss': 'earnings miss',
            'merger_acquisition': 'M&A activity',
            'regulatory_approval': 'regulatory approval',
            'regulatory_block': 'regulatory block',
            'supply_chain': 'supply chain disruption',
            'geopolitical': 'geopolitical event',
            'macro_fed': 'Fed policy signal',
            'macro_inflation': 'inflation data',
            'macro_jobs': 'jobs data',
            'macro_gdp': 'GDP data',
            'opec': 'OPEC decision',
            'ai_tech': 'AI/tech development',
            'news_event': 'news event',
        }
        event_desc = event_descriptions.get(event_type, 'development')

        return f"{source} {event_desc} → {direction_word} signal for {ticker_str}"

    def process_all_news(self, news_list: List[Dict]) -> List[CrossLinkResult]:
        """Process a batch of news articles for cross-link signals."""
        results = []
        for article in news_list:
            result = self.process_news_article(article)
            if result and result.affected_us_tickers:
                results.append(result)
        return results

    def detect_macro_events(self, news_list: List[Dict]) -> List[Dict]:
        """Detect macro events and their sector impacts."""
        macro_impacts = []
        for article in news_list:
            text = (article.get('headline', '') + ' ' + article.get('summary', '')).lower()
            for macro_type, keywords in EVENT_KEYWORDS.items():
                if not macro_type.startswith('macro') and macro_type != 'opec':
                    continue
                for kw in keywords:
                    if kw in text:
                        sector_impact = self.macro_map.get(macro_type.replace('macro_', ''))
                        if not sector_impact:
                            # Try opec
                            sector_impact = self.macro_map.get('opec_cut' if 'cut' in text else 'opec_increase')
                        if sector_impact:
                            macro_impacts.append({
                                'headline': article.get('headline', ''),
                                'macro_type': macro_type,
                                'keyword': kw,
                                'positive_sectors': sector_impact.get('positive', []),
                                'negative_sectors': sector_impact.get('negative', []),
                                'source': article.get('source', ''),
                            })
                        break

        return macro_impacts

    def get_cross_linked_signals(self, ticker: str, news_list: List[Dict]) -> List[CrossLinkResult]:
        """Get all cross-link signals from news that affect a specific ticker."""
        all_signals = self.process_all_news(news_list)
        return [s for s in all_signals if ticker in s.affected_us_tickers]
