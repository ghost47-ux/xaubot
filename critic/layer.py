import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from config import settings
from critic.prompt import CRITIC_SYSTEM_PROMPT
from state.models import CriticOutput, DriftState, ParityState, SignalType

# Decision words that indicate action/recommendation. Must be checked with word boundaries.
DECISION_WORDS = [
    'take', 'skip', 'avoid', 'recommend', 'suggest', 'should',
    'enter', 'wait', 'pass', 'reconsider', 'be careful',
    'i would', 'you might', 'consider'
]


def validate_critic_output(raw_text: str) -> Tuple[bool, List[str]]:
    """
    Check if critic output contains decision language (prohibited).
    Uses word boundary regex to avoid false positives like 'consideration'.
    Returns (is_valid, found_words)
    """
    found = []
    lower = raw_text.lower()
    
    for word in DECISION_WORDS:
        # Build regex pattern with word boundaries
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, lower):
            found.append(word)
    
    return (len(found) == 0, found)


def _split_sections(raw_text: str) -> Dict[str, List[str]]:
    sections = {
        'contradictions': [],
        'confirmations': [],
        'drift_and_parity_flags': [],
        'context_notes': []
    }
    current = None
    for line in raw_text.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith('contradictions:'):
            current = 'contradictions'
            continue
        if normalized.startswith('confirmations:'):
            current = 'confirmations'
            continue
        if normalized.startswith('drift and parity flags:'):
            current = 'drift_and_parity_flags'
            continue
        if normalized.startswith('context notes:'):
            current = 'context_notes'
            continue
        if current is None:
            continue
        text = line.strip()
        if text:
            sections[current].append(text)
    return sections


def parse_critic_sections(raw_text: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    sections = _split_sections(raw_text)
    def normalize(lines: List[str]) -> List[str]:
        if not lines:
            return ['None.']
        return [line for line in lines if line]
    return (
        normalize(sections['contradictions']),
        normalize(sections['confirmations']),
        normalize(sections['drift_and_parity_flags']),
        normalize(sections['context_notes'])
    )


def parity_flags_from_context(context: dict) -> List[str]:
    flags = []
    parity = context.get('parity_state')
    if parity is None:
        return flags
    if hasattr(parity, 'failed_checks') and parity.failed_checks:
        flags.extend(parity.failed_checks)
    if hasattr(parity, 'status') and getattr(parity.status, 'value', None) == 'BREACH':
        flags.append('PARITY_BREACH')
    return flags


def build_critic_context(
    signal_type: str,
    edge_source: str,
    e1_signal: Optional[object],
    e2_signal: Optional[object],
    regime: Optional[object],
    drift_state: Optional[DriftState],
    parity_state: Optional[ParityState],
    recent_logs: List[Dict]
) -> dict:
    return {
        'signal_type': signal_type,
        'edge_source': edge_source,
        'e1_signal': e1_signal.__dict__ if e1_signal else None,
        'e2_signal': e2_signal.__dict__ if e2_signal else None,
        'regime': regime.__dict__ if regime else None,
        'drift_state': {
            'severity': drift_state.severity.value,
            'active_flags': [flag.flag_type for flag in drift_state.active_flags],
        } if drift_state else None,
        'parity_state': {
            'status': parity_state.status.value,
            'failed_checks': parity_state.failed_checks,
        } if parity_state else None,
        'recent_logs': recent_logs,
    }


def call_critic(context: dict) -> CriticOutput:
    timestamp = datetime.now(timezone.utc)
    if not settings.CRITIC_ENABLED:
        return CriticOutput(
            timestamp=timestamp,
            critic_called=False,
            signal_type=context.get('signal_type', 'UNKNOWN'),
            edge_source=context.get('edge_source', 'UNKNOWN'),
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

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return CriticOutput(
            timestamp=timestamp,
            critic_called=False,
            signal_type=context.get('signal_type', 'UNKNOWN'),
            edge_source=context.get('edge_source', 'UNKNOWN'),
            contradictions=['None.'],
            confirmations=['None.'],
            drift_flags_in_context=[],
            parity_flags_in_context=[],
            context_notes=['None.'],
            raw_critic_text='CRITIC DISABLED — missing API key.',
            tokens_used=0,
            output_bounded=True,
            decision_words_found=[]
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        context_str = json.dumps(context, default=str)
        
        response = client.messages.create(
            model=settings.CRITIC_MODEL,
            max_tokens=settings.CRITIC_MAX_TOKENS,
            temperature=settings.CRITIC_TEMPERATURE,
            system=CRITIC_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this signal context:\n\n{context_str}"
                }
            ]
        )
        
        raw_text = response.content[0].text
        is_bounded, found_words = validate_critic_output(raw_text)
        contradictions, confirmations, drift_flags, context_notes = parse_critic_sections(raw_text)
        
        return CriticOutput(
            timestamp=timestamp,
            critic_called=True,
            signal_type=context.get('signal_type', 'UNKNOWN'),
            edge_source=context.get('edge_source', 'UNKNOWN'),
            contradictions=contradictions,
            confirmations=confirmations,
            drift_flags_in_context=drift_flags,
            parity_flags_in_context=parity_flags_from_context(context),
            context_notes=context_notes,
            raw_critic_text=raw_text,
            tokens_used=response.usage.output_tokens,
            output_bounded=is_bounded,
            decision_words_found=found_words
        )
    except Exception as exc:
        return CriticOutput(
            timestamp=timestamp,
            critic_called=False,
            signal_type=context.get('signal_type', 'UNKNOWN'),
            edge_source=context.get('edge_source', 'UNKNOWN'),
            contradictions=['None.'],
            confirmations=['None.'],
            drift_flags_in_context=[],
            parity_flags_in_context=[],
            context_notes=[f'Critic call failed: {exc}'],
            raw_critic_text='CRITIC FAILED.',
            tokens_used=0,
            output_bounded=False,
            decision_words_found=[]
        )
