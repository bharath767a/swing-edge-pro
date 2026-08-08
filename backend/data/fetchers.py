"""
SwingEdge Pro — Data Fetchers
All external data source connectors with caching and graceful degradation.
"""
import time
import logging
import socket
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup
from backend.config import settings

logger = logging.getLogger(__name__)

SEC_HEADERS = {'User-Agent': settings.SEC_USER_AGENT}
REQUEST_TIMEOUT = 8

# ─────────────────────────────────────────────────────────────────────────────
# In-memory News Cache (5-minute TTL)
# ─────────────────────────────────────────────────────────────────────────────
_news_cache: Dict[str, Any] = {}
_NEWS_CACHE_TTL = 300  # 5 minutes

def _cache_get(key: str):
    entry = _news_cache.get(key)
    if entry and (time.time() - entry['ts']) < _NEWS_CACHE_TTL:
        return entry['data']
    return None

def _cache_set(key: str, data):
    _news_cache[key] = {'data': data, 'ts': time.time()}

# ─────────────────────────────────────────────────────────────────────────────
# yfinance Fetchers (No key required)
# ─────────────────────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> Optional[Dict]:
    """Fetch comprehensive stock info from yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None:
            return None
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        prev_close = info.get('previousClose') or price
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
        avg_vol = info.get('averageVolume') or info.get('averageVolume10days') or 1
        cur_vol = info.get('volume') or info.get('regularMarketVolume') or 0
        return {
            'ticker': ticker,
            'company_name': info.get('longName') or info.get('shortName') or ticker,
            'price': price,
            'prev_close': prev_close,
            'change_pct': round(change_pct, 2),
            'volume': cur_vol,
            'avg_volume': avg_vol,
            'rel_volume': round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0,
            'market_cap': info.get('marketCap'),
            'float_shares': info.get('floatShares'),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
            'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            'pe_ratio': info.get('trailingPE'),
            'forward_pe': info.get('forwardPE'),
            'peg': info.get('pegRatio'),
            'pb': info.get('priceToBook'),
            'ps': info.get('priceToSalesTrailing12Months'),
            'ev_ebitda': info.get('enterpriseToEbitda'),
            'roe': info.get('returnOnEquity'),
            'roa': info.get('returnOnAssets'),  # FIX P0-7: was mislabelled as 'roic'
            'roic': None,  # FIX P0-7: yfinance doesn't expose ROIC; must be computed downstream
            'debt_equity': info.get('debtToEquity'),
            'current_ratio': info.get('currentRatio'),
            'quick_ratio': info.get('quickRatio'),
            'revenue_growth': info.get('revenueGrowth'),
            'earnings_growth': info.get('earningsGrowth'),
            'gross_margin': info.get('grossMargins'),
            'operating_margin': info.get('operatingMargins'),
            'net_margin': info.get('profitMargins'),
            'revenue_ttm': info.get('totalRevenue'),
            'earnings_ttm': info.get('netIncomeToCommon'),
            'insider_ownership': info.get('heldPercentInsiders'),
            'institutional_ownership': info.get('heldPercentInstitutions'),
            'short_float': info.get('shortPercentOfFloat'),
            'days_to_cover': info.get('shortRatio'),
            'description': info.get('longBusinessSummary', ''),
            'website': info.get('website', ''),
        }
    except Exception as e:
        logger.warning(f"yfinance info error {ticker}: {e}")
        return None


def get_ohlcv(ticker: str, period: str = '6mo', interval: str = '1d') -> Optional[pd.DataFrame]:
    """Fetch OHLCV data as a DataFrame."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return None
        df.reset_index(inplace=True)
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        # Ensure standard columns
        rename_map = {'datetime': 'date', 'index': 'date'}
        df.rename(columns=rename_map, inplace=True)
        # Convert datetime index to string
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']].dropna()
        return df
    except Exception as e:
        logger.warning(f"OHLCV error {ticker}: {e}")
        return None


