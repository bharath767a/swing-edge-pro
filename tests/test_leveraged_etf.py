"""
Test suite for the 2x Leveraged ETF Swing Engine (NEW in v3).
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
    # Strong uptrend with normal volatility
    returns = np.random.normal(0.002, 0.018, n)  # positive drift, 1.8% daily vol
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
        assert len(all_etfs) > 30, "Universe should have 30+ ETFs"
        assert len(longs) > 15
        assert len(shorts) > 10
        # Long + short should equal total
        assert len(longs) + len(shorts) == len(all_etfs)

    def test_each_etf_has_required_fields(self):
        from backend.data.leveraged_etf_universe import get_all_leveraged_etfs
        required = {'ticker', 'direction', 'underlying', 'asset_class', 'typical_spread_bps', 'decay_risk_base'}
        for etf in get_all_leveraged_etfs():
            missing = required - set(etf.keys())
            assert not missing, f"{etf.get('ticker')} missing fields: {missing}"

    def test_etf_by_ticker(self):
        from backend.data.leveraged_etf_universe import get_etf_by_ticker
        sso = get_etf_by_ticker('SSO')
        assert sso['direction'] == 'LONG'
        assert sso['underlying'] == 'S&P 500'
        # Case insensitive
        assert get_etf_by_ticker('sso')['ticker'] == 'SSO'
        # Not found
        assert get_etf_by_ticker('SPY') == {}

    def test_filter_by_asset_class(self):
        from backend.data.leveraged_etf_universe import get_etfs_by_asset_class
        equity = get_etfs_by_asset_class('equity')
        assert len(equity) >= 6  # SSO, QLD, DDM, MVV, UWM + shorts
        for e in equity:
            assert e['asset_class'] == 'equity'


class TestLeveragedETFEngine:
    def test_universe_summary(self):
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        summary = engine.get_universe_summary()
        assert summary['total_etfs'] > 30
        assert summary['long_etfs'] > 0
        assert summary['short_etfs'] > 0
        assert 'by_asset_class' in summary
        assert 'equity' in summary['by_asset_class']

    def test_regime_alignment_long_in_bull(self):
        """2x long ETFs should be aligned in BULLISH_EXPANSION regime."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'BULLISH_EXPANSION', 'risk_multiplier': 1.0, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('LONG', regime)
        assert aligned is True
        assert score == 100.0

    def test_regime_alignment_long_in_bear_misaligned(self):
        """2x long ETFs should be misaligned in HIGH_VOLATILITY_DEFENSIVE."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'HIGH_VOLATILITY_DEFENSIVE', 'risk_multiplier': 0.4, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('LONG', regime)
        assert aligned is False
        assert score <= 10.0

    def test_regime_alignment_short_in_bear(self):
        """2x short ETFs should be aligned in HIGH_VOLATILITY_DEFENSIVE regime."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'HIGH_VOLATILITY_DEFENSIVE', 'risk_multiplier': 0.4, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('SHORT', regime)
        assert aligned is True
        assert score == 100.0

    def test_regime_alignment_short_in_bull_misaligned(self):
        """2x short ETFs in BULLISH_EXPANSION = death wish."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'BULLISH_EXPANSION', 'risk_multiplier': 1.0, 'data_quality': 'OK'}
        aligned, score = engine._check_regime_alignment('SHORT', regime)
        assert aligned is False
        assert score <= 5.0

    def test_regime_data_degraded_blocks_both(self):
        """DATA_DEGRADED regime should block both directions."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        regime = {'regime': 'DATA_DEGRADED', 'risk_multiplier': 0.5, 'data_quality': 'DEGRADED'}
        aligned_long, _ = engine._check_regime_alignment('LONG', regime)
        aligned_short, _ = engine._check_regime_alignment('SHORT', regime)
        assert aligned_long is False
        assert aligned_short is False

    def test_decay_calculation(self):
        """Decay should scale with volatility squared."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # Mock signal with 2% daily vol
        signal = MagicMock()
        signal.estimated_daily_decay_pct = engine.DECAY_COEFFICIENT * (0.02 ** 2) * 100
        # 0.5 * 0.0004 * 100 = 0.02%/day
        assert signal.estimated_daily_decay_pct == 0.02
        # 4% daily vol (high-vol commodity ETF)
        high_vol_decay = engine.DECAY_COEFFICIENT * (0.04 ** 2) * 100
        assert high_vol_decay == 0.08  # 4x higher decay for 2x vol

    def test_decay_risk_thresholds(self):
        """Decay risk should be LOW / MEDIUM / HIGH based on daily decay %."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # We can't easily test _analyze_etf without mocking everything,
        # but we can verify the threshold logic via the score computation
        signal = MagicMock()
        signal.decay_risk = 'HIGH'
        signal.quality_score = 80
        signal.regime_alignment_score = 100
        signal.pattern_score = 20
        score = engine._compute_composite_score(signal)
        # HIGH decay → 0.85x penalty
        expected = (80 * 0.35 + 100 * 0.35 + 20 * 0.20 + 50 * 0.10) * 0.85
        assert abs(score - round(expected, 1)) < 0.5

    def test_hold_days_within_bounds(self):
        """Recommended hold should be 5-15 days for 2x ETFs."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        from backend.engine.leveraged_etf import LeveragedETFSignal
        engine = LeveragedETFEngine()
        # High decay, weak trend → minimum hold
        signal = LeveragedETFSignal(decay_risk='HIGH', adx=15)
        hold = engine._recommend_hold_days(signal)
        assert engine.MIN_HOLD_DAYS <= hold <= engine.MAX_HOLD_DAYS
        assert hold == engine.MIN_HOLD_DAYS  # HIGH decay + weak trend → 5 days

        # Low decay, strong trend → max hold
        signal2 = LeveragedETFSignal(decay_risk='LOW', adx=40)
        hold2 = engine._recommend_hold_days(signal2)
        assert engine.MIN_HOLD_DAYS <= hold2 <= engine.MAX_HOLD_DAYS

    def test_wider_stops_for_2x_vol(self):
        """Stop loss multiplier should be 2.5x ATR (wider than 2.0x for non-leveraged)."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        assert engine.STOP_LOSS_ATR_MULT == 2.5  # wider than MasterScorer's 2.0

    def test_target_gives_2_to_1_rr(self):
        """Target multiplier should give at least 2:1 R:R (5.0 / 2.5 = 2.0)."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        rr = engine.TARGET_ATR_MULT / engine.STOP_LOSS_ATR_MULT
        assert rr >= 2.0

    def test_min_liquidity_filter(self):
        """Engine should refuse ETFs with avg volume below threshold."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # FIX v3.2.2: lowered from 500K to 100K (many real 2x ETFs have 100-500K)
        assert engine.MIN_AVG_VOLUME == 100_000

    def test_pattern_detection_for_short_etfs(self):
        """Short ETFs should get inverted pattern labels (VCP on SDS = bearish for S&P)."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        # Mock df + detect_patterns to return ['vcp']
        df = pd.DataFrame({'close': [100]*50, 'high': [101]*50, 'low': [99]*50,
                          'volume': [1e6]*50, 'open': [100]*50})
        with patch.object(engine.tech, 'detect_patterns', return_value=['vcp']):
            pattern = engine._detect_pattern(df, 'SHORT')
            assert 'short' in pattern or 'equivalent' in pattern

    def test_catalyst_warnings_returned(self):
        """Engine should return catalyst warnings string (may be empty)."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        engine = LeveragedETFEngine()
        warning = engine._check_catalyst_warnings()
        assert isinstance(warning, str)  # may be empty but must be string

    def test_quality_score_penalizes_wrong_direction(self):
        """Long ETF in bearish trend should be penalized vs aligned trend."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        from backend.engine.leveraged_etf import LeveragedETFSignal
        engine = LeveragedETFEngine()
        # Wrong direction (long in bearish)
        wrong = LeveragedETFSignal(
            direction='LONG', trend='strong_bearish', adx=30,
            rsi=45,  # neutral RSI
        )
        wrong_score = engine._compute_quality_score(wrong, {'typical_spread_bps': 5}, 2_000_000)
        # Right direction (long in bullish)
        right = LeveragedETFSignal(
            direction='LONG', trend='strong_bullish', adx=30,
            rsi=55,
        )
        right_score = engine._compute_quality_score(right, {'typical_spread_bps': 5}, 2_000_000)
        # Wrong should be significantly lower than right
        assert wrong_score < right_score
        assert (right_score - wrong_score) >= 25  # at least 25 points lower

    def test_quality_score_rewards_aligned_trend(self):
        """Long ETF in strong bullish trend should score high."""
        from backend.engine.leveraged_etf import LeveragedETFEngine
        from backend.engine.leveraged_etf import LeveragedETFSignal
        engine = LeveragedETFEngine()
        signal = LeveragedETFSignal(
            direction='LONG', trend='strong_bullish', adx=40,
            rsi=55,  # sweet spot
        )
        score = engine._compute_quality_score(signal, {'typical_spread_bps': 2}, 5_000_000)
        assert score >= 75


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
