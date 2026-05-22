"""ToxFlow API — serves backtest and live analysis data to the React dashboard."""

import asyncio
import os
import time
from typing import Callable, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from toxflow.core.types import Side, Outcome, SynthesisSignal, Trade
from toxflow.core.flow_analyzer import analyze_flow
from toxflow.core.vpin import VPINEngine
from toxflow.data.polymarket_client import (
    PolymarketClient,
    majority_token,
    normalize_one,
)
from toxflow.api.live_stream import stream_market_trades
from toxflow.strategies.toxicity_momentum import StrategyConfig, ToxicityMomentumStrategy
from toxflow.backtesting.engine import (
    BacktestEngine,
    generate_synthetic_market,
)

app = FastAPI(title="ToxFlow API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "TOXFLOW_CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lightweight TTL cache for live Synthesis data ──────────────────────
# Keeps the demo snappy and avoids hammering the public API on repeat clicks.
_CACHE: dict[str, tuple[float, object]] = {}

# Radar ranking: drop books thinner than this, and treat a book as fully
# "trustworthy" for VPIN once it has this many trades.
SCAN_MIN_TRADES = 60
SCAN_CONFIDENCE_TRADES = 800


def _cache_get(key: str, ttl: float):
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    return None


def _cache_put(key: str, value: object):
    _CACHE[key] = (time.time(), value)


def _replay_trades(
    trades: list[Trade],
    config: StrategyConfig,
    capital: float,
    synthesis_provider: Optional[Callable[[int, Trade], Optional[SynthesisSignal]]] = None,
) -> dict:
    """Run the VPIN + signal + strategy-execution loop over a trade list.

    Shared by the synthetic backtest, live market analysis, and real-history
    backtest so all three produce identical time-series + panel data.

    `synthesis_provider(i, trade)` optionally supplies a forecast signal per
    trade (used only by the synthetic demo). Live analysis passes None so the
    signal is pure VPIN — no forecast, no outcome peeking.
    """
    engine = BacktestEngine(config)
    strategy: ToxicityMomentumStrategy = engine.strategy
    strategy.capital = capital

    price_series: list[dict] = []
    vpin_series: list[dict] = []
    signals: list[dict] = []

    for i, trade in enumerate(trades):
        synthesis = synthesis_provider(i, trade) if synthesis_provider else None

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

        if reading is None:
            continue

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
            synthesis_signal=synthesis,
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
            "recommendedSize": round(signal.recommended_size, 2),
            "vpin": round(reading.vpin_value, 4),
            "dvpin": round(reading.directional_vpin, 4),
            "zScore": round(z_score, 4),
        })

    if trades:
        strategy.force_close_all(trades[-1].price, trades[-1].timestamp)

    pnl_curve: list[dict] = []
    cum_pnl = 0.0
    for t in strategy.closed_trades:
        cum_pnl += t.pnl
        pnl_curve.append({
            "time": t.timestamp,
            "pnl": round(cum_pnl, 2),
            "tradePnl": round(t.pnl, 2),
            "side": t.side.value,
            "size": round(t.size, 2),
            "entryPrice": round(t.entry_price, 4),
            "exitPrice": round(t.exit_price, 4),
            "signalStrength": round(t.signal_strength, 4),
            "vpinAtEntry": round(t.vpin_at_entry, 4),
            "synthEdgeAtEntry": round(t.synthesis_edge_at_entry, 4)
            if t.synthesis_edge_at_entry is not None
            else None,
        })

    return {
        "strategy": strategy,
        "priceSeries": price_series,
        "vpinSeries": vpin_series,
        "signals": signals,
        "pnlCurve": pnl_curve,
    }


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

    # Synthetic-demo overlay: a *simulated* forecast correlated with the known
    # outcome. This is labelled "Simulated forecast" in the UI and exists only
    # to demonstrate the agreement/disagreement logic. The live endpoints
    # (/api/analyze, /api/scan) use no forecast — pure VPIN on real flow.
    engine = BacktestEngine(config)
    _synth_cache: dict[str, Optional[SynthesisSignal]] = {"sig": None}

    def synthesis_provider(i: int, trade: Trade) -> Optional[SynthesisSignal]:
        if not use_synthesis:
            return None
        if i % 30 == 0:
            _synth_cache["sig"] = engine._generate_correlated_synthesis(trade, outcome)
        return _synth_cache["sig"]

    replay = _replay_trades(trades, config, capital, synthesis_provider)
    strategy = replay["strategy"]
    price_series = replay["priceSeries"]
    vpin_series = replay["vpinSeries"]
    signals = replay["signals"]
    pnl_curve = replay["pnlCurve"]

    stats = strategy.get_stats()
    performance_stats = _build_performance_stats(stats, pnl_curve, capital)
    risk_summary = _build_risk_summary(
        config=config,
        stats=performance_stats,
        signals=signals,
        pnl_curve=pnl_curve,
        capital=capital,
    )
    market_quality = _build_market_quality(trades, vpin_series)
    opportunities = _build_opportunities(signals)
    decision_brief = _build_decision_brief(
        signals=signals,
        vpin_series=vpin_series,
        price_series=price_series,
        risk_summary=risk_summary,
        market_quality=market_quality,
    )
    benchmark = _build_benchmark(
        config=config,
        trades=trades,
        outcome=outcome,
        capital=capital,
        use_synthesis=use_synthesis,
        composite_stats=performance_stats,
    )

    return {
        "outcome": outcome.value,
        "numTrades": len(trades),
        "dataSource": "synthetic",
        "forecastMode": "simulated" if use_synthesis else "none",
        "config": {
            "bucketVolume": bucket_volume,
            "vpinWindow": vpin_window,
            "zThreshold": z_threshold,
            "duration": duration,
            "seed": seed,
        },
        "stats": performance_stats,
        "decisionBrief": decision_brief,
        "riskSummary": risk_summary,
        "marketQuality": market_quality,
        "opportunities": opportunities,
        "benchmark": benchmark,
        "priceSeries": price_series,
        "vpinSeries": vpin_series,
        "signals": signals,
        "pnlCurve": pnl_curve,
    }


