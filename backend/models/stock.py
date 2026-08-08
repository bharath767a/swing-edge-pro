"""
SwingEdge Pro — Database Models
"""
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime
from sqlalchemy.sql import func
from backend.database import Base


class StockCache(Base):
    __tablename__ = "stock_cache"
    ticker = Column(String, primary_key=True)
    company_name = Column(String)
    price = Column(Float)
    prev_close = Column(Float)
    change_pct = Column(Float)
    volume = Column(Float)
    avg_volume = Column(Float)
    rel_volume = Column(Float)
    market_cap = Column(Float)
    float_shares = Column(Float)
    sector = Column(String)
    industry = Column(String)
    fifty_two_week_high = Column(Float)
    fifty_two_week_low = Column(Float)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FundamentalsCache(Base):
    __tablename__ = "fundamentals_cache"
    ticker = Column(String, primary_key=True)
    pe_ratio = Column(Float)
    forward_pe = Column(Float)
    peg = Column(Float)
    pb = Column(Float)
    ps = Column(Float)
    ev_ebitda = Column(Float)
    roe = Column(Float)
    roic = Column(Float)
    roa = Column(Float)
    debt_equity = Column(Float)
    current_ratio = Column(Float)
    quick_ratio = Column(Float)
    revenue_growth = Column(Float)
    earnings_growth = Column(Float)
    gross_margin = Column(Float)
    operating_margin = Column(Float)
    net_margin = Column(Float)
    eps_surprise = Column(Float)
    eps_surprise_pct = Column(Float)
    revenue_ttm = Column(Float)
    earnings_ttm = Column(Float)
    insider_ownership = Column(Float)
    institutional_ownership = Column(Float)
    short_float = Column(Float)
    days_to_cover = Column(Float)
    fundamental_score = Column(Float)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TechnicalsCache(Base):
    __tablename__ = "technicals_cache"
    ticker = Column(String, primary_key=True)
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    adx = Column(Float)
    atr = Column(Float)
    atr_pct = Column(Float)
    vwap = Column(Float)
    ema8 = Column(Float)
    ema21 = Column(Float)
    ema50 = Column(Float)
    ema200 = Column(Float)
    bb_upper = Column(Float)
    bb_lower = Column(Float)
    bb_width = Column(Float)
    stoch_k = Column(Float)
    stoch_d = Column(Float)
    cci = Column(Float)
    obv = Column(Float)
    trend = Column(String)
    support = Column(Float)
    resistance = Column(Float)
    breakout_flag = Column(Boolean, default=False)
    pattern = Column(String)
    squeeze = Column(Boolean, default=False)
    supertrend_signal = Column(String)
    swing_score = Column(Float)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())


class NewsCache(Base):
    __tablename__ = "news_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=True, index=True)
    headline = Column(Text)
    source = Column(String)
    url = Column(String)
    published_at = Column(DateTime)
    sentiment_score = Column(Float)
    sentiment_label = Column(String)
    sentiment_confidence = Column(Float)
    is_global = Column(Boolean, default=False)
    affects_tickers = Column(Text)  # JSON list
    affects_sectors = Column(Text)  # JSON list
    category = Column(String)       # political, analyst, macro, global, domestic
    impact_explanation = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class InsiderTrade(Base):
    __tablename__ = "insider_trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    filer_name = Column(String)
    filer_title = Column(String)
    trade_type = Column(String)  # P (Purchase) or S (Sale)
    shares = Column(Float)
    price = Column(Float)
    value = Column(Float)
    filed_date = Column(String)
    trade_date = Column(String)
    form_type = Column(String)
    source = Column(String)  # finnhub or edgar


class SectorData(Base):
    __tablename__ = "sector_data"
    sector_name = Column(String, primary_key=True)
    etf_ticker = Column(String)
    price = Column(Float)
    change_1d = Column(Float)
    change_5d = Column(Float)
    change_1m = Column(Float)
    change_3m = Column(Float)
    relative_strength = Column(Float)
    momentum_score = Column(Float)
    rotation_signal = Column(String)  # inflow, outflow, neutral
    risk_signal = Column(String)       # risk-on, risk-off, neutral
    top_picks = Column(Text)           # JSON list of top tickers in sector
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=True)
    alert_type = Column(String)  # price, volume, breakout, insider, sentiment, news
    message = Column(Text)
    priority = Column(String, default="medium")  # high, medium, low
    triggered_at = Column(DateTime, server_default=func.now())
    is_read = Column(Boolean, default=False)


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    ticker = Column(String, primary_key=True)
    added_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, default="")
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    entry_price = Column(Float, nullable=True)


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String)
    ticker = Column(String, nullable=True)
    start_date = Column(String)
    end_date = Column(String)
    win_rate = Column(Float)
    avg_gain = Column(Float)
    avg_loss = Column(Float)
    sharpe = Column(Float)
    max_drawdown = Column(Float)
    total_trades = Column(Integer)
    profit_factor = Column(Float)
    results_json = Column(Text)  # equity curve + trade log JSON
    created_at = Column(DateTime, server_default=func.now())


class MultibaggerScore(Base):
    __tablename__ = "multibagger_scores"
    ticker = Column(String, primary_key=True)
    composite_score = Column(Float)
    revenue_inflection = Column(Float)
    margin_expansion = Column(Float)
    tam_ratio = Column(Float)
    insider_ownership = Column(Float)
    institutional_accumulation = Column(Float)
    float_score = Column(Float)
    breakout_score = Column(Float)
    sector_tailwind = Column(Float)
    explanation = Column(Text)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
