#!/usr/bin/env python3
"""
ToxFlow — Run Backtest

Entry point for running backtests on synthetic or historical data.
Produces a full performance report with metrics.
"""

import logging
import argparse
import numpy as np

from toxflow.strategies.toxicity_momentum import StrategyConfig
from toxflow.backtesting.engine import (
    BacktestEngine,
    generate_synthetic_market,
    print_backtest_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("toxflow")


def main():
    parser = argparse.ArgumentParser(description="ToxFlow Backtester")
    parser.add_argument("--mode", choices=["single", "monte_carlo"], default="monte_carlo")
    parser.add_argument("--simulations", type=int, default=100, help="Monte Carlo simulations")
    parser.add_argument("--duration", type=float, default=7200, help="Market duration (seconds)")
    parser.add_argument("--capital", type=float, default=10000, help="Initial capital ($)")
    parser.add_argument("--bucket-volume", type=float, default=100, help="VPIN bucket size ($)")
    parser.add_argument("--vpin-window", type=int, default=30, help="VPIN window (buckets)")
    parser.add_argument("--z-threshold", type=float, default=0.5, help="VPIN z-score threshold")
    parser.add_argument("--no-synthesis", action="store_true", help="Disable Synthesis signals")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Configure strategy
    config = StrategyConfig(
        bucket_volume=args.bucket_volume,
        vpin_window=args.vpin_window,
        vpin_z_threshold=args.z_threshold,
    )

    engine = BacktestEngine(config)
    use_synthesis = not args.no_synthesis

    if args.mode == "single":
        logger.info("Running single backtest on synthetic market...")

        trades, outcome = generate_synthetic_market(
            duration_seconds=args.duration,
            seed=args.seed,
        )

        logger.info(f"Generated {len(trades)} synthetic trades, outcome={outcome.value}")

        result = engine.run(
            trades=trades,
            initial_capital=args.capital,
            use_synthesis=use_synthesis,
        )

        print_backtest_report(result)

    else:
        logger.info(f"Running Monte Carlo ({args.simulations} simulations)...")

        mc_results = engine.run_monte_carlo(
            n_simulations=args.simulations,
            duration_seconds=args.duration,
            initial_capital=args.capital,
            use_synthesis=use_synthesis,
        )

        # Use last single result for detailed view
        if mc_results:
            print_backtest_report(mc_results[-1], mc_results)

        # Save results summary
        pnls = [r.total_pnl for r in mc_results]
        logger.info(f"\nFinal Summary:")
        logger.info(f"  Mean P&L: ${np.mean(pnls):.2f}")
        logger.info(f"  Median P&L: ${np.median(pnls):.2f}")
        logger.info(f"  Win rate (profitable runs): {sum(1 for p in pnls if p > 0)/len(pnls):.1%}")


if __name__ == "__main__":
    main()
