"""
SwingEdge Pro v3 — 2x Leveraged ETF Universe
Comprehensive list of 2x leveraged long AND short ETFs across all asset classes.

CATEGORIES:
- Equity Index (broad market)
- Sector Equity (tech, financials, energy, etc.)
- International / Regional
- Commodities (gold, silver, oil, gas)
- Currencies
- Rates / Treasuries
- Thematic (biotech, China, India, etc.)

Each ETF is tagged with:
- direction: 'LONG' or 'SHORT'
- underlying: the index/asset it tracks 2x of
- asset_class: equity / sector / commodity / fx / rates / thematic
- typical_spread_bps: estimated bid-ask spread (liquidity proxy)
- decay_risk_base: baseline decay risk for this product (LOW/MEDIUM/HIGH)
"""
from typing import List, Dict

# ── 2x Leveraged ETF Universe ───────────────────────────────────────────────
LEVERAGED_ETF_UNIVERSE: List[Dict] = [
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
    """Filter by asset class (equity, sector, commodity, fx, rates, thematic)."""
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['asset_class'] == asset_class.lower()]


def get_etfs_by_direction(direction: str) -> List[Dict]:
    """Filter by direction ('LONG' or 'SHORT')."""
    direction = direction.upper()
    return [e for e in LEVERAGED_ETF_UNIVERSE if e['direction'] == direction]