# ── Live market endpoints (real Polymarket data via Synthesis) ─────────


@app.get("/api/markets")
async def list_markets(
    limit: int = Query(40, description="Markets to return"),
    query: Optional[str] = Query(None, description="Search keyword"),
    sort: str = Query("volume1wk", description="Synthesis sort key"),
):
    """Discover active Polymarket markets for the live picker.

    Returns lightweight metadata (question, volume, liquidity, current price).
    Multi-outcome 'neg-risk' events whose YES price defaults to 0.50 are still
    returned — the analyzer derives true price from the live trade tape.
    """
    cache_key = f"markets:{limit}:{query}:{sort}"
    cached = _cache_get(cache_key, ttl=60)
    if cached is not None:
        return cached

    client = PolymarketClient()
    try:
        markets = await client.get_active_markets(limit=limit, sort=sort, query=query)
    finally:
        await client.close()

    rows = [
        {
            "conditionId": m.condition_id,
            "question": m.question,
            "outcomeLabel": m.outcome_label,
            "volume": round(m.volume, 2),
            "liquidity": round(m.liquidity, 2),
            "yesPrice": round(m.yes_price, 4),
            "noPrice": round(m.no_price, 4),
            "resolved": m.resolved,
            "endDate": m.end_date,
        }
        for m in markets
        if m.condition_id
    ]
    payload = {"count": len(rows), "markets": rows}
    _cache_put(cache_key, payload)
    return payload


