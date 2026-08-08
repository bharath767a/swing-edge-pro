"""
SwingEdge Pro — Central Configuration
Loads from .env file with graceful degradation if keys are missing.

AUDIT FIX P2: Removed silent .env.example → .env copy (was hiding misconfiguration).
Now logs a clear warning when .env is missing.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
if not env_path.exists():
    # FIX P2: do NOT silently copy .env.example — log a clear warning
    logger.warning(
        f".env file not found at {env_path}. "
        f"Create one from .env.example and add your API keys for full functionality. "
        f"The engine will run in degraded mode with only yfinance + RSS + SEC EDGAR."
    )

load_dotenv(env_path)

class Settings:
    # ── API Keys ──────────────────────────────────────────────────────────────
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    ALPHA_VANTAGE_KEY: str = os.getenv("ALPHA_VANTAGE_KEY", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "SwingEdgePro/1.0")
    POLYGON_IO_KEY: str = os.getenv("POLYGON_IO_KEY", "")
    UNUSUAL_WHALES_KEY: str = os.getenv("UNUSUAL_WHALES_KEY", "")
    EODHD_KEY: str = os.getenv("EODHD_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── API availability flags (graceful degradation) ────────────────────────
    @property
    def has_finnhub(self) -> bool: return bool(self.FINNHUB_API_KEY)
    @property
    def has_alpha_vantage(self) -> bool: return bool(self.ALPHA_VANTAGE_KEY)
    @property
    def has_news_api(self) -> bool: return bool(self.NEWS_API_KEY)
    @property
    def has_fred(self) -> bool: return bool(self.FRED_API_KEY)
    @property
    def has_reddit(self) -> bool: return bool(self.REDDIT_CLIENT_ID and self.REDDIT_CLIENT_SECRET)
    @property
    def has_polygon(self) -> bool: return bool(self.POLYGON_IO_KEY)
    @property
    def has_openai(self) -> bool: return bool(self.OPENAI_API_KEY)

    # ── App Config ────────────────────────────────────────────────────────────
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./swingengine.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Cache TTLs (seconds) ──────────────────────────────────────────────────
    PRICE_CACHE_TTL: int = 900          # 15 minutes
    FUNDAMENTALS_CACHE_TTL: int = 86400 # 24 hours
    NEWS_CACHE_TTL: int = 1800          # 30 minutes
    TECHNICALS_CACHE_TTL: int = 3600    # 1 hour
    SECTOR_CACHE_TTL: int = 3600        # 1 hour

    # ── Trading Config ────────────────────────────────────────────────────────
    PENNY_STOCK_MIN_PRICE: float = 0.50
    PENNY_STOCK_MAX_PRICE: float = 20.0
    MIN_VOLUME: int = 100_000
    TARGET_RETURN_PCT: float = 10.0
    STOP_LOSS_ATR_MULT: float = 2.0
    MIN_RISK_REWARD: float = 2.0

    # ── SEC EDGAR ─────────────────────────────────────────────────────────────
    SEC_USER_AGENT: str = "SwingEdgePro contact@swingedge.pro"

    # ── Sectors (GICS) with ETF tickers ──────────────────────────────────────
    SECTORS: dict = {
        "Technology": "XLK",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Real Estate": "XLRE",
        "Utilities": "XLU",
        "Communications": "XLC",
    }

    # ── Hot Themes / Sector Tailwinds ─────────────────────────────────────────
    HOT_THEMES: list = [
        "artificial intelligence", "ai chip", "semiconductor", "defense", "nuclear",
        "glp-1", "weight loss drug", "cybersecurity", "space", "quantum computing",
        "energy storage", "rare earth", "uranium", "reshoring", "onshoring",
        "robotics", "autonomous", "drone", "hypersonic", "satellite",
    ]

    # ── Global Company → US Peer Mapping ─────────────────────────────────────
    GLOBAL_COMPANY_MAP: dict = {
        # Asia — Semiconductors & Tech
        "Samsung": ["MU", "NVDA", "AMD", "INTC", "AMAT", "LRCX", "KLAC", "ONTO"],
        "TSMC": ["NVDA", "AMD", "QCOM", "AAPL", "ASML", "AMAT", "LRCX"],
        "SK Hynix": ["MU", "WDC", "STX"],
        "Micron": ["MU", "WDC"],
        "Sony": ["MSFT", "EA", "TTWO", "RBLX"],
        "Nintendo": ["MSFT", "ATVI", "EA", "TTWO"],
        "SoftBank": ["T", "TMUS", "ARM"],
        "Arm Holdings": ["NVDA", "QCOM", "AMD", "INTC", "MRVL"],
        "Foxconn": ["AAPL", "HPQ", "DELL", "MSFT"],
        "Rakuten": ["AMZN", "PYPL", "SQ"],
        "Baidu": ["GOOGL", "META", "MSFT"],
        "Alibaba": ["AMZN", "MSFT", "GOOGL", "META"],
        "Tencent": ["EA", "TTWO", "RBLX", "MSFT", "NTES"],
        "BYD": ["TSLA", "NIO", "LI", "XPEV", "GM", "F"],
        "CATL": ["TSLA", "GM", "F", "QS", "STEM"],
        "LG Energy Solution": ["TSLA", "GM", "F", "QS"],
        # Asia — Auto
        "Toyota": ["F", "GM", "TSLA", "TM"],
        "Honda": ["F", "GM", "HMC"],
        "Hyundai": ["F", "GM", "TSLA"],
        # Europe — Semis & Tech
        "ASML": ["AMAT", "LRCX", "KLAC", "INTC", "NVDA"],
        "SAP": ["ORCL", "CRM", "MSFT"],
        "Siemens": ["HON", "GE", "EMR"],
        # Europe — Energy
        "Shell": ["XOM", "CVX", "COP", "BP"],
        "BP": ["XOM", "CVX", "COP"],
        "TotalEnergies": ["XOM", "CVX", "COP"],
        "Equinor": ["XOM", "CVX", "COP"],
        # Europe — Auto
        "Volkswagen": ["F", "GM", "TSLA"],
        "BMW": ["F", "GM", "TSLA"],
        "Mercedes": ["F", "GM", "TSLA"],
        # Europe — Pharma
        "Roche": ["PFE", "MRK", "ABBV", "BMY", "GILD"],
        "Novartis": ["PFE", "MRK", "LLY", "ABBV"],
        "AstraZeneca": ["PFE", "MRK", "BMY", "MRNA"],
        "Novo Nordisk": ["LLY", "VKTX", "ZFOX", "AMGN"],
        "Bayer": ["PFE", "DOW", "MON"],
        # Middle East — Energy
        "Saudi Aramco": ["XOM", "CVX", "COP", "SLB", "HAL"],
        "Petrobras": ["XOM", "CVX", "SLB", "HAL"],
        # Mining & Materials
        "Rio Tinto": ["FCX", "NEM", "AA", "X", "CLF"],
        "BHP": ["FCX", "CLF", "X", "AA", "NUE"],
        "Vale": ["CLF", "X", "NUE", "FCX"],
        "Glencore": ["FCX", "AA", "X"],
        # Luxury
        "LVMH": ["TPR", "PVH", "RL"],
        "Hermes": ["TPR", "RL"],
    }

    # ── Macro Event → Sector Impact Mapping ──────────────────────────────────
    MACRO_EVENT_MAP: dict = {
        "fed_rate_hike":   {"negative": ["XLK", "XLRE", "ARKK"], "positive": ["XLF", "KRE"]},
        "fed_rate_cut":    {"positive": ["XLK", "XLRE", "ARKK"], "negative": ["XLF"]},
        "cpi_high":        {"negative": ["XLK", "XLY"], "positive": ["XLE", "XLB", "GLD"]},
        "cpi_low":         {"positive": ["XLK", "XLY", "ARKK"], "negative": ["XLE", "XLB"]},
        "jobs_strong":     {"positive": ["XLY", "XLF", "XLI"], "negative": ["TLT"]},
        "jobs_weak":       {"negative": ["XLY", "XLF"], "positive": ["TLT", "GLD"]},
        "china_gdp_miss":  {"negative": ["XLB", "XLE", "CAT", "DE"], "positive": ["XLP", "XLU"]},
        "china_gdp_beat":  {"positive": ["XLB", "XLE", "CAT", "DE"], "negative": []},
        "opec_cut":        {"positive": ["XOM", "CVX", "COP", "SLB", "HAL"], "negative": ["XLY", "ALK", "DAL"]},
        "opec_increase":   {"negative": ["XOM", "CVX", "COP"], "positive": ["XLY", "ALK", "DAL"]},
        "dollar_strong":   {"negative": ["EEM", "GLD", "XLB"], "positive": ["XLP"]},
        "dollar_weak":     {"positive": ["EEM", "GLD", "XLB"], "negative": []},
        "yield_curve_invert": {"negative": ["XLF", "KRE"], "positive": ["XLU", "XLP", "GLD"]},
        "chip_shortage":   {"positive": ["AMAT", "LRCX", "KLAC", "NVDA", "MU"], "negative": ["F", "GM"]},
        "tariff_china":    {"negative": ["AAPL", "NVDA", "QCOM", "XLB"], "positive": ["INTC", "AMAT"]},
        "tariff_europe":   {"negative": ["BMW_peers", "wine", "luxury"], "positive": ["domestic_auto"]},
        "geopolitical":    {"negative": ["XLY", "airlines"], "positive": ["XLE", "LMT", "RTX", "GD"]},
        "ai_boom":         {"positive": ["NVDA", "AMD", "MSFT", "GOOGL", "AMAT", "SMCI", "CRDO", "OKLO", "BWXT"], "negative": ["legacy_it_services"]},
        "ai_vs_legacy_it": {"positive": ["NVDA", "AMD", "AVGO", "MU", "SMCI", "CRDO", "VRT", "OKLO"], "negative": ["EPAM", "CTSH", "WIT", "INFY"]},
        "ma_buyout":       {"positive": ["target_stock"], "negative": ["acquirer_cash"]},
        "quarterly_earnings_beat": {"positive": ["high_momentum_tech", "ep_pivot_candidates"], "negative": []},
    }

    # ── Political Signal Keywords ─────────────────────────────────────────────
    POLITICAL_KEYWORDS: list = [
        "great company", "buy american", "deal with", "recommend", "fantastic",
        "beautiful", "tremendous", "sanctions", "tariff", "invest in america",
        "executive order", "national security", "strategic reserve",
        "chip act", "inflation reduction", "infrastructure bill",
    ]

    # ── Analyst Firms ─────────────────────────────────────────────────────────
    ANALYST_FIRMS: list = [
        "Goldman Sachs", "Morgan Stanley", "JP Morgan", "Bank of America",
        "Citigroup", "Wells Fargo", "Deutsche Bank", "UBS", "Barclays",
        "Credit Suisse", "Jefferies", "Piper Sandler", "Needham", "Wedbush",
        "Oppenheimer", "Raymond James", "Bernstein", "Cowen", "Stifel",
        "KeyBanc", "Mizuho", "BTIG", "Canaccord", "Truist", "RBC Capital",
    ]

    # ── Sector P/E Benchmarks ────────────────────────────────────────────────
    SECTOR_PE_BENCHMARKS: dict = {
        "Technology": 28.0,
        "Healthcare": 22.0,
        "Financials": 13.0,
        "Consumer Discretionary": 24.0,
        "Consumer Staples": 20.0,
        "Energy": 12.0,
        "Industrials": 20.0,
        "Materials": 16.0,
        "Real Estate": 35.0,
        "Utilities": 18.0,
        "Communications": 20.0,
        "default": 20.0,
    }


settings = Settings()
