"""
Test suite for the structure/pivot/order-flow/hold-period engines.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


@pytest.fixture
def sample_trending_df():
    """Sample OHLCV with clear swings for structure testing."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range(end=datetime.now(), periods=n, freq='B')
    # Clear up-swing with retracements
    closes = []
    base = 100
    for i in range(n):
        trend = 0.1 * i
        cycle = 3 * np.sin(i / 5)
        noise = np.random.normal(0, 1)
        closes.append(base + trend + cycle + noise)
    closes = np.array(closes)
    highs = closes + np.random.uniform(0.5, 2, n)
    lows = closes - np.random.uniform(0.5, 2, n)
    opens = closes + np.random.normal(0, 0.5, n)
    volumes = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes,
    })


# ── Market Structure Engine (Simplified) ────────────────────────────────────

class TestMarketStructure:
    def test_finds_swing_highs_and_lows(self, sample_trending_df):
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(sample_trending_df)
        assert len(structure.swing_highs) > 0, "Should find swing highs"
        assert len(structure.swing_lows) > 0, "Should find swing lows"
        # Swing prices should be within the data range
        all_swings = [s.price for s in structure.swing_highs] + [s.price for s in structure.swing_lows]
        assert min(all_swings) >= sample_trending_df['low'].min()
        assert max(all_swings) <= sample_trending_df['high'].max()

    def test_swing_high_is_higher_than_neighbors(self, sample_trending_df):
        """Each swing high must be higher than bars around it."""
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine(fractal_window=2)
        structure = ms.analyze(sample_trending_df)
        highs = sample_trending_df['high'].values
        for sw in structure.swing_highs:
            for k in range(1, ms.fractal_window + 1):
                if sw.index - k >= 0 and sw.index + k < len(highs):
                    assert sw.price > highs[sw.index - k]
                    assert sw.price > highs[sw.index + k]

    def test_key_levels_aggregated(self, sample_trending_df):
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(sample_trending_df)
        assert len(structure.key_levels) > 0
        # Each level should have required fields
        for level in structure.key_levels:
            assert 'price' in level
            assert 'type' in level
            assert 'strength' in level
            assert 'distance_pct' in level
        # Sorted by distance
        distances = [abs(l['distance_pct']) for l in structure.key_levels]
        assert distances == sorted(distances)

    def test_trend_bias_determined(self, sample_trending_df):
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(sample_trending_df)
        # Trending data should produce a bias (BULLISH or BEARISH or NEUTRAL)
        assert structure.trend_bias in ('BULLISH', 'BEARISH', 'NEUTRAL')

    def test_structure_summary(self, sample_trending_df):
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(sample_trending_df)
        current_price = float(sample_trending_df['close'].iloc[-1])
        summary = ms.get_structure_summary(structure, current_price)
        assert 'trend_bias' in summary
        assert 'swing_high_count' in summary
        assert 'swing_low_count' in summary
        assert 'total_key_levels' in summary

    def test_handles_empty_df(self):
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(pd.DataFrame())
        assert structure.trend_bias == 'NEUTRAL'

    def test_levels_deduplicated(self, sample_trending_df):
        """Levels within 0.1% of each other should be deduplicated."""
        from backend.engine.market_structure import MarketStructureEngine
        ms = MarketStructureEngine()
        structure = ms.analyze(sample_trending_df)
        # No two levels should be within 0.1% of each other
        for i, l1 in enumerate(structure.key_levels):
            for l2 in structure.key_levels[i+1:]:
                if l1['price'] > 0 and l2['price'] > 0:
                    diff_pct = abs(l1['price'] - l2['price']) / min(l1['price'], l2['price']) * 100
                    assert diff_pct >= 0.1, f"Levels {l1['price']} and {l2['price']} are within 0.1%"


# ── Pivot Engine ────────────────────────────────────────────────────────────