@app.get("/api/analyze")
async def analyze_live_market(
    condition_id: str = Query(..., description="Polymarket condition ID"),
    bucket_volume: float = Query(100, description="VPIN bucket volume ($)"),
    vpin_window: int = Query(30, description="VPIN window size (buckets)"),
    z_threshold: float = Query(0.5, description="VPIN z-score threshold"),
    capital: float = Query(10000, description="Shadow capital ($)"),
    max_trades: int = Query(5000, description="Max trades to pull"),
):
    """Run VPIN + smart-money flow on a real market's live trade tape.

    No forecast and no outcome peeking — the signal is pure orderflow. The
    strategy is replayed as a *shadow* book to show what it would have done.
    Reuses the same panel builders as the synthetic backtest.
    """
    config = StrategyConfig(
        bucket_volume=bucket_volume,
        vpin_window=vpin_window,
        vpin_z_threshold=z_threshold,
    )

    cache_key = f"trades:{condition_id}:{max_trades}"
    trades = _cache_get(cache_key, ttl=120)
    if trades is None:
        client = PolymarketClient()
        try:
            trades = await client.get_all_trades(condition_id, max_trades=max_trades)
        finally:
            await client.close()
        _cache_put(cache_key, trades)

    if not trades:
        raise HTTPException(
            status_code=404,
            detail="No trades found for this market (it may be new or illiquid).",
        )

    replay = _replay_trades(trades, config, capital, synthesis_provider=None)
    strategy = replay["strategy"]
    price_series = replay["priceSeries"]
    vpin_series = replay["vpinSeries"]
    signals = replay["signals"]
    pnl_curve = replay["pnlCurve"]

    stats = strategy.get_stats()
    performance_stats = _build_performance_stats(stats, pnl_curve, capital)
    risk_summary = _build_risk_summary(
        config=config,
        stats=performance_stats,
        signals=signals,
        pnl_curve=pnl_curve,
        capital=capital,
    )
    market_quality = _build_market_quality(trades, vpin_series)
    opportunities = _build_opportunities(signals)
    decision_brief = _build_decision_brief(
        signals=signals,
        vpin_series=vpin_series,
        price_series=price_series,
        risk_summary=risk_summary,
        market_quality=market_quality,
    )
    smart_money = analyze_flow(trades)

    last_price = price_series[-1]["price"] if price_series else 0.0
    span = (trades[-1].timestamp - trades[0].timestamp) if len(trades) > 1 else 0.0

    return {
        "dataSource": "live",
        "forecastMode": "none",
        "conditionId": condition_id,
        "numTrades": len(trades),
        "tapeSpanSeconds": round(span, 0),
        "latestPrice": round(last_price, 4),
        "config": {
            "bucketVolume": bucket_volume,
            "vpinWindow": vpin_window,
            "zThreshold": z_threshold,
        },
        "stats": performance_stats,
        "decisionBrief": decision_brief,
        "riskSummary": risk_summary,
        "marketQuality": market_quality,
        "smartMoney": smart_money,
        "opportunities": opportunities,
        "benchmark": None,
        "priceSeries": price_series,
        "vpinSeries": vpin_series,
        "signals": signals,
        "pnlCurve": pnl_curve,
    }


async def _scan_one(
    client: PolymarketClient,
    market: dict,
    config: StrategyConfig,
    max_trades: int,
) -> Optional[dict]:
    """Compute a compact toxicity snapshot for one market (used by /api/scan)."""
    cid = market["conditionId"]
    cache_key = f"scan:{cid}:{max_trades}"
    trades = _cache_get(cache_key, ttl=120)
    if trades is None:
        trades = await client.get_all_trades(cid, max_trades=max_trades)
        _cache_put(cache_key, trades)
    # Raw VPIN is unreliable on a thin book (a handful of one-sided prints
    # pins it near 1.0), so drop the very thinnest markets entirely.
    if len(trades) < SCAN_MIN_TRADES:
        return None

    replay = _replay_trades(trades, config, capital=10000.0)
    vpin_series = replay["vpinSeries"]
    if not vpin_series:
        return None

    flow = analyze_flow(trades)
    latest = vpin_series[-1]
    latest_price = replay["priceSeries"][-1]["price"] if replay["priceSeries"] else 0.5
    spikes = sum(1 for v in vpin_series if v["isSpike"])
    recent = vpin_series[-min(len(vpin_series), 10):]
    momentum = latest["vpin"] - (sum(v["vpin"] for v in recent) / len(recent))

    # Confidence-adjusted toxicity score. Raw VPIN over-ranks two kinds of
    # uninformative markets, so we down-weight both:
    #   • thin books — a few one-sided prints pin VPIN near 1.0 (shrink by sample size)
    #   • near-resolved books — one-sided flow at 99c is settlement, not informed
    #     money (shrink by how far price sits from the tails)
    # and we reward genuine repeated spikes. So a $5M, 3000-trade book trading
    # at 0.83 beats a $7K, 120-trade book pinned at 0.99.
    confidence = min(len(trades) / SCAN_CONFIDENCE_TRADES, 1.0)
    spike_factor = min(spikes / 20.0, 1.0)
    price_factor = min(min(latest_price, 1.0 - latest_price) / 0.15, 1.0)
    toxicity_score = latest["vpin"] * (0.85 * confidence + 0.15 * spike_factor) * price_factor

    return {
        "conditionId": cid,
        "question": market["question"],
        "eventTitle": market.get("eventTitle"),
        "volume": market["volume"],
        "latestPrice": replay["priceSeries"][-1]["price"] if replay["priceSeries"] else None,
        "vpin": latest["vpin"],
        "toxicityScore": round(toxicity_score, 4),
        "confidence": round(confidence, 4),
        "dvpin": latest["dvpin"],
        "zScore": latest["zScore"],
        "vpinMomentum": round(momentum, 4),
        "spikeCount": spikes,
        "numTrades": len(trades),
        "flowBias": flow["flowBias"],
        "smartVolumePct": flow["smartVolumePct"],
        "divergence": flow["divergence"],
    }


