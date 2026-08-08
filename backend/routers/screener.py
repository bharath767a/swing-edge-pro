"""
SwingEdge Pro — Screener Router
All sync calls wrapped in asyncio.to_thread to prevent blocking.
"""
import asyncio
import logging
from fastapi import APIRouter, Query, BackgroundTasks
from typing import Optional

router = APIRouter(prefix='/api/screener', tags=['screener'])
logger = logging.getLogger(__name__)

# Lazy-init and cache
_scorer = None
_cached_picks = []  # Cache the last screener results


def _get_scorer():
    global _scorer
    if _scorer is None:
        from backend.engine.scoring import MasterScorer
        _scorer = MasterScorer()
    return _scorer


def _run_screen(limit: int = 50):
    """Synchronous screening — runs in thread pool."""
    scorer = _get_scorer()
    return scorer.get_top_picks(n=limit)


def _format_pick(p) -> dict:
    return {
        'ticker': p.ticker,
        'company_name': p.company_name,
        'price': p.current_price,
        'change_pct': getattr(p, 'change_pct', None),
        'volume': getattr(p, 'volume', None),
        'market_cap': getattr(p, 'market_cap', None),
        'sector': p.sector,
        'composite_score': p.composite_score,
        'technical_score': p.technical_score,
        'fundamental_score': p.fundamental_score,
        'sentiment_score': p.sentiment_score,
        'insider_score': p.insider_score,
        'multibagger_score': p.multibagger_score,
        'recommendation': p.recommendation,
        'pattern': p.pattern,
        'target_price': p.target_price,
        'stop_loss': p.stop_loss,
        'risk_reward': p.risk_reward,
        'swing_timeframe': p.swing_timeframe,
        'signals': p.signals,
    }


@router.get('')
async def screen_stocks(
    min_score: float = Query(0, ge=0, le=100),
    max_price: float = Query(20.0),
    min_price: float = Query(0.50),
    min_volume: int = Query(100000),
    sector: Optional[str] = None,
    sort_by: str = Query('composite_score'),
    limit: int = Query(50, le=200),
):
    """Screen stocks by multiple criteria. Results are fetched from a thread pool."""
    global _cached_picks
    try:
        picks = await asyncio.to_thread(_run_screen, limit)
        _cached_picks = picks  # Update cache
    except Exception as e:
        logger.warning(f"Live screener failed, using cache: {e}")
        picks = _cached_picks

    results = []
    for p in picks:
        if p.composite_score < min_score:
            continue
        if p.current_price is not None:
            if p.current_price < min_price or p.current_price > max_price:
                continue
        if sector and hasattr(p, 'sector') and p.sector and p.sector != sector:
            continue
        results.append(_format_pick(p))

    # Sort
    if sort_by in ('composite_score', 'technical_score', 'multibagger_score', 'sentiment_score'):
        results.sort(key=lambda x: x.get(sort_by, 0) or 0, reverse=True)

    return {'count': len(results), 'stocks': results}


@router.get('/top-picks')
async def get_top_picks():
    """Get top 25 swing picks of the day."""
    global _cached_picks
    try:
        picks = await asyncio.to_thread(_run_screen, 100)
        _cached_picks = picks
    except Exception as e:
        logger.warning(f"Top picks failed, using cache: {e}")
        picks = _cached_picks

    results = [_format_pick(p) for p in picks if p.composite_score >= 50]
    results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
    return {'count': len(results[:25]), 'stocks': results[:25]}


@router.get('/multibagger')
async def get_multibagger_candidates():
    """Get top multibagger candidates (score ≥ 75)."""
    try:
        def _fetch():
            from backend.engine.multibagger import MultibaggerEngine
            mb = MultibaggerEngine()
            return mb.get_top_multibagger_candidates(n=20)

        candidates = await asyncio.to_thread(_fetch)
        return {'count': len(candidates), 'candidates': candidates}
    except Exception as e:
        logger.error(f"Multibagger error: {e}")
        return {'count': 0, 'candidates': [], 'error': str(e)}


@router.post('/refresh')
async def refresh_screener(background_tasks: BackgroundTasks):
    """Trigger background screener refresh (clears cache)."""
    def _reset():
        global _scorer, _cached_picks
        _scorer = None
        _cached_picks = []

    background_tasks.add_task(_reset)
    return {'status': 'refresh_queued', 'message': 'Screener will refresh on next request'}