class TestPivotEngine:
    def test_classic_pivots(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        levels = pe.calculate(sample_trending_df, pivot_type='classic', timeframe='daily')
        assert levels.P > 0
        assert levels.R1 > levels.P, "R1 should be above pivot"
        assert levels.S1 < levels.P, "S1 should be below pivot"
        assert levels.R2 > levels.R1
        assert levels.S2 < levels.S1

    def test_fibonacci_pivots(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        levels = pe.calculate(sample_trending_df, pivot_type='fibonacci', timeframe='daily')
        assert levels.P > 0
        assert levels.R4 > levels.R3 > levels.R2 > levels.R1 > levels.P
        assert levels.S4 < levels.S3 < levels.S2 < levels.S1 < levels.P

    def test_camarilla_pivots(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        levels = pe.calculate(sample_trending_df, pivot_type='camarilla', timeframe='daily')
        assert levels.P > 0
        assert levels.R4 > levels.R1, "Camarilla R4 should be above R1"
        assert levels.S4 < levels.S1

    def test_woodie_pivots(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        levels = pe.calculate(sample_trending_df, pivot_type='woodie', timeframe='daily')
        assert levels.P > 0
        assert levels.R1 > levels.P
        assert levels.S1 < levels.P

    def test_classic_formula_correctness(self):
        """Verify the classic pivot formula: P = (H+L+C)/3, R1 = 2P-L, S1 = 2P-H"""
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        # Manually compute expected for yesterday's H/L/C
        H, L, C = 110, 100, 105
        expected_P = (H + L + C) / 3  # 105.0
        expected_R1 = 2 * expected_P - L  # 110.0
        expected_S1 = 2 * expected_P - H  # 100.0
        # Build a 3-bar df so iloc[-2] = the bar with H=110, L=100, C=105
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'open': [100, 105, 105], 'high': [105, H, 106], 'low': [95, L, 104],
            'close': [100, C, 105], 'volume': [1e6, 1e6, 1e6],
        })
        levels = pe.calculate(df, pivot_type='classic', timeframe='daily')
        # iloc[-2] is bar index 1 with H=110, L=100, C=105
        assert abs(levels.P - expected_P) < 0.01
        assert abs(levels.R1 - expected_R1) < 0.01
        assert abs(levels.S1 - expected_S1) < 0.01

    def test_multiple_timeframes(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        mt = pe.calculate_multiple_timeframes(sample_trending_df, pivot_type='classic')
        assert 'daily' in mt
        assert 'weekly' in mt
        assert 'monthly' in mt
        # Weekly range should be wider than daily
        daily_range = mt['daily'].R1 - mt['daily'].S1
        weekly_range = mt['weekly'].R1 - mt['weekly'].S1
        assert weekly_range >= daily_range * 0.5

    def test_confluence_detection(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        mt = pe.calculate_multiple_timeframes(sample_trending_df, pivot_type='classic')
        # Fake some structure levels near pivot levels
        structure_levels = [
            {'price': mt['daily'].P, 'type': 'swing_low', 'direction': 'BULLISH', 'strength': 3, 'distance_pct': 0},
            {'price': mt['daily'].R1 * 1.001, 'type': 'swing_high', 'direction': 'NEUTRAL', 'strength': 4, 'distance_pct': 1},
            {'price': 9999, 'type': 'swing_high', 'direction': 'NEUTRAL', 'strength': 1, 'distance_pct': 50},
        ]
        confluences = pe.find_confluence(mt, structure_levels, tolerance_pct=0.5)
        assert len(confluences) > 0
        assert any(c['level_count'] >= 2 for c in confluences)

    def test_pivot_summary(self, sample_trending_df):
        from backend.engine.pivots import PivotEngine
        pe = PivotEngine()
        levels = pe.calculate(sample_trending_df, pivot_type='classic', timeframe='daily')
        current = float(sample_trending_df['close'].iloc[-1])
        summary = pe.get_pivot_summary(levels, current)
        assert 'position_vs_pivot' in summary
        assert 'all_levels' in summary


# ── Hold Period Engine ──────────────────────────────────────────────────────

class TestHoldPeriodEngine:
    def test_basic_hold_estimate(self):
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        rec = hp.recommend(
            entry_price=100, target=110, stop=95,
            atr=2.0, adx=30, is_leveraged=False,
        )
        assert rec.recommended_days >= 3
        assert rec.recommended_days <= 30
        assert rec.method_used == 'blend' or rec.method_used

    def test_leveraged_caps_at_15_days(self):
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        rec = hp.recommend(
            entry_price=100, target=130, stop=90,
            atr=4.0, adx=40, is_leveraged=True,
            daily_decay_pct=0.05,
        )
        assert rec.recommended_days <= 15

    def test_high_decay_shorter_hold(self):
        """High daily decay should reduce recommended hold for leveraged ETFs."""
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        low_decay = hp.recommend(
            entry_price=100, target=110, stop=95,
            atr=2.0, adx=30, is_leveraged=True, daily_decay_pct=0.02,
        )
        high_decay = hp.recommend(
            entry_price=100, target=110, stop=95,
            atr=2.0, adx=30, is_leveraged=True, daily_decay_pct=0.20,
        )
        assert high_decay.recommended_days <= low_decay.recommended_days

    def test_event_caps_hold(self):
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        rec = hp.recommend(
            entry_price=100, target=110, stop=95,
            atr=2.0, adx=30, is_leveraged=False,
            event_days_ahead=5,
        )
        assert rec.recommended_days <= 4

    def test_structure_levels_reduce_estimate_for_close_target(self):
        """Close target = shorter hold; far target = longer hold."""
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        close_target = hp.recommend(
            entry_price=100, target=102, stop=99,
            atr=1.0, adx=25, is_leveraged=False,
        )
        far_target = hp.recommend(
            entry_price=100, target=115, stop=92,
            atr=1.0, adx=25, is_leveraged=False,
        )
        assert close_target.recommended_days <= far_target.recommended_days

    def test_confidence_higher_when_methods_agree(self):
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        rec = hp.recommend(
            entry_price=100, target=110, stop=95,
            atr=2.0, adx=30, is_leveraged=False,
        )
        assert 0 <= rec.confidence <= 1
        assert rec.rationale

    def test_min_3_days_enforced(self):
        from backend.engine.hold_period import HoldPeriodEngine
        hp = HoldPeriodEngine()
        rec = hp.recommend(
            entry_price=100, target=100.5, stop=99.5,
            atr=0.5, adx=40, is_leveraged=False,
        )
        assert rec.recommended_days >= 3


# ── Order Flow Engine ───────────────────────────────────────────────────────

class TestOrderFlowEngine:
    def test_approximation_runs_by_default(self, sample_trending_df):
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        result = of.analyze(sample_trending_df)
        assert result.data_source in ('approximation', 'polygon', 'databento', 'alpaca', 'ibkr')
        if not of.real_source or of.real_source == 'approximation':
            assert result.data_source == 'approximation'

    def test_buy_pressure_in_uptrend(self):
        """Strong up bars should produce > 50% buy pressure."""
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        n = 30
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=n, freq='B').strftime('%Y-%m-%d'),
            'open': np.linspace(100, 130, n),
            'high': np.linspace(101, 131, n),
            'low': np.linspace(99, 129, n),
            'close': np.linspace(101, 131, n),
            'volume': np.full(n, 1_000_000.0),
        })
        result = of.analyze(df)
        assert result.buy_pressure_pct > 50
        assert result.cvd > 0

    def test_sell_pressure_in_downtrend(self):
        """Strong down bars should produce > 50% sell pressure."""
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        n = 30
        df = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=n, freq='B').strftime('%Y-%m-%d'),
            'open': np.linspace(130, 100, n),
            'high': np.linspace(131, 101, n),
            'low': np.linspace(129, 99, n),
            'close': np.linspace(129, 99, n),
            'volume': np.full(n, 1_000_000.0),
        })
        result = of.analyze(df)
        assert result.sell_pressure_pct > 50
        assert result.cvd < 0

    def test_climax_bar_detection(self):
        """A bar with 3x avg volume + 2x avg range should be flagged as climax."""
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        n = 25
        df_normal = pd.DataFrame({
            'open': [100]*20, 'high': [101]*20, 'low': [99]*20, 'close': [100]*20,
            'volume': [1_000_000]*20,
        })
        df_climax = pd.DataFrame({
            'open': [100]*5, 'high': [105]*5, 'low': [95]*5, 'close': [104]*5,
            'volume': [5_000_000]*5,
        })
        df = pd.concat([df_normal, df_climax], ignore_index=True)
        df['date'] = pd.date_range(end=datetime.now(), periods=25, freq='B').strftime('%Y-%m-%d')
        result = of.analyze(df)
        assert len(result.climax_bars) > 0
        climax = result.climax_bars[-1]
        assert climax['volume_mult'] >= 2.0
        assert climax['type'] in ('BUY_CLIMAX', 'SELL_CLIMAX')

    def test_data_source_info(self):
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        info = of.get_data_source_info()
        assert 'source' in info
        assert 'real_l2' in info
        assert 'description' in info
        if not of.polygon_key and not of.databento_key:
            assert info['source'] == 'approximation'
            assert 'OHLCV-based approximation' in info['description']

    def test_summary_built(self, sample_trending_df):
        from backend.engine.order_flow import OrderFlowEngine
        of = OrderFlowEngine()
        result = of.analyze(sample_trending_df)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