@app.get("/api/scan")
async def scan_markets(
    top: int = Query(8, description="Number of markets to scan"),
    query: Optional[str] = Query(None, description="Search keyword"),
    bucket_volume: float = Query(100),
    vpin_window: int = Query(30),
    z_threshold: float = Query(0.5),
    max_trades: int = Query(1500, description="Max trades per market (kept small for speed)"),
):
    """Scan top markets and rank them by current orderflow toxicity.

    This is the live radar: open the app and instantly see which real markets
    have informed flow active right now. Markets are fetched and analyzed
    concurrently, then ranked by latest VPIN.
    """
    config = StrategyConfig(
        bucket_volume=bucket_volume,
        vpin_window=vpin_window,
        vpin_z_threshold=z_threshold,
    )

    client = PolymarketClient()
    try:
        markets = await client.get_active_markets(limit=max(top * 8, 60), query=query)
        # De-dupe by parent event so the radar shows variety, not 8 near-identical
        # sub-markets of the same event. Markets arrive volume-sorted DESC, so the
        # first per event is the most liquid one.
        seen_events: set = set()
        candidates: list[dict] = []
        for m in markets:
            if not m.condition_id:
                continue
            key = m.event_id if m.event_id is not None else m.condition_id
            if key in seen_events:
                continue
            seen_events.add(key)
            candidates.append({
                "conditionId": m.condition_id,
                "question": m.question,
                "eventTitle": m.event_title,
                "volume": round(m.volume, 2),
            })
            if len(candidates) >= max(top * 2, 12):
                break

        results = await asyncio.gather(
            *[_scan_one(client, m, config, max_trades) for m in candidates],
            return_exceptions=True,
        )
    finally:
        await client.close()

    rows = [r for r in results if isinstance(r, dict)]
    rows.sort(key=lambda r: r["toxicityScore"], reverse=True)
    return {"scanned": len(rows), "markets": rows[:top]}


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


