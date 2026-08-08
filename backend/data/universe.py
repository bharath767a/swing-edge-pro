"""
SwingEdge Pro — Stock Universe Manager
Maintains the universe of US stocks to screen (penny + multibagger candidates).
"""
import logging
from typing import List
import requests
import yfinance as yf
from backend.config import settings

logger = logging.getLogger(__name__)

# Hardcoded penny/small-cap universe (~150 real US tickers across sectors)
PENNY_UNIVERSE = [
    # Tech / AI / Semiconductors
    "SNDX", "PLUG", "MVIS", "IDEX", "GFAI", "PERI", "DTSS", "CRKN", "AEYE",
    "BRTX", "VNRX", "CTRM", "GFAI", "DPRO", "NKLA", "SOLO", "RIDE", "WKHS",
    "GOEV", "FSR", "ARVL", "EVGO", "BLNK", "CHPT", "SES", "FREYR", "MVST",
    # Biotech / Healthcare
    "MNMD", "SAVA", "OCGN", "VXRT", "INO", "ATOS", "MRKR", "HGEN", "PRPO",
    "NRXP", "AEAC", "BIVI", "BXRX", "HALO", "GHSI", "EARS", "ADMP", "COEP",
    "HPCO", "YCBD", "ABUS", "AVXL", "SEEL", "AMRN", "CRVS", "CTIC", "CASI",
    # Energy / Clean Energy
    "FTCI", "AMRC", "SPPI", "FLNC", "SHLS", "STEM", "RSVR", "ENVX", "GDEV",
    "NRGV", "MKFG", "TRCH", "GATO", "HPKV", "AMTX", "CLNE", "REI", "NEXT",
    # Financials / Fintech
    "BRLT", "JMIA", "LMND", "BARK", "SKIN", "XMTR", "FLYW", "MAPS", "GBTC",
    # Defense / Aerospace
    "RKLB", "ASTS", "SPIR", "BWMX", "ACHR", "JOBY", "LILM", "EVTL", "KTTC",
    # Cannabis
    "TLRY", "ACB", "SNDL", "CURLF", "AYRWF", "GRWG", "IIPR",
    # Metals / Mining
    "GPL", "EXK", "PAAS", "HL", "CDE", "AG", "MAG", "USA", "SILV",
    # Retail / Consumer
    "BBBY", "EXPR", "CATO", "DDS", "HDSN", "ZUMZ", "DXLG", "BURL",
    # Shipping / Transport
    "SBLK", "EGLE", "GOGL", "NMCI", "TOPS", "FREE", "HSHP", "PSHG",
    # Misc small caps
    "TIRX", "BOXL", "GXII", "NCAC", "PRPB", "MLVF", "ACST", "AEYE",
]

# Multibagger candidates — mid-cap stocks with explosive potential
MULTIBAGGER_UNIVERSE = [
    # AI / Tech
    "NVDA", "AMD", "SMCI", "ANET", "CRDO", "MRVL", "ONTO", "ICHR", "FORM",
    "CIEN", "VIAV", "COHU", "ACMR", "LSCC", "ALGM", "WOLF", "NXPI", "SWKS",
    # Defense / Space
    "RKLB", "ASTS", "SPIR", "KTOS", "AVAV", "HII", "CACI", "LDOS", "BAH",
    "DRS", "ACHR", "JOBY", "LILM",
    # Biotech / Pharma
    "RXRX", "TMDX", "CLDX", "IMVT", "VKTX", "PEPG", "BLUE", "NTLA", "CRSP",
    "BEAM", "EDIT", "VERV", "ARWR", "ALLO", "FATE", "SANA", "ALNY", "IONS",
    # Clean Energy / Nuclear
    "OKLO", "NNE", "SMR", "BWXT", "CCJ", "UEC", "DNN", "URG", "UUUU",
    "HASI", "ARRY", "FSLR", "ENPH", "RUN", "NOVA", "STEM", "FLNC",
    # Cybersecurity
    "S", "CRWD", "ZS", "PANW", "FTNT", "CYBR", "QLYS", "VRNS",
    # EV / Battery
    "TSLA", "RIVN", "LCID", "QS", "MVST", "FREYR", "AMPS", "ENVX",
]

def get_universe() -> List[str]:
    """Return full ticker universe (deduped)."""
    combined = list(set(PENNY_UNIVERSE + MULTIBAGGER_UNIVERSE))
    return combined

def get_penny_universe() -> List[str]:
    return list(set(PENNY_UNIVERSE))

def get_multibagger_universe() -> List[str]:
    return list(set(MULTIBAGGER_UNIVERSE))

def get_sp500_tickers() -> List[str]:
    """Fetch S&P 500 tickers from Wikipedia."""
    try:
        import pandas as pd
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = tables[0]
        return df['Symbol'].str.replace('.', '-').tolist()
    except Exception as e:
        logger.warning(f"Could not fetch S&P500 list: {e}")
        return []

def filter_active_stocks(tickers: List[str]) -> List[str]:
    """Filter tickers to those with price $0.50-$20 and volume > 100K."""
    valid = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = getattr(info, 'last_price', None)
            volume = getattr(info, 'three_month_average_volume', None)
            if price and volume:
                if settings.PENNY_STOCK_MIN_PRICE <= price <= settings.PENNY_STOCK_MAX_PRICE:
                    if volume >= settings.MIN_VOLUME:
                        valid.append(ticker)
        except Exception:
            pass
    return valid
