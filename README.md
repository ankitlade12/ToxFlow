# ToxFlow — Polymarket Orderflow Toxicity Engine

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Synthesis API](https://img.shields.io/badge/Synthesis-Trade%20API-8B5CF6.svg)](https://synthesis.trade)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AlgoFest Hackathon 2026 Submission** · Track: FinTech Innovations

**Detect when smart money enters a prediction market — and trade in their direction.**

## Quick Highlights

- **Live Toxicity Radar**: Scans real Polymarket markets and ranks them by *current* orderflow toxicity — open the app and instantly see where informed money is active right now
- **Real-Time VPIN Streaming**: WebSocket bridge into the Synthesis trade feed computes VPIN tick-by-tick as live executions arrive, with live spike alerts
- **VPIN Engine**: Volume-Synchronized Probability of Informed Trading adapted for binary outcome markets — first-ever application to prediction markets
- **Directional VPIN**: Novel extension that reveals *which side* (YES/NO) informed flow favors, not just *that* it's present
- **Smart Money Flow**: Classifies informed wallets on the live tape (size, conviction, price-leadership) and flags when smart money diverges from the retail crowd
- **Real Data, No Peeking**: Live analysis runs pure VPIN on real trades — no forecast, no outcome knowledge. The synthetic backtest's forecast overlay is clearly labelled *simulated*
- **Watchlist & Alerts**: Follow markets and get spike / divergence / "turned toxic" alerts as the radar auto-refreshes
- **Monte Carlo Backtesting**: Statistical confidence via 100+ simulated markets with full performance metrics
- **Live Dashboard**: React frontend with the radar, VPIN charts, P&L curves, smart-money panels, signal heatmaps, and trade logs
- **Decision Brief**: Operator-facing recommendation, confidence drivers, risk guardrails, and model lift versus VPIN-only baseline

## Final Round Product Layer

ToxFlow now presents the quant engine as a decision-support product, not just a backtest visualizer:

| Product Surface | Value Added |
|---|---|
| **Decision Brief** | Converts VPIN, D-VPIN, Synthesis edge, and risk state into a clear Trade/Stage/Watch/Standby recommendation |
| **Risk Guard** | Shows suggested position size, capital at risk, stop/target bands, max hold, fee drag, and active risk flags |
| **Opportunity Radar** | Ranks the highest-conviction trade windows with side, signal strength, VPIN, Synthesis edge, size, and rationale |
| **Market Quality Score** | Summarizes volume, unique wallets, top-wallet concentration, toxicity regime, and VPIN spike count |
| **Model Lift** | Compares composite VPIN + Synthesis performance against a VPIN-only baseline on the same replay |

## Live Mode (Real Polymarket Data)

The dashboard opens on the **Live Radar** — the engine pointed at real markets, not a simulator.

| Surface | What it does | Endpoint |
|---|---|---|
| **Toxicity Radar** | Discovers active Polymarket markets (deduped by event) and ranks them by current VPIN, directional bias, toxicity momentum, spike count, and informed-volume share | `GET /api/scan` |
| **Market Analysis** | Pulls a market's real trade tape and runs pure VPIN — no forecast, no outcome peeking — plus a *shadow backtest* of the strategy on that real tape | `GET /api/analyze` |
| **Smart Money Flow** | Classifies informed wallets from observable tape behavior (trade size, directional conviction, price leadership) and flags informed-vs-retail divergence | (in `/api/analyze`) |
| **Real-Time Stream** | Bridges the Synthesis trades WebSocket into the VPIN engine; warms up on history, then updates VPIN tick-by-tick on each live execution with spike flags | `WS /api/stream/{condition_id}` |
| **Watchlist & Alerts** | Star markets and receive spike / divergence / "turned toxic" alerts as the radar auto-refreshes (30s) | client-side |

> **Honesty note.** Live mode is forecast-free: signals are computed purely from real orderflow. The classic *Single Backtest* runs on synthetic markets and includes a **simulated** forecast overlay (clearly labelled) to demonstrate the agreement/disagreement logic — it never claims to be a real model. The data layer normalizes Polymarket's two-token (YES/NO) trade feed into a single coherent price series before any analysis.

## The Problem

Every Polymarket bot on GitHub is doing the same thing — latency arbitrage, copy trading, or simple sentiment analysis. Meanwhile, **institutional market makers** have been using orderflow toxicity analysis for over a decade to detect informed traders in equity markets.

| Current Approach | Why It Fails |
|---|---|
| Copy trading top wallets | Wallets can be gamed, signals are delayed |
| Sentiment analysis | Lagging indicator, doesn't capture real money flow |
| Latency arbitrage | Race to zero, no sustainable edge |
| Simple price momentum | Ignores *who* is trading and *how aggressively* |

**Nobody has brought market microstructure analysis to prediction markets.** ToxFlow applies the same institutional quant framework (VPIN) that detected the 2010 Flash Crash — to Polymarket.

## The Solution

ToxFlow measures **orderflow toxicity** — the probability that incoming trades are from informed participants who know something the market doesn't yet reflect.

### How It Works

1. **Volume Bucketing**: Instead of time bars, trades are grouped by volume ($100 USDC per bucket). This normalizes for prediction market burstiness.

2. **Trade Classification**: Each bucket's buy/sell imbalance is computed using the tick rule (price movement direction).

3. **VPIN Calculation**: Rolling window measures how one-sided the flow is:
   ```
   VPIN = (1/N) x SUM |V_buy(i) - V_sell(i)| / V_total(i)
   ```
   High VPIN = one side is aggressively consuming liquidity = informed traders are active.

4. **Directional VPIN** (our innovation): Signed variant reveals the *direction* of informed flow:
   ```
   D-VPIN = (1/N) x SUM (V_buy(i) - V_sell(i)) / V_total(i)
   ```
   Positive = smart money buying YES. Negative = smart money buying NO.

5. **Composite Signal**: VPIN toxicity + Synthesis market data combined with agreement/disagreement multipliers to generate trade decisions.

## High-Level Workflow

```mermaid
flowchart LR
    subgraph "ToxFlow Pipeline"
        A["Market Data\nSynthesis API"] --> B["VPIN Engine\nVolume Bucketing"]
        B --> C["Signal Compositor\nToxicity + Direction"]
        C --> D["Trade Execution\nPosition Management"]
    end

    subgraph "Analysis Layer"
        E["Wallet Tracker\nSmart Money Clustering"]
        F["Backtesting Engine\nMonte Carlo Simulation"]
        G["React Dashboard\nReal-Time Visualization"]
    end

    A --> E
    E --> C
    B --> F
    C --> G
    D --> F

    style A fill:#8B5CF6,color:#fff
    style B fill:#3b82f6,color:#fff
    style C fill:#10b981,color:#fff
    style D fill:#f59e0b,color:#fff
    style E fill:#6366f1,color:#fff
    style F fill:#ec4899,color:#fff
    style G fill:#14b8a6,color:#fff
```

### Signal Generation Pipeline

| Stage | Component | Input | Output |
|-------|-----------|-------|--------|
| **Ingest** | Synthesis Client | Polymarket condition ID | Raw trades with wallet addresses |
| **Bucket** | VPIN Engine | Stream of trades | Volume-synchronized buckets with buy/sell imbalance |
| **Measure** | VPIN Calculator | Rolling bucket window | VPIN value (0-1) + Directional VPIN (-1 to +1) |
| **Detect** | Spike Detector | VPIN + EMA baseline | Z-score spike alerts when toxicity exceeds threshold |
| **Compose** | Signal Compositor | VPIN + Synthesis data | Composite signal strength + recommended side + position size |
| **Execute** | Strategy Engine | Composite signal | Entry/exit decisions with profit targets and stop losses |

## Architecture & Technical Overview

### System Architecture

```mermaid
graph TB
    subgraph Frontend ["Frontend - React 19 + TypeScript"]
        CONFIG["Config Panel\nParameter Tuning"]
        VPIN_CHART["VPIN Chart\nPrice + Toxicity Overlay"]
        PNL["P&L Curve\nCumulative Returns"]
        HEATMAP["Signal Heatmap\nStrength Over Time"]
        MC["Monte Carlo\nP&L Distribution"]
        TABLE["Trade Log\nDetailed Execution History"]
    end

    subgraph APILayer ["API Layer - FastAPI"]
        SCAN["/api/scan\nLive Toxicity Radar"]
        ANALYZE["/api/analyze\nReal-Tape VPIN + Smart Money"]
        STREAM["WS /api/stream/{id}\nReal-Time VPIN"]
        SINGLE["/api/backtest/single\nSynthetic Time-Series"]
        MONTE["/api/backtest/monte-carlo\nDistribution Statistics"]
    end

    subgraph CoreEngine ["Core Engine - Python"]
        VPINE["VPIN Engine\nVolume Bucketing + Tick Rule"]
        FLOW["Flow Analyzer\nInformed-Wallet Detection"]
        WALLET["Wallet Tracker\nCross-Market Accuracy"]
        SIGNAL["Signal Compositor\nComposite Strength Calculation"]
        STRAT["Strategy Engine\nEntry/Exit + Position Sizing"]
    end

    subgraph DataLayer ["Data Layer - Synthesis API"]
        MARKETS["Market Discovery\nGET /polymarket/markets"]
        TRADES["Trade History\nGET /polymarket/market/{id}/trades"]
        WS["Trades WebSocket\nwss://.../trades/ws"]
        BOOKS["Orderbooks\nPOST /markets/orderbooks"]
    end

    subgraph Backtesting ["Backtesting Engine"]
        SYNTH["Synthetic Market Generator\nRealistic Microstructure"]
        WALK["Walk-Forward Simulator\nFull Strategy Replay"]
        METRICS["Performance Metrics\nSharpe, Drawdown, Win Rate"]
    end

    Frontend -->|"REST + WebSocket"| APILayer
    SCAN --> CoreEngine
    ANALYZE --> CoreEngine
    STREAM --> VPINE
    SINGLE --> CoreEngine
    MONTE --> Backtesting
    CoreEngine --> DataLayer
    STREAM --> WS
    STRAT --> METRICS
    SYNTH --> WALK
    WALK --> STRAT
```

### Data Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React Dashboard
    participant API as FastAPI Server
    participant VPIN as VPIN Engine
    participant SIG as Signal Compositor
    participant SYN as Synthesis API

    Note over U,SYN: Single Backtest Flow
    U->>FE: Configure parameters
    FE->>API: GET /api/backtest/single
    API->>API: Generate synthetic market (or fetch live)
    loop For each trade
        API->>VPIN: process_trade()
        VPIN-->>API: VPINReading (if bucket complete)
        API->>SIG: generate_signal(vpin + synthesis)
        SIG-->>API: CompositeSignal
        API->>API: Check entry/exit rules
    end
    API-->>FE: Full time-series + stats
    FE-->>U: Charts, heatmap, trade log

    Note over U,SYN: Live Market Analysis
    U->>FE: Select market
    FE->>API: Start analysis
    API->>SYN: GET /polymarket/market/{id}/trades
    SYN-->>API: Historical trades with wallets
    loop For each trade
        API->>VPIN: process_trade()
        VPIN-->>API: VPINReading + spike detection
    end
    API-->>FE: VPIN analysis results
    FE-->>U: Toxicity spikes + signals
```

### Technical Deep Dive

#### VPIN Engine (`core/vpin.py`)

The core innovation — VPIN adapted from Easley, Lopez de Prado & O'Hara (2012) for binary outcome markets:

| Component | Method | Purpose |
|-----------|--------|---------|
| `process_trade()` | Trade classification + bucket accumulation | Classifies trades via tick rule, fills volume buckets |
| `_complete_bucket()` | Bucket finalization with overflow handling | Splits excess volume proportionally into next bucket |
| `_compute_vpin()` | Rolling window VPIN + Directional VPIN | Computes both magnitude and direction of informed flow |
| `_update_ema()` | Exponential moving average baseline | Tracks "normal" VPIN level for spike detection |
| `is_spike()` | Z-score based spike detection | Identifies statistically significant toxicity spikes |

**Key adaptation for prediction markets**: Volume bucketing in USDC notional instead of shares, binary outcome classification (YES/NO), and directional variant for side detection.

#### Signal Compositor (`core/signal_compositor.py`)

Combines VPIN toxicity with market data into actionable signals:

```
Composite Strength = (
    0.50 x toxicity_score +
    0.25 x vpin_direction_magnitude +
    0.25 x synthesis_edge
) x direction_agreement_multiplier

Agreement multiplier:
  VPIN direction matches market edge  -> 2.0x (high confidence)
  VPIN direction opposes market edge  -> 0.3x (reduced confidence)
```

#### Flow Analyzer (`core/flow_analyzer.py`)

Live informed-flow detection on a single market's real trade tape — no
resolution needed (powers `/api/scan` and `/api/analyze`):

- Classifies wallets by **size**, **directional conviction** (|net| / gross volume), and **price leadership** (do their trades precede favorable moves?)
- Reports informed-volume share, net YES/NO lean, and a wallet leaderboard
- Flags **divergence** — informed flow taking the opposite side of the retail crowd (the strongest setup)

#### Wallet Tracker (`core/wallet_tracker.py`)

Cross-market accuracy clustering for *resolved* markets (offline / backtest
context where outcomes are known):

- Scores accuracy = correct predictions / total trades across resolved markets
- Flags "smart money" at 60%+ accuracy with 10+ trades

#### Strategy Engine (`strategies/toxicity_momentum.py`)

Full position management with multiple exit rules:

| Rule | Trigger | Default |
|------|---------|---------|
| **Profit target** | P&L exceeds threshold | 12% |
| **Stop loss** | P&L drops below threshold | -4% |
| **Time exit** | Position held too long | 600 seconds |
| **VPIN reversal** | Toxicity drops 50% below entry | Dynamic |
| **Position sizing** | Signal strength scaled | 3-8% of capital |
| **Tradeable band** | Skip near-resolved books (no edge at extremes) | 0.05–0.95 |
| **Realistic fills** | Stops/targets fill at their level, not gapped prints | — |

#### Synthesis Integration (`data/synthesis_client.py`)

Real Polymarket data via Synthesis unified API — no auth required for market data:

| Endpoint | Data | Purpose |
|----------|------|---------|
| `GET /polymarket/markets` | Market discovery | Find active high-volume markets |
| `GET /polymarket/market/{id}/trades` | Trade history with wallets | Feed VPIN engine + wallet tracker |
| `POST /markets/prices` | Live prices (batch) | Current market state |
| `POST /markets/orderbooks` | Orderbook depth | Liquidity analysis |
| `GET /polymarket/market/{id}/price-history` | OHLC candles | Historical context |

## Synthesis API Usage

| Feature | How ToxFlow Uses It |
|---|---|
| **Market Discovery** | Fetches top Polymarket markets by volume, filters by tags/search |
| **Trade History** | Pulls trade-by-trade data with wallet addresses for VPIN computation and smart money tracking |
| **Live Prices** | Batch price queries for real-time market state during analysis |
| **Orderbooks** | Depth analysis for liquidity metrics and spread computation |
| **Price History** | OHLC data for historical context and backtesting validation |
| **WebSocket Trades** | Real-time trade stream for live VPIN monitoring (wss://synthesis.trade/api/v1/trades/ws) |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/scan` | **Live radar** — rank real markets by current VPIN toxicity (deduped by event) |
| `GET` | `/api/markets` | Discover active Polymarket markets (question, volume, price) for the picker |
| `GET` | `/api/analyze` | **Live analysis** — pure VPIN + smart-money flow on a real market's trade tape (no forecast) |
| `WS` | `/api/stream/{condition_id}` | **Real-time** VPIN stream bridged from the Synthesis trades WebSocket |
| `GET` | `/api/backtest/single` | Run single backtest with full time-series data (synthetic, simulated forecast) |
| `GET` | `/api/backtest/monte-carlo` | Run Monte Carlo simulation (N markets) |
| `GET` | `/api/health` | Health check |

### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `duration` | 3600 | Market duration in seconds |
| `bucket_volume` | 100 | USDC per volume bucket |
| `vpin_window` | 30 | Rolling window size (buckets) |
| `z_threshold` | 0.5 | VPIN z-score threshold for signals |
| `capital` | 10000 | Initial capital ($) |
| `seed` | 42 | Random seed for reproducibility |
| `use_synthesis` | true | Enable Synthesis overlay |
| `simulations` | 100 | Monte Carlo simulation count |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- uv (Python package manager)

### Setup

```bash
# Clone
git clone https://github.com/ankitlade12/ToxFlow.git
cd ToxFlow

# Install backend dependencies
uv sync

# Configure credentials (optional — market data works without auth)
cp .env.example .env
```

### Run

```bash
# Start API server
uv run toxflow-api

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Demo

Open **http://localhost:3000** (frontend) · API docs at **http://localhost:8000/docs**

| Step | Action | What You'll See |
|------|--------|----------------|
| **1** | Land on **Live Radar**, click **Scan** | Real Polymarket markets ranked by current VPIN toxicity — directional bias, momentum, spikes, informed-volume share |
| **2** | Click **Analyze** on a market | Real-tape VPIN chart, Smart Money Flow panel, decision brief, and a shadow backtest of the strategy on that market's actual trades |
| **3** | Click **Go Live** | Real-time VPIN streaming over WebSocket — VPIN ticks as live executions arrive, with spike flags |
| **4** | Star a market, toggle **Auto** | Watchlist auto-refreshes and fires spike / divergence / "turned toxic" alerts |
| **5** | Open **Single Backtest** / **Monte Carlo** | Synthetic-market validation with full metrics (forecast overlay labelled *simulated*) |

### CLI Commands

```bash
# Run unit tests (6/6 pass)
uv run python -m toxflow.tests.test_vpin

# Single backtest on synthetic market
uv run toxflow-backtest --mode single --duration 3600

# Monte Carlo simulation (100 markets)
uv run toxflow-backtest --mode monte_carlo --simulations 100

# Live analysis on real Polymarket data
uv run toxflow-live --limit 10 --analyze-top 3

# Live analysis on a specific market
uv run toxflow-live --condition-id 0xabc123...

# Start API server
uv run toxflow-api
```

## Project Structure

```
ToxFlow/
├── toxflow/
│   ├── core/
│   │   ├── vpin.py                # VPIN engine (volume bucketing + calculation)
│   │   ├── signal_compositor.py   # Combines VPIN + forecast into trade signals
│   │   ├── flow_analyzer.py       # Informed ("smart money") flow on a live tape
│   │   ├── wallet_tracker.py      # Cross-market wallet accuracy clustering
│   │   └── types.py               # Shared data types (Trade, VPINReading, etc.)
│   ├── data/
│   │   ├── polymarket_client.py   # Polymarket data + two-token normalization
│   │   └── synthesis_client.py    # Synthesis unified API client
│   ├── strategies/
│   │   └── toxicity_momentum.py   # Primary strategy: trade VPIN spikes
│   ├── backtesting/
│   │   └── engine.py              # Walk-forward + Monte Carlo backtesting
│   ├── api/
│   │   ├── server.py              # FastAPI: scan, analyze, markets, backtest
│   │   └── live_stream.py         # Synthesis trades WebSocket → live trades
│   ├── scripts/
│   │   ├── run_backtest.py        # CLI: backtest runner
│   │   └── run_live.py            # CLI: live market analysis
│   └── tests/
│       └── test_vpin.py           # 6 unit tests for VPIN engine
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Dashboard layout (Live Radar / Backtest / MC tabs)
│   │   ├── components/
│   │   │   ├── LiveView.tsx        # Live tab: radar + watchlist + alerts + drill-down
│   │   │   ├── LiveRadar.tsx       # Toxicity-ranked market scanner table
│   │   │   ├── LiveStreamPanel.tsx # Real-time VPIN stream over WebSocket
│   │   │   ├── SmartMoneyPanel.tsx # Informed-wallet flow + leaderboard
│   │   │   ├── DecisionBrief.tsx   # Recommendation + risk guard + model lift
│   │   │   ├── OpportunityRadar.tsx # Ranked trade windows
│   │   │   ├── VPINChart.tsx      # VPIN + price overlay chart
│   │   │   ├── PnlChart.tsx       # Cumulative P&L curve
│   │   │   ├── SignalHeatmap.tsx   # Signal strength scatter plot
│   │   │   ├── MonteCarloChart.tsx # P&L distribution histogram
│   │   │   ├── StatsCards.tsx      # Key performance metrics
│   │   │   ├── TradeTable.tsx      # Trade execution log
│   │   │   └── ConfigPanel.tsx     # Parameter tuning controls
│   │   └── lib/
│   │       ├── api.ts             # API client
│   │       └── types.ts           # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── pyproject.toml                 # uv project config
├── .env.example                   # Environment template
└── LICENSE                        # MIT
```

## What Makes This Novel

| # | Innovation | Why It Matters |
|---|-----------|---------------|
| 1 | **VPIN on prediction markets** | First-ever application — nobody on GitHub, academic papers, or crypto forums has done this |
| 2 | **Directional VPIN** | Standard VPIN only measures magnitude; our extension reveals *which side* smart money is on |
| 3 | **Composite signal model** | Neither VPIN nor market data alone is reliable; combining them with agreement multipliers filters false positives |
| 4 | **Volume bucketing for binary markets** | Prediction markets are bursty — volume-synchronized analysis normalizes this naturally |
| 5 | **Smart-money flow detection** | Classifies informed wallets on the live tape by size, directional conviction, and price-leadership — then flags when informed flow diverges from the retail crowd |
| 6 | **Monte Carlo validation** | Statistical confidence across 100+ simulated markets, not just cherry-picked results |
| 7 | **Real data via Synthesis API** | Live Polymarket trades with wallet addresses — not simulated, not delayed |
| 8 | **Academically grounded** | Based on Easley, Lopez de Prado & O'Hara (2012) — the paper that detected the Flash Crash |

## Measurable Output

### Backtest Metrics (per run)

| Metric | Description |
|--------|-------------|
| **Total P&L** | Net profit/loss including transaction fees |
| **Win Rate** | Percentage of profitable trades |
| **Profit Factor** | Gross wins / gross losses |
| **Sharpe Ratio** | Risk-adjusted returns (annualized) |
| **Max Drawdown** | Largest peak-to-trough decline |
| **Total Fees** | Cumulative transaction costs (1% taker fee) |

### Monte Carlo Summary (across N simulations)

| Metric | Description |
|--------|-------------|
| **Mean/Median P&L** | Central tendency of strategy returns |
| **5th/95th Percentile** | Tail risk and upside bounds |
| **Profitable Runs %** | How often the strategy makes money |
| **Mean Sharpe** | Average risk-adjusted performance |
| **Mean Drawdown** | Average worst-case decline |

### Live Radar & Analysis Output

| Metric | Description |
|--------|-------------|
| **Toxicity Score** | Radar ranking: VPIN adjusted for sample size, spike density, and price extremity |
| **VPIN / D-VPIN** | Current toxicity level (0-1) and directional bias (-1 to +1) |
| **VPIN Momentum** | Whether toxicity is rising or fading vs. its recent average |
| **Spikes Detected** | Statistically significant toxicity events |
| **Informed Volume %** | Share of volume from wallets classified as informed |
| **Flow Bias / Divergence** | Net YES/NO lean of informed flow, and whether it diverges from retail |
| **Smart-Money Leaderboard** | Top informed wallets by volume, conviction, and price leadership |

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Core Engine** | Python 3.11, NumPy | VPIN computation, signal generation, backtesting |
| **Data Layer** | Synthesis API, httpx | Polymarket market data, trades, orderbooks |
| **Backend** | FastAPI, Uvicorn | REST API serving backtest data to dashboard |
| **Frontend** | React 19, TypeScript, Recharts | Interactive charts, parameter tuning, trade visualization |
| **Styling** | Tailwind CSS v4 | Dark-themed dashboard UI |
| **Package Management** | uv, Hatchling | Python dependency management and build |
| **Streaming** | WebSocket (Synthesis trades feed → FastAPI WS) | Real-time trade streaming + live VPIN |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SYNTHESIS_PROJECT_API_KEY` | No | Synthesis project API key (market data works without auth) |
| `SYNTHESIS_ACCOUNT_API_KEY` | No | Synthesis account API key (for trading endpoints) |
| `POLYMARKET_API_KEY` | No | Direct Polymarket CLOB access (optional) |
| `TOXFLOW_HOST` | No | API server host (default: 0.0.0.0) |
| `TOXFLOW_PORT` | No | API server port (default: 8000) |

## License

MIT License — see [LICENSE](LICENSE) file for details.

---

**Built for AlgoFest Hackathon 2026.** *Bringing institutional market microstructure analysis to prediction markets.*
