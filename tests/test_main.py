from main import _should_call_critic
from state.models import DriftState, DriftSeverity, ParityState, ParityStatus


def test_should_call_critic_for_trade():
    drift = DriftState(
        timestamp=None,
        severity=DriftSeverity.NONE,
        e1_rolling_ev=None,
        e1_rolling_wr=None,
        e1_consecutive_losses=0,
        e1_trade_count=0,
        e2_rolling_ev=None,
        e2_rolling_wr=None,
        e2_consecutive_losses=0,
        e2_trade_count=0,
        atr_1h_current=0.0,
        atr_1h_mean_90d=0.0,
        atr_ratio=1.0,
        volatility_outside_backtest=False,
        regime_flip_count_14d=0,
        regime_choppy=False,
        e1_session_ev={},
        session_rotation_flag=False,
        active_flags=[]
    )
    parity = ParityState(
        timestamp=None,
        status=ParityStatus.OK,
        ema20_check=None,
        ema50_check=None,
        ema200_check=None,
        atr_1h_check=None,
        atr_m15_check=None,
        swing_low_check=None,
        session_check=None,
        candles_checked=0,
        missing_candles_1h=0,
        missing_candles_m15=0,
        data_quality_ok=True,
        cumulative_ema20_drift=0.0,
        cumulative_atr_drift=0.0,
        parity_check_count=0,
        failed_checks=[]
    )
    assert _should_call_critic('TRADE', drift, parity)


def test_should_call_critic_for_alert():
    drift = DriftState(
        timestamp=None,
        severity=DriftSeverity.ALERT,
        e1_rolling_ev=None,
        e1_rolling_wr=None,
        e1_consecutive_losses=0,
        e1_trade_count=0,
        e2_rolling_ev=None,
        e2_rolling_wr=None,
        e2_consecutive_losses=0,
        e2_trade_count=0,
        atr_1h_current=0.0,
        atr_1h_mean_90d=0.0,
        atr_ratio=1.0,
        volatility_outside_backtest=False,
        regime_flip_count_14d=0,
        regime_choppy=False,
        e1_session_ev={},
        session_rotation_flag=False,
        active_flags=[]
    )
    parity = ParityState(
        timestamp=None,
        status=ParityStatus.OK,
        ema20_check=None,
        ema50_check=None,
        ema200_check=None,
        atr_1h_check=None,
        atr_m15_check=None,
        swing_low_check=None,
        session_check=None,
        candles_checked=0,
        missing_candles_1h=0,
        missing_candles_m15=0,
        data_quality_ok=True,
        cumulative_ema20_drift=0.0,
        cumulative_atr_drift=0.0,
        parity_check_count=0,
        failed_checks=[]
    )
    assert _should_call_critic('NO_TRADE', drift, parity)
