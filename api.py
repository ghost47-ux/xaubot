"""
Vercel deployment entry point for XAU/USD signal engine.

This module provides a Flask application that can be deployed to Vercel.
It exposes the trading signal engine as HTTP endpoints.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict

from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Import bot modules
try:
    from state.models import BotState, SignalType
except ImportError as e:
    logger.error(f"Failed to import bot modules: {e}")
    app = Flask(__name__)


# Global state (in production, use persistent storage like DynamoDB or Redis)
_bot_state: Optional[BotState] = None
_trade_log: List[Dict] = []


def _get_bot_state() -> BotState:
    """Get or initialize bot state."""
    global _bot_state
    if _bot_state is None:
        _bot_state = BotState(timestamp=datetime.now(timezone.utc))
    return _bot_state


def _get_trade_log() -> List[Dict]:
    """Get trade log (in production, load from database)."""
    global _trade_log
    return _trade_log


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'xau-trading-signal-engine',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route('/api/signal', methods=['POST'])
def get_signal():
    """
    Main endpoint: Run one analysis cycle and return the signal.
    
    Request body (optional):
    {
        "trade_log": [...]  // Optional: existing trade history
    }
    
    Response:
    {
        "signal": "TRADE|WATCH|NO_TRADE",
        "signal_text": "...",
        "timestamp": "ISO8601",
        "metadata": {...}
    }
    """
    try:
        from main import run_cycle
        
        # Get trade log from request or use global
        data = request.get_json() or {}
        trade_log = data.get('trade_log', _get_trade_log())
        
        # Get bot state
        bot_state = _get_bot_state()
        
        # Run analysis cycle
        signal_text = run_cycle(bot_state, trade_log)
        
        # Extract signal type from output
        if 'SIGNAL: XAU/USD' in signal_text:
            signal_type = 'TRADE'
        elif 'WATCH — XAU/USD' in signal_text:
            signal_type = 'WATCH'
        else:
            signal_type = 'NO_TRADE'
        
        return jsonify({
            'signal': signal_type,
            'signal_text': signal_text,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metadata': {
                'bot_state': {
                    'e1_trades_today': bot_state.e1_trades_today,
                    'e2_trades_today': bot_state.e2_trades_today,
                },
                'trade_log_length': len(trade_log),
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in /api/signal: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }), 500


@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current bot state."""
    try:
        bot_state = _get_bot_state()
        return jsonify({
            'timestamp': bot_state.timestamp.isoformat(),
            'e1_trades_today': bot_state.e1_trades_today,
            'e2_trades_today': bot_state.e2_trades_today,
            'last_reset_date': bot_state.last_reset_date,
            'e2_oos_trade_count': getattr(bot_state, 'e2_oos_trade_count', 0),
        }), 200
    except Exception as e:
        logger.error(f"Error in /api/state: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
        }), 500


@app.route('/api/state', methods=['POST'])
def reset_state():
    """Reset bot state (useful for testing or manual intervention)."""
    try:
        global _bot_state
        _bot_state = BotState(timestamp=datetime.now(timezone.utc))
        return jsonify({
            'message': 'Bot state reset',
            'timestamp': _bot_state.timestamp.isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error in /api/state POST: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
        }), 500


@app.route('/api/trade-log', methods=['GET'])
def get_trade_log():
    """Get trade log."""
    try:
        trade_log = _get_trade_log()
        return jsonify({
            'trade_count': len(trade_log),
            'trades': trade_log[-20:],  # Return last 20 trades
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error in /api/trade-log: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
        }), 500


@app.route('/api/trade-log', methods=['POST'])
def add_trade():
    """Add a trade result to the log."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No trade data provided'}), 400
        
        trade_log = _get_trade_log()
        trade_log.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **data
        })
        
        return jsonify({
            'message': 'Trade logged',
            'trade_count': len(trade_log),
        }), 201
        
    except Exception as e:
        logger.error(f"Error in /api/trade-log POST: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET  /',
            'POST /api/signal',
            'GET  /api/state',
            'POST /api/state',
            'GET  /api/trade-log',
            'POST /api/trade-log',
        ],
    }), 404


if __name__ == '__main__':
    # Development mode
    app.run(debug=True, host='0.0.0.0', port=5000)
