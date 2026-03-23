"""
VPIN Engine — Volume-Synchronized Probability of Informed Trading

Adapted from Easley, López de Prado & O'Hara (2012) for prediction markets.

Key adaptations for Polymarket:
1. Binary outcome markets (YES/NO) instead of continuous price
2. Volume bucketing in USDC notional
3. Tick rule classification adapted for CLOB order flow
4. Directional VPIN variant revealing YES vs NO informed flow
"""

import numpy as np
from collections import deque
from typing import Optional
from toxflow.core.types import Trade, VolumeBucket, VPINReading, Side, Outcome


class VPINEngine:
    """
    Computes Volume-Synchronized Probability of Informed Trading (VPIN)
    adapted for Polymarket prediction markets.
    
    VPIN measures the probability that incoming order flow is "informed" —
    i.e., driven by traders who have an information edge on the market's
    true probability. High VPIN = high toxicity = smart money is active.
    """

    def __init__(
        self,
        bucket_volume: float = 100.0,     # USDC per volume bucket (small = more granular)
        window_size: int = 30,             # number of buckets in VPIN window
        sigma_threshold: float = 1.0,      # std devs for spike detection
        ema_span: int = 20,                # EMA span for baseline VPIN
    ):
        self.bucket_volume = bucket_volume
        self.window_size = window_size
        self.sigma_threshold = sigma_threshold
        self.ema_span = ema_span
        
        # State
        self._current_bucket_trades: list[Trade] = []
        self._current_bucket_volume: float = 0.0
        self._bucket_counter: int = 0
        self._completed_buckets: deque[VolumeBucket] = deque(maxlen=window_size * 2)
        self._vpin_history: deque[VPINReading] = deque(maxlen=1000)
        self._last_price: Optional[float] = None
        
        # EMA state for baseline
        self._ema_vpin: Optional[float] = None
        self._ema_var: Optional[float] = None
        self._ema_alpha: float = 2.0 / (ema_span + 1)

    def process_trade(self, trade: Trade) -> Optional[VPINReading]:
        """
        Process a single trade. Returns a VPINReading when a new volume 
        bucket is completed and enough history exists.
        """
        # Classify trade direction using tick rule if side not provided
        classified_trade = self._classify_trade(trade)
        
        self._current_bucket_trades.append(classified_trade)
        self._current_bucket_volume += classified_trade.size
        
        result = None
        
        # Check if bucket is full
        while self._current_bucket_volume >= self.bucket_volume:
            bucket = self._complete_bucket()
            self._completed_buckets.append(bucket)
            self._bucket_counter += 1
            
            # Compute VPIN if we have enough buckets
            if len(self._completed_buckets) >= self.window_size:
                result = self._compute_vpin()
        
        return result

    def process_trades_batch(self, trades: list[Trade]) -> list[VPINReading]:
        """Process a batch of trades, return all VPIN readings generated."""
        readings = []
        for trade in sorted(trades, key=lambda t: t.timestamp):
            reading = self.process_trade(trade)
            if reading is not None:
                readings.append(reading)
        return readings

    def _classify_trade(self, trade: Trade) -> Trade:
        """
        Classify trade as buy or sell using the tick rule.
        
        In Polymarket's CLOB, we infer aggressor side from price movement:
        - If price > last price → buyer initiated (buy aggressor)
        - If price < last price → seller initiated (sell aggressor)
        - If price == last price → use last classification
        """
        if trade.side != Side.BUY and trade.side != Side.SELL:
            # Need to classify
            if self._last_price is not None:
                if trade.price > self._last_price:
                    trade.side = Side.BUY
                elif trade.price < self._last_price:
                    trade.side = Side.SELL
                else:
                    # Same price — use bulk volume classification (BVC)
                    # Assign probabilistically based on proximity to bid/ask
                    trade.side = Side.BUY  # default, will be refined with orderbook
            else:
                trade.side = Side.BUY
        
        self._last_price = trade.price
        return trade

    def _complete_bucket(self) -> VolumeBucket:
        """
        Complete the current volume bucket.
        
        If accumulated volume exceeds bucket_volume, we split: the excess
        volume rolls into the next bucket proportionally.
        """
        trades = self._current_bucket_trades
        
        buy_vol = sum(t.size for t in trades if t.side == Side.BUY)
        sell_vol = sum(t.size for t in trades if t.side == Side.SELL)
        total_vol = buy_vol + sell_vol
        
        # Handle overflow: scale down to bucket_volume
        if total_vol > self.bucket_volume:
            scale = self.bucket_volume / total_vol
            buy_vol *= scale
            sell_vol *= scale
            total_vol = self.bucket_volume
        
        # VWAP
        total_notional = sum(t.price * t.size for t in trades)
        total_size = sum(t.size for t in trades)
        vwap = total_notional / total_size if total_size > 0 else 0
        
        bucket = VolumeBucket(
            bucket_id=self._bucket_counter,
            start_time=trades[0].timestamp if trades else 0,
            end_time=trades[-1].timestamp if trades else 0,
            total_volume=total_vol,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            num_trades=len(trades),
            vwap=vwap,
        )
        
        # Handle overflow for next bucket
        overflow = self._current_bucket_volume - self.bucket_volume
        if overflow > 0 and trades:
            # Keep last trade's proportional overflow
            last_trade = trades[-1]
            overflow_trade = Trade(
                timestamp=last_trade.timestamp,
                price=last_trade.price,
                size=overflow,
                side=last_trade.side,
                outcome=last_trade.outcome,
                market_id=last_trade.market_id,
                maker=last_trade.maker,
                taker=last_trade.taker,
            )
            self._current_bucket_trades = [overflow_trade]
            self._current_bucket_volume = overflow
        else:
            self._current_bucket_trades = []
            self._current_bucket_volume = 0.0
        
        return bucket

    def _compute_vpin(self) -> VPINReading:
        """
        Compute VPIN over the rolling window of completed buckets.
        
        Standard VPIN:
            VPIN = (1/N) × Σ |V_buy(i) - V_sell(i)| / V(i)
        
        Directional VPIN (our extension):
            D-VPIN = (1/N) × Σ (V_buy(i) - V_sell(i)) / V(i)
            Positive = YES-side informed flow dominates
            Negative = NO-side informed flow dominates
        """
        recent_buckets = list(self._completed_buckets)[-self.window_size:]
        
        imbalances = []
        signed_imbalances = []
        
        for bucket in recent_buckets:
            if bucket.total_volume > 0:
                abs_imb = abs(bucket.buy_volume - bucket.sell_volume) / bucket.total_volume
                signed_imb = (bucket.buy_volume - bucket.sell_volume) / bucket.total_volume
                imbalances.append(abs_imb)
                signed_imbalances.append(signed_imb)
        
        vpin_value = np.mean(imbalances) if imbalances else 0.0
        directional_vpin = np.mean(signed_imbalances) if signed_imbalances else 0.0
        
        # Update EMA baseline
        self._update_ema(vpin_value)
        
        reading = VPINReading(
            timestamp=recent_buckets[-1].end_time if recent_buckets else 0,
            vpin_value=float(vpin_value),
            directional_vpin=float(directional_vpin),
            window_size=len(recent_buckets),
            bucket_id=self._bucket_counter,
        )
        
        self._vpin_history.append(reading)
        return reading

    def _update_ema(self, vpin_value: float):
        """Update exponential moving average of VPIN for baseline detection."""
        if self._ema_vpin is None:
            self._ema_vpin = vpin_value
            self._ema_var = 0.0
        else:
            delta = vpin_value - self._ema_vpin
            self._ema_vpin = self._ema_alpha * vpin_value + (1 - self._ema_alpha) * self._ema_vpin
            self._ema_var = (1 - self._ema_alpha) * (self._ema_var + self._ema_alpha * delta ** 2)

    def is_spike(self, reading: VPINReading) -> bool:
        """
        Detect if current VPIN is a statistically significant spike
        above the EMA baseline.
        """
        if self._ema_vpin is None or self._ema_var is None:
            return False
        
        std = np.sqrt(self._ema_var) if self._ema_var > 0 else 0.01
        z_score = (reading.vpin_value - self._ema_vpin) / std
        
        return z_score > self.sigma_threshold

    def get_z_score(self, reading: VPINReading) -> float:
        """Get z-score of current VPIN relative to EMA baseline."""
        if self._ema_vpin is None or self._ema_var is None:
            return 0.0
        std = np.sqrt(self._ema_var) if self._ema_var > 0 else 0.01
        return (reading.vpin_value - self._ema_vpin) / std

    @property
    def current_ema(self) -> Optional[float]:
        return self._ema_vpin

    @property
    def history(self) -> list[VPINReading]:
        return list(self._vpin_history)

    def reset(self):
        """Reset engine state for a new market."""
        self._current_bucket_trades = []
        self._current_bucket_volume = 0.0
        self._bucket_counter = 0
        self._completed_buckets.clear()
        self._vpin_history.clear()
        self._last_price = None
        self._ema_vpin = None
        self._ema_var = None
