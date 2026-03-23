"""
Backtesting Engine

Walk-forward simulation of the ToxicityMomentum strategy on historical
or synthetic market data. Produces comprehensive performance metrics.
"""

import time
import logging
import numpy as np
from typing import Optional
from dataclasses import dataclass

from toxflow.core.types import Trade, BacktestResult, BacktestTrade, Side, Outcome, SynthesisSignal
from toxflow.strategies.toxicity_momentum import ToxicityMomentumStrategy, StrategyConfig
from toxflow.data.synthesis_client import SynthesisClient

logger = logging.getLogger(__name__)


def generate_synthetic_market(
    duration_seconds: float = 3600,      # 1 hour
    avg_trade_interval: float = 2.0,      # seconds between trades
    base_price: float = 0.50,
    volatility: float = 0.015,
    informed_ratio: float = 0.15,         # 15% of traders are informed
    informed_burst_prob: float = 0.08,    # probability of informed burst per minute
    resolution_outcome: Optional[Outcome] = None,
    seed: int = 42,
) -> tuple[list[Trade], Outcome]:
    """
    Generate synthetic Polymarket trade data with realistic microstructure.
    
    The generator creates:
    - Background noise trading (random walk around fair value)
    - Periodic "informed bursts" where smart money clusters trades
    - Gradual price discovery toward the resolution outcome
    
    This lets us validate VPIN detection without needing live data.
    """
    rng = np.random.RandomState(seed)
    
    # Determine resolution
    if resolution_outcome is None:
        resolution_outcome = Outcome.YES if rng.random() > 0.5 else Outcome.NO
    
    # True probability drifts toward resolution
    true_prob = base_price
    final_prob = 0.95 if resolution_outcome == Outcome.YES else 0.05
    
    trades = []
    current_time = time.time() - duration_seconds
    price = base_price
    
    n_trades = int(duration_seconds / avg_trade_interval)
    informed_wallets = [f"0x{''.join(rng.choice(list('abcdef0123456789'), 40))}" for _ in range(5)]
    retail_wallets = [f"0x{''.join(rng.choice(list('abcdef0123456789'), 40))}" for _ in range(50)]
    
    # Pre-compute informed burst windows (bursts last 2-5 minutes)
    n_minutes = int(duration_seconds / 60)
    burst_minutes = set()
    for m in range(n_minutes):
        if rng.random() < informed_burst_prob:
            burst_len = rng.randint(2, 6)
            for bm in range(m, min(m + burst_len, n_minutes)):
                burst_minutes.add(bm)
    
    for i in range(n_trades):
        elapsed = i * avg_trade_interval
        progress = elapsed / duration_seconds  # 0 to 1
        current_time_i = current_time + elapsed
        current_minute = int(elapsed / 60)
        
        # True probability drifts toward resolution
        true_prob = base_price + (final_prob - base_price) * (progress ** 1.5)
        
        # Is this an informed burst period?
        in_burst = current_minute in burst_minutes
        
        if in_burst and rng.random() < 0.75:
            # INFORMED TRADE — heavily one-sided
            # Smart money trades toward true probability
            is_buy = true_prob > price
            
            # Larger sizes during informed bursts (3-10x normal)
            size = rng.lognormal(mean=5.5, sigma=0.6)  # $100-800
            
            # Stronger price impact during bursts
            impact = size * 0.0003
            if is_buy:
                price = min(0.99, price + impact + rng.normal(0, volatility * 0.3))
            else:
                price = max(0.01, price - impact + rng.normal(0, volatility * 0.3))
            
            wallet = rng.choice(informed_wallets)
            side = Side.BUY if is_buy else Side.SELL
        else:
            # NOISE TRADE — roughly balanced
            # Random walk with slight drift toward true prob
            drift = (true_prob - price) * 0.002
            price_change = drift + rng.normal(0, volatility)
            price = float(np.clip(price + price_change, 0.01, 0.99))
            
            size = rng.lognormal(mean=3.0, sigma=0.8)  # $5-100
            # Noise traders are roughly 50/50 with slight bias
            buy_prob = 0.5 + (true_prob - price) * 0.3
            side = Side.BUY if rng.random() < buy_prob else Side.SELL
            wallet = rng.choice(retail_wallets)
        
        trade = Trade(
            timestamp=current_time_i,
            price=float(np.clip(price, 0.01, 0.99)),
            size=float(size),
            side=side,
            outcome=Outcome.YES,
            market_id=f"synthetic_{seed}",
            taker=wallet,
        )
        trades.append(trade)
    
    return trades, resolution_outcome


