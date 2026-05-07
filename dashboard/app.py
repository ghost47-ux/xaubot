import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
from state.models import BotState, SignalType, CriticOutput

LOG_FILE = Path(os.getcwd()) / 'logs' / 'decisions.jsonl'


def load_logs() -> List[Dict]:
    if not LOG_FILE.exists():
        return []
    entries = []
    with open(LOG_FILE, 'r', encoding='utf-8') as handle:
        for line in handle:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _ensure_session_state() -> None:
    if 'bot_state' not in st.session_state:
        st.session_state['bot_state'] = BotState(timestamp=datetime.now(timezone.utc))
    if 'trade_log' not in st.session_state:
        st.session_state['trade_log'] = []
    if 'analysis_result' not in st.session_state:
        st.session_state['analysis_result'] = {}


def run_analysis() -> None:
    from main import run_cycle

    bot_state: BotState = st.session_state['bot_state']
    trade_log: List[dict] = st.session_state['trade_log']

    with st.status("Running Analysis Cycle...", expanded=True) as status:
        st.write("Fetching 1H candles...")
        st.write("Fetching M15 candles...")
        st.write("Calculating indicators...")
        st.write("Detecting Edge 1...")
        st.write("Detecting Edge 2...")
        st.write("Applying overlap rules...")
        st.write("Assessing risk...")
        st.write("Checking parity...")
        st.write("Detecting drift...")
        st.write("Calling Claude Critic...")
        st.write("Formatting signal...")

        try:
            signal_text, metadata = run_cycle(bot_state, trade_log, return_metadata=True)
            st.session_state['analysis_result'] = {
                'signal_text': signal_text,
                'metadata': metadata,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            status.update(label="Analysis Complete!", state="complete")
        except Exception as exc:
            st.session_state['analysis_result'] = {
                'error': str(exc),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            status.update(label="Analysis Failed", state="error")


def display_signal_card(signal_type: str, metadata: Dict) -> None:
    if signal_type == SignalType.TRADE.value:
        st.success("🚀 TRADE SIGNAL")
        edge_source = metadata.get('edge_source', 'NONE')
        if 'EDGE1' in edge_source:
            with st.container():
                st.subheader("Edge 1: Trend Pullback")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Direction", metadata.get('direction', 'N/A'))
                    st.metric("Entry Price", f"${metadata.get('entry_price', 0):.2f}")
                with col2:
                    st.metric("Stop Loss", f"${metadata.get('stop_loss', 0):.2f}")
                    st.metric("Take Profit", f"${metadata.get('take_profit', 0):.2f}")
        if 'EDGE2' in edge_source:
            with st.container():
                st.subheader("Edge 2: Breakout")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Direction", metadata.get('direction', 'N/A'))
                    st.metric("Breakout Class", metadata.get('e2_breakout_class', 'N/A'))
                with col2:
                    st.metric("Entry Price", f"${metadata.get('entry_price', 0):.2f}")
                    st.metric("Stop Loss", f"${metadata.get('stop_loss', 0):.2f}")
    elif signal_type == SignalType.WATCH.value:
        st.warning("👀 WATCH MODE - Compression Zone Active")
    else:
        st.info("⏸️ NO TRADE")


def display_critic_output(metadata: Dict) -> None:
    st.subheader("🤖 Claude Critic Analysis")
    if not metadata.get('critic_called', False):
        st.info("Critic not called for this cycle.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Contradictions:**")
        for contra in metadata.get('critic_contradictions', ['None.']):
            st.write(f"• {contra}")
        st.markdown("**Confirmations:**")
        for conf in metadata.get('critic_confirmations', ['None.']):
            st.write(f"• {conf}")
    with col2:
        st.markdown("**Context Notes:**")
        for note in metadata.get('critic_context_notes', ['None.']):
            st.write(f"• {note}")

    with st.expander("Raw Critic Text"):
        st.code(metadata.get('critic_raw_text', 'N/A'))


def display_state_management(bot_state: BotState) -> None:
    st.subheader("⚙️ Bot State Management")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("E1 Trades Today", bot_state.e1_trades_today)
        st.metric("E2 Trades Today", bot_state.e2_trades_today)
    with col2:
        st.metric("Last Reset Date", bot_state.last_reset_date or "None")
        if st.button("Reset Daily Counters"):
            bot_state.e1_trades_today = 0
            bot_state.e2_trades_today = 0
            bot_state.last_reset_date = datetime.now(timezone.utc).date().isoformat()
            st.success("Counters reset!")
    with col3:
        st.metric("Regime History Length", len(bot_state.regime_history))
        if st.button("Clear Regime History"):
            bot_state.regime_history = []
            st.success("History cleared!")


def main():
    st.set_page_config(page_title='XAU/USD Signal Monitor', layout='wide')
    st.title('XAU/USD Analysis Dashboard')
    st.markdown('Fully functional management console for the XAU/USD trading bot. No MetaTrader5 dependency.')

    _ensure_session_state()

    with st.sidebar:
        st.header('Controls')
        if st.button('🚀 Run Analysis', type='primary'):
            run_analysis()

        st.markdown('---')
        st.subheader('Requirements')
        st.write('• `TWELVE_DATA_API_KEY` in Streamlit secrets')
        st.write('• Internet access for live data')

    analysis_result = st.session_state['analysis_result']
    if analysis_result.get('error'):
        st.error(f"Analysis Error: {analysis_result['error']}")

    if analysis_result.get('signal_text'):
        st.subheader('📊 Latest Analysis Result')
        metadata = analysis_result['metadata']
        signal_type = metadata.get('signal_type', 'NO_TRADE')

        # Signal Card
        display_signal_card(signal_type, metadata)

        # Critic Output
        display_critic_output(metadata)

        # State Management
        display_state_management(st.session_state['bot_state'])

        st.markdown(f"**Analysis Timestamp:** {analysis_result['timestamp']}")

    # Logs Section
    st.markdown('---')
    st.subheader('📋 Recent Logs')
    logs = load_logs()
    if logs:
        latest = logs[-1]
        st.json(latest)
    else:
        st.info('No logs yet. Run analysis to generate signals.')


if __name__ == '__main__':
    main()

LOG_FILE = Path(os.getcwd()) / 'logs' / 'decisions.jsonl'

