"""
SwingEdge Pro — News Router
All RSS & HTTP fetching wrapped in asyncio.to_thread to keep API endpoints fast and non-blocking.
"""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter
from backend.data.fetchers import get_all_rss_news, get_global_rss_news, get_market_news
from backend.engine.sentiment import SentimentEngine
from backend.engine.cross_linking import CrossLinkEngine

router = APIRouter(prefix='/api/news', tags=['news'])
logger = logging.getLogger(__name__)

_sentiment = None
_cross = None


def _get_sentiment():
    global _sentiment
    if _sentiment is None:
        _sentiment = SentimentEngine()
    return _sentiment


def _get_cross():
    global _cross
    if _cross is None:
        _cross = CrossLinkEngine()
    return _cross


@router.get('')
async def get_all_news(type: Optional[str] = None, ticker: Optional[str] = None):
    """Fetch market news with sentiment analysis."""
    try:
        def _fetch():
            news = get_market_news() or get_all_rss_news()
            scored = _get_sentiment().analyze_news_batch(news)
            if type:
                from backend.data.fetchers import detect_political_signals, detect_analyst_actions
                filtered = []
                for article in scored:
                    text = article.get('headline', '')
                    if type == 'political' and detect_political_signals(text)['is_political']:
                        article['category'] = 'political'
                        filtered.append(article)
                    elif type == 'analyst' and detect_analyst_actions(text)['action']:
                        article['category'] = 'analyst'
                        filtered.append(article)
                    else:
                        filtered.append(article)
                scored = filtered
            if ticker:
                scored = [a for a in scored if ticker.upper() in a.get('headline', '').upper()]
            return scored[:30]

        scored_news = await asyncio.to_thread(_fetch)
        return {'count': len(scored_news), 'news': scored_news}
    except Exception as e:
        logger.error(f"News fetch error: {e}")
        return {'count': 0, 'news': [], 'error': str(e)}


@router.get('/intelligence')
async def get_intelligence():
    """Cross-linked news & intelligence breakdown."""
    try:
        def _fetch_intel():
            global_news = get_global_rss_news()
            domestic_news = get_all_rss_news()
            all_news = global_news + domestic_news
            cross_engine = _get_cross()
            results = cross_engine.process_all_news(all_news)
            macro = cross_engine.detect_macro_events(all_news)
            scored_news = _get_sentiment().analyze_news_batch(all_news[:30])
            return results, macro, scored_news

        results, macro, scored_news = await asyncio.to_thread(_fetch_intel)

        return {
            'cross_linked': [
                {
                    'headline': r.source_headline,
                    'company': r.source_company,
                    'country': r.source_country,
                    'affected_tickers': r.affected_us_tickers,
                    'direction': r.impact_direction,
                    'explanation': r.explanation,
                    'confidence': r.confidence,
                    'event_type': r.event_type,
                }
                for r in results[:20]
            ],
            'macro_events': macro[:10],
            'recent_news': scored_news,
        }
    except Exception as e:
        logger.error(f"Intelligence endpoint error: {e}")
        return {'cross_linked': [], 'macro_events': [], 'recent_news': [], 'error': str(e)}


@router.get('/political')
async def get_political_signals():
    """Political & presidential signal extraction."""
    try:
        def _fetch_political():
            from backend.data.fetchers import detect_political_signals
            all_news = get_market_news() or get_all_rss_news()
            political = []
            sentiment_engine = _get_sentiment()
            for article in all_news:
                text = article.get('headline', '') + ' ' + article.get('summary', '')
                signal = detect_political_signals(text)
                if signal['is_political']:
                    sentiment = sentiment_engine.analyze_text(text)
                    political.append({**article, 'political_signal': signal, 'sentiment': sentiment, 'category': 'political'})
            return political[:20]

        signals = await asyncio.to_thread(_fetch_political)
        return {'count': len(signals), 'signals': signals}
    except Exception as e:
        logger.error(f"Political signals error: {e}")
        return {'count': 0, 'signals': [], 'error': str(e)}


@router.get('/analysts')
async def get_analyst_actions():
    """Analyst upgrade / downgrade recommendations."""
    try:
        def _fetch_analysts():
            from backend.data.fetchers import detect_analyst_actions
            all_news = get_market_news() or get_all_rss_news()
            analyst_news = []
            for article in all_news:
                text = article.get('headline', '')
                action = detect_analyst_actions(text)
                if action.get('action'):
                    analyst_news.append({**article, 'analyst_action': action, 'category': 'analyst'})
            return analyst_news[:20]

        actions = await asyncio.to_thread(_fetch_analysts)
        return {'count': len(actions), 'actions': actions}
    except Exception as e:
        logger.error(f"Analyst actions error: {e}")
        return {'count': 0, 'actions': [], 'error': str(e)}


@router.get('/macro')
async def get_macro_news():
    """Macro economic indicators & news."""
    try:
        def _fetch_macro():
            from backend.data.fetchers import get_macro_indicator, get_market_sentiment_indicators
            macro_data = {
                'fed_funds_rate': get_macro_indicator('FEDFUNDS', limit=3),
                'cpi': get_macro_indicator('CPIAUCSL', limit=3),
                'unemployment': get_macro_indicator('UNRATE', limit=3),
                'yield_curve': get_macro_indicator('T10Y2Y', limit=3),
                'market_sentiment': get_market_sentiment_indicators(),
            }
            all_news = get_all_rss_news()
            macro_events = _get_cross().detect_macro_events(all_news)
            return macro_data, macro_events

        macro_data, macro_events = await asyncio.to_thread(_fetch_macro)
        return {'macro_data': macro_data, 'macro_events': macro_events[:15]}
    except Exception as e:
        logger.error(f"Macro news error: {e}")
        return {'macro_data': {}, 'macro_events': [], 'error': str(e)}
