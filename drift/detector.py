# drift/detector.py
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from state.models import DriftState, DriftFlag, DriftSeverity, RegimeState
from config import settings


def _parse_timestamp(entry: Dict) -> Optional[datetime]:
    ts = entry.get('timestamp_utc') or entry.get('timestamp')
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            return None
    if isinstance(ts, datetime):
        return ts
    return None


def _count_consecutive_losses(completed: List[Dict]) -> int:
    count = 0
    for trade in reversed(completed):
        if trade.get('outcome') == 'LOSS':
            count += 1
        elif trade.get('outcome') == 'WIN':
            break
    return count


def _compute_session_ev(completed: List[Dict], session: str, lookback: int) -> float:
    filtered = [t for t in completed if t.get('session') == session]
    window = filtered[-lookback:]
    if not window:
        return 0.0
    return sum([t.get('result_r', 0.0) for t in window]) / len(window)


def _detect_session_rotation(e1_session_ev: Dict[str, float]) -> bool:
    if not e1_session_ev:
        return False
    values = list(e1_session_ev.values())
    return max(values) - min(values) > 0 and list(e1_session_ev.values()).index(min(values)) != list(e1_session_ev.values()).index(max(values))


def _count_trend_flips(trend_list: List[str]) -> int:
    flips = 0
    for prev, curr in zip(trend_list, trend_list[1:]):
        if prev != curr:
            flips += 1
    return flips


