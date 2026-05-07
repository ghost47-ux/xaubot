# analytics/logger.py
import json
import os
from typing import List, Dict

LOG_SCHEMA = {
    'timestamp_utc':         str,
    'weekday':               str,
    'session':               str,
    'hour_utc':              int,
    'trend_1h':              str,
    'ema20':                 float,
    'ema50':                 float,
    'ema200':                float,
    'atr':                   float,
    'volatility':            str,
    'edge1_fired':           bool,
    'edge1_reject_reason':   str,
    'edge2_fired':           bool,
    'edge2_reject_reason':   str,
    'e2_breakout_class':     str,
    'e2_direction':          str,
    'overlap_active':        bool,
    'e2_short_suppressed':   bool,
    'sizing_factor':         float,
    'entry_price':           float,
    'stop_loss':             float,
    'take_profit':           float,
    'stop_distance':         float,
    'dollar_risk':           float,
    'dollar_risk_adj':       float,
    'rr':                    float,
    'timeout_bars':          int,
    'outcome':               str,
    'exit_price':            float,
    'pnl_usd':               float,
    'bars_held':             int,
    'exit_reason':           str,
    'signal_type':           str,
    'edge_source':           str,
    'e2_oos_trade_count':    int,
    'phase11_caveat_active': bool,
    'drift_severity':            str,
    'drift_flag_count':          int,
    'drift_flag_types':          list,
    'e1_rolling_ev':             float,
    'e1_rolling_wr':             float,
    'e2_rolling_ev':             float,
    'e2_rolling_wr':             float,
    'e1_consecutive_losses':     int,
    'e2_consecutive_losses':     int,
    'atr_ratio_90d':             float,
    'volatility_outside_backtest': bool,
    'regime_flip_count_14d':     int,
    'regime_choppy':             bool,
    'session_rotation_flag':     bool,
    'parity_status':             str,
    'parity_failed_checks':      list,
    'missing_candles_1h':        int,
    'missing_candles_m15':       int,
    'ema20_parity_diff':         float,
    'atr_1h_parity_diff_pct':    float,
    'critic_called':             bool,
    'critic_bounded':            bool,
    'critic_contradiction_count': int,
    'critic_confirmation_count': int,
    'critic_contradictions':     list,
    'critic_confirmations':      list,
    'critic_context_notes':      list,
    'critic_tokens_used':        int,
    'critic_raw_text':           str,
}

LOGS_PATH = os.path.join(os.getcwd(), 'logs')
LOG_FILE = os.path.join(LOGS_PATH, 'decisions.jsonl')


def _ensure_log_file():
    os.makedirs(LOGS_PATH, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8'):
            pass


def log_cycle(log_entry: Dict) -> None:
    _ensure_log_file()
    full_entry = {}
    for key in LOG_SCHEMA:
        full_entry[key] = log_entry.get(key, None)

    with open(LOG_FILE, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(full_entry, default=str) + '\n')


def _safe_mean(values: List[float]) -> float:
    filtered = [v for v in values if v is not None]
    return sum(filtered) / len(filtered) if filtered else 0.0


def update_performance_metrics(trade_log: List[Dict]) -> Dict:
    completed = [t for t in trade_log if t.get('outcome') in ['WIN', 'LOSS', 'TIMEOUT']]
    metrics = {
        'win_rate': 0.0,
        'ev_r': 0.0,
        'profit_factor': 0.0,
        'max_drawdown_r': 0.0,
        'avg_bars_held': 0.0,
        'timeout_rate': 0.0,
        'edge1': {},
        'edge2': {},
        'overlap': {}
    }

    if completed:
        wins = [t for t in completed if t.get('outcome') == 'WIN']
        losses = [t for t in completed if t.get('outcome') == 'LOSS']
        timeouts = [t for t in completed if t.get('outcome') == 'TIMEOUT']
        result_rs = [t.get('result_r', 0.0) for t in completed]
        profit = sum([t.get('pnl_usd', 0.0) for t in completed if t.get('pnl_usd', 0.0) > 0])
        loss = -sum([t.get('pnl_usd', 0.0) for t in completed if t.get('pnl_usd', 0.0) < 0])

        metrics['win_rate'] = len(wins) / len(completed)
        metrics['ev_r'] = _safe_mean(result_rs)
        metrics['profit_factor'] = profit / loss if loss > 0 else float('inf')
        metrics['avg_bars_held'] = _safe_mean([t.get('bars_held', 0) for t in completed])
        metrics['timeout_rate'] = len(timeouts) / len(completed)

        drawdowns = []
        peak = 0.0
        equity = 0.0
        for r in result_rs:
            equity += r
            peak = max(peak, equity)
            drawdowns.append(peak - equity)
        metrics['max_drawdown_r'] = max(drawdowns) if drawdowns else 0.0

    def breakdown(edge_source):
        subset = [t for t in completed if t.get('edge_source') == edge_source]
        if not subset:
            return {}
        wins = [t for t in subset if t.get('outcome') == 'WIN']
        return {
            'win_rate': len(wins) / len(subset),
            'ev_r': _safe_mean([t.get('result_r', 0.0) for t in subset]),
            'profit_factor': sum([t.get('pnl_usd', 0.0) for t in subset if t.get('pnl_usd', 0.0) > 0]) / max(1e-9, -sum([t.get('pnl_usd', 0.0) for t in subset if t.get('pnl_usd', 0.0) < 0])),
            'timeout_rate': len([t for t in subset if t.get('outcome') == 'TIMEOUT']) / len(subset),
            'avg_bars_held': _safe_mean([t.get('bars_held', 0) for t in subset])
        }

    metrics['edge1'] = breakdown('EDGE1')
    metrics['edge2'] = breakdown('EDGE2')
    metrics['overlap'] = {
        'both_active_count': len([t for t in completed if t.get('overlap_active')]),
        'e2_short_suppressed_count': len([t for t in completed if t.get('e2_short_suppressed')])
    }

    return metrics
