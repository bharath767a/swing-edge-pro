"""
SwingEdge Pro v3 — 2x Leveraged ETF Universe (Expanded)
Comprehensive list of 2x leveraged ETFs across all asset classes,
including the AXS/Direxion/T-REX/GraniteShares/Leverage Shares
single-stock 2x ETF family (NVDU, TSLT, SNDG, etc.)

CATEGORIES:
- Single-Stock 2x (NEW v3.3) — tracks ONE underlying stock 2x daily
  These are what swing traders want for leveraged stock exposure.
  Examples: SNDG (2x SNDK), NVDU (2x NVDA), TSLT (2x TSLA), AAPU (2x AAPL)
- Equity Index (broad market)
- Sector Equity (tech, financials, energy, etc.)
- International / Regional
- Commodities (gold, silver, oil, gas)
- Rates / Treasuries

Each ETF is tagged with:
- direction: 'LONG' or 'SHORT'
- underlying: the index/asset/stock it tracks 2x of
- underlying_ticker: for single-stock ETFs, the parent stock ticker
- asset_class: single_stock / equity / sector / commodity / fx / rates / thematic
- typical_spread_bps: estimated bid-ask spread (liquidity proxy)
- decay_risk_base: baseline decay risk for this product (LOW/MEDIUM/HIGH)
"""
from typing import List, Dict

