import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import logging

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

from config import settings
from data import loader
from drift.detector import detect_drift
from edges.edge1.detector import detect_edge1
from edges.edge2.detector import detect_edge2, detect_compression_zones
from overlap.engine import apply_overlap_rules
from regimes.engine import classify_regime
from risk.engine import assess_risk
from signals.output import format_signal
from analytics.logger import log_cycle, update_performance_metrics
from critic.layer import build_critic_context, call_critic
from state.models import BotState, CriticOutput, ParityState, DriftState, DriftSeverity, ParityStatus, SignalType

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    """Get the data directory, using env var or default to project root."""
    data_dir = os.environ.get('DATA_DIR')
    if data_dir:
        return Path(data_dir)
    return Path(__file__).parent / 'data'


def _load_candle_file(path: str, symbol: str, interval: str, n_bars: int):
    """Load candle data from file or API."""
    # Use loader which handles caching and API fetching
    df = loader.load_candles(symbol, interval, n_bars)
    if df.empty or not loader.validate_candles(df):
        logger.warning('Invalid or empty candle data for %s %s', symbol, interval)
        return df  # Return empty to trigger NO_TRADE
    return df


def _initialize_bot_state() -> BotState:
    return BotState(timestamp=datetime.now(timezone.utc))


def _should_call_critic(signal_type: str, drift_state: DriftState, parity_state: ParityState) -> bool:
    if drift_state.severity != DriftSeverity.NONE and settings.CRITIC_CALL_ON_DRIFT_FLAG:
        return True
    if parity_state.status == ParityStatus.BREACH:
        return True
    if signal_type == SignalType.TRADE.value:
        return True
    if signal_type == SignalType.WATCH.value and settings.CRITIC_CALL_ON_WATCH:
        return True
    if signal_type == SignalType.NO_TRADE.value and settings.CRITIC_CALL_ON_NO_TRADE:
        return True
    return False


