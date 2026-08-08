"""
SwingEdge Pro — Wall Street & Berkshire Institutional Intelligence Pack
Multi-layer value chain stack modeling (AI & IT Services) + Warren Buffett Moat & Cash Flow Framework.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. AI VALUE CHAIN STACK (6 LAYERS)
# ==============================================================================
AI_STACK_LAYERS = {
    'layer_1_eda_ip': {
        'name': 'EDA & Semiconductor IP Design',
        'moat_type': 'High Switching Costs & Patents',
        'tickers': ['ARM', 'SNPS', 'CDNS', 'CEVA'],
        'description': 'Foundation silicon architecture and chip design automation software',
    },
    'layer_2_logic_designers': {
        'name': 'Logic & GPU/ASIC Designers',
        'moat_type': 'Software Ecosystem (CUDA) & R&D Velocity',
        'tickers': ['NVDA', 'AMD', 'AVGO', 'MRVL', 'QCOM', 'ALAB'],
        'description': 'AI training & inference accelerators, custom ASICs, and optical DSPs',
    },
    'layer_3_memory_hbm': {
        'name': 'Memory & HBM (High Bandwidth Memory)',
        'moat_type': 'Capital Intensity & Process Yields',
        'tickers': ['MU', 'WDC', 'STX'],
        'description': 'HBM3e / HBM4 DRAM stacks and ultra-fast NAND storage for AI clusters',
    },
    'layer_4_semiconductor_equip_foundry': {
        'name': 'Semi Cap Equipment & Foundries',
        'moat_type': 'Extreme Monopolistic Precision Engineering (EUV)',
        'tickers': ['ASML', 'AMAT', 'LRCX', 'KLAC', 'TSM', 'ONTO', 'ICHR', 'FORM'],
        'description': 'Lithography machines, deposition/etching, and advanced wafer packaging',
    },
    'layer_5_infrastructure_interconnect': {
        'name': 'Data Center Server Racks & Interconnect',
        'moat_type': 'Thermal Management Patents & High-Speed PHYs',
        'tickers': ['SMCI', 'CRDO', 'ANET', 'VRT', 'CIEN', 'COHU', 'ACMR'],
        'description': 'Liquid cooling systems, high-speed 800G/1.6T active electrical cables, switches',
    },
    'layer_6_energy_nuclear': {
        'name': 'Data Center Clean Energy & Nuclear Power',
        'moat_type': 'Regulatory Licensing & Long-Term Power Purchase Agreements (PPAs)',
        'tickers': ['OKLO', 'NNE', 'SMR', 'BWXT', 'CCJ', 'CEG', 'VST', 'UEC', 'DNN'],
        'description': 'Small Modular Reactors (SMRs), micro-reactors, and nuclear utility baseload power',
    },
}

# ==============================================================================
# 2. IT SERVICES VALUE CHAIN STACK (4 LAYERS)
# ==============================================================================
IT_STACK_LAYERS = {
    'layer_1_ai_integrators': {
        'name': 'AI Systems Integrators & Next-Gen Cloud',
        'moat_type': 'Domain Expertise & Specialized Talent',
        'tickers': ['ACN', 'GLOB', 'EPAM'],
        'description': 'High-margin enterprise AI implementation and LLM integration consulting',
        'outlook': 'BULLISH_EVOLUTION',
    },
    'layer_2_saas_ai_monetization': {
        'name': 'Enterprise SaaS & AI Copilots',
        'moat_type': 'High Enterprise Retention & Data Moats',
        'tickers': ['MSFT', 'ORCL', 'CRM', 'NOW', 'PLTR', 'SNOW'],
        'description': 'Software platforms monetizing embedded AI agents and enterprise workflows',
        'outlook': 'HIGH_MARGIN_GROWTH',
    },
    'layer_3_legacy_managed_services': {
        'name': 'Legacy Infrastructure & Hybrid Cloud Managed',
        'moat_type': 'Contract Longevity',
        'tickers': ['IBM', 'KD', 'DXC'],
        'description': 'Traditional mainframe, data center management, and hybrid cloud maintenance',
        'outlook': 'MATURE_CASH_FLOW',
    },
    'layer_4_offshore_outsourcing': {
        'name': 'Legacy Low-Cost Offshore Outsourcing',
        'moat_type': 'Low-Cost Wage Arbitrage (Disrupted by AI Automation)',
        'tickers': ['INFY', 'WIT', 'CTSH'],
        'description': 'Traditional code maintenance, manual QA, and commodity IT staffing',
        'outlook': 'HEADWIND_MARGIN_PRESSURE',
    },
}


@dataclass
class WallStreetAnalysis:
    ticker: str
    ai_layer: Optional[str] = None
    ai_layer_name: Optional[str] = None
    it_layer: Optional[str] = None
    it_layer_name: Optional[str] = None
    buffett_score: float = 50.0  # 0-100 Berkshire Quality Score
    economic_moat: str = 'None'  # Wide / Narrow / None
    fcf_yield: float = 0.0
    roic: float = 0.0
    debt_safety: str = 'Safe'
    institutional_verdict: str = 'NEUTRAL'
    thesis: str = ''


class WallStreetIntelligenceEngine:
    """Wall Street & Warren Buffett style fundamental and supply-chain analyzer."""

    def analyze_ticker(self, ticker: str, info: Dict) -> WallStreetAnalysis:
        ticker_upper = ticker.upper()
        analysis = WallStreetAnalysis(ticker=ticker_upper)

        # 1. Identify AI Layer
        for layer_key, layer_data in AI_STACK_LAYERS.items():
            if ticker_upper in layer_data['tickers']:
                analysis.ai_layer = layer_key
                analysis.ai_layer_name = f"Layer {layer_key.split('_')[1]}: {layer_data['name']}"
                break

        # 2. Identify IT Layer
        for layer_key, layer_data in IT_STACK_LAYERS.items():
            if ticker_upper in layer_data['tickers']:
                analysis.it_layer = layer_key
                analysis.it_layer_name = layer_data['name']
                break

        # 3. Warren Buffett Valuation & Moat Analysis
        pe = info.get('pe_ratio') or 25.0
        forward_pe = info.get('forward_pe') or pe
        pb = info.get('pb') or info.get('pb_ratio') or 3.0
        roe = info.get('roe') or 0.20
        if roe > 5.0:  # If expressed as percentage
            roe = roe / 100.0

        raw_debt = info.get('debt_equity') if info.get('debt_equity') is not None else 40.0
        # Normalize debt to ratio (e.g. 41.5% -> 0.415)
        debt_ratio = raw_debt / 100.0 if raw_debt > 3.0 else raw_debt

        # Calculate ROIC estimate & FCF Yield
        analysis.roic = round(roe * 100, 1)  # Real ROIC percentage
        analysis.fcf_yield = round((1.0 / max(pe, 1.0)) * 100, 2)

        # Buffett Moat Scoring
        moat_score = 50.0
        if analysis.roic > 20 and debt_ratio < 0.6:
            analysis.economic_moat = 'WIDE MOAT'
            moat_score += 30.0
        elif analysis.roic > 12 and debt_ratio < 1.0:
            analysis.economic_moat = 'NARROW MOAT'
            moat_score += 15.0
        else:
            analysis.economic_moat = 'NO MOAT'

        # Balance Sheet Safety
        if debt_ratio < 0.5:
            analysis.debt_safety = 'Pristine (Fortress Balance Sheet)'
            moat_score += 15.0
        elif debt_ratio < 1.0:
            analysis.debt_safety = 'Manageable Debt'
            moat_score += 5.0
        else:
            analysis.debt_safety = 'High Leverage Warning'
            moat_score -= 15.0

        # Growth / Pricing Power multiplier
        revenue_growth = info.get('revenue_growth') or 0.15
        if revenue_growth > 0.20:
            moat_score += 10.0

        analysis.buffett_score = round(max(0.0, min(100.0, moat_score)), 1)

        # Generate Wall Street Thesis
        thesis_parts = []
        if analysis.ai_layer_name:
            thesis_parts.append(f"AI Stack Position: {analysis.ai_layer_name}.")
        if analysis.it_layer_name:
            thesis_parts.append(f"IT Industry Position: {analysis.it_layer_name}.")
        thesis_parts.append(f"Berkshire Moat Assessment: {analysis.economic_moat} with ROIC of {analysis.roic}%.")
        thesis_parts.append(f"Balance Sheet: {analysis.debt_safety}.")

        analysis.thesis = " ".join(thesis_parts)

        # Verdict
        if analysis.buffett_score >= 80 or (analysis.ai_layer and analysis.buffett_score >= 65):
            analysis.institutional_verdict = 'INSTITUTIONAL ACCUMULATION'
        elif analysis.buffett_score >= 55:
            analysis.institutional_verdict = 'HOLD / FAIR VALUE'
        else:
            analysis.institutional_verdict = 'UNDERPERFORM'

        return analysis
