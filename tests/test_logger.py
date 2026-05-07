# tests/test_logger.py
import os
import json

from analytics.logger import log_cycle, update_performance_metrics, LOG_FILE, LOGS_PATH


def test_log_cycle_writes_all_fields(tmp_path, monkeypatch):
    monkeypatch.setattr('analytics.logger.LOGS_PATH', str(tmp_path))
    monkeypatch.setattr('analytics.logger.LOG_FILE', str(tmp_path / 'decisions.jsonl'))
    entry = {
        'timestamp_utc': '2026-05-07T00:00:00Z',
        'weekday': 'WED',
        'session': 'London_Main',
        'hour_utc': 0,
        'trend_1h': 'BULL',
        'ema20': 100.0,
        'ema50': 99.5,
        'ema200': 99.0,
        'atr': 0.5,
        'volatility': 'NORMAL',
        'edge1_fired': False,
        'edge2_fired': False,
        'e2_breakout_class': '',
        'e2_direction': '',
        'overlap_active': False,
        'e2_short_suppressed': False,
        'sizing_factor': 1.0,
        'entry_price': None,
        'stop_loss': None,
        'take_profit': None,
        'stop_distance': None,
        'dollar_risk': None,
        'dollar_risk_adj': None,
        'rr': None,
        'timeout_bars': None,
        'outcome': '',
        'exit_price': None,
        'pnl_usd': None,
        'bars_held': None,
        'exit_reason': '',
        'signal_type': 'NO_TRADE',
        'edge_source': 'NONE',
        'e2_oos_trade_count': 0,
        'phase11_caveat_active': False,
        'drift_severity': 'NONE',
        'drift_flag_count': 0,
        'drift_flag_types': [],
        'e1_rolling_ev': None,
        'e1_rolling_wr': None,
        'e2_rolling_ev': None,
        'e2_rolling_wr': None,
        'e1_consecutive_losses': 0,
        'e2_consecutive_losses': 0,
        'atr_ratio_90d': None,
        'volatility_outside_backtest': False,
        'regime_flip_count_14d': 0,
        'regime_choppy': False,
        'session_rotation_flag': False,
        'parity_status': 'OK',
        'parity_failed_checks': [],
        'missing_candles_1h': 0,
        'missing_candles_m15': 0,
        'ema20_parity_diff': None,
        'atr_1h_parity_diff_pct': None,
        'critic_called': False,
        'critic_bounded': True,
        'critic_contradiction_count': 0,
        'critic_confirmation_count': 0,
        'critic_contradictions': [],
        'critic_confirmations': [],
        'critic_context_notes': [],
        'critic_tokens_used': 0,
        'critic_raw_text': ''
    }
    log_cycle(entry)
    assert os.path.exists(str(tmp_path / 'decisions.jsonl'))
    with open(str(tmp_path / 'decisions.jsonl'), 'r', encoding='utf-8') as f:
        loaded = json.loads(f.readline())
    assert loaded['timestamp_utc'] == '2026-05-07T00:00:00Z'
    assert 'critic_raw_text' in loaded


def test_update_performance_metrics_calculates_empty():
    result = update_performance_metrics([])
    assert result['win_rate'] == 0
    assert result['edge1'] == {}
