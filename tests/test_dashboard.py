import json
import tempfile
from pathlib import Path

from dashboard import app


def test_filter_logs():
    logs = [
        {'signal_type': 'TRADE', 'edge_source': 'EDGE1'},
        {'signal_type': 'WATCH', 'edge_source': 'EDGE2'},
        {'signal_type': 'NO_TRADE', 'edge_source': 'NONE'},
    ]
    filtered = app.filter_logs(logs, 'WATCH', None)
    assert len(filtered) == 1
    assert filtered[0]['signal_type'] == 'WATCH'

    filtered = app.filter_logs(logs, None, 'EDGE1')
    assert len(filtered) == 1
    assert filtered[0]['edge_source'] == 'EDGE1'


def test_load_logs_reads_jsonl(tmp_path):
    file_path = tmp_path / 'decisions.jsonl'
    data = {'signal_type': 'TRADE', 'edge_source': 'EDGE1'}
    with open(file_path, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(data) + '\n')

    app.LOG_FILE = file_path
    loaded = app.load_logs()
    assert len(loaded) == 1
    assert loaded[0]['signal_type'] == 'TRADE'