# ── 2x Leveraged ETF Universe ───────────────────────────────────────────────
LEVERAGED_ETF_UNIVERSE: List[Dict] = [
    # ═══════════════════════════════════════════════════════════════════════
    # SINGLE-STOCK 2x ETFs (NEW v3.3)
    # These track ONE stock 2x daily — ideal for swing traders who want
    # leveraged exposure to a specific name without using margin.
    # US-listed (AXS / Direxion / T-REX / GraniteShares families)
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'NVDU', 'direction': 'LONG',  'underlying': 'NVIDIA',         'underlying_ticker': 'NVDA', 'asset_class': 'single_stock', 'typical_spread_bps': 15, 'decay_risk_base': 'HIGH'},
    {'ticker': 'TSLT', 'direction': 'LONG',  'underlying': 'Tesla',          'underlying_ticker': 'TSLA', 'asset_class': 'single_stock', 'typical_spread_bps': 20, 'decay_risk_base': 'HIGH'},
    {'ticker': 'AAPU', 'direction': 'LONG',  'underlying': 'Apple',          'underlying_ticker': 'AAPL', 'asset_class': 'single_stock', 'typical_spread_bps': 12, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'MSFU', 'direction': 'LONG',  'underlying': 'Microsoft',      'underlying_ticker': 'MSFT', 'asset_class': 'single_stock', 'typical_spread_bps': 12, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'AMZU', 'direction': 'LONG',  'underlying': 'Amazon',         'underlying_ticker': 'AMZN', 'asset_class': 'single_stock', 'typical_spread_bps': 15, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'METU', 'direction': 'LONG',  'underlying': 'Meta',           'underlying_ticker': 'META', 'asset_class': 'single_stock', 'typical_spread_bps': 15, 'decay_risk_base': 'HIGH'},
    {'ticker': 'AMDU', 'direction': 'LONG',  'underlying': 'AMD',            'underlying_ticker': 'AMD',  'asset_class': 'single_stock', 'typical_spread_bps': 20, 'decay_risk_base': 'HIGH'},
    {'ticker': 'NFLU', 'direction': 'LONG',  'underlying': 'Netflix',        'underlying_ticker': 'NFLX', 'asset_class': 'single_stock', 'typical_spread_bps': 20, 'decay_risk_base': 'HIGH'},
    {'ticker': 'CONL', 'direction': 'LONG',  'underlying': 'Coinbase',       'underlying_ticker': 'COIN', 'asset_class': 'single_stock', 'typical_spread_bps': 30, 'decay_risk_base': 'HIGH'},
    # US-listed inverse (short) single-stock ETFs
    {'ticker': 'NVD',  'direction': 'SHORT', 'underlying': 'NVIDIA',         'underlying_ticker': 'NVDA', 'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'HIGH'},
    {'ticker': 'TSDD', 'direction': 'SHORT', 'underlying': 'Tesla',          'underlying_ticker': 'TSLA', 'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'HIGH'},
    {'ticker': 'AAPD', 'direction': 'SHORT', 'underlying': 'Apple',          'underlying_ticker': 'AAPL', 'asset_class': 'single_stock', 'typical_spread_bps': 15, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'MSFD', 'direction': 'SHORT', 'underlying': 'Microsoft',      'underlying_ticker': 'MSFT', 'asset_class': 'single_stock', 'typical_spread_bps': 15, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'AMZD', 'direction': 'SHORT', 'underlying': 'Amazon',         'underlying_ticker': 'AMZN', 'asset_class': 'single_stock', 'typical_spread_bps': 20, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'METD', 'direction': 'SHORT', 'underlying': 'Meta',           'underlying_ticker': 'META', 'asset_class': 'single_stock', 'typical_spread_bps': 20, 'decay_risk_base': 'HIGH'},
    {'ticker': 'AMDD', 'direction': 'SHORT', 'underlying': 'AMD',            'underlying_ticker': 'AMD',  'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'HIGH'},
    # Leverage Shares family (European-listed, trades in USD on Nasdaq/BTS)
    # These include names not available as US-listed 2x ETFs
    {'ticker': 'SNDG', 'direction': 'LONG',  'underlying': 'SanDisk',        'underlying_ticker': 'SNDK', 'asset_class': 'single_stock', 'typical_spread_bps': 30, 'decay_risk_base': 'HIGH'},
    {'ticker': 'NVDG', 'direction': 'LONG',  'underlying': 'NVIDIA',         'underlying_ticker': 'NVDA', 'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'HIGH'},
    {'ticker': 'METG', 'direction': 'LONG',  'underlying': 'Meta',           'underlying_ticker': 'META', 'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'HIGH'},
    {'ticker': 'TSLG', 'direction': 'LONG',  'underlying': 'Tesla',          'underlying_ticker': 'TSLA', 'asset_class': 'single_stock', 'typical_spread_bps': 30, 'decay_risk_base': 'HIGH'},
    {'ticker': 'AMZG', 'direction': 'LONG',  'underlying': 'Amazon',         'underlying_ticker': 'AMZN', 'asset_class': 'single_stock', 'typical_spread_bps': 25, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'AMDG', 'direction': 'LONG',  'underlying': 'AMD',            'underlying_ticker': 'AMD',  'asset_class': 'single_stock', 'typical_spread_bps': 30, 'decay_risk_base': 'HIGH'},

    # ═══════════════════════════════════════════════════════════════════════
    # EQUITY INDEX (Broad Market) — most liquid, lowest decay
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'SSO', 'direction': 'LONG',  'underlying': 'S&P 500',           'asset_class': 'equity',     'typical_spread_bps': 2, 'decay_risk_base': 'LOW'},
    {'ticker': 'QLD', 'direction': 'LONG',  'underlying': 'Nasdaq 100',        'asset_class': 'equity',     'typical_spread_bps': 2, 'decay_risk_base': 'LOW'},
    {'ticker': 'DDM', 'direction': 'LONG',  'underlying': 'Dow 30',            'asset_class': 'equity',     'typical_spread_bps': 4, 'decay_risk_base': 'LOW'},
    {'ticker': 'MVV', 'direction': 'LONG',  'underlying': 'MidCap 400',        'asset_class': 'equity',     'typical_spread_bps': 8, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'UWM', 'direction': 'LONG',  'underlying': 'Russell 2000',      'asset_class': 'equity',     'typical_spread_bps': 6, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'SDS', 'direction': 'SHORT', 'underlying': 'S&P 500',           'asset_class': 'equity',     'typical_spread_bps': 2, 'decay_risk_base': 'LOW'},
    {'ticker': 'QID', 'direction': 'SHORT', 'underlying': 'Nasdaq 100',        'asset_class': 'equity',     'typical_spread_bps': 2, 'decay_risk_base': 'LOW'},
    {'ticker': 'DXD', 'direction': 'SHORT', 'underlying': 'Dow 30',            'asset_class': 'equity',     'typical_spread_bps': 6, 'decay_risk_base': 'LOW'},
    {'ticker': 'MZZ', 'direction': 'SHORT', 'underlying': 'MidCap 400',        'asset_class': 'equity',     'typical_spread_bps': 12,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'TWM', 'direction': 'SHORT', 'underlying': 'Russell 2000',      'asset_class': 'equity',     'typical_spread_bps': 6, 'decay_risk_base': 'MEDIUM'},

    # ═══════════════════════════════════════════════════════════════════════
    # SECTOR EQUITY — medium liquidity, sector-dependent decay
    # NOTE: FINU, SFZ, TLL removed in v3.2.2 (delisted by ProShares in 2023)
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'ROM', 'direction': 'LONG',  'underlying': 'Technology',        'asset_class': 'sector',     'typical_spread_bps': 8, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'UXI', 'direction': 'LONG',  'underlying': 'Industrials',       'asset_class': 'sector',     'typical_spread_bps': 10,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'UCC', 'direction': 'LONG',  'underlying': 'Consumer Disc',     'asset_class': 'sector',     'typical_spread_bps': 10,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'UPW', 'direction': 'LONG',  'underlying': 'Utilities',         'asset_class': 'sector',     'typical_spread_bps': 12,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'URE', 'direction': 'LONG',  'underlying': 'Real Estate',       'asset_class': 'sector',     'typical_spread_bps': 12,'decay_risk_base': 'HIGH'},
    {'ticker': 'BIB', 'direction': 'LONG',  'underlying': 'Nasdaq Biotech',    'asset_class': 'sector',     'typical_spread_bps': 10,'decay_risk_base': 'HIGH'},
    {'ticker': 'REW', 'direction': 'SHORT', 'underlying': 'Technology',        'asset_class': 'sector',     'typical_spread_bps': 12,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'SIJ', 'direction': 'SHORT', 'underlying': 'Industrials',       'asset_class': 'sector',     'typical_spread_bps': 15,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'SCC', 'direction': 'SHORT', 'underlying': 'Consumer Disc',     'asset_class': 'sector',     'typical_spread_bps': 12,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'SDP', 'direction': 'SHORT', 'underlying': 'Utilities',         'asset_class': 'sector',     'typical_spread_bps': 15,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'SRS', 'direction': 'SHORT', 'underlying': 'Real Estate',       'asset_class': 'sector',     'typical_spread_bps': 15,'decay_risk_base': 'HIGH'},
    {'ticker': 'BIS', 'direction': 'SHORT', 'underlying': 'Nasdaq Biotech',    'asset_class': 'sector',     'typical_spread_bps': 12,'decay_risk_base': 'HIGH'},

    # ═══════════════════════════════════════════════════════════════════════
    # INTERNATIONAL / REGIONAL — higher decay, currency overlay
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'EET', 'direction': 'LONG',  'underlying': 'Emerging Markets',  'asset_class': 'thematic',   'typical_spread_bps': 15,'decay_risk_base': 'HIGH'},
    {'ticker': 'EFO', 'direction': 'LONG',  'underlying': 'Developed Markets', 'asset_class': 'thematic',   'typical_spread_bps': 20,'decay_risk_base': 'HIGH'},
    {'ticker': 'YINN','direction': 'LONG',  'underlying': 'China',             'asset_class': 'thematic',   'typical_spread_bps': 12,'decay_risk_base': 'HIGH'},
    {'ticker': 'INDL','direction': 'LONG',  'underlying': 'India',             'asset_class': 'thematic',   'typical_spread_bps': 20,'decay_risk_base': 'HIGH'},
    {'ticker': 'YANG','direction': 'SHORT', 'underlying': 'China',             'asset_class': 'thematic',   'typical_spread_bps': 12,'decay_risk_base': 'HIGH'},

    # ═══════════════════════════════════════════════════════════════════════
    # COMMODITIES — high decay (choppy markets destroy these)
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'UGL', 'direction': 'LONG',  'underlying': 'Gold',              'asset_class': 'commodity',  'typical_spread_bps': 15,'decay_risk_base': 'HIGH'},
    {'ticker': 'AGQ', 'direction': 'LONG',  'underlying': 'Silver',            'asset_class': 'commodity',  'typical_spread_bps': 15,'decay_risk_base': 'HIGH'},
    {'ticker': 'UCO', 'direction': 'LONG',  'underlying': 'Crude Oil',         'asset_class': 'commodity',  'typical_spread_bps': 8, 'decay_risk_base': 'HIGH'},
    {'ticker': 'BOIL','direction': 'LONG',  'underlying': 'Natural Gas',       'asset_class': 'commodity',  'typical_spread_bps': 10,'decay_risk_base': 'HIGH'},
    {'ticker': 'GLL', 'direction': 'SHORT', 'underlying': 'Gold',              'asset_class': 'commodity',  'typical_spread_bps': 20,'decay_risk_base': 'HIGH'},
    {'ticker': 'ZSL', 'direction': 'SHORT', 'underlying': 'Silver',            'asset_class': 'commodity',  'typical_spread_bps': 20,'decay_risk_base': 'HIGH'},
    {'ticker': 'SCO', 'direction': 'SHORT', 'underlying': 'Crude Oil',         'asset_class': 'commodity',  'typical_spread_bps': 10,'decay_risk_base': 'HIGH'},

    # ═══════════════════════════════════════════════════════════════════════
    # RATES / TREASURIES — sensitive to Fed, high duration
    # ═══════════════════════════════════════════════════════════════════════
    {'ticker': 'UBT', 'direction': 'LONG',  'underlying': '20+ Year Treasury', 'asset_class': 'rates',      'typical_spread_bps': 8, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'UST', 'direction': 'LONG',  'underlying': '7-10 Year Treasury','asset_class': 'rates',      'typical_spread_bps': 10,'decay_risk_base': 'MEDIUM'},
    {'ticker': 'TBT', 'direction': 'SHORT', 'underlying': '20+ Year Treasury', 'asset_class': 'rates',      'typical_spread_bps': 2, 'decay_risk_base': 'MEDIUM'},
    {'ticker': 'PST', 'direction': 'SHORT', 'underlying': '7-10 Year Treasury','asset_class': 'rates',      'typical_spread_bps': 8, 'decay_risk_base': 'MEDIUM'},
]


