# ToxFlow — Polymarket Orderflow Toxicity Engine

> **Ordeflow 001 Hackathon Submission**
> A novel application of Volume-Synchronized Probability of Informed Trading (VPIN) to prediction market microstructure, augmented with Synthesis AI probabilistic forecasts.

## 🧠 Core Thesis

Prediction markets exhibit measurable **orderflow toxicity** — periods when informed traders (wallets with historically accurate resolution timing) cluster their activity. By measuring this toxicity in real-time using VPIN adapted for binary outcome markets, we can:

1. **Detect** when smart money is entering a market
2. **Quantify** the direction and confidence of informed flow
3. **Overlay** Synthesis AI probabilistic forecasts to confirm/reject the signal
4. **Execute** trades when toxicity + AI consensus align

This creates a **composite edge** that neither signal provides alone.

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ToxFlow Engine                           │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ Data Ingestor│──▶│ VPIN Engine  │──▶│ Signal Compositor  │  │
│  │ (Polymarket  │   │ (Volume-Clock│   │ (Toxicity + Synth) │  │
│  │  CLOB + WS)  │   │  Bucketing)  │   │                    │  │
│  └──────────────┘   └──────────────┘   └────────┬───────────┘  │
│         │                                        │              │
│         │           ┌──────────────┐             │              │
│         └──────────▶│Wallet Tracker│─────────────┘              │
│                     │(Smart Money  │                            │
│                     │ Clustering)  │             │              │
│                     └──────────────┘             ▼              │
│                                        ┌────────────────────┐  │
│  ┌──────────────┐                      │ Execution / Paper  │  │
│  │Synthesis API │─────────────────────▶│ Trade Engine       │  │
│  │(AI Forecasts)│                      └────────────────────┘  │
│  └──────────────┘                                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Backtesting & Performance Engine              │  │
│  │  • Historical VPIN computation                            │  │
│  │  • Walk-forward simulation                                │  │
│  │  • Sharpe, max drawdown, win rate, P&L curves             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 🔬 What is VPIN?

**Volume-Synchronized Probability of Informed Trading** was introduced by Easley, López de Prado, and O'Hara (2012) as a real-time measure of order flow toxicity in equity markets. We adapt it for prediction markets:

1. **Volume Bucketing**: Instead of time bars, we bucket trades by volume (e.g., every $500 of notional). This normalizes for activity bursts.
2. **Trade Classification**: Each bucket's buy/sell volume is classified using tick rule (price movement direction) since Polymarket's CLOB doesn't tag aggressor side.
3. **VPIN Calculation**: Over a rolling window of N buckets:

   ```
   VPIN = (1/N) × Σ |V_buy(i) - V_sell(i)| / V_total(i)
   ```

   High VPIN = one side is aggressively consuming liquidity = informed traders are active.

4. **Directional VPIN**: We extend standard VPIN with a signed variant that reveals *which side* (YES/NO) the informed flow favors.

## 🤖 Synthesis Integration

[Synthesis](https://synthesis.trade) provides AI-powered probabilistic forecasts for prediction markets. We query Synthesis data to:

- Get AI-estimated "fair value" probability for each market
- Compare against Polymarket's current implied probability
- When **VPIN spike direction aligns with Synthesis edge direction**, confidence is maximized

**Composite Signal** = `toxicity_score × direction_agreement × synthesis_edge_magnitude`

## 📊 Measurable Output

- **Backtest P&L curves** with transaction costs
- **VPIN vs. market resolution correlation** (does high toxicity predict outcomes?)
- **Signal accuracy**: win rate, profit factor, Sharpe ratio
- **Wallet clustering accuracy**: do identified "smart wallets" outperform?

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USERNAME/toxflow.git
cd toxflow
pip install -r requirements.txt

# Run backtest on historical data
python -m scripts.run_backtest

# Run live paper trading
python -m scripts.run_live --mode paper

# Launch dashboard
python -m dashboard.app
```

## 📁 Project Structure

```
toxflow/
├── core/
│   ├── vpin.py              # VPIN engine (volume bucketing + calculation)
│   ├── wallet_tracker.py     # Smart money wallet clustering
│   ├── signal_compositor.py  # Combines VPIN + Synthesis into trade signals
│   └── types.py              # Shared data types
├── data/
│   ├── polymarket_client.py  # Polymarket CLOB API + WebSocket client
│   ├── synthesis_client.py   # Synthesis API integration
│   └── historical.py         # Historical data fetcher + cache
├── strategies/
│   ├── toxicity_momentum.py  # Primary strategy: trade VPIN spikes
│   └── base.py               # Strategy base class
├── backtesting/
│   ├── engine.py             # Walk-forward backtesting engine
│   ├── metrics.py            # Performance metrics (Sharpe, drawdown, etc.)
│   └── report.py             # Generate backtest reports
├── dashboard/
│   └── app.py                # Real-time monitoring dashboard
├── scripts/
│   ├── run_backtest.py       # Entry point: run backtest
│   ├── run_live.py           # Entry point: live/paper trading
│   └── fetch_history.py      # Fetch and cache historical data
├── tests/
│   └── test_vpin.py          # Unit tests
├── requirements.txt
└── README.md
```

## 📚 References

- Easley, D., López de Prado, M., & O'Hara, M. (2012). "Flow Toxicity and Liquidity in a High-Frequency World." *Review of Financial Studies*.
- Easley, D., López de Prado, M., & O'Hara, M. (2011). "The Microstructure of the Flash Crash."

## License

MIT