@app.websocket("/api/stream/{condition_id}")
async def stream_vpin(
    websocket: WebSocket,
    condition_id: str,
    bucket_volume: float = 100,
    vpin_window: int = 30,
):
    """Stream real-time VPIN for a market over a WebSocket.

    Bridges the Synthesis trades WebSocket into the VPIN engine: the historical
    batch warms the engine, then each live execution is pushed to the client
    with the updated VPIN reading and a spike flag.
    """
    await websocket.accept()
    engine = VPINEngine(bucket_volume=bucket_volume, window_size=vpin_window)
    reference = None
    try:
        async for kind, payload in stream_market_trades(condition_id):
            if kind == "initial":
                batch = sorted(payload, key=lambda t: t.timestamp)
                reference = majority_token(batch)
                engine.process_trades_batch([normalize_one(t, reference) for t in batch])
                history = engine.history[-80:]
                await websocket.send_json({
                    "type": "ready",
                    "warmTrades": len(batch),
                    "vpinHistory": [
                        {
                            "time": r.timestamp,
                            "vpin": round(r.vpin_value, 4),
                            "dvpin": round(r.directional_vpin, 4),
                            "isSpike": bool(engine.is_spike(r)),
                        }
                        for r in history
                    ],
                })
            else:
                trade = normalize_one(payload, reference)
                reading = engine.process_trade(trade)
                msg = {
                    "type": "trade",
                    "time": trade.timestamp,
                    "price": round(trade.price, 4),
                    "size": round(trade.size, 2),
                    "side": trade.side.value,
                    "wallet": trade.taker,
                }
                if reading is not None:
                    msg["vpin"] = round(reading.vpin_value, 4)
                    msg["dvpin"] = round(reading.directional_vpin, 4)
                    msg["zScore"] = round(engine.get_z_score(reading), 4)
                    msg["isSpike"] = bool(engine.is_spike(reading))
                await websocket.send_json(msg)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001 - surface stream errors to client
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "toxflow", "version": "0.2.0"}


def _build_performance_stats(
    stats: dict,
    pnl_curve: list[dict],
    capital: float,
) -> dict:
    """Normalize strategy stats into frontend-ready product metrics."""
    total_pnl = round(stats.get("total_pnl", 0), 2)
    profit_factor = stats.get("profit_factor", 0)
    if not np.isfinite(profit_factor):
        profit_factor = 99.0

    max_drawdown = 0.0
    if pnl_curve:
        equity = np.array([capital + p["pnl"] for p in pnl_curve])
        peaks = np.maximum.accumulate(equity)
        drawdowns = (peaks - equity) / np.maximum(peaks, 1e-9)
        max_drawdown = float(np.max(drawdowns))

    return {
        "totalPnl": total_pnl,
        "roi": round(total_pnl / capital, 4) if capital else 0,
        "winRate": round(stats.get("win_rate", 0), 4),
        "profitFactor": round(float(profit_factor), 2),
        "numTrades": stats.get("num_trades", 0),
        "avgWin": round(stats.get("avg_win", 0), 2),
        "avgLoss": round(stats.get("avg_loss", 0), 2),
        "avgTradePnl": round(total_pnl / stats.get("num_trades", 1), 2)
        if stats.get("num_trades", 0)
        else 0,
        "maxDrawdown": round(max_drawdown, 4),
        "totalFees": round(stats.get("total_fees", 0), 2),
        "finalCapital": round(stats.get("final_capital", capital), 2),
    }


def _build_market_quality(trades: list, vpin_series: list[dict]) -> dict:
    """Summarize whether the replay looks liquid and information-rich."""
    total_volume = sum(t.size for t in trades)
    buy_volume = sum(t.size for t in trades if t.side == Side.BUY)
    sell_volume = sum(t.size for t in trades if t.side == Side.SELL)
    sizes = [t.size for t in trades]
    wallets: dict[str, float] = {}

    for trade in trades:
        wallet = trade.taker or trade.maker
        if wallet:
            wallets[wallet] = wallets.get(wallet, 0.0) + trade.size

    large_threshold = float(np.percentile(sizes, 90)) if sizes else 0.0
    large_trade_volume = sum(t.size for t in trades if t.size >= large_threshold)
    top_wallet_volume = sum(sorted(wallets.values(), reverse=True)[:5])
    latest_vpin = vpin_series[-1]["vpin"] if vpin_series else 0.0
    spike_count = sum(1 for v in vpin_series if v["isSpike"])

    if latest_vpin >= 0.65:
        toxicity_regime = "toxic"
    elif latest_vpin >= 0.45:
        toxicity_regime = "active"
    else:
        toxicity_regime = "calm"

    volume_score = min(total_volume / 125_000, 1.0)
    wallet_score = min(len(wallets) / 35, 1.0)
    concentration_score = 1.0 - min((top_wallet_volume / total_volume) if total_volume else 0.0, 1.0)
    signal_score = min((spike_count / max(len(vpin_series), 1)) * 5, 1.0)
    liquidity_score = (
        0.35 * volume_score
        + 0.25 * wallet_score
        + 0.25 * concentration_score
        + 0.15 * signal_score
    )

    return {
        "totalVolume": round(total_volume, 2),
        "uniqueWallets": len(wallets),
        "buySellImbalance": round((buy_volume - sell_volume) / total_volume, 4)
        if total_volume
        else 0,
        "largeTradePct": round(large_trade_volume / total_volume, 4)
        if total_volume
        else 0,
        "topWalletVolumePct": round(top_wallet_volume / total_volume, 4)
        if total_volume
        else 0,
        "spikeCount": spike_count,
        "latestVpin": round(latest_vpin, 4),
        "toxicityRegime": toxicity_regime,
        "liquidityScore": round(liquidity_score, 4),
    }