class BacktestEngine:
    """Walk-forward backtesting engine."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self.strategy = ToxicityMomentumStrategy(self.config)
        self.synthesis_client = SynthesisClient(simulation_mode=True)

    def run(
        self,
        trades: list[Trade],
        initial_capital: float = 10000.0,
        use_synthesis: bool = True,
        resolution_outcome: Optional[Outcome] = None,
    ) -> BacktestResult:
        """
        Run backtest on a list of historical trades.
        """
        self.strategy.capital = initial_capital
        
        signals_generated = 0
        trades_executed = 0
        cached_synthesis = None
        
        for i, trade in enumerate(trades):
            # Refresh Synthesis signal every ~30 trades (simulates polling)
            if use_synthesis and i % 30 == 0:
                cached_synthesis = self._generate_correlated_synthesis(
                    trade, resolution_outcome,
                )
            
            # Process trade through strategy
            signal = self.strategy.on_trade(
                trade=trade,
                current_yes_price=trade.price,
                synthesis_signal=cached_synthesis,
            )
            
            if signal is not None:
                signals_generated += 1
                if signal.should_trade:
                    trades_executed += 1
        
        # Force close remaining positions at last price
        if trades:
            last_price = trades[-1].price
            self.strategy.force_close_all(last_price, trades[-1].timestamp)
        
        # Compute metrics
        result = self._compute_metrics(
            self.strategy.closed_trades,
            initial_capital,
        )
        
        logger.info(
            f"Backtest complete: {signals_generated} signals, "
            f"{trades_executed} trades executed, "
            f"PnL=${result.total_pnl:.2f}"
        )
        
        return result

    def run_monte_carlo(
        self,
        n_simulations: int = 100,
        duration_seconds: float = 3600,
        initial_capital: float = 10000.0,
        use_synthesis: bool = True,
    ) -> list[BacktestResult]:
        """
        Run Monte Carlo simulation across many synthetic markets.
        This provides statistical confidence in the strategy's edge.
        """
        results = []
        
        for i in range(n_simulations):
            # Generate synthetic market
            trades, outcome = generate_synthetic_market(
                duration_seconds=duration_seconds,
                seed=i * 17 + 42,
                base_price=np.random.uniform(0.3, 0.7),
                volatility=np.random.uniform(0.01, 0.04),
                informed_burst_prob=np.random.uniform(0.03, 0.10),
            )
            
            # Reset strategy for each simulation
            self.strategy = ToxicityMomentumStrategy(self.config)
            
            # Run backtest
            result = self.run(trades, initial_capital, use_synthesis, resolution_outcome=outcome)
            results.append(result)
            
            if (i + 1) % 10 == 0:
                avg_pnl = np.mean([r.total_pnl for r in results])
                logger.info(f"Monte Carlo {i+1}/{n_simulations}: avg PnL=${avg_pnl:.2f}")
        
        return results

    def _generate_correlated_synthesis(
        self,
        trade: Trade,
        resolution_outcome: Optional[Outcome],
    ) -> SynthesisSignal:
        """
        Generate a Synthesis signal that is correlated with the actual outcome.
        
        Models an AI that is ~58% accurate: it knows the right direction
        most of the time but adds noise. This simulates what a real AI
        forecasting system would produce.
        """
        rng = np.random.RandomState(
            int(hash(f"{trade.market_id}_{int(trade.timestamp)}") % 2**31)
        )
        
        market_price = trade.price
        
        if resolution_outcome is not None:
            # AI "knows" the direction ~58% of the time
            true_fair = 0.80 if resolution_outcome == Outcome.YES else 0.20
            
            if rng.random() < 0.58:
                # Correct direction with noise
                ai_prob = true_fair + rng.normal(0, 0.12)
            else:
                # Wrong direction
                ai_prob = (1.0 - true_fair) + rng.normal(0, 0.15)
        else:
            ai_prob = market_price + rng.normal(0, 0.08)
        
        ai_prob = float(np.clip(ai_prob, 0.02, 0.98))
        edge = ai_prob - market_price
        confidence = min(0.9, 0.3 + abs(edge) * 2.0)
        
        return SynthesisSignal(
            timestamp=trade.timestamp,
            market_id=trade.market_id,
            ai_probability=ai_prob,
            market_probability=market_price,
            edge=edge,
            confidence=confidence,
        )

    def _compute_metrics(
        self,
        trades: list[BacktestTrade],
        initial_capital: float,
    ) -> BacktestResult:
        """Compute comprehensive backtest metrics."""
        if not trades:
            return BacktestResult(
                trades=trades,
                num_trades=0,
            )
        
        pnls = [t.pnl for t in trades]
        cum_pnl = np.cumsum(pnls)
        
        # Win rate
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        win_rate = len(wins) / len(pnls) if pnls else 0
        
        # Sharpe ratio (annualized, assuming ~8760 hours/year)
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_capital
            sharpe = np.mean(returns) / (np.std(returns) + 1e-10)
            # Annualize (rough estimate)
            trades_per_year = 8760  # assuming ~1 trade per hour
            sharpe *= np.sqrt(trades_per_year)
        else:
            sharpe = 0.0
        
        # Max drawdown
        peak = np.maximum.accumulate(cum_pnl + initial_capital)
        drawdowns = (peak - (cum_pnl + initial_capital)) / peak
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        return BacktestResult(
            trades=trades,
            total_pnl=float(sum(pnls)),
            win_rate=win_rate,
            sharpe_ratio=float(sharpe),
            max_drawdown=max_dd,
            profit_factor=profit_factor,
            num_trades=len(trades),
            avg_trade_pnl=float(np.mean(pnls)),
            total_fees=self.strategy.total_fees,
        )


def print_backtest_report(result: BacktestResult, mc_results: Optional[list[BacktestResult]] = None):
    """Print a formatted backtest report."""
    print("\n" + "=" * 60)
    print("  ToxFlow Backtest Report")
    print("=" * 60)
    
    print(f"\n  Trades Executed:   {result.num_trades}")
    print(f"  Total P&L:         ${result.total_pnl:,.2f}")
    print(f"  Win Rate:          {result.win_rate:.1%}")
    print(f"  Profit Factor:     {result.profit_factor:.2f}")
    print(f"  Sharpe Ratio:      {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown:      {result.max_drawdown:.1%}")
    print(f"  Avg Trade P&L:     ${result.avg_trade_pnl:,.2f}")
    print(f"  Total Fees Paid:   ${result.total_fees:,.2f}")
    
    if mc_results:
        pnls = [r.total_pnl for r in mc_results]
        win_rates = [r.win_rate for r in mc_results]
        sharpes = [r.sharpe_ratio for r in mc_results]
        
        print(f"\n  Monte Carlo ({len(mc_results)} simulations):")
        print(f"  {'':>20} {'Mean':>10} {'Std':>10} {'5th%':>10} {'95th%':>10}")
        print(f"  {'P&L ($)':>20} {np.mean(pnls):>10.2f} {np.std(pnls):>10.2f} "
              f"{np.percentile(pnls, 5):>10.2f} {np.percentile(pnls, 95):>10.2f}")
        print(f"  {'Win Rate':>20} {np.mean(win_rates):>10.1%} {np.std(win_rates):>10.1%} "
              f"{np.percentile(win_rates, 5):>10.1%} {np.percentile(win_rates, 95):>10.1%}")
        print(f"  {'Sharpe':>20} {np.mean(sharpes):>10.2f} {np.std(sharpes):>10.2f} "
              f"{np.percentile(sharpes, 5):>10.2f} {np.percentile(sharpes, 95):>10.2f}")
        print(f"\n  Profitable runs: {sum(1 for p in pnls if p > 0)}/{len(pnls)} "
              f"({sum(1 for p in pnls if p > 0)/len(pnls):.1%})")
    
    print("\n" + "=" * 60)
