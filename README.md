# XAU Master: XAU/USD Trading Analysis Bot

## Overview
This is a deterministic Python analysis bot for XAU/USD price action trading. It does NOT auto-execute trades — it outputs signals that you manually execute in MetaTrader 5.

**Current Version**: v2.0 (Hardened Build with Drift Detection & Parity Monitoring)

## Key Features
- **Edge 1**: Trend Pullback on 1H (LONG only, Mon-Wed, specific sessions)
- **Edge 2**: Breakout System on M15 (BOTH directions, all weekdays)
- **Overlap Engine**: Phase 11 conflict resolution & sizing reduction
- **Risk Engine**: Deterministic position sizing (0.01 lot fixed, $10 account)
- **Drift Detection**: Flags when market regime shifts away from research baseline
- **Parity Monitor**: Verifies live indicators match backtest calculations
- **Claude Critic Layer**: Read-only AI analysis (flags contradictions, never modifies signals)

## Quick Start

### Local CLI (Analysis Mode)
```bash
# Install dependencies
pip install -r requirements.txt

# Run one analysis cycle
python main.py
```

### Local API Server
```bash
# Run Flask API server on port 5000
python api.py

# Get a signal
curl -X POST http://localhost:5000/api/signal
```

### Vercel Deployment
```bash
# Deploy to Vercel
vercel

# Or link GitHub repo in Vercel dashboard
```

See `DEPLOYMENT.md` for complete guides.

## Architecture

```
config/              → Locked parameters (do not edit)
state/               → Dataclasses (deterministic typed state)
indicators/          → Single EMA/ATR/swing implementations (Rule 1)
regimes/             → Market regime classification
edges/
  ├── edge1/         → Trend pullback detector (6 gates)
  └── edge2/         → Breakout detector (compression zones)
overlap/             → Phase 11 overlap rules
risk/                → Position sizing & dollar risk
drift/               → Regime drift detection (v2)
parity/              → Live vs backtest parity check (v2)
critic/              → Claude read-only critic layer (v2)
signals/             → Signal formatting (TRADE/WATCH/NO_TRADE)
analytics/           → Decision logging (52-field schema)
data/                → Candle fetching & reference snapshots
tests/               → Integration test suite
```

## Configuration

All locked parameters in `config/settings.py`:
- Account: $10, 0.01 lot, $1 per point
- Edge 1: LONG only, 1H, Tue-Thu, specific sessions, RR=1.5
- Edge 2: BOTH, M15, all weekdays, all sessions, RR=1.5
- Drift thresholds, parity tolerances, critic config

## Signal Output Types

### TRADE Signal
```
SIGNAL: XAU/USD [EDGE 1 — TREND PULLBACK]
Entry: $2050.00
Stop Loss: $2025.00
Take Profit: $2087.50
```

### WATCH Signal
```
WATCH — XAU/USD
Compression zone detected, waiting for breakout
```

### NO_TRADE Signal
```
NO TRADE — XAU/USD
Edge 1: ✗ Reason
Edge 2: ✗ Reason
```

## API Endpoints

```
GET  /                  → Health check
POST /api/signal        → Get one signal (main endpoint)
GET  /api/state         → View bot state
POST /api/state         → Reset bot state
GET  /api/trade-log     → View trade history
POST /api/trade-log     → Log a completed trade
```

## Testing

```bash
# Run integration tests (11 tests)
pytest tests/test_integration_v2.py -v
```

## Monitoring

```bash
# Dashboard
streamlit run dashboard/app.py

# View logs
grep "signal_type" logs/decisions.jsonl | head -20
```

## Documentation

- **Logic Specification**: `XAU_Bot_Logic_v2.md` (complete requirements)
- **Deployment Guide**: `DEPLOYMENT.md` (API, Vercel, local)
- **Audit Report**: `AUDIT_REPORT.md` (detailed findings)
- **Summary**: `AUDIT_SUMMARY.md` (executive overview)

## Status

✓ **PRODUCTION READY**
- 100% Logic Compliance
- All 9 Critical Rules Verified
- 11/11 Integration Tests Passed
- Fully Audited
- Deployment Ready (Vercel, local, Docker)

## Latest Updates (v2.0)

- ✓ Fixed main.py syntax
- ✓ Migrated Critic to Messages API
- ✓ Parameterized Risk Engine
- ✓ Added Parity Reference System
- ✓ Added Drift Detection
- ✓ Added Flask API
- ✓ Added Vercel Support
- ✓ Improved path handling

---

**Version**: 2.0  
**Last Updated**: May 7, 2026  
**Status**: Production Ready
