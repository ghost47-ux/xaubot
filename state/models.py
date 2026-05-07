# state/models.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

# ============================================================
# EXISTING ENUMS (unchanged from v1)
# ============================================================

class TrendState(Enum):
    BULL    = "BULL"
    BEAR    = "BEAR"
    MIXED   = "MIXED"


class VolatilityState(Enum):
    LOW     = "LOW"
    NORMAL  = "NORMAL"
    HIGH    = "HIGH"


class SessionName(Enum):
    ASIAN        = "Asian"
    LONDON_OPEN  = "London_Open"
    LONDON_MAIN  = "London_Main"
    NY_MAIN      = "NY_Main"
    OFF          = "Off"


class WeekdayName(Enum):
    MON = 0
    TUE = 1
    WED = 2
    THU = 3
    FRI = 4


class SignalType(Enum):
    TRADE    = "TRADE"
    WATCH    = "WATCH"
    NO_TRADE = "NO_TRADE"


class BreakoutClass(Enum):
    A       = "A"
    B       = "B"
    FAKEOUT = "FAKEOUT"


# ============================================================
# NEW IN v2 — DRIFT SEVERITY
# ============================================================

class DriftSeverity(Enum):
    NONE     = "NONE"
    WATCH    = "WATCH"
    CAUTION  = "CAUTION"
    ALERT    = "ALERT"


# ============================================================
# NEW IN v2 — PARITY STATUS
# ============================================================

class ParityStatus(Enum):
    OK       = "OK"
    WARNING  = "WARNING"
    BREACH   = "BREACH"


# ============================================================
# EXISTING DATACLASSES (unchanged from v1)
# ============================================================

@dataclass
class RegimeState:
    timestamp:        datetime
    trend_1h:         TrendState
    ema20_1h:         float
    ema50_1h:         float
    ema200_1h:        float
    atr_1h:           float
    volatility:       VolatilityState
    session:          SessionName
    weekday:          WeekdayName
    hour_utc:         int

    @property
    def is_e1_eligible_weekday(self) -> bool:
        return self.weekday.value in [1, 2, 3]

    @property
    def is_e1_eligible_session(self) -> bool:
        return self.session in [
            SessionName.LONDON_OPEN,
            SessionName.LONDON_MAIN,
            SessionName.NY_MAIN
        ]

    @property
    def is_bull_trend(self) -> bool:
        return self.trend_1h == TrendState.BULL


@dataclass
class Edge1Signal:
    timestamp:        datetime
    direction:        str
    entry_price:      float
    stop_loss:        float
    take_profit:      float
    stop_distance:    float
    dollar_risk:      float
    timeout_bar:      int
    ema20:            float
    ema50:            float
    ema200:           float
    atr:              float
    session:          str
    weekday:          str
    regime:           RegimeState
    sizing_factor:    float = 1.0
    adjusted_risk:    float = 0.0
    overlap_active:   bool  = False


@dataclass
class CompressionZone:
    start_bar:        int
    end_bar:          int
    range_high:       float
    range_low:        float
    range_height:     float
    atr_at_detection: float


@dataclass
class Edge2Signal:
    timestamp:           datetime
    direction:           str
    breakout_class:      BreakoutClass
    entry_price:         float
    stop_loss:           float
    take_profit:         float
    stop_distance:       float
    dollar_risk:         float
    timeout_bar:         int
    compression_high:    float
    compression_low:     float
    atr:                 float
    session:             str
    sizing_factor:       float = 1.0
    adjusted_risk:       float = 0.0
    overlap_active:      bool  = False
    e2_short_suppressed: bool  = False


@dataclass
class BotState:
    timestamp:           datetime
    regime:              Optional[RegimeState] = None
    e1_active:           bool = False
    e1_signal:           Optional[Edge1Signal] = None
    e1_open_since:       Optional[datetime] = None
    e1_trades_today:     int = 0
    e2_active:           bool = False
    e2_signal:           Optional[Edge2Signal] = None
    e2_open_since:       Optional[datetime] = None
    e2_trades_today:     int = 0
    e1_pending:          Optional[Edge1Signal] = None
    e2_pending:          Optional[Edge2Signal] = None
    both_active:         bool = False
    combined_risk:       float = 0.0
    last_reset_date:     Optional[str] = None


# ============================================================
# NEW IN v2 — DRIFT STATE
# ============================================================

@dataclass
class DriftFlag:
    """
    A single flagged drift condition. Multiple flags can be
    active simultaneously. Each is logged independently.
    """
    flag_type:        str
    description:      str
    current_value:    float
    threshold:        float
    trades_in_window: int
    timestamp:        datetime


@dataclass
class DriftState:
    """
    Output of the Regime Drift Detector.
    Produced every cycle. Always logged.
    Read-only to the decision engine.
    The engine never branches on this object.
    """
    timestamp:              datetime
    severity:               DriftSeverity

    e1_rolling_ev:          Optional[float]
    e1_rolling_wr:          Optional[float]
    e1_consecutive_losses:  int
    e1_trade_count:         int

    e2_rolling_ev:          Optional[float]
    e2_rolling_wr:          Optional[float]
    e2_consecutive_losses:  int
    e2_trade_count:         int

    atr_1h_current:         float
    atr_1h_mean_90d:        float
    atr_ratio:              float
    volatility_outside_backtest: bool

    regime_flip_count_14d:  int
    regime_choppy:          bool

    e1_session_ev:          Dict[str, float]
    session_rotation_flag:  bool

    active_flags:           List[DriftFlag] = field(default_factory=list)

    e1_baseline_ev:         float = 0.29
    e1_baseline_wr:         float = 0.50
    e2_baseline_ev:         float = 0.65
    e2_baseline_wr:         float = 0.56


# ============================================================
# NEW IN v2 — PARITY STATE
# ============================================================

@dataclass
class ParityCheck:
    """
    Result of comparing one indicator between live and reference.
    """
    indicator_name:   str
    live_value:       float
    reference_value:  float
    difference:       float
    difference_pct:   float
    tolerance:        float
    passed:           bool
    timestamp:        datetime


@dataclass
class ParityState:
    """
    Output of the Live vs Backtest Parity Monitor.
    Produced every PARITY_CHECK_FREQUENCY candles.
    Read-only to the decision engine.
    """
    timestamp:              datetime
    status:                 ParityStatus

    ema20_check:            ParityCheck
    ema50_check:            ParityCheck
    ema200_check:           ParityCheck
    atr_1h_check:           ParityCheck
    atr_m15_check:          ParityCheck
    swing_low_check:        ParityCheck
    session_check:          ParityCheck

    candles_checked:        int
    missing_candles_1h:     int
    missing_candles_m15:    int
    data_quality_ok:        bool

    cumulative_ema20_drift: float
    cumulative_atr_drift:   float
    parity_check_count:     int

    failed_checks:          List[str] = field(default_factory=list)


# ============================================================
# NEW IN v2 — CRITIC OUTPUT
# ============================================================

@dataclass
class CriticOutput:
    """
    Output of the Claude Critic Layer.
    Appended to signal report. Never modifies signal fields.
    Contains only FLAGS, CONFIRMATIONS, and CONTRADICTIONS.
    """
    timestamp:              datetime
    critic_called:          bool
    signal_type:            str
    edge_source:            str

    contradictions:         List[str]
    confirmations:          List[str]
    drift_flags_in_context: List[str]
    parity_flags_in_context: List[str]
    context_notes:          List[str]

    raw_critic_text:        str
    tokens_used:            int

    output_bounded:         bool
    decision_words_found:   List[str]