def get_all_leveraged_etfs() -> List[Dict]:
    """Return the full 2x leveraged ETF universe."""
    return LEVERAGED_ETF_UNIVERSE


def get_long_leveraged_etfs() -> List[Dict]:
    """Return only 2x long ETFs."""
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'LONG']


def get_short_leveraged_etfs() -> List[Dict]:
    """Return only 2x short ETFs."""
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == 'SHORT']


def get_etf_by_ticker(ticker: str) -> Dict:
    """Look up an ETF by ticker."""
    ticker = ticker.upper()
    for e in LEVERAGED_ETF_UNIVERSE:
        if e['ticker'] == ticker:
            return e
    return {}


def get_etfs_by_asset_class(asset_class: str) -> List[Dict]:
    """Filter by asset class (single_stock / equity / sector / commodity / rates / thematic)."""
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == asset_class.lower()]


def get_etfs_by_direction(direction: str) -> List[Dict]:
    """Filter by direction ('LONG' or 'SHORT')."""
    direction = direction.upper()
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == direction]


def get_single_stock_etfs() -> List[Dict]:
    """Return only single-stock 2x ETFs (NVDU, TSLT, SNDG, etc.)."""
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == 'single_stock']


def get_etfs_by_underlying(underlying_ticker: str) -> List[Dict]:
    """Find all leveraged ETFs tracking a specific underlying stock.

    Example: get_etfs_by_underlying('NVDA') returns NVDU (long) and NVD (short).
    """
    underlying_ticker = underlying_ticker.upper()
    return [e for e in LEVERAGED_ETF_UNIVERSE if e.get('underlying_ticker') == underlying_ticker]
