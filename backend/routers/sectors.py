import asyncio
from fastapi import APIRouter
from backend.engine.sector_rotation import SectorRotationEngine
import logging

router = APIRouter(prefix='/api/sectors', tags=['sectors'])
logger = logging.getLogger(__name__)
_rotation = SectorRotationEngine()

# Cached sector data to avoid repeated slow fetches
_sector_cache = {}

@router.get('')
async def get_sectors():
    """Get all sector performances. Uses thread executor for sync yfinance calls."""
    try:
        # Run the heavy synchronous calls in a thread pool
        performance = await asyncio.to_thread(_rotation.get_sector_performance)
        risk = await asyncio.to_thread(_rotation.detect_risk_on_off)
        rotation = _rotation.detect_rotation_signal()
        # Cache for next request
        _sector_cache['performance'] = performance
        _sector_cache['risk'] = risk
        _sector_cache['rotation'] = rotation
        return {'sectors': list(performance.values()), 'risk_signal': risk, 'rotation': rotation}
    except Exception as e:
        logger.error(f"Sector performance error: {e}")
        # Return cached data if available
        if _sector_cache:
            return {'sectors': list(_sector_cache.get('performance', {}).values()),
                    'risk_signal': _sector_cache.get('risk', {}),
                    'rotation': _sector_cache.get('rotation', {}),
                    'cached': True}
        return {'sectors': [], 'risk_signal': {}, 'rotation': {}, 'error': str(e)}

@router.get('/rotation')
async def get_rotation():
    try:
        risk = await asyncio.to_thread(_rotation.detect_risk_on_off)
        rotation = _rotation.detect_rotation_signal()
        return {**rotation, 'risk_mode': risk}
    except Exception as e:
        return {'error': str(e)}

@router.get('/global')
async def get_global_correlation():
    try:
        corr = await asyncio.to_thread(_rotation.get_global_market_correlation)
        return corr
    except Exception as e:
        return {'error': str(e), 'correlation': {}}

@router.get('/correlation')
async def get_correlation():
    try:
        from backend.config import settings
        sector_etfs = list(settings.SECTORS.values())
        corr = await asyncio.to_thread(_rotation.get_correlation_matrix, sector_etfs)
        return {'correlation': corr, 'etfs': sector_etfs}
    except Exception as e:
        return {'error': str(e), 'correlation': {}}

@router.get('/{sector}/leaders')
async def get_sector_leaders(sector: str):
    try:
        leaders = await asyncio.to_thread(_rotation.get_sector_leaders, sector, 5)
        return {'sector': sector, 'leaders': leaders}
    except Exception as e:
        return {'sector': sector, 'leaders': [], 'error': str(e)}
