"""Shared data types for ToxFlow."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


class Outcome(Enum):
    YES = "yes"
    NO = "no"


@dataclass
class Trade:
    """A single trade on Polymarket CLOB."""
    timestamp: float
    price: float
    size: float  # in USDC notional
    side: Side  # aggressor side (inferred via tick rule)
    outcome: Outcome  # YES or NO token
    market_id: str
    maker: Optional[str] = None  # wallet address
    taker: Optional[str] = None


@dataclass
class OrderBookSnapshot:
    """Point-in-time orderbook state."""
    timestamp: float
    market_id: str
    outcome: Outcome
    bids: list[tuple[float, float]]  # [(price, size), ...]
    asks: list[tuple[float, float]]


@dataclass
class VolumeBucket:
    """A volume-synchronized bucket of trades."""
    bucket_id: int
    start_time: float
    end_time: float
    total_volume: float
    buy_volume: float
    sell_volume: float
    num_trades: int
    vwap: float  # volume-weighted average price
    imbalance: float = 0.0  # |buy - sell| / total

    def __post_init__(self):
        if self.total_volume > 0:
            self.imbalance = abs(self.buy_volume - self.sell_volume) / self.total_volume


@dataclass
class VPINReading:
    """A single VPIN measurement."""
    timestamp: float
    vpin_value: float  # 0 to 1, higher = more toxic
    directional_vpin: float  # -1 to +1, positive = YES-side informed flow
    window_size: int  # number of buckets in window
    bucket_id: int


@dataclass
class SynthesisSignal:
    """Signal from Synthesis AI forecast."""
    timestamp: float
    market_id: str
    ai_probability: float  # Synthesis estimate of YES probability
    market_probability: float  # current Polymarket implied probability
    edge: float  # ai_prob - market_prob (positive = YES underpriced)
    confidence: float  # 0 to 1


@dataclass
class CompositeSignal:
    """Combined VPIN + Synthesis signal."""
    timestamp: float
    market_id: str
    vpin: VPINReading
    synthesis: Optional[SynthesisSignal]
    toxicity_score: float  # 0 to 1
    direction: float  # -1 (NO) to +1 (YES)
    composite_strength: float  # final signal strength
    should_trade: bool = False
    recommended_side: Optional[Outcome] = None
    recommended_size: float = 0.0


@dataclass
class WalletProfile:
    """Tracked wallet with performance history."""
    address: str
    total_trades: int = 0
    correct_predictions: int = 0
    total_pnl: float = 0.0
    avg_entry_time_before_resolution: float = 0.0  # seconds
    markets_traded: set = field(default_factory=set)
    is_smart_money: bool = False
    accuracy: float = 0.0

    def update_accuracy(self):
        if self.total_trades > 0:
            self.accuracy = self.correct_predictions / self.total_trades


@dataclass
class BacktestTrade:
    """A trade executed during backtesting."""
    timestamp: float
    market_id: str
    side: Outcome
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    signal_strength: float
    vpin_at_entry: float
    synthesis_edge_at_entry: Optional[float] = None


@dataclass
class BacktestResult:
    """Summary of a backtest run."""
    trades: list[BacktestTrade]
    total_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    num_trades: int = 0
    avg_trade_pnl: float = 0.0
    total_fees: float = 0.0
