"""
SwingEdge Pro v3 — Real LLM-Driven Multi-Agent Consensus
NEW INTELLIGENCE: Replaces the fake "multi-agent" (was 3 if-statements) with
actual LLM-driven debate using OpenAI's GPT-4 / Claude / any OpenAI-compatible API.

Architecture:
- Agent 1: Technical & Microstructure Agent (CMT-style analyst)
- Agent 2: Fundamental & Buffett Moat Agent (CFA-style analyst)
- Agent 3: Macro Regime & Liquidity Agent (macro strategist)
- Agent 4 (Synthesizer): Portfolio Consensus Manager — reads all 3 debates,
  produces final consensus action + confidence + synthesis summary

Falls back to rule-based agent_consensus.py if no OPENAI_API_KEY configured.

Usage:
    from backend.engine.llm_consensus import LLMConsensusEngine
    engine = LLMConsensusEngine()
    result = engine.evaluate(ticker, master_score, tech_report, info, regime_data, whale_data)
"""
import json
import logging
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Check for OpenAI API key at import time
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # cheaper default
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')


@dataclass
class LLMConsensusResult:
    ticker: str = ''
    consensus_action: str = 'NEUTRAL HOLD'
    confidence_pct: float = 50.0
    synthesis_summary: str = ''
    agent_debates: List[Dict] = field(default_factory=list)
    method: str = 'rule_based'  # 'llm' or 'rule_based'
    model_used: str = ''