def _build_opportunities(
    signals: list[dict],
    min_direction: float = 0.12,
    min_gap_seconds: float = 300.0,
) -> list[dict]:
    """Pick the highest-conviction, well-separated tradeable windows.

    Two guards keep the radar honest:
      • directional conviction — a signal must have a clear side
        (|direction| >= min_direction). At peak toxicity, D-VPIN can sit near
        zero and flip bucket-to-bucket, which would otherwise list a YES and a
        NO call seconds apart and read as the model contradicting itself.
      • time separation — picks are spaced out so the list reads as distinct
        windows, not one burst of opposing signals.
    """
    tradeable = [
        signal for signal in signals
        if signal.get("shouldTrade")
        and signal.get("side")
        and abs(signal.get("direction", 0.0)) >= min_direction
    ]
    ordered = sorted(
        tradeable,
        key=lambda s: (s["strength"], abs(s["direction"])),
        reverse=True,
    )

    picked: list[dict] = []
    for signal in ordered:
        if any(abs(signal["time"] - p["time"]) < min_gap_seconds for p in picked):
            continue
        picked.append(signal)
        if len(picked) >= 6:
            break

    opportunities = []
    for rank, signal in enumerate(picked, start=1):
        side = signal["side"].upper()
        synth_edge = signal.get("synthEdge")
        agreement = (
            "Synthesis confirms"
            if synth_edge is not None and np.sign(synth_edge) == np.sign(signal["direction"])
            else "VPIN-led"
        )
        opportunities.append({
            "rank": rank,
            "time": signal["time"],
            "action": f"Trade {side}",
            "side": signal["side"],
            "strength": signal["strength"],
            "toxicity": signal["toxicity"],
            "vpin": signal.get("vpin", 0),
            "dvpin": signal.get("dvpin", 0),
            "zScore": signal.get("zScore", 0),
            "synthEdge": synth_edge,
            "recommendedSize": signal.get("recommendedSize", 0),
            "rationale": f"{agreement}; directional flow favors {side}",
        })

    return opportunities


def _build_risk_summary(
    config: StrategyConfig,
    stats: dict,
    signals: list[dict],
    pnl_curve: list[dict],
    capital: float,
) -> dict:
    """Convert strategy controls into a compact execution risk summary."""
    latest_trade_signal = next(
        (signal for signal in reversed(signals) if signal.get("shouldTrade")),
        None,
    )
    suggested_position = latest_trade_signal.get("recommendedSize", 0) if latest_trade_signal else 0
    capital_at_risk = suggested_position / capital if capital else 0
    round_trip_fee_bps = config.taker_fee_bps * 2
    fee_drag = stats["totalFees"] / max(abs(stats["totalPnl"]) + stats["totalFees"], 1)
    last_trade_pnl = pnl_curve[-1]["tradePnl"] if pnl_curve else 0

    flags = []
    if not latest_trade_signal:
        flags.append("No active entry under current gates")
    if stats["maxDrawdown"] > 0.06:
        flags.append("Drawdown above 6% review band")
    if fee_drag > 0.35 and stats["numTrades"] > 0:
        flags.append("Fee drag is material")
    if last_trade_pnl < 0:
        flags.append("Last closed trade lost money")
    if not flags:
        flags.append("Risk gates inside policy")

    return {
        "suggestedPosition": round(suggested_position, 2),
        "capitalAtRiskPct": round(capital_at_risk, 4),
        "maxPositionPct": round(config.max_size_pct, 4),
        "stopLossPct": round(config.stop_loss, 4),
        "profitTargetPct": round(config.profit_target, 4),
        "maxHoldSeconds": round(config.max_hold_seconds, 0),
        "maxConcurrentPositions": config.max_positions,
        "roundTripFeeBps": round(round_trip_fee_bps, 1),
        "feeDragPct": round(fee_drag, 4),
        "riskFlags": flags,
    }


