"""ToxFlow API — serves backtest data to the React dashboard."""

import time
import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from toxflow.core.types import Side, Outcome
from toxflow.strategies.toxicity_momentum import StrategyConfig
from toxflow.backtesting.engine import (
    BacktestEngine,
    generate_synthetic_market,
)

app = FastAPI(title="ToxFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/backtest/single")
def run_single_backtest(
    duration: float = Query(3600, description="Market duration in seconds"),
    bucket_volume: float = Query(100, description="VPIN bucket volume ($)"),
    vpin_window: int = Query(30, description="VPIN window size (buckets)"),
    z_threshold: float = Query(0.5, description="VPIN z-score threshold"),
    capital: float = Query(10000, description="Initial capital ($)"),
    seed: int = Query(42, description="Random seed"),
    use_synthesis: bool = Query(True, description="Use Synthesis overlay"),
):
    """Run a single backtest and return full time-series data for charts."""
    config = StrategyConfig(
        bucket_volume=bucket_volume,
        vpin_window=vpin_window,
        vpin_z_threshold=z_threshold,
    )

    # Generate synthetic market
    trades, outcome = generate_synthetic_market(
        duration_seconds=duration,
        seed=seed,
    )

    # Run backtest, capturing VPIN readings along the way
    engine = BacktestEngine(config)
    strategy = engine.strategy
    strategy.capital = capital

    vpin_series = []
    price_series = []
    signals = []
    pnl_curve = []
    running_pnl = 0.0
    cached_synthesis = None

    for i, trade in enumerate(trades):
        if use_synthesis and i % 30 == 0:
            cached_synthesis = engine._generate_correlated_synthesis(trade, outcome)

        vpin_eng = strategy.get_or_create_vpin(trade.market_id)
        reading = vpin_eng.process_trade(trade)

        strategy.wallet_tracker.record_trade(trade)
        strategy._check_exits(trade.market_id, trade.price, trade.timestamp)

        price_series.append({
            "time": trade.timestamp,
            "price": round(trade.price, 4),
            "size": round(trade.size, 2),
            "side": trade.side.value,
        })

        if reading is not None:
            z_score = vpin_eng.get_z_score(reading)
            vpin_series.append({
                "time": reading.timestamp,
                "vpin": round(reading.vpin_value, 4),
                "dvpin": round(reading.directional_vpin, 4),
                "zScore": round(z_score, 4),
                "isSpike": bool(vpin_eng.is_spike(reading)),
                "bucketId": reading.bucket_id,
            })

            signal = strategy.compositor.generate_signal(
                vpin_reading=reading,
                vpin_engine=vpin_eng,
                synthesis_signal=cached_synthesis,
                market_id=trade.market_id,
                capital=strategy.capital,
            )

            if signal.should_trade and len(strategy.positions) < config.max_positions:
                strategy._open_position(signal, trade.price, trade.timestamp)

            signals.append({
                "time": signal.timestamp,
                "strength": round(signal.composite_strength, 4),
                "direction": round(signal.direction, 4),
                "shouldTrade": signal.should_trade,
                "side": signal.recommended_side.value if signal.recommended_side else None,
                "toxicity": round(signal.toxicity_score, 4),
                "synthEdge": round(signal.synthesis.edge, 4) if signal.synthesis else None,
            })

    # Force close remaining
    if trades:
        strategy.force_close_all(trades[-1].price, trades[-1].timestamp)

    # Build P&L curve
    cum_pnl = 0.0
    for t in strategy.closed_trades:
        cum_pnl += t.pnl
        pnl_curve.append({
            "time": t.timestamp,
            "pnl": round(cum_pnl, 2),
            "tradePnl": round(t.pnl, 2),
            "side": t.side.value,
            "entryPrice": round(t.entry_price, 4),
            "exitPrice": round(t.exit_price, 4),
            "signalStrength": round(t.signal_strength, 4),
            "vpinAtEntry": round(t.vpin_at_entry, 4),
        })

    stats = strategy.get_stats()

    return {
        "outcome": outcome.value,
        "numTrades": len(trades),
        "config": {
            "bucketVolume": bucket_volume,
            "vpinWindow": vpin_window,
            "zThreshold": z_threshold,
            "duration": duration,
            "seed": seed,
        },
        "stats": {
            "totalPnl": round(stats.get("total_pnl", 0), 2),
            "winRate": round(stats.get("win_rate", 0), 4),
            "profitFactor": round(stats.get("profit_factor", 0), 2),
            "numTrades": stats.get("num_trades", 0),
            "avgWin": round(stats.get("avg_win", 0), 2),
            "avgLoss": round(stats.get("avg_loss", 0), 2),
            "totalFees": round(stats.get("total_fees", 0), 2),
            "finalCapital": round(stats.get("final_capital", 0), 2),
        },
        "priceSeries": price_series,
        "vpinSeries": vpin_series,
        "signals": signals,
        "pnlCurve": pnl_curve,
    }


@app.get("/api/backtest/monte-carlo")
def run_monte_carlo(
    simulations: int = Query(100, description="Number of simulations"),
    duration: float = Query(3600, description="Market duration in seconds"),
    bucket_volume: float = Query(100),
    vpin_window: int = Query(30),
    z_threshold: float = Query(0.5),
    capital: float = Query(10000),
    use_synthesis: bool = Query(True),
):
    """Run Monte Carlo simulation and return distribution data."""
    config = StrategyConfig(
        bucket_volume=bucket_volume,
        vpin_window=vpin_window,
        vpin_z_threshold=z_threshold,
    )

    engine = BacktestEngine(config)
    mc_results = engine.run_monte_carlo(
        n_simulations=simulations,
        duration_seconds=duration,
        initial_capital=capital,
        use_synthesis=use_synthesis,
    )

    pnls = [r.total_pnl for r in mc_results]
    win_rates = [r.win_rate for r in mc_results]
    sharpes = [r.sharpe_ratio for r in mc_results]
    drawdowns = [r.max_drawdown for r in mc_results]
    trade_counts = [r.num_trades for r in mc_results]

    return {
        "simulations": simulations,
        "results": [
            {
                "pnl": round(r.total_pnl, 2),
                "winRate": round(r.win_rate, 4),
                "sharpe": round(r.sharpe_ratio, 2),
                "maxDrawdown": round(r.max_drawdown, 4),
                "profitFactor": round(min(r.profit_factor, 100), 2),
                "numTrades": r.num_trades,
                "totalFees": round(r.total_fees, 2),
            }
            for r in mc_results
        ],
        "summary": {
            "meanPnl": round(float(np.mean(pnls)), 2),
            "medianPnl": round(float(np.median(pnls)), 2),
            "stdPnl": round(float(np.std(pnls)), 2),
            "pnl5th": round(float(np.percentile(pnls, 5)), 2),
            "pnl95th": round(float(np.percentile(pnls, 95)), 2),
            "meanWinRate": round(float(np.mean(win_rates)), 4),
            "meanSharpe": round(float(np.mean(sharpes)), 2),
            "meanDrawdown": round(float(np.mean(drawdowns)), 4),
            "profitableRuns": sum(1 for p in pnls if p > 0),
            "profitableRunsPct": round(sum(1 for p in pnls if p > 0) / len(pnls), 4),
            "meanTradeCount": round(float(np.mean(trade_counts)), 1),
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "toxflow", "version": "0.1.0"}


def main():
    import uvicorn
    uvicorn.run("toxflow.api.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
