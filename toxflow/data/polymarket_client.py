"""
Polymarket Data Client — via Synthesis.trade API

Uses Synthesis as the unified data layer for:
- Market discovery (GET /api/v1/polymarket/markets)
- Trade history with wallet addresses (GET /api/v1/polymarket/market/{id}/trades)
- Live prices (POST /api/v1/markets/prices)
- Orderbooks (POST /api/v1/markets/orderbooks)
- Price history OHLC (GET /api/v1/polymarket/market/{id}/price-history)

No auth required for market data endpoints.
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from toxflow.core.types import Trade, OrderBookSnapshot, Side, Outcome

logger = logging.getLogger(__name__)

SYNTHESIS_BASE = "https://synthesis.trade/api/v1"


@dataclass
class MarketInfo:
    """Polymarket market metadata."""
    condition_id: str
    question: str
    tokens: list[dict]
    active: bool
    end_date: Optional[str]
    volume: float
    liquidity: float
    yes_price: float
    no_price: float


class PolymarketClient:
    """Client for Polymarket data via Synthesis API."""

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=30.0)

    async def get_active_markets(
        self,
        limit: int = 50,
        sort: str = "volume1wk",
        query: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> list[MarketInfo]:
        """Fetch active Polymarket markets via Synthesis."""
        params: dict = {
            "limit": min(limit, 250),
            "sort": sort,
            "order": "DESC",
            "markets": True,
        }
        if query:
            params["query"] = query
        if tags:
            params["tags"] = tags

        try:
            resp = await self._http.get(
                f"{SYNTHESIS_BASE}/polymarket/markets", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []
        except Exception:
            logger.exception("Failed to fetch Polymarket markets")
            return []

        markets = []
        for event in data.get("response", []):
            for m in event.get("markets", []):
                try:
                    outcomes = m.get("outcomes", [])
                    prices = m.get("prices", [])
                    yes_price = float(prices[0]) if prices else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else 1 - yes_price

                    tokens = []
                    token_ids = m.get("token_ids", [])
                    for i, outcome in enumerate(outcomes):
                        tokens.append({
                            "token_id": token_ids[i] if i < len(token_ids) else "",
                            "outcome": outcome,
                        })

                    info = MarketInfo(
                        condition_id=m.get("condition_id", ""),
                        question=event.get("event", {}).get("title", m.get("question", "")),
                        tokens=tokens,
                        active=not m.get("closed", False),
                        end_date=m.get("end_date_iso"),
                        volume=float(m.get("volume", 0)),
                        liquidity=float(event.get("event", {}).get("liquidity", 0)),
                        yes_price=yes_price,
                        no_price=no_price,
                    )
                    markets.append(info)
                except (KeyError, ValueError, IndexError):
                    continue

        return markets

    async def get_market_trades(
        self,
        condition_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Trade]:
        """Fetch trade history for a market via Synthesis."""
        try:
            resp = await self._http.get(
                f"{SYNTHESIS_BASE}/polymarket/market/{condition_id}/trades",
                params={"limit": min(limit, 10000), "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []
        except Exception:
            logger.exception("Failed to fetch trades for %s", condition_id)
            return []

        trades = []
        for t in data.get("response", []):
            try:
                side = Side.BUY if t.get("side", True) else Side.SELL
                price = float(t.get("price", 0))
                shares = float(t.get("shares", 0))
                amount = float(t.get("amount", 0))
                size = amount if amount > 0 else shares * price

                trade = Trade(
                    timestamp=_parse_timestamp(t.get("created_at", "")),
                    price=price,
                    size=size,
                    side=side,
                    outcome=Outcome.YES,
                    market_id=condition_id,
                    taker=t.get("address"),
                )
                trades.append(trade)
            except (KeyError, ValueError, TypeError):
                continue

        return sorted(trades, key=lambda t: t.timestamp)

    async def get_prices(self, token_ids: list[str]) -> dict[str, float]:
        """Get current prices for tokens (batch)."""
        try:
            resp = await self._http.post(
                f"{SYNTHESIS_BASE}/markets/prices",
                json={"markets": token_ids},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", {}).get("prices", {})
        except Exception:
            logger.exception("Failed to fetch prices")
        return {}

    async def get_orderbook(
        self,
        token_id: str,
    ) -> Optional[OrderBookSnapshot]:
        """Fetch current orderbook for a token via Synthesis."""
        try:
            resp = await self._http.post(
                f"{SYNTHESIS_BASE}/markets/orderbooks",
                json={"markets": [token_id]},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return None

            books = data.get("response", [])
            if not books:
                return None

            ob = books[0].get("orderbook", {})
            bids = [
                (float(b["price"]), float(b["size"]))
                for b in ob.get("bids", [])
            ]
            asks = [
                (float(a["price"]), float(a["size"]))
                for a in ob.get("asks", [])
            ]

            return OrderBookSnapshot(
                timestamp=time.time(),
                market_id=token_id,
                outcome=Outcome.YES,
                bids=sorted(bids, key=lambda x: -x[0]),
                asks=sorted(asks, key=lambda x: x[0]),
            )
        except Exception:
            logger.exception("Failed to fetch orderbook for %s", token_id)
            return None

    async def get_price_history(
        self,
        token_id: str,
        interval: str = "1h",
    ) -> dict:
        """Get OHLC price history for a token."""
        try:
            resp = await self._http.get(
                f"{SYNTHESIS_BASE}/polymarket/market/{token_id}/price-history",
                params={"interval": interval, "volume": True},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", {})
        except Exception:
            logger.exception("Failed to fetch price history for %s", token_id)
        return {}

    async def get_all_trades(
        self,
        condition_id: str,
        max_trades: int = 10000,
    ) -> list[Trade]:
        """Paginate through all available trades."""
        all_trades: list[Trade] = []
        offset = 0
        page_size = 1000

        while len(all_trades) < max_trades:
            batch = await self.get_market_trades(
                condition_id, limit=page_size, offset=offset
            )
            if not batch:
                break
            all_trades.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size

        return sorted(all_trades, key=lambda t: t.timestamp)

    async def close(self):
        await self._http.aclose()


def _parse_timestamp(ts_str: str) -> float:
    """Parse ISO 8601 timestamp to unix epoch."""
    if not ts_str:
        return time.time()
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()
