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
    resolved: bool = False
    winner_token_id: Optional[str] = None
    outcome_label: Optional[str] = None  # e.g. "Uzbekistan" for neg-risk events
    event_id: Optional[int] = None       # parent event (for de-duping sub-markets)
    event_title: Optional[str] = None


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
            ev = event.get("event", {})
            for m in event.get("markets", []):
                try:
                    # Current Synthesis schema uses left_/right_ outcome fields.
                    # left is conventionally "Yes"; fall back gracefully.
                    left_outcome = str(m.get("left_outcome", "Yes")).lower()
                    left_price = float(m.get("left_price", 0.5) or 0.5)
                    right_price = float(m.get("right_price", 1 - left_price) or (1 - left_price))
                    if left_outcome == "yes":
                        yes_price, no_price = left_price, right_price
                    else:
                        yes_price, no_price = right_price, left_price

                    tokens = [
                        {"token_id": m.get("left_token_id", ""), "outcome": m.get("left_outcome", "Yes")},
                        {"token_id": m.get("right_token_id", ""), "outcome": m.get("right_outcome", "No")},
                    ]

                    info = MarketInfo(
                        condition_id=m.get("condition_id", ""),
                        # Prefer the specific market question over the event title
                        # so neg-risk sub-markets are distinguishable.
                        question=m.get("question") or ev.get("title", ""),
                        tokens=tokens,
                        active=bool(m.get("active", True)) and not m.get("resolved", False),
                        end_date=m.get("ends_at") or ev.get("ends_at"),
                        volume=float(m.get("volume", 0) or 0),
                        liquidity=float(m.get("liquidity", 0) or ev.get("liquidity", 0) or 0),
                        yes_price=yes_price,
                        no_price=no_price,
                        resolved=bool(m.get("resolved", False)),
                        winner_token_id=m.get("winner_token_id") or None,
                        outcome_label=m.get("outcome"),
                        event_id=ev.get("event_id"),
                        event_title=ev.get("title"),
                    )
                    markets.append(info)
                except (KeyError, ValueError, IndexError, TypeError):
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
                    token_id=t.get("token_id"),
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
        """Paginate through all trades, normalized into the YES-token frame."""
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

        normalized = normalize_trades(all_trades)
        return sorted(normalized, key=lambda t: t.timestamp)

    async def close(self):
        await self._http.aclose()


def parse_raw_trade(raw: dict, condition_id: str) -> Optional[Trade]:
    """Parse one raw Synthesis trade dict into a Trade (REST or WebSocket)."""
    try:
        side = Side.BUY if raw.get("side", True) else Side.SELL
        price = float(raw.get("price", 0))
        shares = float(raw.get("shares", 0) or 0)
        amount = float(raw.get("amount", 0) or 0)
        size = amount if amount > 0 else shares * price
        return Trade(
            timestamp=_parse_timestamp(raw.get("created_at", "")),
            price=price,
            size=size,
            side=side,
            outcome=Outcome.YES,
            market_id=condition_id,
            taker=raw.get("address"),
            token_id=raw.get("token_id"),
        )
    except (KeyError, ValueError, TypeError):
        return None


def normalize_trades(trades: list[Trade]) -> list[Trade]:
    """Re-frame a mixed-token tape into a single coherent YES-token series.

    A binary market trades two complementary tokens (YES and NO). The raw feed
    interleaves both, so price flips between p and 1-p and the tape looks
    nonsensical (e.g. 0.18 then 0.82). We pick the most-traded token as the
    reference ("YES") and convert every trade on the other token:

        price -> 1 - price          (NO @ 0.82  ==  YES @ 0.18)
        side  -> flipped            (buying NO  ==  selling YES)

    Prices are clamped to [0.01, 0.99] to drop the occasional bad print that
    would otherwise distort VPIN and P&L. Trades without a token_id are passed
    through unchanged (e.g. synthetic data).
    """
    if not trades:
        return trades

    counts: dict[str, int] = {}
    for t in trades:
        if t.token_id:
            counts[t.token_id] = counts.get(t.token_id, 0) + 1
    if not counts:
        return trades

    reference = max(counts, key=counts.get)
    return [normalize_one(t, reference) for t in trades]


def majority_token(trades: list[Trade]) -> Optional[str]:
    """Return the most-traded token_id (the YES-frame reference) or None."""
    counts: dict[str, int] = {}
    for t in trades:
        if t.token_id:
            counts[t.token_id] = counts.get(t.token_id, 0) + 1
    return max(counts, key=counts.get) if counts else None


def normalize_one(trade: Trade, reference_token: Optional[str]) -> Trade:
    """Re-frame a single trade into the reference (YES) token's perspective.

    Used by both the batch normalizer and the live WebSocket stream so the
    in-flight tape stays consistent with the historical one.
    """
    price = trade.price
    side = trade.side
    if reference_token and trade.token_id and trade.token_id != reference_token:
        price = 1.0 - trade.price
        side = Side.SELL if trade.side == Side.BUY else Side.BUY
    price = min(max(price, 0.01), 0.99)
    return Trade(
        timestamp=trade.timestamp,
        price=price,
        size=trade.size,
        side=side,
        outcome=Outcome.YES,
        market_id=trade.market_id,
        maker=trade.maker,
        taker=trade.taker,
        token_id=trade.token_id,
    )


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
