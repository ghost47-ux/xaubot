from datetime import datetime, timezone
from typing import Optional

from config import settings
from state.models import (
    Edge1Signal,
    Edge2Signal,
    DriftState,
    ParityState,
    CriticOutput,
    SignalType,
)


def _format_price(value: float) -> str:
    return f"${value:.2f}"


def _list_text(items):
    if not items:
        return "None."
    return " | ".join(str(item) for item in items)


def _system_health(
    drift_state: Optional[DriftState],
    parity_state: Optional[ParityState],
    bot_state=None
) -> str:
    drift_severity = drift_state.severity.value if drift_state else 'NONE'
    active_flags = len(drift_state.active_flags) if drift_state else 0
    active_flag_types = [flag.flag_type for flag in drift_state.active_flags] if drift_state else []
    parity_status = parity_state.status.value if parity_state else 'UNKNOWN'
    parity_issues = parity_state.failed_checks if parity_state else []
    e2_oos_count = getattr(bot_state, 'e2_oos_trade_count', 0) if bot_state is not None else 0

    health = []
    health.append('  SYSTEM HEALTH')
    health.append(f'  Drift severity : {drift_severity}')
    health.append(f'  Active flags   : {active_flags} {active_flag_types if active_flag_types else "[]"}')
    health.append(f'  Parity status  : {parity_status}')
    health.append(f'  Parity issues  : {_list_text(parity_issues)}')
    health.append(f'  E2 OOS count   : {e2_oos_count} / {settings.E2_MIN_OOS_TRADES_FOR_LOCK}')
    return '\n'.join(health)


def _critic_block(critic_output: Optional[CriticOutput]) -> str:
    if critic_output is None or not critic_output.critic_called:
        return '  CRITIC LAYER OUTPUT\n  None.\n  CRITIC OUTPUT BOUNDED: YES'

    contradictions = _list_text(critic_output.contradictions)
    confirmations = _list_text(critic_output.confirmations)
    drift_notes = _list_text(critic_output.drift_flags_in_context)
    context_notes = _list_text(critic_output.context_notes)
    bounded = 'YES' if critic_output.output_bounded else 'NO'
    if not critic_output.output_bounded:
        return (
            '  CRITIC LAYER OUTPUT\n'
            '  CRITIC OUTPUT INVALID — decision language detected. Critic response discarded. Review critic prompt.\n'
            f'  CRITIC OUTPUT BOUNDED: {bounded}'
        )

    return (
        '  CRITIC LAYER OUTPUT\n'
        '  ── CONTRADICTIONS ──────────────────────────────────────────\n'
        f'  {contradictions}\n'
        '  ── CONFIRMATIONS ───────────────────────────────────────────\n'
        f'  {confirmations}\n'
        '  ── DRIFT AND PARITY FLAGS ──────────────────────────────────\n'
        f'  {drift_notes}\n'
        '  ── CONTEXT NOTES ───────────────────────────────────────────\n'
        f'  {context_notes}\n'
        f'  ── CRITIC OUTPUT BOUNDED: {bounded} ─────\n'
    )


