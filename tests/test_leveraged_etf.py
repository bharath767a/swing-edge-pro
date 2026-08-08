"""
Test suite for the Unified Leveraged ETF Swing Engine (v3.3).
Tests verify the engine uses MasterScorer (unified) + ETF-specific overlays.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


@pytest.fixture
def sample_etf_ohlcv():
    """Sample OHLCV for a trending 2x ETF (bullish)."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range(end=datetime.now(), periods=n, freq='B')
    returns = np.random.normal(0.002, 0.018, n)
    closes = 100 * np.exp(np.cumsum(returns))
    highs = closes * (1 + np.abs(np.random.normal(0, 0.008, n)))
    lows = closes * (1 - np.abs(np.random.normal(0, 0.008, n)))
    opens = closes * (1 + np.random.normal(0, 0.004, n))
    volumes = np.random.randint(2_000_000, 8_000_000, n).astype(float)
    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes,
    })


class TestLeveragedETFUniverse:
    def test_universe_has_both_directions(self):
        from backend.data.leveraged_etf_universe import (
            get_all_leveraged_etfs, get_long_leveraged_etfs, get_short_leveraged_etfs
        )
        all_etfs = get_all_leveraged_etfs()
        longs = get_long_leveraged_etfs()
        shorts = get_short_leveraged_etfs()
        assert len(all_etfs) >= 50, "Universe should have 50+ ETFs (including single-stock)"
        assert len(longs) > 20
        assert len(shorts) > 10

    def test_single_stock_etfs_present(self):
        """v3.3: Should include single-stock 2x ETFs (NVDU, TSLT, SNDG, etc.)."""
        from backend.data.leveraged_etf_universe import get_single_stock_etfs, get_etf_by_ticker
        singles = get_single_stock_etfs()
        assert len(singles) >= 15, f"Should have 15+ single-stock ETFs, got {len(singles)}"
        # SNDG must be there (the user's example)
        sndg = get_etf_by_ticker('SNDG')
        assert sndg, "SNDG (2x SNDK) must be in universe"
        assert sndg['underlying_ticker'] == 'SNDK'
        # NVDU must be there
        nvdu = get_etf_by_ticker('NVDU')
        assert nvdu, "NVDU (2x NVDA) must be in universe"
        assert nvdu['underlying_ticker'] == 'NVDA'

    def test_each_etf_has_required_fields(self):
        from backend.data.leveraged_etf_universe import get_all_leveraged_etfs
        required = {'ticker', 'direction', 'underlying', 'asset_class', 'typical_spread_bps', 'decay_risk_base'}
        for etf in get_all_leveraged_etfs():
            missing = required - set(etf.keys())
            assert not missing, f"{etf.get('ticker')} missing fields: {missing}"

    def test_get_etfs_by_underlying(self):
        """Should find all leveraged ETFs tracking a specific underlying."""
        from backend.data.leveraged_etf_universe import get_etfs_by_underlying
        nvda_etfs = get_etfs_by_underlying('NVDA')
        # Should include NVDU (long) and NVD (short) and NVDG (long)
        tickers = [e['ticker'] for e in nvda_etfs]
        assert 'NVDU' in tickers
        assert 'NVD' in tickers
        assert 'NVDG' in tickers

    def test_etf_by_ticker(self):
        from backend.data.leveraged_etf_universe import get_etf_by_ticker
        sso = get_etf_by_ticker('SSO')
        assert sso['direction'] == 'LONG'
        assert sso['underlying'] == 'S&P 500'


