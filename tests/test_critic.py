from critic.layer import validate_critic_output, parse_critic_sections, build_critic_context
from state.models import DriftSeverity, ParityStatus


def test_validate_critic_output_rejects_decision_language():
    raw = 'This output says you should take this trade.'
    bounded, words = validate_critic_output(raw)
    assert not bounded
    assert 'should' in words


def test_parse_critic_sections_returns_none_when_empty():
    raw = 'CONTRADICTIONS:\n\nCONFIRMATIONS:\n\nDRIFT AND PARITY FLAGS:\n\nCONTEXT NOTES:\n'
    contradictions, confirmations, drift_flags, context_notes = parse_critic_sections(raw)
    assert contradictions == ['None.']
    assert confirmations == ['None.']
    assert drift_flags == ['None.']
    assert context_notes == ['None.']


def test_build_critic_context_includes_expected_entries():
    context = build_critic_context(
        signal_type='TRADE',
        edge_source='EDGE 1',
        e1_signal=None,
        e2_signal=None,
        regime=None,
        drift_state=type('D', (), {'severity': DriftSeverity.NONE, 'active_flags': []})(),
        parity_state=type('P', (), {'status': ParityStatus.OK, 'failed_checks': []})(),
        recent_logs=[]
    )
    assert context['signal_type'] == 'TRADE'
    assert context['edge_source'] == 'EDGE 1'
    assert context['drift_state']['severity'] == 'NONE'
    assert context['parity_state']['status'] == 'OK'