def format_signal(
    signal_type: str,
    e1_signal: Optional[Edge1Signal],
    e2_signal: Optional[Edge2Signal],
    risk_assessment: Optional[dict],
    bot_state=None,
    drift_state: Optional[DriftState] = None,
    parity_state: Optional[ParityState] = None,
    critic_output: Optional[CriticOutput] = None,
    compression_zone=None,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    if signal_type == SignalType.TRADE.value and e2_signal and e2_signal.e2_short_suppressed:
        header = '╔══════════════════════════════════════════════════════════════╗\n'
        header += '  WARNING — XAU/USD\n'
        header += f'  Generated: {timestamp}\n'
        header += '╠══════════════════════════════════════════════════════════════╣\n'
        header += '  NOTE: E2 SHORT SUPPRESSED — Phase 11 caveat active.\n'
        header += _system_health(drift_state, parity_state, bot_state) + '\n'
        header += _critic_block(critic_output) + '\n'
        header += '╚══════════════════════════════════════════════════════════════╝'
        return header

    if signal_type == SignalType.TRADE.value and (e1_signal or e2_signal):
        signal = e1_signal or e2_signal
        edge_label = 'EDGE 1 — TREND PULLBACK' if e1_signal else 'EDGE 2 — BREAKOUT'
        direction = signal.direction
        class_text = 'E1 only' if e1_signal else f'E2 Class {signal.breakout_class.value}'
        overlap_status = 'ACTIVE' if signal.overlap_active else 'NONE'
        if e2_signal and e2_signal.e2_short_suppressed:
            overlap_status = 'E2 SHORT SUPPRESSED — with Phase 11 caveat'

        overlap_text = 'YES — sized down 30%' if signal.overlap_active else 'NO'

        body = []
        body.append('╔══════════════════════════════════════════════════════════════╗')
        body.append(f'  SIGNAL: XAU/USD [{edge_label}]')
        body.append(f'  Direction: {direction}')
        body.append(f'  Class: {class_text}')
        body.append(f'  Generated: {timestamp}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append(f'  ENTRY       : {_format_price(signal.entry_price)}')
        body.append(f'  STOP LOSS   : {_format_price(signal.stop_loss)}     ← swing_low/high(10) ± 0.5 ATR')
        body.append(f'  TAKE PROFIT : {_format_price(signal.take_profit)}     ← 1.5R from entry')
        body.append(f'  STOP DIST   : {_format_price(signal.stop_distance)}')
        body.append('  RR          : 1:1.5 (fixed)')
        timeout_text = f'{risk_assessment.get("timeout_hours", 0)}H' if risk_assessment else 'N/A'
        body.append(f'  TIMEOUT     : {timeout_text} from entry bar')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        account_pct = f'{risk_assessment.get("account_risk_pct", 0.0):.2f}' if risk_assessment else '0.00'
        body.append('  ACCOUNT RISK (0.01 lot, $10 account)')
        body.append(f'  Dollar risk : {_format_price(risk_assessment.get("dollar_risk_adj", 0.0))}  ({account_pct}% of account)')
        body.append(f'  Risk flag   : {risk_assessment.get("risk_flag", "UNKNOWN")}')
        body.append(f'  Overlap adj : {overlap_text}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  WHY THIS SIGNAL FIRED:')
        body.append('  Gate-by-gate confirmation — same as v1')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  REGIME STATE:')
        body.append(f'  Trend: {signal.regime.trend_1h.value}  |  ATR: {signal.regime.atr_1h:.2f}')
        body.append(f'  Volatility: {signal.regime.volatility.value}')
        body.append(f'  Session: {signal.regime.session.value}  |  Weekday: {signal.regime.weekday.name}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  OVERLAP STATUS:')
        body.append(f'  {overlap_status}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append(_system_health(drift_state, parity_state, bot_state))
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append(_critic_block(critic_output))
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  EXECUTE IN MT5:')
        body.append('  Symbol : XAUUSD')
        body.append(f'  Type   : Buy/Sell [Limit/Market]')
        body.append('  Lots   : 0.01')
        body.append(f'  SL     : {_format_price(signal.stop_loss)}')
        body.append(f'  TP     : {_format_price(signal.take_profit)}')
        body.append('╚══════════════════════════════════════════════════════════════╝')
        return '\n'.join(body)

    if signal_type == SignalType.WATCH.value:
        body = []
        body.append('╔══════════════════════════════════════════════════════════════╗')
        body.append('  WATCH — XAU/USD')
        body.append(f'  Generated: {timestamp}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        if compression_zone:
            width = compression_zone.range_height
            atr_mult = width / compression_zone.atr_at_detection if compression_zone.atr_at_detection else 0.0
            age = compression_zone.end_bar - compression_zone.start_bar
            body.append('  STATUS: Edge 2 — Compression zone active, waiting for breakout')
            body.append(f'  Zone high: {_format_price(compression_zone.range_high)}  |  Zone low: {_format_price(compression_zone.range_low)}')
            body.append(f'  Zone width: {_format_price(width)} ({atr_mult:.2f}x ATR)  |  Zone age: {age} bars')
            body.append(f'  LONG trigger:  close above {_format_price(compression_zone.range_high)} + Class A/B confirmation')
            body.append(f'  SHORT trigger: close below {_format_price(compression_zone.range_low)}  + Class A/B confirmation')
        else:
            body.append('  STATUS: Edge 2 — Compression zone active, waiting for breakout')
            body.append('  Zone high: N/A  |  Zone low: N/A')
            body.append('  Zone width: N/A  |  Zone age: N/A bars')
            body.append('  LONG trigger:  close above N/A + Class A/B confirmation')
            body.append('  SHORT trigger: close below N/A  + Class A/B confirmation')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append(f'  SYSTEM HEALTH: Drift {drift_state.severity.value if drift_state else "NONE"} | Parity {parity_state.status.value if parity_state else "UNKNOWN"}')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  CRITIC LAYER:')
        body.append('  Active on WATCH when CRITIC_CALL_ON_WATCH = True')
        body.append('  Particularly useful here: identifies if E1 regime context')
        body.append('   contradicts the expected E2 breakout direction before it fires')
        body.append('╠══════════════════════════════════════════════════════════════╣')
        body.append('  NOTE: This is not a signal. No entry until breakout confirmed.')
        body.append('╚══════════════════════════════════════════════════════════════╝')
        return '\n'.join(body)

    body = []
    body.append('╔══════════════════════════════════════════════════════════════╗')
    body.append('  NO TRADE — XAU/USD')
    body.append(f'  Generated: {timestamp}')
    body.append('╠══════════════════════════════════════════════════════════════╣')
    body.append('  REASON:')
    if bot_state is not None:
        e1_reason = getattr(bot_state, 'e1_reject_reason', 'None.') or 'None.'
        e2_reason = getattr(bot_state, 'e2_reject_reason', 'None.') or 'None.'
        body.append(f'  [Edge 1]: ✗ {e1_reason}')
        body.append(f'  [Edge 2]: ✗ {e2_reason}')
    else:
        body.append('  [Edge 1]: ✗ None.')
        body.append('  [Edge 2]: ✗ None.')
    body.append('╠══════════════════════════════════════════════════════════════╣')
    body.append(f'  SYSTEM HEALTH: Drift {drift_state.severity.value if drift_state else "NONE"} | Parity {parity_state.status.value if parity_state else "UNKNOWN"}')
    body.append('╠══════════════════════════════════════════════════════════════╣')
    critic_enabled = (critic_output is not None and critic_output.critic_called) or (drift_state is not None and drift_state.severity != None and settings.CRITIC_CALL_ON_NO_TRADE)
    if critic_enabled:
        body.append('  CRITIC LAYER: active')
    else:
        body.append('  CRITIC LAYER: Disabled on NO_TRADE unless drift flag active or CRITIC_CALL_ON_NO_TRADE = True')
    body.append('╚══════════════════════════════════════════════════════════════╝')
    return '\n'.join(body)