def get_earnings_calendar() -> List[Dict]:
    """Get upcoming earnings from yfinance."""
    try:
        # Use a few bellwether tickers to show upcoming earnings
        results = []
        for ticker in ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL']:
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is not None and not cal.empty:
                for col in cal.columns:
                    row = cal[col]
                    results.append({'ticker': ticker, 'date': str(col), 'event': row.to_dict()})
        return results
    except Exception as e:
        logger.warning(f"Earnings calendar error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Finnhub Fetchers (free tier: 60 req/min)
# ─────────────────────────────────────────────────────────────────────────────

def _finnhub_get(endpoint: str, params: dict = {}) -> Optional[Any]:
    """Generic Finnhub API call."""
    if not settings.has_finnhub:
        return None
    try:
        url = f"https://finnhub.io/api/v1/{endpoint}"
        params['token'] = settings.FINNHUB_API_KEY
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            logger.warning("Finnhub rate limit hit. Sleeping 2s.")
            time.sleep(2)
    except Exception as e:
        logger.warning(f"Finnhub error {endpoint}: {e}")
    return None


def get_company_news(ticker: str, days: int = 7) -> List[Dict]:
    """Fetch company news from Finnhub."""
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = _finnhub_get('company-news', {
        'symbol': ticker,
        'from': from_date.strftime('%Y-%m-%d'),
        'to': to_date.strftime('%Y-%m-%d'),
    })
    if not data:
        # Fallback to yfinance news
        return get_stock_news_yf(ticker)
    articles = []
    for item in data[:20]:  # cap at 20
        articles.append({
            'headline': item.get('headline', ''),
            'source': item.get('source', ''),
            'url': item.get('url', ''),
            'published_at': datetime.fromtimestamp(item.get('datetime', 0)).isoformat(),
            'summary': item.get('summary', ''),
            'ticker': ticker,
        })
    return articles


def get_stock_news_yf(ticker: str) -> List[Dict]:
    """Fallback: get news from yfinance."""
    try:
        t = yf.Ticker(ticker)
        news = t.news
        results = []
        for item in (news or [])[:10]:
            results.append({
                'headline': item.get('title', ''),
                'source': item.get('publisher', ''),
                'url': item.get('link', ''),
                'published_at': datetime.fromtimestamp(item.get('providerPublishTime', 0)).isoformat(),
                'summary': '',
                'ticker': ticker,
            })
        return results
    except Exception as e:
        logger.warning(f"yfinance news error {ticker}: {e}")
        return []


def get_finnhub_insider_trades(ticker: str) -> List[Dict]:
    """Fetch insider trades from Finnhub."""
    data = _finnhub_get('stock/insider-transactions', {'symbol': ticker})
    if not data:
        return []
    trades = []
    for item in (data.get('data') or [])[:30]:
        trade_type = item.get('transactionType', '')
        shares = item.get('share', 0)
        price = item.get('price', 0)
        trades.append({
            'ticker': ticker,
            'filer_name': item.get('name', 'Unknown'),
            'filer_title': '',
            'trade_type': 'P' if 'Purchase' in trade_type or 'Buy' in trade_type else 'S',
            'shares': shares,
            'price': price,
            'value': shares * price if price else 0,
            'trade_date': item.get('transactionDate', ''),
            'filed_date': item.get('filingDate', ''),
            'form_type': '4',
            'source': 'finnhub',
        })
    return trades


def get_earnings_surprise(ticker: str) -> List[Dict]:
    """Fetch EPS surprise history from Finnhub."""
    data = _finnhub_get('stock/earnings', {'symbol': ticker, 'limit': 8})
    if not data:
        return []
    results = []
    for item in (data or []):
        actual = item.get('actual')
        estimate = item.get('estimate')
        surprise_pct = 0
        if estimate and actual and estimate != 0:
            surprise_pct = ((actual - estimate) / abs(estimate)) * 100
        results.append({
            'period': item.get('period', ''),
            'actual': actual,
            'estimate': estimate,
            'surprise_pct': round(surprise_pct, 2),
        })
    return results


def get_analyst_recommendations(ticker: str) -> Dict:
    """Get analyst buy/hold/sell counts from Finnhub."""
    data = _finnhub_get('stock/recommendation', {'symbol': ticker})
    if not data or not data:
        return {'buy': 0, 'hold': 0, 'sell': 0, 'strong_buy': 0, 'strong_sell': 0}
    latest = data[0] if data else {}
    return {
        'buy': latest.get('buy', 0),
        'hold': latest.get('hold', 0),
        'sell': latest.get('sell', 0),
        'strong_buy': latest.get('strongBuy', 0),
        'strong_sell': latest.get('strongSell', 0),
        'period': latest.get('period', ''),
    }


def get_price_target(ticker: str) -> Dict:
    """Get analyst consensus price target from Finnhub."""
    data = _finnhub_get('stock/price-target', {'symbol': ticker})
    if not data:
        return {}
    return {
        'target_high': data.get('targetHigh'),
        'target_low': data.get('targetLow'),
        'target_mean': data.get('targetMean'),
        'target_median': data.get('targetMedian'),
        'analyst_count': data.get('numberOfAnalysts'),
        'last_updated': data.get('lastUpdated'),
    }


def get_social_sentiment(ticker: str) -> Dict:
    """Get social media sentiment from Finnhub."""
    data = _finnhub_get('stock/social-sentiment', {'symbol': ticker})
    if not data:
        return {'reddit_mentions': 0, 'reddit_score': 0, 'twitter_mentions': 0, 'twitter_score': 0}
    reddit = data.get('reddit', [])
    twitter = data.get('twitter', [])
    r_mentions = sum(r.get('mention', 0) for r in reddit[-7:]) if reddit else 0
    r_score = sum(r.get('score', 0) for r in reddit[-7:]) / len(reddit[-7:]) if reddit else 0
    t_mentions = sum(t.get('mention', 0) for t in twitter[-7:]) if twitter else 0
    t_score = sum(t.get('score', 0) for t in twitter[-7:]) / len(twitter[-7:]) if twitter else 0
    return {
        'reddit_mentions': r_mentions,
        'reddit_score': round(r_score, 3),
        'twitter_mentions': t_mentions,
        'twitter_score': round(t_score, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SEC EDGAR Fetchers (No key required)
# ─────────────────────────────────────────────────────────────────────────────

_CIK_CACHE: Dict[str, str] = {}


def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Lookup SEC EDGAR CIK number for a ticker."""
    if ticker in _CIK_CACHE:
        return _CIK_CACHE[ticker]
    try:
        resp = requests.get(
            'https://www.sec.gov/files/company_tickers.json',
            headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            for _, v in data.items():
                if v.get('ticker', '').upper() == ticker.upper():
                    cik = str(v['cik_str']).zfill(10)
                    _CIK_CACHE[ticker] = cik
                    return cik
    except Exception as e:
        logger.warning(f"CIK lookup error {ticker}: {e}")
    return None


def get_form4_filings(ticker: str) -> List[Dict]:
    """Fetch SEC EDGAR Form 4 filings (insider trades) for a ticker.

    AUDIT FIX P0-6: Now downloads and parses the actual Form 4 XML to extract
    real trade_type, shares, price, value, and filer_title. Previously returned
    zeros for all transaction fields, making EDGAR-sourced insider data useless.
    """
    try:
        import xml.etree.ElementTree as ET
        from_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
            f"&dateRange=custom&startdt={from_date}&forms=4"
        )
        resp = requests.get(url, headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        hits = data.get('hits', {}).get('hits', [])
        trades = []
        for hit in hits[:20]:
            src = hit.get('_source', {})
            display_names = src.get('display_names', [])
            entity_name = display_names[0].get('name', 'Unknown') if display_names else 'Unknown'
            filed = src.get('file_date', '')
            filing_url = src.get('_source_url') or src.get('url')

            # FIX P0-6: actually parse the Form 4 XML for transaction details
            detail = _parse_form4_detail(filing_url) if filing_url else {}

            shares = detail.get('shares', 0)
            price = detail.get('price', 0)
            trades.append({
                'ticker': ticker,
                'filer_name': entity_name,
                'filer_title': detail.get('filer_title', ''),
                'trade_type': detail.get('trade_type', 'S'),  # P/S/A/M — was hardcoded 'P'
                'shares': shares,                            # was hardcoded 0
                'price': price,                              # was hardcoded 0
                'value': shares * price if price else 0,     # was hardcoded 0
                'trade_date': detail.get('trade_date') or filed,
                'filed_date': filed,
                'form_type': '4',
                'source': 'edgar',
                'filing_url': filing_url or '',
            })
        return trades
    except Exception as e:
        logger.warning(f"EDGAR Form4 error {ticker}: {e}")
        return []


def _parse_form4_detail(filing_url: str) -> dict:
    """Download and parse a Form 4 XML filing for transaction details.

    Extracts:
    - transactionActionCode: P (Purchase), S (Sale), A (Award), M (Exercise), F (Tax)
    - transactionShares, transactionPricePerShare
    - officerTitle, transactionDate
    """
    try:
        import xml.etree.ElementTree as ET
        if not filing_url:
            return {}
        resp = requests.get(filing_url, headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {}
        root = ET.fromstring(resp.content)
        # Form 4 XML namespace — handle both common variants
        ns = {'ns4': 'http://www.sec.gov/edgar/form4'}
        # Try non-derivative transactions first (open-market buys/sells)
        non_deriv = root.findall('.//ns4:nonDerivativeTransaction', ns)
        derivative = root.findall('.//ns4:derivativeTransaction', ns)
        tx_list = non_deriv + derivative
        if not tx_list:
            # Fallback: try without namespace
            tx_list = root.findall('.//nonDerivativeTransaction') + root.findall('.//derivativeTransaction')
        if not tx_list:
            return {}
        tx = tx_list[0]

        def _text(parent, path, default=''):
            node = parent.find(path, ns)
            if node is None:
                node = parent.find(path.replace('ns4:', ''),  # no-namespace fallback
                                   ) if 'ns4:' in path else None
            if node is None:
                return default
            return node.text or default

        def _value(parent, path, default=0.0):
            v = _text(parent, path, None)
            if v is None or v == '':
                return default
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        trade_type = _text(tx, 'ns4:transactionActionCode', 'S')
        shares = _value(tx, 'ns4:transactionShares/ns4:value', 0.0)
        price = _value(tx, 'ns4:transactionPricePerShare/ns4:value', 0.0)
        filer_title = _text(root, './/ns4:officerTitle', '')
        trade_date = _text(root, './/ns4:transactionDate/ns4:value', '')

        return {
            'trade_type': trade_type,
            'shares': shares,
            'price': price,
            'filer_title': filer_title,
            'trade_date': trade_date,
        }
    except Exception as e:
        logger.debug(f"Form 4 detail parse error: {e}")
        return {}


def get_institutional_holders(ticker: str) -> List[Dict]:
    """Get institutional holders from yfinance."""
    try:
        t = yf.Ticker(ticker)
        holders = t.institutional_holders
        if holders is None or holders.empty:
            return []
        holders.columns = [c.lower().replace(' ', '_') for c in holders.columns]
        return holders.head(10).to_dict('records')
    except Exception as e:
        logger.warning(f"Institutional holders error {ticker}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# NewsAPI Fetcher
# ─────────────────────────────────────────────────────────────────────────────

def get_global_news(query: str, language: str = 'en', page_size: int = 20) -> List[Dict]:
    """Fetch news from NewsAPI."""
    if not settings.has_news_api:
        return get_rss_news_for_query(query)
    try:
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': query,
            'language': language,
            'pageSize': page_size,
            'sortBy': 'publishedAt',
            'apiKey': settings.NEWS_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            articles = resp.json().get('articles', [])
            return [
                {
                    'headline': a.get('title', ''),
                    'source': a.get('source', {}).get('name', ''),
                    'url': a.get('url', ''),
                    'published_at': a.get('publishedAt', ''),
                    'summary': a.get('description', '') or a.get('content', ''),
                    'ticker': None,
                }
                for a in articles if a.get('title') and '[Removed]' not in a.get('title', '')
            ]
    except Exception as e:
        logger.warning(f"NewsAPI error: {e}")
    return get_rss_news_for_query(query)


def get_market_news() -> List[Dict]:
    """Get top business/market news."""
    if not settings.has_news_api:
        return get_all_rss_news()
    try:
        url = 'https://newsapi.org/v2/top-headlines'
        params = {'category': 'business', 'language': 'en', 'pageSize': 30, 'apiKey': settings.NEWS_API_KEY}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            articles = resp.json().get('articles', [])
            return [
                {'headline': a.get('title', ''), 'source': a.get('source', {}).get('name', ''),
                 'url': a.get('url', ''), 'published_at': a.get('publishedAt', ''),
                 'summary': a.get('description', ''), 'ticker': None}
                for a in articles if a.get('title') and '[Removed]' not in a.get('title', '')
            ]
    except Exception as e:
        logger.warning(f"NewsAPI headlines error: {e}")
    return get_all_rss_news()


# ─────────────────────────────────────────────────────────────────────────────
# RSS Fetchers (No key required — always available fallback)
# ─────────────────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex'),
    ('MarketWatch', 'https://feeds.marketwatch.com/marketwatch/topstories/'),
    ('Reuters Business', 'https://feeds.reuters.com/reuters/businessNews'),
    ('CNBC Top News', 'https://www.cnbc.com/id/100003114/device/rss/rss.html'),
    ('Seeking Alpha', 'https://seekingalpha.com/market_currents.xml'),
    ('Benzinga', 'https://www.benzinga.com/feed'),
    ('Investopedia', 'https://www.investopedia.com/feeds/rss.aspx'),
]

GLOBAL_RSS_FEEDS = [
    ('Nikkei Asia', 'https://asia.nikkei.com/rss/feed/nar'),
    ('Reuters World', 'https://feeds.reuters.com/Reuters/worldNews'),
    ('BBC Business', 'https://feeds.bbci.co.uk/news/business/rss.xml'),
    ('FT', 'https://www.ft.com/rss/home/us'),
    ('Bloomberg Markets', 'https://feeds.bloomberg.com/markets/news.rss'),
]


def _parse_feed(name: str, url: str) -> List[Dict]:
    """Parse a single RSS feed with timeout protection."""
    articles = []
    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(6)
        feed = feedparser.parse(url)
        socket.setdefaulttimeout(old_timeout)
        for entry in (feed.entries or [])[:10]:
            published = entry.get('published', entry.get('updated', ''))
            articles.append({
                'headline': entry.get('title', ''),
                'source': name,
                'url': entry.get('link', ''),
                'published_at': published,
                'summary': entry.get('summary', '') or entry.get('description', ''),
                'ticker': None,
            })
    except Exception as e:
        logger.debug(f"RSS parse error {name}: {e}")
    return articles


def get_all_rss_news() -> List[Dict]:
    """Fetch from all domestic RSS feeds in parallel with 5-min cache."""
    cached = _cache_get('domestic_rss')
    if cached is not None:
        return cached
    all_articles = []
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(_parse_feed, name, url): name for name, url in RSS_FEEDS}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception:
                pass
    _cache_set('domestic_rss', all_articles)
    return all_articles


def get_global_rss_news() -> List[Dict]:
    """Fetch from all global RSS feeds in parallel with 5-min cache."""
    cached = _cache_get('global_rss')
    if cached is not None:
        return cached
    all_articles = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_parse_feed, name, url): name for name, url in GLOBAL_RSS_FEEDS}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception:
                pass
    _cache_set('global_rss', all_articles)
    return all_articles


def get_rss_news_for_query(query: str) -> List[Dict]:
    """Search for query term in RSS news headlines."""
    all_news = get_all_rss_news() + get_global_rss_news()
    query_lower = query.lower()
    return [a for a in all_news if query_lower in a.get('headline', '').lower() or query_lower in a.get('summary', '').lower()]


def detect_political_signals(text: str) -> Dict:
    """Check if text contains political/presidential recommendations affecting stocks."""
    text_lower = text.lower()
    keywords = settings.POLITICAL_KEYWORDS
    found = [kw for kw in keywords if kw in text_lower]
    if not found:
        return {'is_political': False, 'keywords': [], 'confidence': 0.0}
    # Identify companies or sectors mentioned
    mentioned_companies = []
    for company in settings.GLOBAL_COMPANY_MAP.keys():
        if company.lower() in text_lower:
            mentioned_companies.append(company)
    sector_keywords = {
        'semiconductor': ['XLK', 'NVDA', 'AMD', 'INTC', 'MU'],
        'defense': ['LMT', 'RTX', 'GD', 'NOC', 'HII'],
        'energy': ['XOM', 'CVX', 'COP'],
        'pharmaceutical': ['PFE', 'MRK', 'ABBV'],
        'steel': ['X', 'NUE', 'CLF'],
        'automobile': ['F', 'GM', 'TSLA'],
    }
    affected_tickers = []
    for sector, tickers in sector_keywords.items():
        if sector in text_lower:
            affected_tickers.extend(tickers)
    for co in mentioned_companies:
        affected_tickers.extend(settings.GLOBAL_COMPANY_MAP.get(co, []))
    # Determine direction
    positive_words = ['great', 'buy', 'invest', 'beautiful', 'tremendous', 'deal', 'wonderful']
    negative_words = ['sanction', 'ban', 'tariff', 'bad', 'terrible', 'fraud', 'investigate']
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    direction = 'positive' if pos_count >= neg_count else 'negative'
    return {
        'is_political': True,
        'keywords': found,
        'direction': direction,
        'confidence': min(1.0, len(found) * 0.25 + (0.5 if mentioned_companies else 0)),
        'affected_tickers': list(set(affected_tickers))[:10],
        'mentioned_companies': mentioned_companies,
    }


def detect_analyst_actions(text: str) -> Dict:
    """Detect analyst upgrades/downgrades/initiations in a news headline."""
    text_lower = text.lower()
    result = {'action': None, 'firm': '', 'target_price': None, 'ticker': None}
    action_patterns = {
        'upgrade': ['upgrade', 'raised to buy', 'raises to buy', 'upgraded to'],
        'downgrade': ['downgrade', 'cut to sell', 'lowered to sell', 'downgraded to', 'cuts to'],
        'initiate': ['initiates', 'initiated', 'starts coverage', 'begins coverage', 'initiating'],
        'reiterate': ['reiterates', 'maintains', 'reaffirms', 'keeps'],
        'price_target': ['price target', 'pt to', 'pt raised', 'pt cut', 'raises pt', 'cuts pt'],
    }
    for action, patterns in action_patterns.items():
        for pat in patterns:
            if pat in text_lower:
                result['action'] = action
                break
        if result['action']:
            break
    # Try to find analyst firm
    for firm in settings.ANALYST_FIRMS:
        if firm.lower() in text_lower:
            result['firm'] = firm
            break
    # Try to extract price target (e.g., "$45" or "to $45")
    import re
    price_match = re.search(r'\$([\d,]+\.?\d*)', text)
    if price_match:
        try:
            result['target_price'] = float(price_match.group(1).replace(',', ''))
        except ValueError:
            pass
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FRED API Fetcher
# ─────────────────────────────────────────────────────────────────────────────

def get_macro_indicator(series_id: str, limit: int = 12) -> List[Dict]:
    """Fetch macro indicator from FRED."""
    if not settings.has_fred:
        return []
    try:
        url = 'https://api.stlouisfed.org/fred/series/observations'
        params = {
            'series_id': series_id,
            'api_key': settings.FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': limit,
        }
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            obs = resp.json().get('observations', [])
            return [{'date': o['date'], 'value': o['value']} for o in obs if o['value'] != '.']
    except Exception as e:
        logger.warning(f"FRED error {series_id}: {e}")
    return []


def get_market_sentiment_indicators() -> Dict:
    """Fetch VIX, put/call ratio, and market breadth from Yahoo Finance.

    AUDIT FIX P1: VIX returns None on failure (was hardcoded 20.0).
    put_call_ratio remains None unless a real source is configured.
    """
    result = {'vix': None, 'put_call_ratio': None, 'advance_decline': None}
    try:
        vix = yf.Ticker('^VIX')
        vix_info = vix.fast_info
        vix_price = getattr(vix_info, 'last_price', None)
        # FIX P1: do NOT fabricate — return None when VIX fetch fails
        if vix_price is not None and vix_price > 0:
            result['vix'] = round(float(vix_price), 2)
        # S&P breadth proxies via ETFs
        spy = yf.Ticker('SPY')
        spy_hist = spy.history(period='5d')
        if not spy_hist.empty:
            result['spy_5d_change'] = round(
                (spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[0]) / spy_hist['Close'].iloc[0] * 100, 2
            )
        # Put/call ratio — FIX P1: do NOT fabricate 0.85; leave None unless real source wired
        # To enable: subscribe to CBOE daily stats CSV (free) or Polygon options endpoint (paid)
        result['put_call_ratio'] = None
    except Exception as e:
        logger.warning(f"Market sentiment error: {e}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Reddit PRAW Fetcher
# ─────────────────────────────────────────────────────────────────────────────

_reddit_instance = None


def _get_reddit():
    global _reddit_instance
    if _reddit_instance:
        return _reddit_instance
    if not settings.has_reddit:
        return None
    try:
        import praw
        _reddit_instance = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )
        return _reddit_instance
    except Exception as e:
        logger.warning(f"Reddit init error: {e}")
        return None


def get_wsb_mentions(ticker: str, limit: int = 100) -> Dict:
    """Get WSB mention count and sentiment for a ticker."""
    reddit = _get_reddit()
    if not reddit:
        return {'mentions': 0, 'score': 0.0, 'bullish_count': 0, 'bearish_count': 0}
    try:
        subreddit = reddit.subreddit('wallstreetbets')
        posts = list(subreddit.search(ticker, limit=limit, sort='new', time_filter='week'))
        mentions = len(posts)
        if mentions == 0:
            return {'mentions': 0, 'score': 0.0, 'bullish_count': 0, 'bearish_count': 0}
        # Simple bullish/bearish keyword count
        bullish_words = ['moon', 'calls', 'buy', 'long', 'bull', 'squeeze', 'yolo', 'rocket', 'lambo', 'tendies']
        bearish_words = ['puts', 'short', 'sell', 'bear', 'crash', 'dump', 'baghold']
        bull_count, bear_count = 0, 0
        for post in posts:
            text = (post.title + ' ' + (post.selftext or '')).lower()
            bull_count += sum(1 for w in bullish_words if w in text)
            bear_count += sum(1 for w in bearish_words if w in text)
        total = bull_count + bear_count or 1
        score = (bull_count - bear_count) / total
        return {'mentions': mentions, 'score': round(score, 3), 'bullish_count': bull_count, 'bearish_count': bear_count}
    except Exception as e:
        logger.warning(f"WSB mentions error {ticker}: {e}")
        return {'mentions': 0, 'score': 0.0, 'bullish_count': 0, 'bearish_count': 0}


# ─────────────────────────────────────────────────────────────────────────────
# Alpha Vantage Fallback
# ─────────────────────────────────────────────────────────────────────────────

def get_fundamentals_av(ticker: str) -> Optional[Dict]:
    """Fetch fundamental overview from Alpha Vantage."""
    if not settings.has_alpha_vantage:
        return None
    try:
        url = 'https://www.alphavantage.co/query'
        params = {'function': 'OVERVIEW', 'symbol': ticker, 'apikey': settings.ALPHA_VANTAGE_KEY}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if 'Symbol' not in data:
                return None
            def _f(key: str) -> Optional[float]:
                val = data.get(key)
                try:
                    return float(val) if val and val != 'None' and val != '-' else None
                except (TypeError, ValueError):
                    return None
            return {
                'pe_ratio': _f('PERatio'),
                'forward_pe': _f('ForwardPE'),
                'peg': _f('PEGRatio'),
                'pb': _f('PriceToBookRatio'),
                'ps': _f('PriceToSalesRatioTTM'),
                'ev_ebitda': _f('EVToEBITDA'),
                'roe': _f('ReturnOnEquityTTM'),
                'debt_equity': _f('DebtToEquityRatio'),
                'revenue_growth': _f('QuarterlyRevenueGrowthYOY'),
                'earnings_growth': _f('QuarterlyEarningsGrowthYOY'),
                'gross_margin': _f('GrossProfitTTM'),
                'insider_ownership': _f('PercentInsiders'),
                'institutional_ownership': _f('PercentInstitutions'),
                'short_float': _f('ShortPercentFloat'),
                'description': data.get('Description', ''),
                'sector': data.get('Sector', ''),
                'industry': data.get('Industry', ''),
                '52wk_high': _f('52WeekHigh'),
                '52wk_low': _f('52WeekLow'),
            }
    except Exception as e:
        logger.warning(f"Alpha Vantage error {ticker}: {e}")
    return None


def get_earnings_av(ticker: str) -> List[Dict]:
    """Fetch earnings history from Alpha Vantage."""
    if not settings.has_alpha_vantage:
        return []
    try:
        url = 'https://www.alphavantage.co/query'
        params = {'function': 'EARNINGS', 'symbol': ticker, 'apikey': settings.ALPHA_VANTAGE_KEY}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            quarterly = data.get('quarterlyEarnings', [])
            return quarterly[:8]
    except Exception as e:
        logger.warning(f"Alpha Vantage earnings error {ticker}: {e}")
    return []