def detect_drift(trade_log: List[Dict], regime: RegimeState, df_1h, current_bar: int) -> DriftState:
    e1_completed = [t for t in trade_log if t.get('edge_source') == 'EDGE1' and t.get('outcome') in ['WIN', 'LOSS', 'TIMEOUT']]
    e2_completed = [t for t in trade_log if t.get('edge_source') == 'EDGE2' and t.get('outcome') in ['WIN', 'LOSS', 'TIMEOUT']]

    window = settings.DRIFT_EV_WINDOW_TRADES
    e1_rolling_ev = None
    e1_rolling_wr = None
    if len(e1_completed) >= window:
        window_e1 = e1_completed[-window:]
        e1_rolling_ev = sum([t.get('result_r', 0.0) for t in window_e1]) / window
        e1_rolling_wr = sum([1 if t.get('outcome') == 'WIN' else 0 for t in window_e1]) / window

    e2_rolling_ev = None
    e2_rolling_wr = None
    if len(e2_completed) >= window:
        window_e2 = e2_completed[-window:]
        e2_rolling_ev = sum([t.get('result_r', 0.0) for t in window_e2]) / window
        e2_rolling_wr = sum([1 if t.get('outcome') == 'WIN' else 0 for t in window_e2]) / window

    e1_consecutive_losses = _count_consecutive_losses(e1_completed)
    e2_consecutive_losses = _count_consecutive_losses(e2_completed)

    atr_history = df_1h['atr_1h'] if 'atr_1h' in df_1h.columns else df_1h['atr'] if 'atr' in df_1h.columns else None
    if atr_history is not None:
        atr_1h_mean_90d = atr_history.iloc[max(0, current_bar - 90): current_bar + 1].mean()
    else:
        atr_1h_mean_90d = regime.atr_1h
    atr_ratio = regime.atr_1h / atr_1h_mean_90d if atr_1h_mean_90d else 1.0
    volatility_outside_backtest = atr_ratio > settings.DRIFT_ATR_MULTIPLIER_HIGH or atr_ratio < settings.DRIFT_ATR_MULTIPLIER_LOW

    cutoff = regime.timestamp - timedelta(days=settings.DRIFT_REGIME_FLIP_WINDOW)
    recent_regimes = [t for t in trade_log if _parse_timestamp(t) and _parse_timestamp(t) >= cutoff]
    trend_states = [t.get('trend_1h') for t in recent_regimes if t.get('trend_1h')]
    regime_flip_count_14d = _count_trend_flips(trend_states)
    regime_choppy = regime_flip_count_14d > settings.DRIFT_REGIME_FLIP_THRESHOLD

    e1_session_ev = {
        'London_Open': _compute_session_ev(e1_completed, 'London_Open', settings.DRIFT_SESSION_EV_LOOKBACK),
        'London_Main': _compute_session_ev(e1_completed, 'London_Main', settings.DRIFT_SESSION_EV_LOOKBACK),
        'NY_Main': _compute_session_ev(e1_completed, 'NY_Main', settings.DRIFT_SESSION_EV_LOOKBACK),
    }
    session_rotation_flag = _detect_session_rotation(e1_session_ev)

    flags: List[DriftFlag] = []
    if e1_rolling_ev is not None and e1_rolling_ev < settings.DRIFT_EV_THRESHOLD_E1:
        flags.append(DriftFlag(
            flag_type='EV_BELOW_THRESHOLD_E1',
            description=f"Edge 1 rolling EV = {e1_rolling_ev:.3f}R over last {window} trades. Research baseline: +0.29R. Threshold: +{settings.DRIFT_EV_THRESHOLD_E1}R. This may indicate regime shift or edge decay.",
            current_value=e1_rolling_ev,
            threshold=settings.DRIFT_EV_THRESHOLD_E1,
            trades_in_window=len(e1_completed[-window:]),
            timestamp=regime.timestamp
        ))
    if e1_rolling_wr is not None and e1_rolling_wr < settings.DRIFT_WR_THRESHOLD_E1:
        flags.append(DriftFlag(
            flag_type='WR_BELOW_THRESHOLD_E1',
            description=f"Edge 1 rolling win rate = {e1_rolling_wr:.1%} over last {window} trades. Baseline: ~50%.",
            current_value=e1_rolling_wr,
            threshold=settings.DRIFT_WR_THRESHOLD_E1,
            trades_in_window=len(e1_completed[-window:]),
            timestamp=regime.timestamp
        ))
    if e1_consecutive_losses >= settings.DRIFT_CONSECUTIVE_LOSS_E1:
        flags.append(DriftFlag(
            flag_type='CONSECUTIVE_LOSSES_E1',
            description=f"Edge 1 has recorded {e1_consecutive_losses} consecutive losses. Fast-decay warning.",
            current_value=float(e1_consecutive_losses),
            threshold=float(settings.DRIFT_CONSECUTIVE_LOSS_E1),
            trades_in_window=len(e1_completed),
            timestamp=regime.timestamp
        ))
    if volatility_outside_backtest:
        direction = 'HIGH' if atr_ratio > settings.DRIFT_ATR_MULTIPLIER_HIGH else 'LOW'
        flags.append(DriftFlag(
            flag_type=f'VOLATILITY_OUTSIDE_BACKTEST_{direction}',
            description=f"Current ATR = {regime.atr_1h:.2f}. 90d mean ATR = {atr_1h_mean_90d:.2f}. Ratio = {atr_ratio:.2f}. Market volatility is outside the distribution this edge was validated on.",
            current_value=atr_ratio,
            threshold=settings.DRIFT_ATR_MULTIPLIER_HIGH if direction == 'HIGH' else settings.DRIFT_ATR_MULTIPLIER_LOW,
            trades_in_window=len(e1_completed) + len(e2_completed),
            timestamp=regime.timestamp
        ))
    if regime_choppy:
        flags.append(DriftFlag(
            flag_type='REGIME_CHOPPY',
            description=f"Trend state has flipped {regime_flip_count_14d} times in the last 14 days (threshold: {settings.DRIFT_REGIME_FLIP_THRESHOLD}). Edge 1 is a trend-following system. Choppy regimes reduce its validity.",
            current_value=float(regime_flip_count_14d),
            threshold=float(settings.DRIFT_REGIME_FLIP_THRESHOLD),
            trades_in_window=len(recent_regimes),
            timestamp=regime.timestamp
        ))
    if session_rotation_flag:
        flags.append(DriftFlag(
            flag_type='SESSION_LEADERSHIP_SHIFT',
            description="The session producing the highest Edge 1 EV in the last 30 trades differs from the backtested leadership distribution. Monitor.",
            current_value=max(e1_session_ev.values()) if e1_session_ev else 0.0,
            threshold=0.0,
            trades_in_window=len(e1_completed),
            timestamp=regime.timestamp
        ))

    ev_flags = [f for f in flags if 'EV_BELOW' in f.flag_type]
    total_flags = len(flags)
    if total_flags == 0:
        severity = DriftSeverity.NONE
    elif total_flags == 1 and len(ev_flags) == 0:
        severity = DriftSeverity.WATCH
    elif total_flags >= 2 or (total_flags == 1 and len(ev_flags) == 1):
        severity = DriftSeverity.CAUTION
    else:
        severity = DriftSeverity.NONE
    if len(ev_flags) >= 1 and total_flags >= 2:
        severity = DriftSeverity.ALERT

    return DriftState(
        timestamp=regime.timestamp,
        severity=severity,
        e1_rolling_ev=e1_rolling_ev,
        e1_rolling_wr=e1_rolling_wr,
        e1_consecutive_losses=e1_consecutive_losses,
        e1_trade_count=len(e1_completed),
        e2_rolling_ev=e2_rolling_ev,
        e2_rolling_wr=e2_rolling_wr,
        e2_consecutive_losses=e2_consecutive_losses,
        e2_trade_count=len(e2_completed),
        atr_1h_current=regime.atr_1h,
        atr_1h_mean_90d=atr_1h_mean_90d,
        atr_ratio=atr_ratio,
        volatility_outside_backtest=volatility_outside_backtest,
        regime_flip_count_14d=regime_flip_count_14d,
        regime_choppy=regime_choppy,
        e1_session_ev=e1_session_ev,
        session_rotation_flag=session_rotation_flag,
        active_flags=flags
    )
