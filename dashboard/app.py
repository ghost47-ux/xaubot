import json
import os
from pathlib import Path
from typing import List, Dict, Optional

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


def filter_logs(logs: List[Dict], signal_type: Optional[str], edge_source: Optional[str]) -> List[Dict]:
    filtered = logs
    if signal_type:
        filtered = [entry for entry in filtered if entry.get('signal_type') == signal_type]
    if edge_source:
        filtered = [entry for entry in filtered if entry.get('edge_source') == edge_source]
    return filtered


def main():
    try:
        import streamlit as st
    except ImportError as exc:
        raise ImportError('Streamlit is required to run the dashboard. Install streamlit to use this module.') from exc

    st.title('XAU/USD Signal Monitor')
    st.sidebar.header('Filters')

    signal_type = st.sidebar.selectbox('Signal type', ['ALL', 'TRADE', 'WATCH', 'NO_TRADE'])
    edge_source = st.sidebar.selectbox('Edge source', ['ALL', 'EDGE1', 'EDGE2', 'NONE'])
    refresh = st.sidebar.button('Refresh')

    logs = load_logs()
    if refresh:
        st.experimental_rerun()

    if signal_type != 'ALL':
        logs = filter_logs(logs, signal_type, None)
    if edge_source != 'ALL':
        logs = filter_logs(logs, None, edge_source)

    st.markdown('## Current Signal')
    if logs:
        latest = logs[-1]
        st.code(latest.get('critic_raw_text', 'No signal text available'))
    else:
        st.write('No logs available yet.')

    st.markdown('## Drift and Parity Summary')
    if logs:
        latest = logs[-1]
        st.write(f"Drift severity: {latest.get('drift_severity', 'N/A')}")
        st.write(f"Parity status: {latest.get('parity_status', 'N/A')}")
    else:
        st.write('No summary available.')

    st.markdown('## Log Viewer')
    display_logs = logs[-50:][::-1]
    st.write(display_logs)


if __name__ == '__main__':
    main()
