# config/settings.py

# ============================================================
# ACCOUNT CONSTANTS (never change)
# ============================================================
ACCOUNT_BALANCE       = 10.00
LOT_SIZE              = 0.01
USD_PER_POINT         = 1.00

# ============================================================
# EDGE 1 — TREND PULLBACK (locked from Phase 5)
# ============================================================
E1_TIMEFRAME          = '1H'
E1_DIRECTION          = 'LONG'
E1_VALID_WEEKDAYS     = [1, 2, 3]
E1_VALID_SESSIONS     = ['London_Open', 'London_Main', 'NY_Main']
E1_RR                 = 1.5
E1_TIMEOUT_BARS       = 72
E1_SL_SWING_LOOKBACK  = 10
E1_SL_ATR_BUFFER      = 0.5
E1_EMA_FAST           = 20
E1_EMA_MID            = 50
E1_EMA_SLOW           = 200

# ============================================================
# EDGE 2 — BREAKOUT SYSTEM (locked from Phase 10)
# ============================================================
E2_TIMEFRAME          = 'M15'
E2_DIRECTION          = 'BOTH'
E2_VALID_WEEKDAYS     = [0,1,2,3,4]
E2_VALID_SESSIONS     = 'ALL'
E2_RR                 = 1.5
E2_TIMEOUT_BARS       = 72
E2_SL_SWING_LOOKBACK  = 10
E2_SL_ATR_BUFFER      = 0.5
E2_COMPRESSION_MULT   = 3.5
E2_RANGE_MIN_ATR_MULT = 0.3
E2_RANGE_MAX_ATR_MULT = 3.0
E2_FAKEOUT_BODY_MIN   = 0.4
E2_FAKEOUT_WICK_RATIO = 0.3
E2_CLASS_A_CLOSE_MULT = 0.7
E2_CLASS_B_CLOSE_MULT = 0.4

# ============================================================
# OVERLAP / CONFLICT ENGINE (locked from Phase 11)
# ============================================================
OVERLAP_SIZING_REDUCTION  = 0.30
E2_SHORT_SUPPRESSION      = True
E2_MIN_OOS_TRADES_FOR_LOCK = 20

# ============================================================
# ACCOUNT RISK LIMITS
# ============================================================
MAX_SINGLE_TRADE_RISK_USD   = 5.00
MAX_COMBINED_RISK_USD       = 8.00
MAX_DAILY_TRADES_E1         = 1
MAX_DAILY_TRADES_E2         = 2


# ============================================================
# REGIME DRIFT DETECTION (new in v2)
# ============================================================
# These parameters define what "drift" means relative to
# the backtested performance baseline. They are NOT edge
# parameters. They do not gate trades.

DRIFT_EV_WINDOW_TRADES      = 20
# Rolling window size in trades. Drift is measured over
# the last N completed trades per edge. Minimum 20 before
# any drift signal is meaningful.

DRIFT_EV_THRESHOLD_E1       = 0.10
# If rolling EV for Edge 1 drops below +0.10R (vs research
# baseline of +0.29R), drift flag is raised.
# Rationale: halfway between zero and the research EV.
# Below this level, the edge may be operating in noise.

DRIFT_EV_THRESHOLD_E2       = 0.30
# If rolling EV for Edge 2 drops below +0.30R (vs research
# baseline of +0.65R), drift flag is raised.

DRIFT_WR_THRESHOLD_E1       = 0.35
# If rolling win rate for Edge 1 drops below 35% (vs
# research baseline of ~50%), drift flag is raised.

DRIFT_WR_THRESHOLD_E2       = 0.40
# If rolling win rate for Edge 2 drops below 40% (vs
# research baseline of ~56%), drift flag is raised.

DRIFT_CONSECUTIVE_LOSS_E1   = 5
# If Edge 1 records 5 consecutive losses, drift flag is raised.
# This is separate from EV drift — fast-moving warning.

DRIFT_CONSECUTIVE_LOSS_E2   = 4
# If Edge 2 records 4 consecutive losses, drift flag is raised.

DRIFT_ATR_MULTIPLIER_HIGH   = 2.0
# If current ATR_1H > 2.0 * ATR_1H_mean_90d, the market
# is operating in an abnormal volatility regime.
# Flag: "Current volatility is outside the distribution
# this edge was validated on."

DRIFT_ATR_MULTIPLIER_LOW    = 0.4
# If current ATR_1H < 0.4 * ATR_1H_mean_90d, the market
# is in abnormally compressed volatility.

DRIFT_SESSION_EV_LOOKBACK   = 30
# Rolling window in trades for per-session EV breakdown.
# Used to detect if session leadership has rotated in a
# way that suggests regime change.

DRIFT_REGIME_FLIP_WINDOW    = 14
# If the 1H trend state has flipped between BULL/BEAR/MIXED
# more than 4 times in the last 14 days, flag raised.
# Choppy regime flipping degrades trend-following edges.

DRIFT_REGIME_FLIP_THRESHOLD = 4


# ============================================================
# LIVE VS BACKTEST PARITY MONITOR (new in v2)
# ============================================================
PARITY_CHECK_FREQUENCY      = 10
# Run parity check every N completed candles (1H timeframe).
# Runs separately on M15 candles for Edge 2 calculations.

PARITY_EMA_TOLERANCE        = 0.05
# Allowed absolute difference between live EMA and reference
# EMA in USD. Gold price means EMA values are in the 2000–3000
# range. A 0.05 USD tolerance is tight but realistic.
# If divergence exceeds this: parity flag raised.

PARITY_ATR_TOLERANCE_PCT    = 0.5
# Allowed percentage difference between live ATR and reference
# ATR. Expressed as percent of reference ATR value.
# If |live_atr - ref_atr| / ref_atr > 0.005: parity flag raised.

PARITY_SESSION_TOLERANCE_MIN = 1
# Allowed session classification mismatch in minutes.
# If live session classification and reference session differ
# by more than 1 minute at session boundaries: flag raised.
# This catches broker-side UTC offset issues.

PARITY_SWING_TOLERANCE      = 0.10
# Allowed absolute difference in swing_low / swing_high
# values between live and reference engines.

PARITY_MAX_GAP_CANDLES      = 2
# Maximum number of missing candles in the live feed before
# parity flag is raised and a data-quality warning is issued.
# Missing candles corrupt EMA and ATR calculations silently.


# ============================================================
# CRITIC LAYER CONFIGURATION (new in v2)
# ============================================================
CRITIC_MODEL                = 'claude-sonnet-4-20250514'
CRITIC_MAX_TOKENS           = 600
# Hard cap on critic output tokens. Forces concision.
# A critic that writes 2000 tokens is speculating, not flagging.

CRITIC_TEMPERATURE          = 0.1
# Near-zero temperature. The critic is not creative.
# It is analytical. Consistency is required.

CRITIC_ENABLED              = True
# Can be toggled off for performance or debugging.
# When off: critic_output field is populated with "CRITIC DISABLED."

CRITIC_CALL_ON_NO_TRADE     = False
# Whether to call Claude when no signal fires.
# Default False — saves API cost and noise on quiet cycles.
# Set True during active monitoring phases.

CRITIC_CALL_ON_WATCH        = True
# Call critic when compression zone is active (WATCH state).
# Useful for detecting contradiction between E1 and E2 context
# before the breakout fires.

CRITIC_CALL_ON_DRIFT_FLAG   = True
# Always call critic when any drift flag is active,
# regardless of signal type.