def _build_decision_brief(
    signals: list[dict],
    vpin_series: list[dict],
    price_series: list[dict],
    risk_summary: dict,
    market_quality: dict,
) -> dict:
    """Create an operator-facing recommendation from latest signal state."""
    latest_signal = signals[-1] if signals else None
    latest_trade_signal = next(
        (signal for signal in reversed(signals) if signal.get("shouldTrade")),
        None,
    )
    candidate = latest_signal if latest_signal and latest_signal.get("shouldTrade") else latest_trade_signal
    latest_vpin = vpin_series[-1] if vpin_series else None
    latest_price = price_series[-1]["price"] if price_series else 0.0

    if candidate:
        side = candidate["side"].upper()
        signal_age = (
            max(price_series[-1]["time"] - candidate["time"], 0)
            if price_series
            else 0
        )
        if candidate["strength"] >= 0.72 and signal_age <= 900:
            action = f"Trade {side}"
        elif signal_age <= 900:
            action = f"Stage {side}"
        else:
            action = f"Watch {side}"
        confidence = candidate["strength"]
        flow_bias = "YES" if candidate["direction"] > 0 else "NO"
    else:
        signal_age = None
        confidence = latest_signal["strength"] if latest_signal else 0.0
        flow_bias = "YES" if latest_vpin and latest_vpin["dvpin"] > 0 else "NO"
        action = "Standby"

    if confidence >= 0.72:
        confidence_label = "High"
    elif confidence >= 0.48:
        confidence_label = "Medium"
    else:
        confidence_label = "Low"

    reasons = []
    if latest_vpin:
        reasons.append(
            f"VPIN {latest_vpin['vpin']:.2f} in {market_quality['toxicityRegime']} regime"
        )
        reasons.append(
            f"Directional VPIN favors {flow_bias}"
        )
    if candidate and candidate.get("synthEdge") is not None:
        reasons.append(
            f"Synthesis edge {candidate['synthEdge']:+.1%}"
        )
    reasons.append(risk_summary["riskFlags"][0])

    return {
        "action": action,
        "confidence": round(confidence, 4),
        "confidenceLabel": confidence_label,
        "flowBias": flow_bias,
        "latestPrice": round(latest_price, 4),
        "latestSignalTime": candidate["time"] if candidate else None,
        "signalAgeSeconds": round(signal_age, 0) if signal_age is not None else None,
        "recommendedSide": candidate["side"] if candidate else None,
        "reasons": reasons[:4],
    }


def _build_benchmark(
    config: StrategyConfig,
    trades: list,
    outcome: Outcome,
    capital: float,
    use_synthesis: bool,
    composite_stats: dict,
) -> dict | None:
    """Compare the composite model against a VPIN-only run on the same tape."""
    if not use_synthesis or not trades:
        return None

    baseline_engine = BacktestEngine(config)
    baseline = baseline_engine.run(
        trades=trades,
        initial_capital=capital,
        use_synthesis=False,
        resolution_outcome=outcome,
    )

    return {
        "label": "VPIN-only baseline",
        "vpinOnlyPnl": round(baseline.total_pnl, 2),
        "vpinOnlyWinRate": round(baseline.win_rate, 4),
        "vpinOnlyTrades": baseline.num_trades,
        "compositeLift": round(composite_stats["totalPnl"] - baseline.total_pnl, 2),
        "tradeDelta": composite_stats["numTrades"] - baseline.num_trades,
        "winRateDelta": round(composite_stats["winRate"] - baseline.win_rate, 4),
    }


def main():
    import uvicorn
    host = os.getenv("TOXFLOW_HOST", "0.0.0.0")
    port = int(os.getenv("TOXFLOW_PORT", "8000"))
    uvicorn.run("toxflow.api.server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
