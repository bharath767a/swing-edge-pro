"""
SwingEdge Pro v3 — 2x Leveraged ETF Swing Screener Router
Endpoints for identifying quality, high-probability 2x long/short ETF swing trades.

Endpoints:
- GET /api/leveraged-etfs                    — screen all (with filters)
- GET /api/leveraged-etfs/long               — top 2x long candidates
- GET /api/leveraged-etfs/short              — top 2x short candidates
- GET /api/leveraged-etfs/{ticker}           — analyze specific ETF
- GET /api/leveraged-etfs/universe/summary   — universe stats
"""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Query

from backend.engine.leveraged_etf import LeveragedETFEngine

router = APIRouter(prefix='/api/leveraged-etfs', tags=['leveraged-etfs'])
logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = LeveragedETFEngine()
    return _engine


def _format_signal(s) -> dict:
    """Convert LeveragedETFSignal dataclass to dict for JSON response."""
    return {
        'ticker': s.ticker,
        'direction': s.direction,
        'underlying': s.underlying,
        'asset_class': s.asset_class,
        'current_price': s.current_price,
        'composite_score': s.composite_score,
        'quality_score': s.quality_score,
        'pattern_score': s.pattern_score,
        'regime_alignment_score': s.regime_alignment_score,
        'decay_risk': s.decay_risk,
        'estimated_daily_decay_pct': s.estimated_daily_decay_pct,
        'volatility_drag_5d_pct': s.volatility_drag_5d_pct,
        'entry_price': s.entry_price,
        'stop_loss': s.stop_loss,
        'target_price': s.target_price,
        'risk_reward': s.risk_reward,
        'recommended_hold_days': s.recommended_hold_days,
        'pattern': s.pattern,
        'trend': s.trend,
        'rsi': s.rsi,
        'adx': s.adx,
        'atr_pct': s.atr_pct,
        'rel_volume': s.rel_volume,
        'regime_aligned': s.regime_aligned,
        'catalyst_warning': s.catalyst_warning,
        'rationale': s.rationale,
    }


@router.get('')
async def screen_leveraged_etfs(
    direction: Optional[str] = Query(None, description='LONG / SHORT / both'),
    asset_class: Optional[str] = Query(None, description='equity / sector / commodity / rates / thematic'),
    min_score: float = Query(50, ge=0, le=100, description='Minimum composite score'),
    limit: int = Query(20, le=50, description='Max results'),
):
    """Screen the 2x leveraged ETF universe for swing trade candidates.

    Returns ranked list with decay risk, regime alignment, entry/stop/target,
    and recommended holding period for each ETF.

    FIX v3.2.2: Lowered default min_score from 60 to 50 (many real candidates
    score 50-60 in neutral regimes). Also returns regime info + data quality
    so frontend can show why results may be empty (e.g. regime = sideways
    means no 2x ETFs are recommended — that's correct, not an error).
    """
    try:
        engine = _get_engine()
        signals = await asyncio.to_thread(
            engine.screen,
            direction, asset_class, min_score, limit
        )
        # Include regime info so frontend can explain why results may be empty
        regime_data = engine.regime.evaluate_regime()
        return {
            'count': len(signals),
            'signals': [_format_signal(s) for s in signals],
            'regime': {
                'regime': regime_data.get('regime', 'NEUTRAL'),
                'risk_multiplier': regime_data.get('risk_multiplier', 1.0),
                'data_quality': regime_data.get('data_quality', 'OK'),
                'vix_level': regime_data.get('vix_level'),
            },
            'note': (
                'No qualifying ETFs in current regime — this is expected in sideways/volatile markets. '
                '2x longs need BULLISH regime; 2x shorts need HIGH_VOLATILITY_DEFENSIVE.'
            ) if len(signals) == 0 else None,
        }
    except Exception as e:
        logger.error(f"Leveraged ETF screen error: {e}", exc_info=True)
        return {
            'count': 0,
            'signals': [],
            'error': str(e),
            'error_type': type(e).__name__,
            'suggestion': 'Check server logs. Most common cause: yfinance rate limiting or network issue.',
        }


@router.get('/long')
async def top_long_candidates(limit: int = Query(10, le=20)):
    """Top 2x long ETF swing candidates (regime-permitting)."""
    try:
        engine = _get_engine()
        signals = await asyncio.to_thread(engine.get_top_long_candidates, limit)
        return {'count': len(signals), 'direction': 'LONG', 'signals': [_format_signal(s) for s in signals]}
    except Exception as e:
        logger.error(f"Long candidates error: {e}")
        return {'count': 0, 'signals': [], 'error': str(e)}


@router.get('/short')
async def top_short_candidates(limit: int = Query(10, le=20)):
    """Top 2x short ETF swing candidates (regime-permitting)."""
    try:
        engine = _get_engine()
        signals = await asyncio.to_thread(engine.get_top_short_candidates, limit)
        return {'count': len(signals), 'direction': 'SHORT', 'signals': [_format_signal(s) for s in signals]}
    except Exception as e:
        logger.error(f"Short candidates error: {e}")
        return {'count': 0, 'signals': [], 'error': str(e)}


@router.get('/{ticker}')
async def analyze_etf(ticker: str):
    """Analyze a specific 2x leveraged ETF ticker."""
    ticker = ticker.upper()
    try:
        engine = _get_engine()
        signal = await asyncio.to_thread(engine.analyze_ticker, ticker)
        if signal is None:
            return {'error': f'{ticker} not in leveraged ETF universe', 'available_etfs': [
                e['ticker'] for e in engine.get_universe_summary().get('etfs', [])
            ]}
        return _format_signal(signal)
    except Exception as e:
        logger.error(f"ETF analyze error {ticker}: {e}", exc_info=True)
        return {'error': str(e)}


@router.get('/universe/summary')
async def universe_summary():
    """Stats for the 2x leveraged ETF universe."""
    engine = _get_engine()
    return engine.get_universe_summary()
