# parity/monitor.py
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from config import settings
from indicators.core import ema, atr, swing_low
from state.models import ParityState, ParityCheck, ParityStatus

REFERENCE_PATH = os.path.join(os.getcwd(), 'data', 'backtest_ref', 'reference.parquet')


def load_reference_snapshot(timestamp: datetime) -> Optional[dict]:
    if not os.path.exists(REFERENCE_PATH):
        return None
    ref = pd.read_parquet(REFERENCE_PATH)
    match = ref[ref['timestamp'] == timestamp]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def check_absolute(live_value: float, reference_value: float, tolerance: float, indicator_name: str) -> ParityCheck:
    diff = abs(live_value - reference_value)
    passed = diff <= tolerance
    return ParityCheck(
        indicator_name=indicator_name,
        live_value=live_value,
        reference_value=reference_value,
        difference=diff,
        difference_pct=(diff / reference_value if reference_value else 0.0),
        tolerance=tolerance,
        passed=passed,
        timestamp=datetime.now(timezone.utc)
    )


def check_percent(live_value: float, reference_value: float, tolerance_pct: float, indicator_name: str) -> ParityCheck:
    diff = abs(live_value - reference_value)
    diff_pct = diff / reference_value if reference_value else 0.0
    passed = diff_pct <= tolerance_pct / 100.0
    return ParityCheck(
        indicator_name=indicator_name,
        live_value=live_value,
        reference_value=reference_value,
        difference=diff,
        difference_pct=diff_pct,
        tolerance=tolerance_pct,
        passed=passed,
        timestamp=datetime.now(timezone.utc)
    )


def check_session(live_session: str, reference_session: str, tolerance_min: int) -> ParityCheck:
    passed = live_session == reference_session
    difference = 0.0 if passed else tolerance_min + 1.0
    return ParityCheck(
        indicator_name='session',
        live_value=0.0 if passed else difference,
        reference_value=0.0,
        difference=difference,
        difference_pct=0.0,
        tolerance=tolerance_min,
        passed=passed,
        timestamp=datetime.now(timezone.utc)
    )


def count_missing_candles(df: pd.DataFrame, interval: str, lookback: int) -> int:
    if df.empty:
        return 0
    diffs = df['timestamp'].diff().dropna().dt.total_seconds()
    expected = 3600 if interval == '1H' else 900
    missing = [int(diff / expected) - 1 for diff in diffs if diff > expected]
    return sum(missing)


def run_parity_check(df_1h, df_m15, current_bar_1h, current_bar_m15, regime) -> ParityState:
    current_ts = df_1h.iloc[current_bar_1h]['timestamp']
    ref = load_reference_snapshot(current_ts)
    if ref is None:
        empty_check = ParityCheck('missing', 0.0, 0.0, 0.0, 0.0, 0.0, False, datetime.now(timezone.utc))
        return ParityState(
            timestamp=current_ts,
            status=ParityStatus.WARNING,
            ema20_check=empty_check,
            ema50_check=empty_check,
            ema200_check=empty_check,
            atr_1h_check=empty_check,
            atr_m15_check=empty_check,
            swing_low_check=empty_check,
            session_check=empty_check,
            candles_checked=0,
            missing_candles_1h=0,
            missing_candles_m15=0,
            data_quality_ok=False,
            cumulative_ema20_drift=0.0,
            cumulative_atr_drift=0.0,
            parity_check_count=0,
            failed_checks=['reference_missing']
        )

    live_ema20 = ema(df_1h['close'], 20).iloc[current_bar_1h]
    live_ema50 = ema(df_1h['close'], 50).iloc[current_bar_1h]
    live_ema200 = ema(df_1h['close'], 200).iloc[current_bar_1h]
    live_atr_1h = atr(df_1h, 14).iloc[current_bar_1h]
    live_atr_m15 = atr(df_m15, 14).iloc[current_bar_m15]
    live_swing_l = swing_low(df_1h.iloc[current_bar_1h - 9: current_bar_1h + 1], 10).iloc[-1]

    ema20_check = check_absolute(live_ema20, ref.get('ema20_1h', 0.0), settings.PARITY_EMA_TOLERANCE, 'ema20')
    ema50_check = check_absolute(live_ema50, ref.get('ema50_1h', 0.0), settings.PARITY_EMA_TOLERANCE, 'ema50')
    ema200_check = check_absolute(live_ema200, ref.get('ema200_1h', 0.0), settings.PARITY_EMA_TOLERANCE, 'ema200')
    atr_1h_check = check_percent(live_atr_1h, ref.get('atr_1h', 0.0), settings.PARITY_ATR_TOLERANCE_PCT, 'atr_1h')
    atr_m15_check = check_percent(live_atr_m15, ref.get('atr_m15', 0.0), settings.PARITY_ATR_TOLERANCE_PCT, 'atr_m15')
    swing_low_check = check_absolute(live_swing_l, ref.get('swing_low_10', 0.0), settings.PARITY_SWING_TOLERANCE, 'swing_low_10')
    session_check = check_session(regime.session.value, ref.get('session', ''), settings.PARITY_SESSION_TOLERANCE_MIN)

    missing_1h = count_missing_candles(df_1h, '1H', 48)
    missing_m15 = count_missing_candles(df_m15, 'M15', 192)
    data_quality_ok = missing_1h <= settings.PARITY_MAX_GAP_CANDLES and missing_m15 <= settings.PARITY_MAX_GAP_CANDLES

    failed = [check.indicator_name for check in [ema20_check, ema50_check, ema200_check, atr_1h_check, atr_m15_check, swing_low_check, session_check] if not check.passed]

    if len(failed) == 0 and missing_1h == 0 and missing_m15 == 0:
        status = ParityStatus.OK
    elif len(failed) == 1 or (missing_1h <= settings.PARITY_MAX_GAP_CANDLES and missing_m15 <= settings.PARITY_MAX_GAP_CANDLES):
        status = ParityStatus.WARNING
    else:
        status = ParityStatus.BREACH

    return ParityState(
        timestamp=current_ts,
        status=status,
        ema20_check=ema20_check,
        ema50_check=ema50_check,
        ema200_check=ema200_check,
        atr_1h_check=atr_1h_check,
        atr_m15_check=atr_m15_check,
        swing_low_check=swing_low_check,
        session_check=session_check,
        candles_checked=7,
        missing_candles_1h=missing_1h,
        missing_candles_m15=missing_m15,
        data_quality_ok=data_quality_ok,
        cumulative_ema20_drift=abs(ema20_check.difference),
        cumulative_atr_drift=abs(atr_1h_check.difference),
        parity_check_count=1,
        failed_checks=failed
    )
