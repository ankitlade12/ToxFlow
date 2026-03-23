"""
Wallet Tracker — Smart Money Clustering

Identifies wallets that consistently trade on the correct side before
market resolution. These "informed" wallets' activity is weighted more
heavily in the VPIN calculation.

Clustering approach:
1. Track all wallets that trade in resolved markets
2. Score each wallet: accuracy = correct_predictions / total_trades
3. Weight by recency and volume
4. Wallets above threshold = "smart money"
"""

import numpy as np
from collections import defaultdict
from typing import Optional
from toxflow.core.types import Trade, WalletProfile, Outcome


class WalletTracker:
    """
    Tracks wallet performance across resolved markets and identifies
    consistently informed traders ("smart money").
    """

    def __init__(
        self,
        accuracy_threshold: float = 0.60,   # min accuracy to be "smart"
        min_trades: int = 10,                # min trades before classification
        recency_halflife: float = 86400 * 7, # 7-day halflife for recency weighting
    ):
        self.accuracy_threshold = accuracy_threshold
        self.min_trades = min_trades
        self.recency_halflife = recency_halflife
        
        self._wallets: dict[str, WalletProfile] = {}
        self._market_trades: dict[str, list[Trade]] = defaultdict(list)
        self._smart_money_set: set[str] = set()

    def record_trade(self, trade: Trade):
        """Record a trade for wallet tracking."""
        if trade.taker:
            self._ensure_wallet(trade.taker)
            self._market_trades[trade.market_id].append(trade)
        if trade.maker:
            self._ensure_wallet(trade.maker)

    def resolve_market(self, market_id: str, winning_outcome: Outcome):
        """
        When a market resolves, score all wallets that traded in it.
        
        A wallet's trade is "correct" if they were net long the winning
        outcome at resolution time.
        """
        trades = self._market_trades.get(market_id, [])
        if not trades:
            return
        
        # Compute net position per wallet
        wallet_positions: dict[str, float] = defaultdict(float)
        
        for trade in trades:
            wallet = trade.taker or trade.maker
            if not wallet:
                continue
            
            # Positive = net YES, Negative = net NO
            if trade.outcome == Outcome.YES:
                if trade.side.value == "buy":
                    wallet_positions[wallet] += trade.size
                else:
                    wallet_positions[wallet] -= trade.size
            else:  # NO token
                if trade.side.value == "buy":
                    wallet_positions[wallet] -= trade.size
                else:
                    wallet_positions[wallet] += trade.size
        
        # Score each wallet
        for wallet, net_position in wallet_positions.items():
            profile = self._wallets.get(wallet)
            if not profile:
                continue
            
            profile.total_trades += 1
            profile.markets_traded.add(market_id)
            
            # Was the wallet on the correct side?
            correct = (
                (net_position > 0 and winning_outcome == Outcome.YES) or
                (net_position < 0 and winning_outcome == Outcome.NO)
            )
            
            if correct:
                profile.correct_predictions += 1
            
            profile.update_accuracy()
        
        # Update smart money set
        self._update_smart_money()

    def _update_smart_money(self):
        """Reclassify wallets as smart money based on current stats."""
        self._smart_money_set.clear()
        
        for addr, profile in self._wallets.items():
            if (profile.total_trades >= self.min_trades and
                    profile.accuracy >= self.accuracy_threshold):
                profile.is_smart_money = True
                self._smart_money_set.add(addr)
            else:
                profile.is_smart_money = False

    def is_smart_money(self, address: str) -> bool:
        """Check if a wallet is classified as smart money."""
        return address in self._smart_money_set

    def get_smart_money_weight(self, trade: Trade) -> float:
        """
        Returns a weight multiplier for a trade based on wallet classification.
        Smart money trades get higher weight in VPIN calculation.
        
        Returns:
            1.0 for unknown wallets
            2.0-5.0 for smart money (scaled by accuracy)
            0.5 for known "dumb money" (consistently wrong)
        """
        wallet = trade.taker or trade.maker
        if not wallet:
            return 1.0
        
        profile = self._wallets.get(wallet)
        if not profile or profile.total_trades < self.min_trades:
            return 1.0
        
        if profile.is_smart_money:
            # Scale weight by accuracy: 60% accuracy → 2x, 80% → 4x, 90% → 5x
            weight = 1.0 + (profile.accuracy - 0.5) * 8.0
            return min(max(weight, 1.0), 5.0)
        
        if profile.accuracy < 0.40:
            # Consistently wrong — contrarian signal
            return 0.5
        
        return 1.0

    def get_flow_composition(self, trades: list[Trade]) -> dict:
        """
        Analyze the composition of a set of trades.
        Returns breakdown of smart money vs retail flow.
        """
        smart_volume = 0.0
        retail_volume = 0.0
        smart_buy_vol = 0.0
        smart_sell_vol = 0.0
        
        for trade in trades:
            wallet = trade.taker or trade.maker
            if wallet and wallet in self._smart_money_set:
                smart_volume += trade.size
                if trade.side.value == "buy":
                    smart_buy_vol += trade.size
                else:
                    smart_sell_vol += trade.size
            else:
                retail_volume += trade.size
        
        total = smart_volume + retail_volume
        return {
            "smart_money_pct": smart_volume / total if total > 0 else 0,
            "retail_pct": retail_volume / total if total > 0 else 0,
            "smart_volume": smart_volume,
            "retail_volume": retail_volume,
            "smart_buy_volume": smart_buy_vol,
            "smart_sell_volume": smart_sell_vol,
            "smart_direction": (smart_buy_vol - smart_sell_vol) / smart_volume if smart_volume > 0 else 0,
        }

    def get_top_wallets(self, n: int = 20) -> list[WalletProfile]:
        """Get top N wallets by accuracy (with min trade threshold)."""
        qualified = [
            p for p in self._wallets.values()
            if p.total_trades >= self.min_trades
        ]
        return sorted(qualified, key=lambda p: p.accuracy, reverse=True)[:n]

    def _ensure_wallet(self, address: str):
        if address not in self._wallets:
            self._wallets[address] = WalletProfile(address=address)

    @property
    def smart_money_count(self) -> int:
        return len(self._smart_money_set)

    @property
    def total_wallets_tracked(self) -> int:
        return len(self._wallets)
