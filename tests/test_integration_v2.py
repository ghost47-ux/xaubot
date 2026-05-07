"""
Integration test for XAU/USD Signal Engine v2.0

Tests that all modules integrate correctly and produce expected outputs.
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from config import settings
from state.models import *
from indicators.core import ema, atr, swing_low, body_ratio, wick_ratio, classify_volatility, classify_session
from regimes.engine import classify_regime
from edges.edge1.detector import detect_edge1
from edges.edge2.detector import detect_edge2, detect_compression_zones, classify_breakout
from overlap.engine import apply_overlap_rules
from risk.engine import assess_risk
from drift.detector import detect_drift
from parity.monitor import run_parity_check


def _create_sample_ohlcv_data(n_bars=100, base_price=2000.0, seed=42) -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    np.random.seed(seed)
    timestamps = [datetime.now(timezone.utc) - timedelta(hours=i) for i in range(n_bars)]
    timestamps = sorted(timestamps)
    
    closes = [base_price + np.random.randn() * 5 for _ in range(n_bars)]
    opens = [closes[0]] + [closes[i-1] for i in range(1, n_bars)]
    highs = [max(opens[i], closes[i]) + abs(np.random.randn() * 2) for i in range(n_bars)]
    lows = [min(opens[i], closes[i]) - abs(np.random.randn() * 2) for i in range(n_bars)]
    volumes = [np.random.randint(1000, 10000) for _ in range(n_bars)]
    
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })


class TestIndicators:
    """Test indicator calculations."""
    
    def test_ema_calculation(self):
        """EMA should be a smooth line."""
        df = _create_sample_ohlcv_data(50)
        ema_series = ema(df['close'], 20)
        
        # EMA should be initialized at bar 19+
        assert not pd.isna(ema_series.iloc[25])
        # EMA should be between min and max
        assert ema_series.iloc[25] > df['close'].min()
        assert ema_series.iloc[25] < df['close'].max()
    
    def test_atr_calculation(self):
        """ATR should be positive."""
        df = _create_sample_ohlcv_data(50)
        atr_series = atr(df, 14)
        
        # ATR should be positive
        valid_atr = atr_series.dropna()
        assert (valid_atr > 0).all()
    
    def test_body_ratio(self):
        """Body ratio should be between 0 and 1."""
        row = {'open': 100, 'close': 110, 'high': 115, 'low': 95}
        ratio = body_ratio(row)
        assert 0 <= ratio <= 1
    
    def test_classify_session(self):
        """Session classification should work."""
        # Test known times
        assert classify_session(5, 0) == SessionName.ASIAN
        assert classify_session(8, 30) == SessionName.LONDON_OPEN
        assert classify_session(10, 0) == SessionName.LONDON_MAIN
        assert classify_session(15, 0) == SessionName.NY_MAIN
        assert classify_session(20, 0) == SessionName.OFF
    
    def test_classify_volatility(self):
        """Volatility should classify correctly."""
        atr_current = 1.0
        atr_mean_20 = 1.0
        
        assert classify_volatility(atr_current, atr_mean_20) == VolatilityState.NORMAL
        assert classify_volatility(0.5, 1.0) == VolatilityState.LOW
        assert classify_volatility(2.0, 1.0) == VolatilityState.HIGH


class TestRegimeEngine:
    """Test regime classification."""
    
    def test_classify_regime_bull(self):
        """Should detect BULL trend when ema20 > ema50 > ema200."""
        df = _create_sample_ohlcv_data(100, base_price=2050.0)
        
        # Create uptrend
        for i in range(100):
            df.loc[i, 'close'] = 2000 + i * 1.0
        
        current_bar = 99
        regime = classify_regime(df, current_bar, df.iloc[current_bar]['timestamp'])
        
        # Should detect bull trend
        assert regime.trend_1h == TrendState.BULL or regime.trend_1h.value == 'BULL'


class TestOverlapEngine:
    """Test overlap rules."""
    
    def test_no_overlap_when_single_signal(self):
        """Should not modify sizing when only one signal active."""
        e1 = Edge1Signal(
            timestamp=datetime.now(timezone.utc),
            direction='LONG',
            entry_price=2000,
            stop_loss=1950,
            take_profit=2100,
            stop_distance=50,
            dollar_risk=50,
            timeout_bar=100,
            ema20=2010, ema50=1990, ema200=1950,
            atr=5,
            session='NY_Main',
            weekday='MON',
            regime=RegimeState(
                timestamp=datetime.now(timezone.utc),
                trend_1h=TrendState.BULL,
                ema20_1h=2010, ema50_1h=1990, ema200_1h=1950,
                atr_1h=5, volatility=VolatilityState.NORMAL,
                session=SessionName.NY_MAIN, weekday=WeekdayName.TUE,
                hour_utc=13
            ),
            sizing_factor=1.0
        )
        bot_state = BotState(timestamp=datetime.now(timezone.utc))
        
        e1_out, e2_out = apply_overlap_rules(e1, None, bot_state)
        
        # E1 should not be modified
        assert e1_out.sizing_factor == 1.0
        assert not e1_out.overlap_active


class TestRiskEngine:
    """Test risk assessment."""
    
    def test_risk_assessment_e1(self):
        """Risk assessment should calculate correctly for Edge 1."""
        e1 = Edge1Signal(
            timestamp=datetime.now(timezone.utc),
            direction='LONG',
            entry_price=2000,
            stop_loss=1950,
            take_profit=2075,
            stop_distance=50,
            dollar_risk=50,
            timeout_bar=100,
            ema20=2010, ema50=1990, ema200=1950,
            atr=5,
            session='NY_Main',
            weekday='TUE',
            regime=None,
            sizing_factor=1.0
        )
        bot_state = BotState(timestamp=datetime.now(timezone.utc))
        
        risk = assess_risk(e1, bot_state)
        
        # Check risk fields
        assert 'dollar_risk_raw' in risk
        assert 'dollar_risk_adj' in risk
        assert 'rr' in risk
        assert risk['rr'] == settings.E1_RR


class TestDriftDetector:
    """Test drift detection."""
    
    def test_drift_none_when_no_trades(self):
        """Drift should be NONE when no completed trades."""
        regime = RegimeState(
            timestamp=datetime.now(timezone.utc),
            trend_1h=TrendState.BULL,
            ema20_1h=2010, ema50_1h=1990, ema200_1h=1950,
            atr_1h=5, volatility=VolatilityState.NORMAL,
            session=SessionName.NY_MAIN, weekday=WeekdayName.TUE,
            hour_utc=13
        )
        df_1h = _create_sample_ohlcv_data(100)
        
        drift_state = detect_drift([], regime, df_1h, 99, [])
        
        # Should default to NONE when no trades
        assert drift_state.severity == DriftSeverity.NONE


class TestCriticLayer:
    """Test critic layer bounds checking."""
    
    def test_decision_words_detected(self):
        """Decision words should be detected in critic output."""
        from critic.layer import validate_critic_output
        
        text = "I would recommend taking this trade."
        is_bounded, words = validate_critic_output(text)
        
        assert not is_bounded
        assert 'recommend' in [w.lower() for w in words]


def test_end_to_end_signal_generation():
    """Test a complete cycle without data fetch (mock data)."""
    # Create mock data
    df_1h = _create_sample_ohlcv_data(100)
    
    # Create bot state
    bot_state = BotState(timestamp=datetime.now(timezone.utc))
    
    # Test that we can classify regime
    regime = classify_regime(df_1h, 50, df_1h.iloc[50]['timestamp'])
    assert regime is not None
    assert hasattr(regime, 'trend_1h')
    assert hasattr(regime, 'atr_1h')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
