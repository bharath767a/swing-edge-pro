"""
SwingEdge Pro v2 — Master Composite Engine with Microstructure,
Market Regime Exposure Scaling, Whale Matrix, & Multi-Agent Consensus.

AUDIT FIXES APPLIED:
- P0-1: Added `import pandas as pd` (was missing, crashed fallback path)
- P0-3: Compute WallStreet analysis once, pass real economic_moat into consensus
- P2:   Eliminated triple-fetch — info/technicals/ohlcv now reused across engines
- P2:   Multibagger engine now receives pre-computed tech_report (no duplicate analyze())
"""
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import pandas as pd
from backend.data.fetchers import get_stock_info, get_company_news, get_ohlcv
from backend.engine.fundamentals import FundamentalsEngine
from backend.engine.technicals import TechnicalsEngine
from backend.engine.sentiment import SentimentEngine
from backend.engine.insider_tracker import InsiderTracker
from backend.engine.multibagger import MultibaggerEngine
from backend.engine.sector_rotation import SectorRotationEngine
from backend.engine.microstructure import MicrostructureEngine
from backend.engine.market_regime import MarketRegimeClassifier
from backend.engine.whale_matrix import InstitutionalWhaleMatrix
from backend.engine.agent_consensus import MultiAgentConsensusEngine
from backend.engine.wallstreet_intelligence import WallStreetIntelligenceEngine
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MasterScore:
    ticker: str = ''
    composite_score: float = 50.0
    technical_score: float = 50.0
    fundamental_score: float = 50.0
    sentiment_score: float = 50.0
    insider_score: float = 50.0
    multibagger_score: float = 50.0
    sector_score: float = 50.0
    signals: List[str] = field(default_factory=list)
    recommendation: str = 'NEUTRAL'
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward: Optional[float] = None
    swing_timeframe: str = '1-2 weeks'
    current_price: Optional[float] = None
    company_name: str = ''
    sector: str = ''
    pattern: str = 'none'
    # v2 Engine Additions
    microstructure: Dict = field(default_factory=dict)
    whale_signals: Dict = field(default_factory=dict)
    market_regime: Dict = field(default_factory=dict)
    agent_consensus: Dict = field(default_factory=dict)
    wallstreet: Dict = field(default_factory=dict)  # FIX P0-3: added to expose real moat


