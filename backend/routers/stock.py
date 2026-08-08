"""
SwingEdge Pro — Stock Router
All heavy sync calls wrapped in asyncio.to_thread to prevent blocking.
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from backend.engine.scoring import MasterScorer
from backend.data.fetchers import get_stock_info, get_ohlcv, get_company_news
from backend.engine.sentiment import SentimentEngine
from backend.engine.insider_tracker import InsiderTracker
from backend.engine.cross_linking import CrossLinkEngine
from backend.engine.sector_rotation import SectorRotationEngine

router = APIRouter(prefix='/api/stock', tags=['stock'])
logger = logging.getLogger(__name__)

# Lazy-init to avoid slow startup
_scorer = None
_sentiment = None
_insider = None
_cross = None
_sector = None

def _get_scorer():
    global _scorer
    if _scorer is None:
        _scorer = MasterScorer()
    return _scorer

def _get_sentiment():
    global _sentiment
    if _sentiment is None:
        _sentiment = SentimentEngine()
    return _sentiment

def _get_insider():
    global _insider
    if _insider is None:
        _insider = InsiderTracker()
    return _insider

def _get_cross():
    global _cross
    if _cross is None:
        _cross = CrossLinkEngine()
    return _cross

def _get_sector():
    global _sector
    if _sector is None:
        _sector = SectorRotationEngine()
    return _sector


def _sanitize_for_json(obj):
    """Recursively convert numpy types (bool_, float64, int64) to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, 'item'):
        return obj.item()
    return obj


@router.get('/{ticker}')
async def get_stock(ticker: str):
    ticker = ticker.upper()
    try:
        # AUDIT FIX P2: single pass — score_stock now does everything internally
        def _do_score():
            scorer = _get_scorer()
            score = scorer.score_stock(ticker)
            tech_report = scorer.technicals.analyze(ticker)  # cache hit
            return score, tech_report

        score, tech_report = await asyncio.to_thread(_do_score)
        
        technicals_dict = {
            'rsi': getattr(tech_report, 'rsi', 50.0),
            'rsi_signal': getattr(tech_report, 'rsi_signal', 'neutral'),
            'macd': getattr(tech_report, 'macd', 0.0),
            'macd_signal': getattr(tech_report, 'macd_signal', 0.0),
            'macd_cross': getattr(tech_report, 'macd_cross', 'none'),
            'adx': getattr(tech_report, 'adx', 20.0),
            'atr': getattr(tech_report, 'atr', 0.0),
            'vwap': getattr(tech_report, 'vwap', 0.0),
            'ema8': getattr(tech_report, 'ema8', 0.0),
            'ema21': getattr(tech_report, 'ema21', 0.0),
            'ema50': getattr(tech_report, 'ema50', 0.0),
            'ema200': getattr(tech_report, 'ema200', 0.0),
            'trend': getattr(tech_report, 'trend', 'neutral'),
            'support': getattr(tech_report, 'support', 0.0),
            'resistance': getattr(tech_report, 'resistance', 0.0),
            'rel_volume': getattr(tech_report, 'rel_volume', 1.0),
            'squeeze': getattr(tech_report, 'squeeze', False),
            'pattern': getattr(tech_report, 'pattern', 'none'),
        }

        wallstreet_dict = getattr(score, 'wallstreet', {}) or {}

        response_payload = {
            'ticker': ticker,
            'company_name': score.company_name,
            'price': score.current_price,
            'sector': score.sector,
            'composite_score': score.composite_score,
            'technical_score': score.technical_score,
            'fundamental_score': score.fundamental_score,
            'sentiment_score': score.sentiment_score,
            'insider_score': score.insider_score,
            'multibagger_score': score.multibagger_score,
            'recommendation': score.recommendation,
            'signals': score.signals,
            'target_price': score.target_price,
            'stop_loss': score.stop_loss,
            'risk_reward': score.risk_reward,
            'swing_timeframe': score.swing_timeframe,
            'pattern': score.pattern,
            'fundamentals': {'price': score.current_price, 'company_name': score.company_name, 'sector': score.sector},
            'technicals': technicals_dict,
            'wallstreet_intelligence': wallstreet_dict,
            'microstructure': getattr(score, 'microstructure', {}),
            'whale_signals': getattr(score, 'whale_signals', {}),
            'market_regime': getattr(score, 'market_regime', {}),
            'agent_consensus': getattr(score, 'agent_consensus', {}),
        }
        return _sanitize_for_json(response_payload)
    except Exception as e:
        logger.error(f"Stock score error {ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/{ticker}/chart')
async def get_chart(ticker: str, period: str = '6mo', interval: str = '1d'):
    ticker = ticker.upper()
    try:
        df = await asyncio.to_thread(get_ohlcv, ticker, period, interval)
        if df is None:
            raise HTTPException(status_code=404, detail=f'No chart data for {ticker}')
        return {'ticker': ticker, 'period': period, 'interval': interval, 'data': df.to_dict('records')}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/{ticker}/news')
async def get_news(ticker: str):
    ticker = ticker.upper()
    try:
        def _fetch():
            news = get_company_news(ticker, days=14)
            return _get_sentiment().analyze_news_batch(news)
        scored = await asyncio.to_thread(_fetch)
        return {'ticker': ticker, 'count': len(scored), 'news': scored}
    except Exception as e:
        return {'ticker': ticker, 'count': 0, 'news': [], 'error': str(e)}


@router.get('/{ticker}/insiders')
async def get_insiders(ticker: str):
    ticker = ticker.upper()
    try:
        sentiment = await asyncio.to_thread(_get_insider().get_insider_sentiment, ticker)
        return {'ticker': ticker, **sentiment}
    except Exception as e:
        return {'ticker': ticker, 'score': 50, 'trades': [], 'error': str(e)}


@router.get('/{ticker}/similar')
async def get_similar(ticker: str):
    ticker = ticker.upper()
    try:
        from backend.data.universe import get_universe

        def _compute():
            universe_sample = get_universe()[:30]
            corr = _get_sector().get_correlation_matrix([ticker] + universe_sample[:15])
            ticker_corr = {k: v.get(ticker, 0) for k, v in corr.items() if k != ticker}
            similar = sorted(ticker_corr.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
            return [{'ticker': t, 'correlation': round(c, 3)} for t, c in similar]

        similar = await asyncio.to_thread(_compute)
        return {'ticker': ticker, 'similar': similar}
    except Exception as e:
        return {'ticker': ticker, 'similar': [], 'error': str(e)}


@router.get('/{ticker}/intelligence')
async def get_intelligence(ticker: str):
    ticker = ticker.upper()
    try:
        from backend.data.fetchers import get_all_rss_news, get_global_rss_news

        def _fetch():
            all_news = get_all_rss_news() + get_global_rss_news()
            signals = _get_cross().get_cross_linked_signals(ticker, all_news)
            return signals

        signals = await asyncio.to_thread(_fetch)
        return {
            'ticker': ticker,
            'signals': [
                {
                    'headline': s.source_headline,
                    'company': s.source_company,
                    'country': s.source_country,
                    'direction': s.impact_direction,
                    'explanation': s.explanation,
                    'confidence': s.confidence,
                    'event_type': s.event_type,
                }
                for s in signals
            ],
        }
    except Exception as e:
        return {'ticker': ticker, 'signals': [], 'error': str(e)}
