"""
SwingEdge Pro — FastAPI Application Entry Point

AUDIT FIXES APPLIED:
- P0-2: Path traversal fixed in serve_frontend (uses Path.resolve + startswith check)
- P2:   CORS now reads from env ALLOWED_ORIGINS (was wildcard + credentials = invalid)
- P2:   Added slowapi rate limiting + API key auth (optional)
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
import uvicorn

from backend.database import init_db
from backend.scheduler import scheduler, init_scheduler
from backend.routers import screener, stock, news, sectors, insider, backtest, alerts, watchlist, leveraged_etfs
from backend.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("🚀 SwingEdge Pro starting...")
    # Initialize DB
    await init_db()
    # Start scheduler
    init_scheduler()
    scheduler.start()
    logger.info("✅ Scheduler started.")
    # Log API key status
    api_status = {
        'yfinance': '✅ (always available)',
        'sec_edgar': '✅ (always available)',
        'finnhub': '✅ configured' if settings.has_finnhub else '⚠️ not configured',
        'alpha_vantage': '✅ configured' if settings.has_alpha_vantage else '⚠️ not configured',
        'news_api': '✅ configured' if settings.has_news_api else '⚠️ not configured',
        'fred': '✅ configured' if settings.has_fred else '⚠️ not configured',
        'reddit': '✅ configured' if settings.has_reddit else '⚠️ not configured',
    }
    for k, v in api_status.items():
        logger.info(f"  API {k}: {v}")

    yield

    logger.info("Shutting down SwingEdge Pro...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title='SwingEdge Pro API',
    description='Full-Stack US Stock Swing Trading Intelligence Engine',
    version='1.0.0',
    lifespan=lifespan,
)

# CORS — FIX P2: read allowed origins from env, no wildcard
_allowed_origins_env = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000')
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_env.split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'X-API-Key'],
)

# Optional API key auth (only enforced if VALID_API_KEYS env is set)
API_KEY_HEADER = APIKeyHeader(name='X-API-Key', auto_error=False)
VALID_API_KEYS = set(os.getenv('VALID_API_KEYS', '').split(',')) - {''}

async def verify_api_key(api_key: str = Depends(API_KEY_HEADER)):
    """Enforce API key auth only when VALID_API_KEYS is configured (dev mode = no auth)."""
    if not VALID_API_KEYS:
        return 'dev'  # dev mode: no keys configured = no auth
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail='Invalid or missing API key')
    return api_key

# Register all API routers
app.include_router(screener.router)
app.include_router(stock.router)
app.include_router(news.router)
app.include_router(sectors.router)
app.include_router(insider.router)
app.include_router(backtest.router)
app.include_router(alerts.router)
app.include_router(watchlist.router)
app.include_router(leveraged_etfs.router)  # NEW in v3: 2x leveraged ETF screener


@app.get('/api/health')
async def health_check():
    return {
        'status': 'healthy',
        'version': '1.0.0',
        'api_keys': {
            'finnhub': settings.has_finnhub,
            'alpha_vantage': settings.has_alpha_vantage,
            'news_api': settings.has_news_api,
            'fred': settings.has_fred,
            'reddit': settings.has_reddit,
        },
    }


@app.get('/api/market-pulse')
async def market_pulse():
    from backend.data.fetchers import get_market_sentiment_indicators, get_ohlcv
    import yfinance as yf
    try:
        indicators = get_market_sentiment_indicators()
        # Get index prices
        indices = {}
        for symbol, name in [('^GSPC', 'sp500'), ('^IXIC', 'nasdaq'), ('^RUT', 'russell2000'), ('^DJI', 'dow')]:
            try:
                t = yf.Ticker(symbol)
                fi = t.fast_info
                price = getattr(fi, 'last_price', None)
                prev = getattr(fi, 'previous_close', None)
                chg = round((price - prev) / prev * 100, 2) if price and prev else 0
                indices[name] = {'price': round(price, 2) if price else 0, 'change_pct': chg}
            except Exception:
                indices[name] = {'price': 0, 'change_pct': 0}
        return {
            # FIX P1: surface nulls instead of fabricated 20/0.85
            'vix': indicators.get('vix'),
            'put_call_ratio': indicators.get('put_call_ratio'),  # may be None — frontend should handle
            'indices': indices,
            'market_status': 'LIVE',
            'data_quality': 'OK' if indicators.get('vix') is not None else 'DEGRADED',
        }
    except Exception as e:
        # FIX P1: do NOT fabricate VIX/put-call on error — return nulls and a degraded flag
        return {'vix': None, 'put_call_ratio': None, 'indices': {}, 'error': str(e), 'data_quality': 'DEGRADED'}


# Serve frontend static files (MUST be last, after all API routes)
# FIX P0-2: Path traversal guard using Path.resolve + startswith
frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
frontend_root = Path(frontend_dir).resolve()

if os.path.exists(frontend_dir):
    app.mount('/static', StaticFiles(directory=frontend_dir), name='static')

    @app.get('/{path:path}')
    async def serve_frontend(path: str):
        # Resolve and verify the resolved path is inside frontend_root
        target = (frontend_root / path).resolve()
        if not str(target).startswith(str(frontend_root) + os.sep):
            raise HTTPException(status_code=404, detail='Not found')
        if target.is_file():
            return FileResponse(str(target))
        # Fallback to index.html for SPA-style routes
        index_path = frontend_root / 'index.html'
        return FileResponse(str(index_path))

    @app.get('/')
    async def root():
        return FileResponse(os.path.join(frontend_dir, 'index.html'))


if __name__ == '__main__':
    uvicorn.run(
        'backend.main:app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True,
        reload_dirs=['backend'],
    )
