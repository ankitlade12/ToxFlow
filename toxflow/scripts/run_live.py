#!/usr/bin/env python3
"""
ToxFlow — Live Market Analysis

Fetches real Polymarket trade data via Synthesis API and runs
VPIN analysis on it. No auth required for market data endpoints.

Usage:
    uv run python -m toxflow.scripts.run_live
    uv run python -m toxflow.scripts.run_live --query "election"
    uv run python -m toxflow.scripts.run_live --condition-id 0xabc...
"""

import asyncio
import argparse
import logging
import json
from pathlib import Path

from toxflow.data.polymarket_client import PolymarketClient
from toxflow.data.synthesis_client import SynthesisClient
from toxflow.core.vpin import VPINEngine
from toxflow.core.signal_compositor import SignalCompositor
from toxflow.strategies.toxicity_momentum import StrategyConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("toxflow.live")


async def discover_markets(client: PolymarketClient, query: str | None, limit: int):
    """Find active Polymarket markets."""
    logger.info("Discovering markets%s...", f' matching "{query}"' if query else "")
    markets = await client.get_active_markets(limit=limit, query=query)

    if not markets:
        logger.warning("No markets found.")
        return []

    logger.info("Found %d markets:", len(markets))
    for i, m in enumerate(markets[:20]):
        logger.info(
            "  [%d] %s  (vol=$%.0f, yes=%.2f)",
            i, m.question[:60], m.volume, m.yes_price,
        )
    return markets


async def analyze_market(
    client: PolymarketClient,
    condition_id: str,
    config: StrategyConfig,
    max_trades: int = 5000,
):
    """Fetch trades for a market and run VPIN analysis."""
    logger.info("Fetching trades for %s...", condition_id)
    trades = await client.get_all_trades(condition_id, max_trades=max_trades)

    if not trades:
        logger.warning("No trades found for %s", condition_id)
        return None

    logger.info("Got %d trades, running VPIN analysis...", len(trades))

    engine = VPINEngine(
        bucket_volume=config.bucket_volume,
        window_size=config.vpin_window,
    )
    compositor = SignalCompositor(
        vpin_z_threshold=config.vpin_z_threshold,
        min_composite_strength=config.min_composite_strength,
    )

    readings = []
    signals = []
    spikes = []

    for trade in trades:
        reading = engine.process_trade(trade)
        if reading is None:
            continue

        readings.append(reading)
        z = engine.get_z_score(reading)
        is_spike = engine.is_spike(reading)

        signal = compositor.generate_signal(
            vpin_reading=reading,
            vpin_engine=engine,
            market_id=condition_id,
        )
        signals.append(signal)

        if is_spike:
            spikes.append({
                "time": reading.timestamp,
                "vpin": reading.vpin_value,
                "dvpin": reading.directional_vpin,
                "z_score": z,
                "signal_strength": signal.composite_strength,
                "direction": "YES" if signal.direction > 0 else "NO",
                "should_trade": signal.should_trade,
            })

    # Summary
    result = {
        "condition_id": condition_id,
        "total_trades": len(trades),
        "vpin_readings": len(readings),
        "total_signals": len(signals),
        "trade_signals": sum(1 for s in signals if s.should_trade),
        "spikes_detected": len(spikes),
    }

    if readings:
        result["latest_vpin"] = round(readings[-1].vpin_value, 4)
        result["latest_dvpin"] = round(readings[-1].directional_vpin, 4)
        result["avg_vpin"] = round(
            sum(r.vpin_value for r in readings) / len(readings), 4
        )

    print("\n" + "=" * 60)
    print("  ToxFlow Live Analysis")
    print("=" * 60)
    print(f"  Market:          {condition_id[:20]}...")
    print(f"  Trades analyzed: {result['total_trades']}")
    print(f"  VPIN readings:   {result['vpin_readings']}")
    print(f"  Spikes detected: {result['spikes_detected']}")
    print(f"  Trade signals:   {result['trade_signals']}")

    if readings:
        print(f"\n  Latest VPIN:     {result['latest_vpin']}")
        print(f"  Latest D-VPIN:   {result['latest_dvpin']}")
        print(f"  Avg VPIN:        {result['avg_vpin']}")

    if spikes:
        print(f"\n  Recent spikes:")
        for sp in spikes[-5:]:
            print(
                f"    VPIN={sp['vpin']:.3f} z={sp['z_score']:.2f} "
                f"dir={sp['direction']} trade={sp['should_trade']}"
            )

    print("=" * 60)

    return result


async def main_async(args):
    client = PolymarketClient()

    try:
        if args.condition_id:
            config = StrategyConfig(
                bucket_volume=args.bucket_volume,
                vpin_window=args.vpin_window,
                vpin_z_threshold=args.z_threshold,
            )
            await analyze_market(
                client, args.condition_id, config, max_trades=args.max_trades
            )
        else:
            markets = await discover_markets(client, args.query, args.limit)
            if not markets:
                return

            config = StrategyConfig(
                bucket_volume=args.bucket_volume,
                vpin_window=args.vpin_window,
                vpin_z_threshold=args.z_threshold,
            )

            # Analyze top markets by volume
            n = min(args.analyze_top, len(markets))
            logger.info("Analyzing top %d markets by volume...", n)

            for market in markets[:n]:
                if not market.condition_id:
                    continue
                await analyze_market(
                    client, market.condition_id, config, max_trades=args.max_trades
                )
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="ToxFlow Live Market Analysis")
    parser.add_argument("--condition-id", type=str, help="Specific market condition ID")
    parser.add_argument("--query", type=str, help="Search markets by keyword")
    parser.add_argument("--limit", type=int, default=20, help="Markets to fetch")
    parser.add_argument("--analyze-top", type=int, default=3, help="Analyze top N markets")
    parser.add_argument("--max-trades", type=int, default=5000, help="Max trades per market")
    parser.add_argument("--bucket-volume", type=float, default=100)
    parser.add_argument("--vpin-window", type=int, default=30)
    parser.add_argument("--z-threshold", type=float, default=0.5)
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
