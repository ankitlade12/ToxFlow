"""
Toxicity Momentum Strategy

The primary trading strategy that combines VPIN spikes with
Synthesis AI forecasts to generate trades.

Entry Logic:
1. VPIN z-score exceeds threshold (informed flow detected)
2. Directional VPIN indicates which side (YES/NO) is being accumulated
3. Synthesis AI forecast confirms the direction (optional but boosts signal)
4. Composite signal strength exceeds minimum threshold

Exit Logic:
- Time-based: exit after N minutes (prediction markets have natural expiry)
- Profit target: exit at X% gain
- Stop loss: exit at Y% loss
- VPIN reversal: exit if toxicity drops below baseline (informed flow stopped)
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass, field

from toxflow.core.types import (
    Trade, CompositeSignal, BacktestTrade, Outcome, VPINReading, SynthesisSignal
)
from toxflow.core.vpin import VPINEngine
from toxflow.core.signal_compositor import SignalCompositor
from toxflow.core.wallet_tracker import WalletTracker

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """An open position."""
    market_id: str
    side: Outcome
    entry_price: float
    entry_time: float
    size: float  # USDC
    signal_strength: float
    vpin_at_entry: float
    synthesis_edge: Optional[float] = None


@dataclass
class StrategyConfig:
    """Configuration for ToxicityMomentum strategy."""
    # VPIN parameters
    bucket_volume: float = 100.0
    vpin_window: int = 30
    vpin_z_threshold: float = 0.5
    
    # Signal parameters
    min_synthesis_edge: float = 0.03
    min_composite_strength: float = 0.40
    
    # Position management
    max_hold_seconds: float = 600.0   # 10 minutes
    profit_target: float = 0.12       # 12% take profit (must overcome fees)
    stop_loss: float = 0.04           # 4% stop loss
    max_positions: int = 2            # max concurrent positions (concentrated)
    base_size_pct: float = 0.03       # 3% of capital per trade
    max_size_pct: float = 0.08        # 8% max
    
    # Fees (Polymarket 2026 dynamic taker fee, maker is 0)
    taker_fee_bps: float = 100        # ~1% effective taker fee
    maker_fee_bps: float = 0          # 0% maker fee


class ToxicityMomentumStrategy:
    """
    Trades VPIN toxicity spikes on Polymarket prediction markets.
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        
        # Core engines (initialized per-market)
        self.vpin_engines: dict[str, VPINEngine] = {}
        self.compositor = SignalCompositor(
            vpin_z_threshold=self.config.vpin_z_threshold,
            min_synthesis_edge=self.config.min_synthesis_edge,
            min_composite_strength=self.config.min_composite_strength,
            base_position_pct=self.config.base_size_pct,
            max_position_pct=self.config.max_size_pct,
        )
        self.wallet_tracker = WalletTracker()
        
        # State
        self.positions: list[Position] = []
        self.closed_trades: list[BacktestTrade] = []
        self.capital: float = 10000.0
        self.total_fees: float = 0.0

    def get_or_create_vpin(self, market_id: str) -> VPINEngine:
        """Get or create a VPIN engine for a market."""
        if market_id not in self.vpin_engines:
            self.vpin_engines[market_id] = VPINEngine(
                bucket_volume=self.config.bucket_volume,
                window_size=self.config.vpin_window,
            )
        return self.vpin_engines[market_id]

    def on_trade(
        self,
        trade: Trade,
        current_yes_price: float,
        synthesis_signal: Optional[SynthesisSignal] = None,
    ) -> Optional[CompositeSignal]:
        """
        Process an incoming trade. Returns a signal if one is generated.
        May also open or close positions.
        """
        # Feed to VPIN engine
        vpin_engine = self.get_or_create_vpin(trade.market_id)
        reading = vpin_engine.process_trade(trade)
        
        # Track wallet
        self.wallet_tracker.record_trade(trade)
        
        # Check exits on existing positions
        self._check_exits(trade.market_id, current_yes_price, trade.timestamp)
        
        if reading is None:
            return None
        
        # Generate composite signal
        signal = self.compositor.generate_signal(
            vpin_reading=reading,
            vpin_engine=vpin_engine,
            synthesis_signal=synthesis_signal,
            market_id=trade.market_id,
            capital=self.capital,
        )
        
        # Maybe open position
        if signal.should_trade and len(self.positions) < self.config.max_positions:
            self._open_position(signal, current_yes_price, trade.timestamp)
        
        return signal

    def _open_position(
        self,
        signal: CompositeSignal,
        current_yes_price: float,
        timestamp: float,
    ):
        """Open a new position based on signal."""
        # Determine entry price
        if signal.recommended_side == Outcome.YES:
            entry_price = current_yes_price
        else:
            entry_price = 1.0 - current_yes_price
        
        # Apply taker fee
        fee = signal.recommended_size * (self.config.taker_fee_bps / 10000)
        self.total_fees += fee
        
        position = Position(
            market_id=signal.market_id,
            side=signal.recommended_side,
            entry_price=entry_price,
            entry_time=timestamp,
            size=signal.recommended_size,
            signal_strength=signal.composite_strength,
            vpin_at_entry=signal.vpin.vpin_value,
            synthesis_edge=signal.synthesis.edge if signal.synthesis else None,
        )
        
        self.positions.append(position)
        logger.info(
            f"OPEN {position.side.value} @ {entry_price:.4f} "
            f"size=${position.size:.2f} signal={signal.composite_strength:.3f}"
        )

    def _check_exits(
        self,
        market_id: str,
        current_yes_price: float,
        timestamp: float,
    ):
        """Check if any positions should be closed."""
        remaining = []
        
        for pos in self.positions:
            if pos.market_id != market_id:
                remaining.append(pos)
                continue
            
            # Current price of our position's side
            if pos.side == Outcome.YES:
                current_price = current_yes_price
            else:
                current_price = 1.0 - current_yes_price
            
            pnl_pct = (current_price - pos.entry_price) / pos.entry_price
            hold_time = timestamp - pos.entry_time
            
            should_exit = False
            exit_reason = ""
            
            # Time exit
            if hold_time >= self.config.max_hold_seconds:
                should_exit = True
                exit_reason = "time"
            
            # Profit target
            elif pnl_pct >= self.config.profit_target:
                should_exit = True
                exit_reason = "profit"
            
            # Stop loss
            elif pnl_pct <= -self.config.stop_loss:
                should_exit = True
                exit_reason = "stoploss"
            
            # VPIN reversal (toxicity dropped)
            vpin_engine = self.vpin_engines.get(market_id)
            if vpin_engine and vpin_engine.history:
                latest_vpin = vpin_engine.history[-1]
                if latest_vpin.vpin_value < (pos.vpin_at_entry * 0.5):
                    should_exit = True
                    exit_reason = "vpin_reversal"
            
            if should_exit:
                self._close_position(pos, current_price, timestamp, exit_reason)
            else:
                remaining.append(pos)
        
        self.positions = remaining

    def _close_position(
        self,
        position: Position,
        exit_price: float,
        timestamp: float,
        reason: str = "",
    ):
        """Close a position and record the trade."""
        # Apply taker fee on exit
        exit_fee = position.size * (self.config.taker_fee_bps / 10000)
        self.total_fees += exit_fee
        
        pnl = position.size * (exit_price - position.entry_price) / position.entry_price
        pnl -= exit_fee  # subtract exit fee
        
        self.capital += pnl
        
        trade = BacktestTrade(
            timestamp=timestamp,
            market_id=position.market_id,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            pnl=pnl,
            signal_strength=position.signal_strength,
            vpin_at_entry=position.vpin_at_entry,
            synthesis_edge_at_entry=position.synthesis_edge,
        )
        
        self.closed_trades.append(trade)
        logger.info(
            f"CLOSE {position.side.value} @ {exit_price:.4f} "
            f"PnL=${pnl:.2f} reason={reason}"
        )

    def force_close_all(self, current_yes_price: float, timestamp: float):
        """Force close all positions (end of backtest)."""
        for pos in self.positions:
            price = current_yes_price if pos.side == Outcome.YES else 1.0 - current_yes_price
            self._close_position(pos, price, timestamp, "forced")
        self.positions = []

    def get_stats(self) -> dict:
        """Get strategy performance statistics."""
        if not self.closed_trades:
            return {"num_trades": 0}
        
        pnls = [t.pnl for t in self.closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        return {
            "num_trades": len(self.closed_trades),
            "total_pnl": sum(pnls),
            "win_rate": len(wins) / len(pnls) if pnls else 0,
            "avg_win": sum(wins) / len(wins) if wins else 0,
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "profit_factor": abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float('inf'),
            "max_pnl": max(pnls),
            "min_pnl": min(pnls),
            "total_fees": self.total_fees,
            "final_capital": self.capital,
        }
