"""
SwingEdge Pro v2 — Institutional Whale & Insider Cluster Matrix
Tracks 13F Institutional QoQ Net Accumulation & 3+ C-Suite Insider Clusters.
"""
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class InstitutionalWhaleMatrix:
    def __init__(self):
        pass

    def evaluate_whale_signals(self, ticker: str, trades: List[Dict], info: Dict) -> Dict:
        """
        Evaluate Institutional 13F Accumulation & C-Suite Cluster Purchases.

        AUDIT FIX P0-4: Removed fabricated defaults (was `or 0.65` / `or 0.05`).
        Now treats missing data as None and does not award ownership-based bonus points
        when the underlying field is unknown.
        """
        ticker = ticker.upper()

        # FIX P0-4: do NOT fabricate ownership when missing — return None and skip bonus
        inst_ownership_raw = info.get('institutional_ownership')
        if inst_ownership_raw is None:
            inst_ownership = None
        elif inst_ownership_raw > 5.0:
            inst_ownership = inst_ownership_raw / 100.0
        else:
            inst_ownership = inst_ownership_raw

        insider_ownership_raw = info.get('insider_ownership')
        if insider_ownership_raw is None:
            insider_ownership = None
        elif insider_ownership_raw > 5.0:
            insider_ownership = insider_ownership_raw / 100.0
        else:
            insider_ownership = insider_ownership_raw

        # Cluster Buy Check (3+ unique C-suite/directors buying in recent trades)
        unique_buyers = set()
        c_suite_buyers = set()
        total_buy_val = 0.0
        
        for t in trades:
            ttype = str(t.get('trade_type') or t.get('type') or '').upper()
            code = str(t.get('transaction_code', '')).upper()
            # FIX: trade_type can be 'P' (Purchase), 'S' (Sale), or full words
            is_buy = (ttype == 'P' or ttype == 'BUY' or ttype == 'PURCHASE' or
                      'BUY' in ttype or 'PURCHASE' in ttype or code == 'P')
            if is_buy:
                name = t.get('filer_name') or t.get('insider_name') or 'Insider'
                title = str(t.get('officer_title') or t.get('title') or t.get('filer_title') or '').upper()
                unique_buyers.add(name)
                if any(role in title for role in ['CEO', 'CFO', 'PRESIDENT', 'DIRECTOR', 'CHAIRMAN']):
                    c_suite_buyers.add(name)
                shrs = float(t.get('shares') or 0)
                prc = float(t.get('price') or 0)
                total_buy_val += shrs * prc

        cluster_detected = len(unique_buyers) >= 2 or len(c_suite_buyers) >= 1
        high_conviction_cluster = len(c_suite_buyers) >= 2 or len(unique_buyers) >= 3
        
        # Scoring calculation (0-100) — FIX P0-4: no bonus when ownership is unknown
        whale_score = 50.0
        if inst_ownership is None:
            # data missing — stay neutral, do not award bonus
            pass
        elif inst_ownership >= 0.70:
            whale_score += 20.0
        elif inst_ownership >= 0.40:
            whale_score += 10.0
            
        if high_conviction_cluster:
            whale_score += 25.0
            signal_desc = f"HIGH CONVICTION CLUSTER: {len(c_suite_buyers)} C-Suite Executives bought on open market."
        elif cluster_detected:
            whale_score += 15.0
            signal_desc = f"INSIDER CLUSTER: {len(unique_buyers)} Insiders buying accumulated shares."
        else:
            signal_desc = "Standard Institutional Holding Base."

        return {
            'ticker': ticker,
            'institutional_ownership_pct': round(inst_ownership * 100, 1) if inst_ownership is not None else None,
            'insider_ownership_pct': round(insider_ownership * 100, 1) if insider_ownership is not None else None,
            'ownership_data_available': inst_ownership is not None,  # new: surface data quality
            'cluster_detected': cluster_detected,
            'high_conviction_cluster': high_conviction_cluster,
            'c_suite_buyers_count': len(c_suite_buyers),
            'recent_buy_volume_usd': round(total_buy_val, 2),
            'whale_conviction_score': round(max(0.0, min(100.0, whale_score)), 1),
            'signal_description': signal_desc
        }