class LLMConsensusEngine:
    """Real LLM-driven multi-agent consensus.

    Each agent has a distinct system prompt reflecting its analytical lens.
    The Synthesizer agent reads all 3 debates and produces the final call.
    """

    AGENT_PROMPTS = {
        'technical': """You are a Chartered Market Technician (CMT) analyzing a stock for a swing trade (1-3 week horizon).

Focus on:
- Trend structure (EMA alignment, ADX strength)
- Pattern recognition (VCP, Episodic Pivot, Bull Flag, Cup & Handle, Squeeze)
- Volume confirmation (relative volume, OBV trend, accumulation/distribution)
- Microstructure (Anchored VWAP, Volume Profile POC, support/resistance)
- Risk levels (ATR-based stop distance, R:R ratio)

Respond in JSON: {"verdict": "BULLISH|NEUTRAL|BEARISH", "confidence": 0-100, "comment": "2-3 sentence reasoning"}""",

        'fundamental': """You are a CFA-chartered equity analyst applying Warren Buffett's framework.

Focus on:
- Economic moat (WIDE / NARROW / NONE) — ROIC, switching costs, network effects
- Balance sheet safety (debt/equity, current ratio, FCF yield)
- Growth quality (revenue growth, margin expansion, EPS acceleration)
- Valuation vs sector benchmark (P/E, forward P/E, PEG)
- Insider + institutional ownership signals (cluster buying = bullish)

Respond in JSON: {"verdict": "BULLISH|NEUTRAL|BEARISH", "confidence": 0-100, "comment": "2-3 sentence reasoning"}""",

        'macro': """You are a macro strategist at a systematic hedge fund.

Focus on:
- Market regime (VIX level, SPY trend, breadth %)
- Sector rotation (is the stock's sector in favor?)
- Risk-on / risk-off environment
- Fed policy + yield curve signals
- Portfolio exposure scaling (risk multiplier)

Respond in JSON: {"verdict": "BULLISH|NEUTRAL|CAUTIOUS", "confidence": 0-100, "comment": "2-3 sentence reasoning"}""",

        'synthesizer': """You are the Portfolio Consensus Manager at a multi-strategy hedge fund.

You will receive the verdicts from 3 specialized agents (Technical, Fundamental, Macro).
Your job is to synthesize them into a final trade recommendation.

Rules:
- Only output "HIGH CONVICTION BUY" if ALL 3 agents are BULLISH and confidence >= 80
- Output "BUY" if 2+ agents are BULLISH and no agent is BEARISH
- Output "ACCUMULATE ON PULLBACK" if 2+ agents are BULLISH/NEUTRAL but mixed
- Output "NEUTRAL HOLD" if mixed or low confidence
- Output "AVOID" if 2+ agents are BEARISH

Respond in JSON: {
  "consensus_action": "HIGH CONVICTION BUY|BUY|ACCUMULATE ON PULLBACK|NEUTRAL HOLD|AVOID",
  "confidence": 0-100,
  "synthesis": "3-4 sentence synthesis explaining the call"
}""",
    }

    def __init__(self, api_key: str = OPENAI_API_KEY, model: str = OPENAI_MODEL,
                 base_url: str = OPENAI_BASE_URL):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = None
        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key, base_url=base_url)
                logger.info(f"LLMConsensusEngine initialized with model={model}")
            except ImportError:
                logger.warning("openai package not installed — falling back to rule-based consensus")
                self.client = None
            except Exception as e:
                logger.warning(f"OpenAI client init failed: {e}")
                self.client = None

    def evaluate(self, ticker: str, master_score: float,
                 tech_report=None, info: Optional[Dict] = None,
                 regime_data: Optional[Dict] = None,
                 whale_data: Optional[Dict] = None,
                 wallstreet_data: Optional[Dict] = None) -> LLMConsensusResult:
        """Run real LLM multi-agent consensus, or fall back to rule-based."""
        if self.client is None:
            return self._fallback_rule_based(
                ticker, master_score, tech_report, regime_data, whale_data, wallstreet_data
            )

        try:
            # Build context for each agent
            tech_context = self._build_technical_context(tech_report)
            fund_context = self._build_fundamental_context(info, whale_data, wallstreet_data)
            macro_context = self._build_macro_context(regime_data)

            # Run 3 specialist agents in parallel (sequential for now — could parallelize)
            tech_verdict = self._call_agent('technical', ticker, tech_context)
            fund_verdict = self._call_agent('fundamental', ticker, fund_context)
            macro_verdict = self._call_agent('macro', ticker, macro_context)

            # Synthesizer reads all 3
            synth_input = json.dumps({
                'technical_agent': tech_verdict,
                'fundamental_agent': fund_verdict,
                'macro_agent': macro_verdict,
                'composite_score': master_score,
            }, indent=2)
            synthesis = self._call_agent('synthesizer', ticker, synth_input)

            return LLMConsensusResult(
                ticker=ticker,
                consensus_action=synthesis.get('consensus_action', 'NEUTRAL HOLD'),
                confidence_pct=float(synthesis.get('confidence', 50)),
                synthesis_summary=synthesis.get('synthesis', ''),
                agent_debates=[
                    {'agent': 'Technical & Microstructure Agent (LLM)', **tech_verdict},
                    {'agent': 'Fundamental & Buffett Moat Agent (LLM)', **fund_verdict},
                    {'agent': 'Macro Regime Agent (LLM)', **macro_verdict},
                ],
                method='llm',
                model_used=self.model,
            )
        except Exception as e:
            logger.error(f"LLM consensus failed for {ticker}: {e}")
            return self._fallback_rule_based(
                ticker, master_score, tech_report, regime_data, whale_data, wallstreet_data
            )

    def _call_agent(self, agent_role: str, ticker: str, context: str) -> Dict:
        """Call the LLM for one agent. Returns parsed JSON verdict."""
        system_prompt = self.AGENT_PROMPTS[agent_role]
        user_msg = f"Ticker: {ticker}\n\nContext:\n{context}\n\nProvide your verdict as JSON."
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_msg},
                ],
                temperature=0.3,  # low temp for analytical consistency
                max_tokens=400,
                response_format={'type': 'json_object'},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Agent {agent_role} call failed for {ticker}: {e}")
            return {'verdict': 'NEUTRAL', 'confidence': 50, 'comment': f'Agent unavailable: {e}'}

    def _build_technical_context(self, tech_report) -> str:
        if tech_report is None:
            return "Technical data unavailable."
        return (
            f"Trend: {tech_report.trend} | "
            f"RSI: {tech_report.rsi} ({tech_report.rsi_signal}) | "
            f"MACD cross: {tech_report.macd_cross} | "
            f"ADX: {tech_report.adx} | "
            f"ATR%: {tech_report.atr_pct} | "
            f"Pattern: {tech_report.pattern} | "
            f"Squeeze: {tech_report.squeeze} | "
            f"Relative volume: {tech_report.rel_volume}x | "
            f"Volume trend: {tech_report.volume_trend} | "
            f"Support: {tech_report.support} | Resistance: {tech_report.resistance} | "
            f"Supertrend: {tech_report.supertrend_signal} | "
            f"Swing score: {tech_report.swing_score}/100"
        )

    def _build_fundamental_context(self, info: Optional[Dict], whale_data: Optional[Dict],
                                    wallstreet_data: Optional[Dict]) -> str:
        if not info:
            return "Fundamental data unavailable."
        parts = [
            f"Sector: {info.get('sector', 'Unknown')}",
            f"P/E: {info.get('pe_ratio', 'N/A')} | Forward P/E: {info.get('forward_pe', 'N/A')} | PEG: {info.get('peg', 'N/A')}",
            f"Revenue growth: {info.get('revenue_growth', 0)*100:.1f}% YoY" if info.get('revenue_growth') else "Revenue growth: N/A",
            f"Gross margin: {info.get('gross_margin', 0)*100:.1f}%" if info.get('gross_margin') else "Gross margin: N/A",
            f"Net margin: {info.get('net_margin', 0)*100:.1f}%" if info.get('net_margin') else "Net margin: N/A",
            f"ROE: {info.get('roe', 0)*100:.1f}%" if info.get('roe') else "ROE: N/A",
            f"Debt/Equity: {info.get('debt_equity', 'N/A')}",
            f"Short float: {info.get('short_float', 0)*100:.1f}%" if info.get('short_float') else "Short float: N/A",
        ]
        if wallstreet_data:
            parts.append(f"Buffett moat: {wallstreet_data.get('economic_moat', 'N/A')}")
            parts.append(f"Buffett score: {wallstreet_data.get('buffett_score', 'N/A')}/100")
        if whale_data:
            parts.append(f"Insider cluster: {whale_data.get('cluster_detected', False)}")
            parts.append(f"High conviction: {whale_data.get('high_conviction_cluster', False)}")
            parts.append(f"C-suite buyers: {whale_data.get('c_suite_buyers_count', 0)}")
        return " | ".join(parts)

    def _build_macro_context(self, regime_data: Optional[Dict]) -> str:
        if not regime_data:
            return "Macro data unavailable."
        return (
            f"Regime: {regime_data.get('regime', 'NEUTRAL')} | "
            f"VIX: {regime_data.get('vix_level', 'N/A')} | "
            f"Market breadth: {regime_data.get('market_breadth_pct', 'N/A')}% | "
            f"Risk multiplier: {regime_data.get('risk_multiplier', 1.0)} | "
            f"SPY above 50-EMA: {regime_data.get('spy_above_50_ema', 'N/A')} | "
            f"SPY above 200-EMA: {regime_data.get('spy_above_200_ema', 'N/A')} | "
            f"Guidance: {regime_data.get('guidance', 'N/A')}"
        )

    def _fallback_rule_based(self, ticker, master_score, tech_report,
                              regime_data, whale_data, wallstreet_data) -> LLMConsensusResult:
        """Fall back to the rule-based consensus from agent_consensus.py if LLM unavailable."""
        from backend.engine.agent_consensus import MultiAgentConsensusEngine
        rule_engine = MultiAgentConsensusEngine()
        moat = (wallstreet_data or {}).get('economic_moat', 'NARROW MOAT')
        regime = (regime_data or {}).get('regime', 'NEUTRAL')
        micro = {}  # not needed for rule-based
        rule_result = rule_engine.evaluate_consensus(
            ticker, master_score, 50.0, moat, regime, micro, whale_data or {}
        )
        return LLMConsensusResult(
            ticker=ticker,
            consensus_action=rule_result.get('consensus_action', 'NEUTRAL HOLD'),
            confidence_pct=rule_result.get('confidence_pct', 50.0),
            synthesis_summary=rule_result.get('synthesis_summary', ''),
            agent_debates=rule_result.get('agent_debates', []),
            method='rule_based',
            model_used='none',
        )