def run_cycle(bot_state: BotState, trade_log: List[dict], return_metadata: bool = False):
    df_1h = _load_candle_file('candles/xauusd_1h.parquet', 'XAU/USD', '1h', 250)
    df_m15 = _load_candle_file('candles/xauusd_m15.parquet', 'XAU/USD', '15min', 500)

    if not loader.validate_candles(df_1h) or not loader.validate_candles(df_m15):
        signal_text = format_signal(SignalType.NO_TRADE.value, None, None, None, bot_state=bot_state)
        log_cycle({'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'signal_type': SignalType.NO_TRADE.value})
        return signal_text

    current_bar_1h = len(df_1h) - 1
    current_bar_m15 = len(df_m15) - 1
    current_datetime = df_1h.iloc[current_bar_1h]['timestamp']

    if bot_state.last_reset_date != current_datetime.date().isoformat():
        bot_state.e1_trades_today = 0
        bot_state.e2_trades_today = 0
        bot_state.last_reset_date = current_datetime.date().isoformat()

    regime = classify_regime(df_1h, current_bar_1h, current_datetime)
    bot_state.regime = regime
    if not bot_state.regime_history or bot_state.regime_history[-1].timestamp != regime.timestamp:
        bot_state.regime_history.append(regime)

    compression_zones = detect_compression_zones(df_m15)
    e1_signal = detect_edge1(df_1h, current_bar_1h, regime, bot_state)
    e2_signal = detect_edge2(df_m15, current_bar_m15, regime, bot_state, compression_zones)

    e1_signal, e2_signal = apply_overlap_rules(e1_signal, e2_signal, bot_state)

    risk_assessment = None
    if e1_signal:
        bot_state.e1_trades_today += 1
        risk_assessment = assess_risk(e1_signal, bot_state)
    if e2_signal:
        bot_state.e2_trades_today += 1
        if not risk_assessment:
            risk_assessment = assess_risk(e2_signal, bot_state)

    if e1_signal or e2_signal:
        signal_type = SignalType.TRADE.value
    elif compression_zones:
        signal_type = SignalType.WATCH.value
    else:
        signal_type = SignalType.NO_TRADE.value

    parity_state = ParityState(
        timestamp=current_datetime,
        status=ParityStatus.WARNING,
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
        data_quality_ok=False,
        cumulative_ema20_drift=0.0,
        cumulative_atr_drift=0.0,
        parity_check_count=0,
        failed_checks=[]
    )
    if len(df_1h) % settings.PARITY_CHECK_FREQUENCY == 0:
        from parity.monitor import run_parity_check
        parity_state = run_parity_check(df_1h, df_m15, current_bar_1h, current_bar_m15, regime)

    drift_state = detect_drift(trade_log, regime, df_1h, current_bar_1h, bot_state.regime_history)

    edge_source = 'BOTH' if e1_signal and e2_signal else 'EDGE 1' if e1_signal else 'EDGE 2' if e2_signal else 'NONE'
    critic_output = CriticOutput(
        timestamp=datetime.now(timezone.utc),
        critic_called=False,
        signal_type=signal_type,
        edge_source=edge_source,
        contradictions=['None.'],
        confirmations=['None.'],
        drift_flags_in_context=[],
        parity_flags_in_context=[],
        context_notes=['None.'],
        raw_critic_text='CRITIC DISABLED.',
        tokens_used=0,
        output_bounded=True,
        decision_words_found=[]
    )
    if _should_call_critic(signal_type, drift_state, parity_state):
        context = build_critic_context(signal_type, edge_source, e1_signal, e2_signal, regime, drift_state, parity_state, trade_log[-10:])
        critic_output = call_critic(context)

    signal_text = format_signal(
        signal_type,
        e1_signal,
        e2_signal,
        risk_assessment,
        bot_state=bot_state,
        drift_state=drift_state,
        parity_state=parity_state,
        critic_output=critic_output,
        compression_zone=compression_zones[-1] if compression_zones else None
    )

    log_entry = {
        'timestamp_utc': current_datetime.isoformat(),
        'weekday': regime.weekday.name,
        'session': regime.session.value,
        'hour_utc': regime.hour_utc,
        'trend_1h': regime.trend_1h.value,
        'ema20': regime.ema20_1h,
        'ema50': regime.ema50_1h,
        'ema200': regime.ema200_1h,
        'atr': regime.atr_1h,
        'volatility': regime.volatility.value,
        'edge1_fired': e1_signal is not None,
        'edge1_reject_reason': getattr(bot_state, 'e1_reject_reason', None),
        'edge2_fired': e2_signal is not None,
        'edge2_reject_reason': getattr(bot_state, 'e2_reject_reason', None),
        'e2_breakout_class': e2_signal.breakout_class.value if e2_signal else None,
        'e2_direction': e2_signal.direction if e2_signal else None,
        'overlap_active': (e1_signal.overlap_active or e2_signal.overlap_active) if (e1_signal or e2_signal) else False,
        'e2_short_suppressed': e2_signal.e2_short_suppressed if e2_signal else False,
        'sizing_factor': (e1_signal.sizing_factor if e1_signal else e2_signal.sizing_factor if e2_signal else None),
        'entry_price': (e1_signal.entry_price if e1_signal else e2_signal.entry_price if e2_signal else None),
        'stop_loss': (e1_signal.stop_loss if e1_signal else e2_signal.stop_loss if e2_signal else None),
        'take_profit': (e1_signal.take_profit if e1_signal else e2_signal.take_profit if e2_signal else None),
        'stop_distance': (e1_signal.stop_distance if e1_signal else e2_signal.stop_distance if e2_signal else None),
        'dollar_risk': (e1_signal.dollar_risk if e1_signal else e2_signal.dollar_risk if e2_signal else None),
        'dollar_risk_adj': risk_assessment.get('dollar_risk_adj') if risk_assessment else None,
        'rr': risk_assessment.get('rr') if risk_assessment else None,
        'timeout_bars': risk_assessment.get('timeout_hours') if risk_assessment else None,
        'outcome': None,
        'exit_price': None,
        'pnl_usd': None,
        'bars_held': None,
        'exit_reason': None,
        'signal_type': signal_type,
        'edge_source': edge_source,
        'e2_oos_trade_count': getattr(bot_state, 'e2_oos_trade_count', 0),
        'phase11_caveat_active': bool(e2_signal and e2_signal.e2_short_suppressed),
        'drift_severity': drift_state.severity.value,
        'drift_flag_count': len(drift_state.active_flags),
        'drift_flag_types': [flag.flag_type for flag in drift_state.active_flags],
        'e1_rolling_ev': drift_state.e1_rolling_ev,
        'e1_rolling_wr': drift_state.e1_rolling_wr,
        'e2_rolling_ev': drift_state.e2_rolling_ev,
        'e2_rolling_wr': drift_state.e2_rolling_wr,
        'e1_consecutive_losses': drift_state.e1_consecutive_losses,
        'e2_consecutive_losses': drift_state.e2_consecutive_losses,
        'atr_ratio_90d': drift_state.atr_ratio,
        'volatility_outside_backtest': drift_state.volatility_outside_backtest,
        'regime_flip_count_14d': drift_state.regime_flip_count_14d,
        'regime_choppy': drift_state.regime_choppy,
        'session_rotation_flag': drift_state.session_rotation_flag,
        'parity_status': parity_state.status.value,
        'parity_failed_checks': parity_state.failed_checks,
        'missing_candles_1h': parity_state.missing_candles_1h,
        'missing_candles_m15': parity_state.missing_candles_m15,
        'ema20_parity_diff': getattr(parity_state.ema20_check, 'difference', None),
        'atr_1h_parity_diff_pct': getattr(parity_state.atr_1h_check, 'difference_pct', None),
        'critic_called': critic_output.critic_called,
        'critic_bounded': critic_output.output_bounded,
        'critic_contradiction_count': len(critic_output.contradictions),
        'critic_confirmation_count': len(critic_output.confirmations),
        'critic_contradictions': critic_output.contradictions,
        'critic_confirmations': critic_output.confirmations,
        'critic_context_notes': critic_output.context_notes,
        'critic_tokens_used': critic_output.tokens_used,
        'critic_raw_text': critic_output.raw_critic_text,
        'formatted_signal_text': signal_text,
    }

    log_cycle(log_entry)
    if signal_type == SignalType.TRADE.value and (e1_signal or e2_signal):
        if len(trade_log) >= 10:
            metrics = update_performance_metrics(trade_log)
            # Metrics are computed but not used by the deterministic engine.
    if return_metadata:
        return signal_text, log_entry
    return signal_text


def main_loop():
    bot_state = _initialize_bot_state()
    trade_log: List[dict] = []
    signal_text = run_cycle(bot_state, trade_log)
    print(signal_text)


if __name__ == '__main__':
    main_loop()
