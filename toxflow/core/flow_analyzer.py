"""
Flow Analyzer — Informed ("smart money") flow detection on a real trade tape.

The wallet tracker (`wallet_tracker.py`) scores wallets by *cross-market*
accuracy, which requires resolved-market history. On a single live market we
don't yet know the outcome, so this analyzer classifies informed flow from
*observable microstructure behavior* on the tape itself:

  1. Size      — informed players trade larger than the retail crowd.
  2. Conviction — they accumulate one side (|net| / gross volume is high),
                  rather than churning both ways.
  3. Leadership — their trades precede favorable price moves (their buys come
                  before up-ticks, sells before down-ticks).

A wallet's informed score blends these three. Wallets above the score
threshold are treated as "smart money", and we report how much of total
volume they represent and which side (YES/NO) they are leaning. When smart
money and retail diverge, that is the strongest signal — informed flow is
taking the other side of the crowd.

This is computed entirely from real trades — no outcome peeking.
"""

from __future__ import annotations

import numpy as np

from toxflow.core.types import Trade, Side


def _signed_size(trade: Trade) -> float:
    """+size for YES-accumulating flow, -size for NO-accumulating flow.

    A BUY of the YES token accumulates YES; a SELL releases it. Trades are
    normalized to the YES token upstream, so side maps directly to direction.
    """
    return trade.size if trade.side == Side.BUY else -trade.size


def _leadership_for_wallet(
    wallet_trade_idx: list[int],
    signed_flows: np.ndarray,
    prices: np.ndarray,
    horizon: int = 10,
) -> float:
    """How well a wallet's signed flow anticipates forward price moves.

    For each of the wallet's trades, look `horizon` trades ahead and check
    whether price moved in the direction the wallet was leaning. Returns a
    value in [-1, 1]: positive = the wallet tends to be right early.
    """
    if not wallet_trade_idx:
        return 0.0
    hits = []
    n = len(prices)
    for i in wallet_trade_idx:
        j = min(i + horizon, n - 1)
        if j <= i:
            continue
        fwd = prices[j] - prices[i]
        lean = signed_flows[i]
        if lean == 0 or fwd == 0:
            continue
        hits.append(1.0 if np.sign(fwd) == np.sign(lean) else -1.0)
    return float(np.mean(hits)) if hits else 0.0


def analyze_flow(
    trades: list[Trade],
    informed_threshold: float = 0.55,
    leadership_horizon: int = 10,
) -> dict:
    """Classify informed vs. retail flow on a trade tape.

    Returns a JSON-friendly dict describing smart-money composition,
    direction, divergence from retail, and a leaderboard of the most
    informed wallets observed.
    """
    empty = {
        "informedWallets": 0,
        "totalWallets": 0,
        "smartVolumePct": 0.0,
        "smartDirection": 0.0,
        "retailDirection": 0.0,
        "divergence": False,
        "convictionScore": 0.0,
        "flowBias": "NEUTRAL",
        "leaders": [],
    }
    tape = [t for t in trades if (t.taker or t.maker)]
    if len(tape) < 20:
        return empty

    tape = sorted(tape, key=lambda t: t.timestamp)
    prices = np.array([t.price for t in tape], dtype=float)
    signed_flows = np.array([_signed_size(t) for t in tape], dtype=float)

    # Per-wallet aggregates
    wallets: dict[str, dict] = {}
    for idx, t in enumerate(tape):
        addr = t.taker or t.maker
        w = wallets.setdefault(
            addr,
            {"vol": 0.0, "net": 0.0, "n": 0, "sizes": [], "idx": []},
        )
        w["vol"] += t.size
        w["net"] += _signed_size(t)
        w["n"] += 1
        w["sizes"].append(t.size)
        w["idx"].append(idx)

    total_volume = sum(w["vol"] for w in wallets.values())
    if total_volume <= 0:
        return empty

    # Size percentile baseline across wallets' average trade size
    avg_sizes = np.array([np.mean(w["sizes"]) for w in wallets.values()])
    size_p70 = float(np.percentile(avg_sizes, 70)) if len(avg_sizes) else 0.0
    size_p95 = float(np.percentile(avg_sizes, 95)) if len(avg_sizes) else 1.0
    size_span = max(size_p95 - size_p70, 1e-9)

    # Score each wallet
    for addr, w in wallets.items():
        avg_size = float(np.mean(w["sizes"]))
        # Conviction: how one-sided the wallet is. Gross volume == sum of
        # (positive) trade sizes == w["vol"]; |net| can't exceed it.
        conviction = min(abs(w["net"]) / w["vol"], 1.0) if w["vol"] > 0 else 0.0
        size_score = float(np.clip((avg_size - size_p70) / size_span, 0.0, 1.0))
        leadership = _leadership_for_wallet(
            w["idx"], signed_flows, prices, horizon=leadership_horizon
        )
        leadership_score = (leadership + 1.0) / 2.0  # map [-1,1] -> [0,1]

        # Informed score: conviction and size matter most; leadership refines.
        score = 0.45 * conviction + 0.35 * size_score + 0.20 * leadership_score
        w.update(
            avg_size=avg_size,
            conviction=conviction,
            leadership=leadership,
            score=score,
            informed=score >= informed_threshold and w["n"] >= 2,
        )

    informed = {a: w for a, w in wallets.items() if w["informed"]}

    smart_vol = sum(w["vol"] for w in informed.values())
    smart_net = sum(w["net"] for w in informed.values())
    retail_vol = total_volume - smart_vol
    retail_net = sum(w["net"] for a, w in wallets.items() if not w["informed"])

    smart_direction = (smart_net / smart_vol) if smart_vol > 0 else 0.0
    retail_direction = (retail_net / retail_vol) if retail_vol > 0 else 0.0
    conviction_score = abs(smart_direction)
    divergence = (
        smart_vol > 0
        and retail_vol > 0
        and np.sign(smart_direction) != np.sign(retail_direction)
        and abs(smart_direction) > 0.15
    )

    if conviction_score < 0.1:
        flow_bias = "NEUTRAL"
    else:
        flow_bias = "YES" if smart_direction > 0 else "NO"

    leaders_out = []
    for a, w in sorted(informed.items(), key=lambda kv: kv[1]["vol"], reverse=True)[:8]:
        leaders_out.append(
            {
                "address": a,
                "volume": round(w["vol"], 2),
                "trades": w["n"],
                "avgSize": round(w["avg_size"], 2),
                "netDirection": round(w["net"] / w["vol"], 4) if w["vol"] else 0.0,
                "conviction": round(w["conviction"], 4),
                "leadership": round(w["leadership"], 4),
                "score": round(w["score"], 4),
                "side": "YES" if w["net"] > 0 else "NO",
            }
        )

    return {
        "informedWallets": len(informed),
        "totalWallets": len(wallets),
        "smartVolumePct": round(smart_vol / total_volume, 4),
        "smartDirection": round(smart_direction, 4),
        "retailDirection": round(retail_direction, 4),
        "divergence": bool(divergence),
        "convictionScore": round(conviction_score, 4),
        "flowBias": flow_bias,
        "leaders": leaders_out,
    }
