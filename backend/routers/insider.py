"""
SwingEdge Pro — Insider Trading Intelligence Router
All heavy SEC Form 4 and Finnhub fetches run concurrently via ThreadPoolExecutor.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter
from backend.engine.insider_tracker import InsiderTracker
from backend.data.universe import MULTIBAGGER_UNIVERSE

router = APIRouter(prefix='/api/insiders', tags=['insiders'])
logger = logging.getLogger(__name__)
_tracker = None

def _get_tracker():
    global _tracker
    if _tracker is None:
        _tracker = InsiderTracker()
    return _tracker

@router.get('/recent')
async def get_recent_insiders():
    try:
        def _fetch():
            tracker = _get_tracker()
            all_trades = []
            sample_tickers = MULTIBAGGER_UNIVERSE[:15]

            with ThreadPoolExecutor(max_workers=10) as executor:
                future_map = {executor.submit(tracker.fetch_insider_trades, ticker): ticker for ticker in sample_tickers}
                for future in as_completed(future_map):
                    try:
                        trades = future.result()
                        if trades:
                            all_trades.extend(trades)
                    except Exception:
                        pass

            all_trades.sort(key=lambda x: str(x.get('filed_date', '')), reverse=True)
            return all_trades[:50]

        trades = await asyncio.to_thread(_fetch)
        return {'count': len(trades), 'trades': trades}
    except Exception as e:
        logger.error(f"Recent insiders error: {e}")
        return {'count': 0, 'trades': [], 'error': str(e)}

@router.get('/cluster')
async def get_cluster_buys():
    try:
        def _fetch():
            tracker = _get_tracker()
            clusters = []
            sample_tickers = MULTIBAGGER_UNIVERSE[:20]

            def _check_cluster(ticker):
                try:
                    trades = tracker.fetch_insider_trades(ticker)
                    cluster = tracker.detect_cluster_buying(ticker, trades)
                    if cluster and cluster.get('detected'):
                        return {'ticker': ticker, **cluster}
                except Exception:
                    pass
                return None

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(_check_cluster, t) for t in sample_tickers]
                for f in as_completed(futures):
                    res = f.result()
                    if res:
                        clusters.append(res)

            return clusters

        clusters = await asyncio.to_thread(_fetch)
        return {'count': len(clusters), 'clusters': clusters}
    except Exception as e:
        logger.error(f"Cluster buys error: {e}")
        return {'count': 0, 'clusters': [], 'error': str(e)}

@router.get('/{ticker}')
async def get_ticker_insiders(ticker: str):
    ticker = ticker.upper()
    try:
        sentiment = await asyncio.to_thread(_get_tracker().get_insider_sentiment, ticker)
        return {'ticker': ticker, **sentiment}
    except Exception as e:
        return {'ticker': ticker, 'score': 50, 'trades': [], 'error': str(e)}