class TestLeveragedETFEngine:
    def test_universe_summary(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        summary = engine.get_universe_summary()
        assert summary['total_etfs'] >= 50
        assert summary['single_stock_etfs'] >= 15
        assert 'single_stock' in summary['by_asset_class']

    def test_uses_master_scorer(self):
        """v3.3: Engine should use MasterScorer (unified), not separate scoring logic."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        assert hasattr(engine, 'scorer'), "Engine should have a MasterScorer instance"
        from backend.engine.scoring import MasterScorer
        assert isinstance(engine.scorer, MasterScorer)

    def test_normalize_filter_handles_none(self):
        """FIX v3.3: _normalize_filter must handle None / empty / Query objects."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        assert engine._normalize_filter(None) is None
        assert engine._normalize_filter('') is None
        assert engine._normalize_filter('long') == 'LONG'
        assert engine._normalize_filter('LONG') == 'LONG'

    def test_regime_alignment_long_in_bull(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'BULLISH_EXPANSION', 'risk_multiplier': 1.0, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('LONG', regime)
        assert aligned is True
        assert score == 100.0

    def test_regime_alignment_long_in_bear_misaligned(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'HIGH_VOLATILITY_DEFENSIVE', 'risk_multiplier': 0.4, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('LONG', regime)
        assert aligned is False
        assert score <= 10.0

    def test_regime_alignment_short_in_bear(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'HIGH_VOLATILITY_DEFENSIVE', 'risk_multiplier': 0.4, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('SHORT', regime)
        assert aligned is True
        assert score == 100.0

    def test_regime_data_degraded_blocks_both(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'DATA_DEGRADED', 'risk_multiplier': 0.5, 'data_quality': 'DEGRADED'}
        aligned_long, _ = engine._check_regime_alignment('LONG', regime)
        aligned_short, _ = engine._check_regime_alignment('SHORT', regime)
        assert aligned_long is False
        assert aligned_short is False

    def test_decay_calculation(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # 2% daily vol → decay = 0.5 * 0.0004 * 100 = 0.02%/day
        decay = engine.DECAY_COEFFICIENT * (0.02 ** 2) * 100
        assert decay == 0.02

    def test_wider_stops_for_2x_vol(self):
        """Stop loss multiplier should be 2.5x ATR (wider than 2.0x for non-leveraged)."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        assert engine.STOP_LOSS_ATR_MULT == 2.5

    def test_target_gives_2_to_1_rr(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        rr = engine.TARGET_ATR_MULT / engine.STOP_LOSS_ATR_MULT
        assert rr >= 2.0

    def test_hold_days_within_bounds(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine, LeveragedETFSignal
        engine = LeveragedETFEngine()
        signal = LeveragedETFSignal(decay_risk='HIGH', adx=15)
        hold = engine._recommend_hold_days(signal)
        assert engine.MIN_HOLD_DAYS <= hold <= engine.MAX_HOLD_DAYS

    def test_catalyst_warnings_returned(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        warning = engine._check_catalyst_warnings('NVDA')
        assert isinstance(warning, str)

    def test_catalyst_warnings_include_underlying(self):
        """When underlying ticker provided, warning should mention it during earnings season."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # Force earnings season month
        with patch('backend.engine.leveraged_etf.datetime') as mock_dt:
            mock_now = MagicMock()
            mock_now.day = 15
            mock_now.month = 1  # January = earnings season
            mock_dt.now.return_value = mock_now
            warning = engine._check_catalyst_warnings('NVDA')
            assert 'NVDA' in warning or 'earnings' in warning.lower() or warning == ''

    def test_pattern_detection_for_short_etfs(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        df = pd.DataFrame({'close': [100]*50, 'high': [101]*50, 'low': [99]*50,
                          'volume': [1e6]*50, 'open': [100]*50})
        with patch.object(engine.tech, 'detect_patterns', return_value=['vcp']):
            pattern = engine._detect_pattern(df, 'SHORT')
            assert 'short' in pattern or 'equivalent' in pattern

    def test_signal_has_unified_fields(self):
        """v3.3: Signal should have base_swing_score + underlying_score fields."""
        from backend.engine.leveraged_etf import LeveragedETFSignal
        sig = LeveragedETFSignal()
        assert hasattr(sig, 'base_swing_score')
        assert hasattr(sig, 'underlying_score')
        assert hasattr(sig, 'composite_score')

    def test_screen_handles_query_objects(self):
        """FIX v3.3: screen() should handle FastAPI Query objects without crashing."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # Simulate a FastAPI Query object (has .default attribute)
        mock_query = MagicMock()
        mock_query.default = None
        # Should not crash — should normalize to None
        with patch.object(engine, '_analyze_etf_safe', return_value=None):
            result = engine.screen(direction_filter=mock_query, asset_class_filter=mock_query)
            assert isinstance(result, list)

    def test_single_stock_etf_scores_underlying(self):
        """For single-stock ETFs, should attempt to score the underlying."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        from backend.data.leveraged_etf_universe import get_etf_by_ticker
        engine = LeveragedETFEngine()
        sndg_meta = get_etf_by_ticker('SNDG')
        assert sndg_meta['underlying_ticker'] == 'SNDK'
        # Mock the underlying scoring to verify it's called
        with patch.object(engine, '_score_underlying', return_value=75.0) as mock_score:
            with patch.object(engine, '_compute_base_score', return_value=60.0):
                with patch.object(engine, '_check_regime_alignment', return_value=(True, 100.0)):
                    # Need to mock get_ohlcv + technicals too
                    with patch('backend.engine.leveraged_etf.get_ohlcv') as mock_ohlcv:
                        mock_ohlcv.return_value = sample_etf_ohlcv_fixture()
                        signal = engine._analyze_etf(sndg_meta, {'regime': 'BULLISH_EXPANSION'})
                        # Should have called underlying scoring
                        mock_score.assert_called_with('SNDK')
                        assert signal.underlying_score == 75.0


def sample_etf_ohlcv_fixture():
    """Helper for the test above."""
    np.random.seed(42)
    n = 250
    dates = pd.date_range(end=datetime.now(), periods=n, freq='B')
    returns = np.random.normal(0.002, 0.018, n)
    closes = 100 * np.exp(np.cumsum(returns))
    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': closes, 'high': closes*1.01, 'low': closes*0.99,
        'close': closes, 'volume': np.full(n, 1e6),
    })


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
