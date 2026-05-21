"""
Live trade streaming from the Synthesis Trades WebSocket.

Connects to `wss://synthesis.trade/api/v1/trades/ws`, subscribes to a market,
and yields parsed trades. The first WS message is a historical batch (yielded
as one list to warm the VPIN engine); subsequent messages are live executions.

Used by the `/api/stream/{condition_id}` endpoint to push real-time VPIN.
"""

import json
import logging
from typing import AsyncIterator, Union

import websockets

from toxflow.core.types import Trade
from toxflow.data.polymarket_client import parse_raw_trade

logger = logging.getLogger(__name__)

SYNTHESIS_WS = "wss://synthesis.trade/api/v1/trades/ws"


async def stream_market_trades(
    condition_id: str,
) -> AsyncIterator[tuple[str, Union[list[Trade], Trade]]]:
    """Yield ('initial', list[Trade]) once, then ('live', Trade) per execution."""
    async with websockets.connect(
        SYNTHESIS_WS, open_timeout=10, ping_interval=20, ping_timeout=20
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "subscribe",
                    "venue": "polymarket",
                    "markets": [condition_id],
                }
            )
        )
        while True:
            raw = await ws.recv()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict) or not msg.get("success"):
                continue
            resp = msg.get("response", {})
            if not isinstance(resp, dict):
                continue

            if resp.get("trades"):
                batch = []
                for item in resp["trades"]:
                    inner = item.get("trade", item) if isinstance(item, dict) else item
                    t = parse_raw_trade(inner, condition_id)
                    if t:
                        batch.append(t)
                yield "initial", batch
            elif resp.get("trade"):
                t = parse_raw_trade(resp["trade"], condition_id)
                if t:
                    yield "live", t