class MasterScorer:

    WEIGHTS = {
        'technical': 0.25,
        'fundamental': 0.20,
        'microstructure': 0.15,
        'sentiment': 0.15,
        'insider': 0.15,
        'multibagger': 0.10,
    }

    def __init__(self):
        self.fundamentals = FundamentalsEngine()
        self.technicals = TechnicalsEngine()
        self.sentiment = SentimentEngine()
        self.insider = InsiderTracker()
        self.multibagger = MultibaggerEngine()
        self.sector_engine = SectorRotationEngine()
        self.microstructure = MicrostructureEngine()
        self.regime = MarketRegimeClassifier()
        self.whale = InstitutionalWhaleMatrix()
        self.consensus = MultiAgentConsensusEngine()
        self.wallstreet = WallStreetIntelligenceEngine()  # FIX P0-3: was instantiated only in router

    def score_stock(self, ticker: str) -> MasterScore:
        """Run complete v2 multi-factor analysis on a ticker.

        AUDIT FIXES:
        - Single-fetch: get_stock_info() called once (was 3x)
        - Single technicals pass: tech_report.analyze() called once (was 3x)
        - Single OHLCV fetch: reused from technicals engine (was separate yfinance call)
        - Real economic_moat: WallStreet analysis computed here, passed to consensus
        - Multibagger receives pre-computed tech_report (no duplicate analyze())
        """
        result = MasterScore(ticker=ticker)
        signals = []

        try:
            # ── SINGLE FETCH: stock info ─────────────────────────────────
            info = get_stock_info(ticker)
            if not info or not info.get('price'):
                return result
            current_price = info.get('price')
            result.current_price = current_price
            result.company_name = info.get('company_name', ticker)
            result.sector = info.get('sector', 'Unknown')

            # ── SINGLE PASS: technicals (caches internally + exposes _df) ──
            tech_report = self.technicals.analyze(ticker)
            result.technical_score = tech_report.swing_score
            result.pattern = tech_report.pattern
            if tech_report.breakout_flag:
                signals.append(f'Breakout detected on {tech_report.rel_volume:.1f}x volume')
            if tech_report.pattern in ('vcp', 'episodic_pivot', 'bull_flag', 'cup_handle'):
                signals.append(f'Pattern: {tech_report.pattern.upper().replace("_", " ")}')
            if tech_report.squeeze:
                signals.append('Volatility Squeeze — explosive move imminent')

            # ── REUSE the OHLCV DataFrame that technicals already fetched ──
            df_ohlc = getattr(tech_report, '_df', None)
            if df_ohlc is None or df_ohlc.empty:
                # Fallback to fetchers.get_ohlcv (lowercase columns)
                df_ohlc = get_ohlcv(ticker, period='6mo', interval='1d')
                # Normalize to Title-case columns that microstructure expects
                if df_ohlc is not None and not df_ohlc.empty:
                    df_ohlc = df_ohlc.rename(columns={
                        'open': 'Open', 'high': 'High', 'low': 'Low',
                        'close': 'Close', 'volume': 'Volume',
                    })
            if df_ohlc is None:
                df_ohlc = pd.DataFrame()

            micro_data = self.microstructure.analyze_microstructure(ticker, df_ohlc)
            result.microstructure = micro_data
            if micro_data.get('confluence_status') and micro_data['confluence_status'] != 'NEUTRAL':
                signals.append(f"{micro_data['confluence_status']}")

            # ── Fundamental score (uses already-fetched info) ────────────
            fund_report = self.fundamentals.composite_fundamental_score(ticker, info)
            # FIX v3.2.2: fundamentals returns None when data missing — don't fabricate
            if fund_report is None:
                result.fundamental_score = 50.0  # neutral in composite, but mark as missing
                signals.append('Fundamental data unavailable — scoring neutral')
            else:
                result.fundamental_score = fund_report
            if info.get('revenue_growth') and info['revenue_growth'] > 0.25:
                signals.append(f"Revenue growing {info['revenue_growth']*100:.0f}% YoY")

            # ── Sentiment ────────────────────────────────────────────────
            news_list = get_company_news(ticker, days=7)
            sent_score = self.sentiment.score_sentiment_for_stock(ticker, news_list)
            result.sentiment_score = sent_score

            # ── Insider + Whale ──────────────────────────────────────────
            insider_trades = self.insider.fetch_insider_trades(ticker)
            whale_data = self.whale.evaluate_whale_signals(ticker, insider_trades, info)
            result.whale_signals = whale_data
            result.insider_score = whale_data.get('whale_conviction_score', 50.0)
            if whale_data.get('high_conviction_cluster'):
                signals.append('HIGH CONVICTION C-SUITE CLUSTER BUY')
            elif whale_data.get('cluster_detected'):
                signals.append('Insider Cluster Buying Detected')

            # ── WallStreet Intelligence (FIX P0-3: compute once, use everywhere) ──
            ws_analysis = self.wallstreet.analyze_ticker(ticker, info)
            result.wallstreet = {
                'ai_layer': ws_analysis.ai_layer,
                'ai_layer_name': ws_analysis.ai_layer_name,
                'it_layer': ws_analysis.it_layer,
                'it_layer_name': ws_analysis.it_layer_name,
                'buffett_score': ws_analysis.buffett_score,
                'economic_moat': ws_analysis.economic_moat,
                'fcf_yield': ws_analysis.fcf_yield,
                'roic': ws_analysis.roic,
                'debt_safety': ws_analysis.debt_safety,
                'institutional_verdict': ws_analysis.institutional_verdict,
                'thesis': ws_analysis.thesis,
            }

            # ── Multibagger (FIX P2: pass tech_report + info, no duplicate fetch) ──
            mb_score = self.multibagger.score_stock(ticker, tech_report=tech_report, info=info)
            result.multibagger_score = mb_score.composite_score

            # ── Market Regime (cached globally, 15-min TTL) ──────────────
            regime_data = self.regime.evaluate_regime()
            result.market_regime = regime_data

            # ── Composite Score ──────────────────────────────────────────
            base_score = (
                result.technical_score * self.WEIGHTS['technical'] +
                result.fundamental_score * self.WEIGHTS['fundamental'] +
                micro_data.get('confluence_score', 50.0) * self.WEIGHTS['microstructure'] +
                result.sentiment_score * self.WEIGHTS['sentiment'] +
                result.insider_score * self.WEIGHTS['insider'] +
                result.multibagger_score * self.WEIGHTS['multibagger']
            )

            # Exposure scaling — but if data quality is DEGRADED, scale DOWN
            risk_mult = regime_data.get('risk_multiplier', 1.0)
            data_quality = regime_data.get('data_quality', 'OK')
            quality_mult = 0.7 if data_quality == 'DEGRADED' else 1.0
            result.composite_score = round(base_score * (0.8 + 0.2 * risk_mult) * quality_mult, 1)

            # ── Multi-Agent Consensus — REAL moat from WallStreet analysis ──
            consensus_data = self.consensus.evaluate_consensus(
                ticker, result.technical_score, result.fundamental_score,
                ws_analysis.economic_moat,  # FIX P0-3: real value, not 'NARROW MOAT' constant
                regime_data.get('regime', 'NEUTRAL'),
                micro_data, whale_data
            )
            result.agent_consensus = consensus_data
            result.recommendation = consensus_data.get('consensus_action', self.get_recommendation(result.composite_score))

            # ── Risk Management — use ATR-based stop (config.STOP_LOSS_ATR_MULT) ──
            atr = tech_report.atr
            resistance = tech_report.resistance
            result.stop_loss = round(current_price - (atr * settings.STOP_LOSS_ATR_MULT), 4) if atr > 0 else round(current_price * 0.95, 4)
            result.target_price = round(max(resistance, current_price * 1.10), 4)
            if result.stop_loss and result.stop_loss < current_price:
                risk = current_price - result.stop_loss
                reward = result.target_price - current_price
                result.risk_reward = round(reward / risk, 2) if risk > 0 else 0

            result.signals = signals[:8]

        except Exception as e:
            logger.error(f"Master score v2 error {ticker}: {e}", exc_info=True)

        return result

    def get_recommendation(self, score: float) -> str:
        if score >= 80: return 'STRONG BUY'
        elif score >= 65: return 'BUY'
        elif score >= 50: return 'WATCH'
        elif score >= 35: return 'NEUTRAL'
        else: return 'AVOID'

    def get_top_picks(self, n: int = 25) -> List[MasterScore]:
        from backend.data.universe import get_universe
        from concurrent.futures import ThreadPoolExecutor, as_completed

        universe = get_universe()[:50]
        results = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_ticker = {executor.submit(self.score_stock, ticker): ticker for ticker in universe}
            for future in as_completed(future_to_ticker):
                try:
                    score = future.result()
                    if score and score.composite_score > 0 and score.current_price:
                        results.append(score)
                except Exception as e:
                    logger.debug(f"Score error: {e}")

        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results[:n]
