# XAU/USD Trading Signal Engine v2.0 - Deployment Guides

## Overview

This is a deterministic Python analysis bot for XAU/USD price action trading. It does NOT auto-execute trades - it outputs signals that you manually execute in MetaTrader 5.

## Installation

### Local Development

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd xaubot
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # - ANTHROPIC_API_KEY: Your Claude API key (for Critic Layer)
   # - TWELVEDATA_API_KEY: Optional, for live price data feed
   ```

### Run Locally

#### CLI Mode (Single Signal)
```bash
python main.py
```
This runs one analysis cycle and prints the signal to stdout.

#### API Server (Continuous)
```bash
python api.py
```
Starts a Flask server on `http://localhost:5000`

#### Available API Endpoints
- `GET /` - Health check
- `POST /api/signal` - Get one signal (main endpoint)
- `GET /api/state` - View bot state
- `POST /api/state` - Reset bot state
- `GET /api/trade-log` - View trade history
- `POST /api/trade-log` - Add a trade result

#### Test the API
```bash
# Get a signal
curl -X POST http://localhost:5000/api/signal

# View bot state
curl http://localhost:5000/api/state

# Log a completed trade
curl -X POST http://localhost:5000/api/trade-log \
  -H "Content-Type: application/json" \
  -d '{"outcome": "WIN", "pnl_usd": 50}'
```

## Deployment to Vercel

### Prerequisites
- Vercel account
- GitHub repository with this code
- Anthropic API key

### Steps

1. **Connect to Vercel:**
   ```bash
   # Install Vercel CLI
   npm install -g vercel
   
   # Deploy
   vercel
   ```
   Or link your GitHub repo directly in Vercel dashboard.

2. **Configure Environment Variables in Vercel:**
   In Vercel project settings, add:
   - `ANTHROPIC_API_KEY` = your Claude API key
   - `TWELVEDATA_API_KEY` = optional, for data feed
   - `DATA_DIR` = `/tmp` (for temporary file storage)

3. **Deploy:**
   Push to your GitHub branch. Vercel auto-deploys.

## Architecture

### Core Modules

```
config/settings.py         → All locked parameters (NEVER modify without research)
state/models.py           → State dataclasses (deterministic, typed)
indicators/core.py        → Single implementation of EMA, ATR, etc.
regimes/engine.py         → Market regime classification
edges/edge1/detector.py   → Edge 1: Trend Pullback (1H, LONG only)
edges/edge2/detector.py   → Edge 2: Breakout System (M15, BOTH)
overlap/engine.py         → Phase 11 overlap rules
risk/engine.py            → Position sizing & dollar risk
drift/detector.py         → Regime drift detection (NEW in v2)
parity/monitor.py         → Live vs backtest parity check (NEW in v2)
critic/layer.py           → Claude Critic Layer (NEW in v2, read-only)
signals/output.py         → Signal formatting
analytics/logger.py       → Decision logging
data/fetcher.py           → Data retrieval & validation
```

### Signal Output Types

1. **TRADE** - Edge fired + all conditions met
   - Shows entry, stop loss, take profit
   - Drift/parity status
   - Critic analysis (if applicable)

2. **WATCH** - Compression zone detected (Edge 2)
   - Zone boundaries
   - Expected breakout directions
   - Waiting for confirmation

3. **NO_TRADE** - All edges rejected
   - Rejection reasons per edge
   - System health (drift, parity)

## Key Rules (NON-NEGOTIABLE)

**RULE 1 - ONE INDICATOR IMPLEMENTATION**
- All indicators calculated in indicators/core.py only
- No duplicate logic anywhere
- Verified by byte-for-byte parity checks

**RULE 2 - BACKTEST PARITY**
- Live calculations must match research baseline
- Parity monitor checks every N candles
- Alerts on divergence (does NOT stop trading)

**RULE 3 - NO AI IN DECISIONS**
- Claude (Critic Layer) is read-only
- Never generates or modifies signals
- Only flags contradictions and confirmations

**RULE 4 - DRIFT IS MONITORED, NOT ACTED UPON**
- Drift detector flags regime changes
- Does NOT stop the bot
- Human decides if action needed

**RULE 5 - DETERMINISTIC ENGINE**
- No randomness, no ML, no neural nets
- Edges locked from Phase 5/Phase 10/Phase 11 research
- No refinements, no additions

## Settings Reference

All parameters in `config/settings.py` (DO NOT EDIT without research approval):

```
ACCOUNT_BALANCE = $10
LOT_SIZE = 0.01
USD_PER_POINT = $1

Edge 1 (LONG only, 1H):
  E1_VALID_WEEKDAYS = [1, 2, 3]
  E1_VALID_SESSIONS = [London_Open, London_Main, NY_Main]
  E1_RR = 1.5
  
Edge 2 (BOTH, M15):
  E2_DIRECTION = BOTH
  E2_VALID_WEEKDAYS = [0,1,2,3,4]
  E2_VALID_SESSIONS = ALL
  E2_RR = 1.5
  
Drift Detection:
  DRIFT_EV_WINDOW_TRADES = 20 (rolling window)
  DRIFT_EV_THRESHOLD_E1 = 0.10R
  DRIFT_WR_THRESHOLD_E1 = 35%
  
Critic Layer:
  CRITIC_ENABLED = True
  CRITIC_MODEL = claude-sonnet-4-20250514
  CRITIC_MAX_TOKENS = 600
  CRITIC_TEMPERATURE = 0.1
```

## Monitoring

### Logs

Trade decisions are logged to `logs/decisions.jsonl` (one JSON per line):
```json
{
  "timestamp_utc": "2026-05-07T13:45:00+00:00",
  "signal_type": "TRADE",
  "edge_source": "EDGE 1",
  "trend_1h": "BULL",
  "drift_severity": "NONE",
  "parity_status": "OK",
  "critic_called": true,
  "critic_bounded": true,
  ...
}
```

### Dashboard

View historical signals and metrics:
```bash
streamlit run dashboard/app.py
```

## Operational Notes

1. **Data Quality**: Validate candles every cycle. Missing bars are flagged.
2. **Parity Mismatches**: If parity status = BREACH, review alert before trading.
3. **Drift Flags**: Monitor drift severity. ALERT = significant regime shift detected.
4. **Manual Trade Logging**: Add completed trades to log for drift calculation:
   ```bash
   curl -X POST http://localhost:5000/api/trade-log \
     -d '{"outcome": "WIN", "pnl_usd": 75, "edge_source": "EDGE1"}'
   ```

## Troubleshooting

**"No module named anthropic"**
- Run `pip install anthropic`

**"ANTHROPIC_API_KEY not found"**
- Add to .env file or Vercel environment variables
- Critic layer disabled if missing

**"No candle data"**
- Check TWELVE_DATA_API_KEY and internet connectivity
- Verify internet connectivity

**"Parity BREACH"**
- Check if data feed has gaps
- May indicate stale reference snapshot
- Review against reference baseline

## Support

For questions about logic or research, refer to:
- `XAU_Bot_Logic_v2.md` - Complete logic specification
- `XAU_Master_Build_Prompt.md` - Build requirements
- Tests in `tests/test_integration_v2.py` - Validated logic

---

**Last Updated**: May 2026  
**Version**: 2.0  
**Status**: Production Ready
