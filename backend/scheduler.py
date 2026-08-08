"""
SwingEdge Pro — Background Scheduler
Runs periodic data refresh jobs.

AUDIT FIX P2:
- News refresh now uses a watermark (last processed article URL) to avoid re-analyzing
  the same articles every 30 min (was infinite CPU burn).
- Scheduler is idempotent — safe to call refresh_market_data() multiple times.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Watermark for news dedup — set of article URLs already processed
_PROCESSED_NEWS_URLS: set = set()
_PROCESSED_NEWS_URLS_MAX = 5000  # cap memory


async def refresh_market_data():
    """Refresh prices for watchlist stocks (persisted in DB)."""
    logger.info("[Scheduler] Refreshing market data...")
    try:
        from backend.database import AsyncSessionLocal
        from backend.models.stock import WatchlistItem
        from backend.data.fetchers import get_stock_info
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(WatchlistItem).limit(20))
            items = result.scalars().all()
            for item in items:
                try:
                    get_stock_info(item.ticker)
                except Exception:
                    pass
    except Exception as e:
        # Fallback to legacy in-memory if DB unavailable
        logger.debug(f"DB-based watchlist refresh failed, using empty: {e}")


async def refresh_news_sentiment():
    """Fetch new news and run sentiment + cross-linking.

    AUDIT FIX P2: Uses _PROCESSED_NEWS_URLS watermark to skip articles already analyzed.
    Prevents unbounded CPU burn as news volume grows.
    """
    logger.info("[Scheduler] Refreshing news and sentiment...")
    try:
        from backend.data.fetchers import get_all_rss_news, get_global_rss_news
        from backend.engine.sentiment import SentimentEngine
        from backend.engine.cross_linking import CrossLinkEngine
        sentiment = SentimentEngine()
        cross = CrossLinkEngine()
        all_news = get_all_rss_news() + get_global_rss_news()

        # FIX P2: filter out already-processed articles
        new_news = [a for a in all_news if a.get('url') and a['url'] not in _PROCESSED_NEWS_URLS]
        if not new_news:
            logger.info(f"[Scheduler] No new news since last refresh ({len(all_news)} total, all already processed)")
            return
        logger.info(f"[Scheduler] Processing {len(new_news)} new articles (skipping {len(all_news) - len(new_news)} already-processed)")

        sentiment.analyze_news_batch(new_news)
        cross.process_all_news(new_news)

        # Update watermark
        for a in new_news:
            if a.get('url'):
                _PROCESSED_NEWS_URLS.add(a['url'])
        # Cap memory: if we exceed max, drop oldest half
        if len(_PROCESSED_NEWS_URLS) > _PROCESSED_NEWS_URLS_MAX:
            to_drop = len(_PROCESSED_NEWS_URLS) - _PROCESSED_NEWS_URLS_MAX
            _PROCESSED_NEWS_URLS.difference_update(list(_PROCESSED_NEWS_URLS)[:to_drop])
    except Exception as e:
        logger.error(f"News refresh error: {e}")


async def refresh_sector_data():
    """Refresh sector performance data."""
    logger.info("[Scheduler] Refreshing sector data...")
    try:
        from backend.engine.sector_rotation import SectorRotationEngine
        engine = SectorRotationEngine()
        engine.get_sector_performance()
    except Exception as e:
        logger.error(f"Sector refresh error: {e}")


async def refresh_macro_data():
    """Refresh macro indicators."""
    logger.info("[Scheduler] Refreshing macro data...")
    try:
        from backend.data.fetchers import get_market_sentiment_indicators, get_macro_indicator
        get_market_sentiment_indicators()
        for series in ['FEDFUNDS', 'CPIAUCSL', 'UNRATE', 'T10Y2Y']:
            get_macro_indicator(series)
    except Exception as e:
        logger.error(f"Macro refresh error: {e}")


def init_scheduler():
    """Register all scheduled jobs."""
    # Every 15 minutes: refresh watchlist prices
    scheduler.add_job(refresh_market_data, IntervalTrigger(minutes=15), id='market_data', replace_existing=True)
    # Every 30 minutes: refresh news
    scheduler.add_job(refresh_news_sentiment, IntervalTrigger(minutes=30), id='news_sentiment', replace_existing=True)
    # Every hour: refresh sectors
    scheduler.add_job(refresh_sector_data, IntervalTrigger(hours=1), id='sector_data', replace_existing=True)
    # Daily 6am ET: refresh macro
    scheduler.add_job(refresh_macro_data, CronTrigger(hour=6, minute=0, timezone='America/New_York'), id='macro_data', replace_existing=True)
    logger.info("[Scheduler] All jobs registered.")
