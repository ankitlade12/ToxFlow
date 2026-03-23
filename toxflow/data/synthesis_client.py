"""
Synthesis Client — Unified Prediction Market Data via Synthesis.trade API

Synthesis provides a single API to access Polymarket and Kalshi data:
- Market discovery and search
- Live prices and orderbooks
- Trade history with wallet addresses
- Price history (OHLC)
- WebSocket streams for real-time trades

For backtesting, we also support a simulation mode that generates
synthetic signals.

API Docs: https://api.synthesis.trade/docs/llms.txt
Base URL: https://synthesis.trade/api/v1
Auth: No auth required for market data endpoints
"""

import time
import logging
import hashlib
from typing import Optional

import httpx
import numpy as np

from toxflow.core.types import (
    Trade, OrderBookSnapshot, SynthesisSignal, Side, Outcome
)

logger = logging.getLogger(__name__)

SYNTHESIS_BASE = "https://synthesis.trade/api/v1"
SYNTHESIS_WS = "wss://synthesis.trade/api/v1/trades/ws"


class SynthesisClient:
    """
    Client for Synthesis prediction market platform.

    Live mode: queries Synthesis REST API for market data, prices, trades.
    Simulation mode: generates plausible synthetic signals for backtesting.
    """

    def __init__(
        self,
        simulation_mode: bool = True,
        simulation_accuracy: float = 0.58,
    ):
        self.simulation_mode = simulation_mode
        self.simulation_accuracy = simulation_accuracy
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    # ── Market Discovery ──────────────────────────────────────────────

    async def get_polymarket_markets(
        self,
        limit: int = 100,
        sort: str = "volume1wk",
        order: str = "DESC",
        query: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch Polymarket markets from Synthesis.
        GET /api/v1/polymarket/markets
        """
        http = await self._get_http()
        params: dict = {
            "limit": min(limit, 250),
            "sort": sort,
            "order": order,
            "markets": True,
        }
        if query:
            params["query"] = query
        if tags:
            params["tags"] = tags

        try:
            resp = await http.get(f"{SYNTHESIS_BASE}/polymarket/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", [])
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket markets: {e}")
        return []

    async def get_markets(
        self,
        venue: Optional[str] = None,
        limit: int = 100,
        sort: str = "volume",
        live: bool = True,
    ) -> list[dict]:
        """
        Fetch markets across venues.
        GET /api/v1/markets
        """
        http = await self._get_http()
        params: dict = {"limit": min(limit, 250), "sort": sort, "live": live}
        if venue:
            params["venue"] = venue

        try:
            resp = await http.get(f"{SYNTHESIS_BASE}/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", [])
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
        return []

    # ── Prices & Orderbooks ───────────────────────────────────────────

    async def get_prices(self, market_ids: list[str]) -> dict[str, float]:
        """
        Get current prices for markets (batch, up to 5000).
        POST /api/v1/markets/prices
        """
        http = await self._get_http()
        try:
            resp = await http.post(
                f"{SYNTHESIS_BASE}/markets/prices",
                json={"markets": market_ids},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", {}).get("prices", {})
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
        return {}

    async def get_orderbooks(self, market_ids: list[str]) -> list[dict]:
        """
        Get orderbooks for markets (batch, up to 5000).
        POST /api/v1/markets/orderbooks
        """
        http = await self._get_http()
        try:
            resp = await http.post(
                f"{SYNTHESIS_BASE}/markets/orderbooks",
                json={"markets": market_ids},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", [])
        except Exception as e:
            logger.error(f"Failed to fetch orderbooks: {e}")
        return []

    # ── Trade History ─────────────────────────────────────────────────

    async def get_polymarket_trades(
        self,
        condition_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Trade]:
        """
        Fetch trade history for a Polymarket market.
        GET /api/v1/polymarket/market/{condition_id}/trades

        Returns trades with wallet addresses, useful for VPIN + wallet tracking.
        """
        http = await self._get_http()
        try:
            resp = await http.get(
                f"{SYNTHESIS_BASE}/polymarket/market/{condition_id}/trades",
                params={"limit": min(limit, 10000), "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                return []

            trades = []
            for t in data.get("response", []):
                try:
                    # side: boolean in Synthesis API (true = buy)
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
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket trades: {e}")
        return []

    async def get_all_trades(
        self,
        condition_id: str,
        max_trades: int = 10000,
    ) -> list[Trade]:
        """Paginate through all trades for a market."""
        all_trades: list[Trade] = []
        offset = 0
        page_size = 1000

        while len(all_trades) < max_trades:
            batch = await self.get_polymarket_trades(
                condition_id, limit=page_size, offset=offset
            )
            if not batch:
                break
            all_trades.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size

        return sorted(all_trades, key=lambda t: t.timestamp)

    # ── Price History (OHLC) ──────────────────────────────────────────

    async def get_price_history(
        self,
        token_id: str,
        interval: str = "1h",
        volume: bool = True,
    ) -> dict:
        """
        Get OHLC price history for a Polymarket token.
        GET /api/v1/polymarket/market/{token_id}/price-history
        """
        http = await self._get_http()
        try:
            resp = await http.get(
                f"{SYNTHESIS_BASE}/polymarket/market/{token_id}/price-history",
                params={"interval": interval, "volume": volume},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                return data.get("response", {})
        except Exception as e:
            logger.error(f"Failed to fetch price history: {e}")
        return {}

    # ── Simulation Mode (for backtesting) ─────────────────────────────

    def simulate_signal(
        self,
        market_id: str,
        current_market_price: float,
    ) -> SynthesisSignal:
        """
        Generate a simulated signal for backtesting.
        Models an AI that detects edges of ~3-15% with noise.
        """
        seed = int(
            hashlib.md5(
                f"{market_id}_{int(time.time() // 60)}".encode()
            ).hexdigest()[:8],
            16,
        )
        rng = np.random.RandomState(seed)

        edge_direction = rng.choice([-1, 1])
        edge_magnitude = rng.uniform(0.02, 0.15)
        noise = rng.normal(0, 0.03)

        ai_prob = current_market_price + edge_direction * edge_magnitude + noise
        ai_prob = float(np.clip(ai_prob, 0.01, 0.99))

        confidence = min(0.9, 0.3 + abs(ai_prob - current_market_price) * 3)

        return SynthesisSignal(
            timestamp=time.time(),
            market_id=market_id,
            ai_probability=ai_prob,
            market_probability=current_market_price,
            edge=ai_prob - current_market_price,
            confidence=confidence,
        )

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None


def _parse_timestamp(ts_str: str) -> float:
    """Parse ISO 8601 timestamp to unix epoch."""
    if not ts_str:
        return time.time()
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return time.time()
