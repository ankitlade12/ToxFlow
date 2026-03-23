# ToxFlow — Getting Started Guide

## Ordeflow 001 Hackathon Submission

**Deadline:** March 24, 2026 @ 6:00am EET
**Track:** AI-Augmented Systems + Quantitative Trading (dual-track)
**Prizes:** 1st Place ($250) + Synthesis Prize ($200) = $450 potential

---

## What You're Building

**ToxFlow** is a Polymarket orderflow toxicity engine that detects when informed traders ("smart money") are entering a market, then trades in their direction. It uses two novel components nobody else has built:

1. **VPIN (Volume-Synchronized Probability of Informed Trading)** — a quant finance metric from Easley, López de Prado & O'Hara (2012) adapted for prediction markets. It measures how "toxic" the current order flow is by bucketing trades by volume instead of time, then computing buy/sell imbalance across a rolling window.

2. **Synthesis AI Overlay** — Synthesis.trade's probabilistic forecasts are compared against Polymarket's live prices. When VPIN detects a toxicity spike AND Synthesis agrees on the direction, the composite signal fires a trade.

**Why this wins:** It's academically grounded (citable paper), technically deep (market microstructure), and nobody on GitHub has applied VPIN to prediction markets. The judges score on Technical Depth, Strategy Logic, Measurable Output, and Implementation Quality — this nails all four.

---

## Step 1: Set Up Your Local Environment

```bash
# Clone/create the project
mkdir toxflow && cd toxflow

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install numpy httpx
```

### Project Structure

Copy the following files from the scaffold into your project:

```
toxflow/
├── core/
│   ├── __init__.py           # empty
│   ├── types.py              # shared data types
│   ├── vpin.py               # VPIN engine (the core innovation)
│   ├── wallet_tracker.py     # smart money wallet clustering
│   └── signal_compositor.py  # combines VPIN + Synthesis signals
├── data/
│   ├── __init__.py
│   ├── polymarket_client.py  # Polymarket CLOB API client
│   └── synthesis_client.py   # Synthesis API client (live + sim)
├── strategies/
│   ├── __init__.py
│   └── toxicity_momentum.py  # primary trading strategy
├── backtesting/
│   ├── __init__.py
│   └── engine.py             # Monte Carlo backtesting engine
├── scripts/
│   ├── __init__.py
│   └── run_backtest.py       # CLI entry point
├── tests/
│   ├── __init__.py
│   └── test_vpin.py          # unit tests (6 tests)
├── dashboard/
│   └── __init__.py
├── requirements.txt
└── README.md
```

---

## Step 2: Verify Everything Works

```bash
# Run unit tests (should see 6/6 pass)
python tests/test_vpin.py

# Run a quick backtest
python scripts/run_backtest.py --mode single --duration 3600

# Run full Monte Carlo (200 sims, takes ~15 seconds)
python scripts/run_backtest.py --mode monte_carlo --simulations 200 --duration 7200
```

Expected output from tests:
```
✓ test_bucket_completion passed
✓ test_vpin_symmetric_flow passed (avg VPIN=0.200)
✓ test_vpin_informed_burst passed (VPIN=1.000, D-VPIN=1.000)
✓ test_spike_detection passed
✓ test_directional_vpin_sell_pressure passed (D-VPIN=-1.000)
✓ test_reset passed

✅ All tests passed!
```

---

## Step 3: Understand the Core Algorithm

### How VPIN Works (the 60-second version)

Traditional markets measure toxicity in time intervals. We use **volume buckets** instead — every $100 of traded volume becomes one bucket. This is critical for prediction markets where activity is bursty.

```
For each volume bucket:
  1. Classify trades as buy or sell (using tick rule)
  2. Compute imbalance = |buy_volume - sell_volume| / total_volume

VPIN = average imbalance over last N buckets

High VPIN (>0.6) → one side is aggressively consuming liquidity
                  → informed traders are probably active
                  → follow them
```

### The Directional Extension (our innovation)

Standard VPIN only measures *magnitude* of imbalance. We added **Directional VPIN**:

```
D-VPIN = average (buy_volume - sell_volume) / total_volume

Positive D-VPIN → informed flow is buying YES tokens
Negative D-VPIN → informed flow is buying NO tokens
```

This tells us not just *that* smart money is active, but *which side* they're on.

### Composite Signal with Synthesis

```
Composite = 0.50 × toxicity_score
          + 0.25 × vpin_direction_magnitude
          + 0.25 × synthesis_edge

If VPIN direction matches Synthesis edge direction → 2× multiplier
If they disagree → 0.3× multiplier (reduce confidence)

Trade when composite > 0.40
```

---

## Step 4: Key Parameters to Tune

These are in `strategies/toxicity_momentum.py` → `StrategyConfig`:

| Parameter | Default | What It Does | Tune Direction |
|---|---|---|---|
| `bucket_volume` | 100 | USDC per volume bucket | Lower = more sensitive to small bursts |
| `vpin_window` | 30 | Buckets in rolling VPIN window | Higher = smoother, less noise |
| `vpin_z_threshold` | 0.5 | Min z-score for signal activation | Higher = fewer but stronger signals |
| `min_composite_strength` | 0.40 | Min strength to trigger trade | Higher = more selective |
| `profit_target` | 0.12 | Take profit at 12% gain | Must exceed 2× fees |
| `stop_loss` | 0.04 | Cut losses at 4% | Tight stops reduce drawdown |
| `taker_fee_bps` | 100 | 1% taker fee (Polymarket 2026) | Matches current fee structure |

**Tuning tip:** Run Monte Carlo, change one param, run again. Compare win rate and profit factor.

```bash
# Example: test higher selectivity
python scripts/run_backtest.py --mode monte_carlo --simulations 100 --z-threshold 0.8

# Example: smaller buckets for more sensitivity
python scripts/run_backtest.py --mode monte_carlo --simulations 100 --bucket-volume 50
```

---

## Step 5: What to Build Next (Prioritized)

### Priority 1: Dashboard (HIGH IMPACT for judges)

Build a React or HTML dashboard that shows:
- **VPIN time series** overlaid on market price (the money chart)
- **Signal heatmap** — when composite signals fire, what strength
- **Cumulative P&L curve** from backtest
- **Wallet clustering scatter plot** — accuracy vs. trade count
- **Monte Carlo distribution** — histogram of P&L across simulations

This is what the judges will see in your demo video. Make it look good.

### Priority 2: Live Polymarket Data

Wire up the real Polymarket CLOB WebSocket for a paper trading demo:

```python
# In data/polymarket_client.py — the client is already written
# You need to:
# 1. Get a Polymarket API key (polymarket.com/settings)
# 2. Connect to WebSocket for real-time trade feed
# 3. Feed trades into VPINEngine.process_trade()
# 4. Log signals to a file for the demo
```

### Priority 3: Synthesis Live Integration

If Synthesis has a public API, connect `data/synthesis_client.py` in live mode.
If not, the simulation mode is fine — just explain in your demo that the
architecture supports live Synthesis data and show the simulated results.

### Priority 4: Additional Tests

- Test wallet tracker with mock resolved markets
- Test signal compositor with known edge cases
- Integration test: full pipeline from trade → signal → position

---

## Step 6: Submission Checklist

The hackathon requires:

- [ ] **Public GitHub repository** — push all code
- [ ] **2–3 minute demo video** — see script below
- [ ] **Strategy logic explanation** — in README.md (already written)
- [ ] **Architecture diagram** — in README.md (already written)
- [ ] **Data sources** — Polymarket CLOB + Synthesis (documented)
- [ ] **Performance metrics** — backtest report output
- [ ] **Measurable output** — Monte Carlo P&L distribution

### Demo Video Script (2:30)

**[0:00–0:20] Hook**
"ToxFlow applies institutional quant finance — specifically VPIN from Easley, López de Prado and O'Hara — to Polymarket prediction markets. It detects when informed traders are entering a market and trades in their direction, confirmed by Synthesis AI forecasts."

**[0:20–0:50] Architecture (show diagram)**
"The system has four components: a VPIN engine that buckets trades by volume and measures order flow toxicity, a wallet tracker that clusters wallets by historical accuracy, a Synthesis overlay that provides AI probability estimates, and a signal compositor that combines all three into a trade decision."

**[0:50–1:30] How VPIN Works (show dashboard)**
"Here's VPIN in action on a synthetic Polymarket. Watch the blue line — that's VPIN. When it spikes, one side of the orderbook is being aggressively consumed by informed flow. The green line is Directional VPIN — it tells us whether smart money is buying YES or NO. When both spike together, that's our signal."

**[1:30–2:00] Results (show Monte Carlo)**
"We ran 200 Monte Carlo simulations. The strategy shows [X]% win rate with a profit factor of [Y]. The key insight: VPIN alone generates signals, but combining it with Synthesis AI forecasts — requiring agreement — filters out false positives and improves the profit factor by [Z]%."

**[2:00–2:30] Why This Is Novel**
"Nobody has applied VPIN to prediction markets before. Every Polymarket bot on GitHub is doing latency arbitrage, copy trading, or simple sentiment analysis. ToxFlow operates at the market microstructure level — measuring information asymmetry in real-time. This is how institutional market makers think about flow. We brought it to prediction markets."

---

## Step 7: GitHub Setup

```bash
# Initialize git
cd toxflow
git init
git add .
git commit -m "ToxFlow: VPIN-based orderflow toxicity engine for Polymarket"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/toxflow.git
git branch -M main
git push -u origin main
```

### Recommended `.gitignore`

```
__pycache__/
*.pyc
venv/
.env
*.egg-info/
dist/
build/
.DS_Store
```

---

## Quick Reference: Key Files to Edit

| I want to... | Edit this file |
|---|---|
| Change VPIN parameters | `core/vpin.py` → `__init__` method |
| Change trade entry/exit rules | `strategies/toxicity_momentum.py` → `StrategyConfig` |
| Change composite signal formula | `core/signal_compositor.py` → `generate_signal` |
| Add new data sources | `data/` directory |
| Change synthetic market behavior | `backtesting/engine.py` → `generate_synthetic_market` |
| Add wallet classification rules | `core/wallet_tracker.py` → `get_smart_money_weight` |

---

## References to Cite in Your Submission

1. Easley, D., López de Prado, M., & O'Hara, M. (2012). "Flow Toxicity and Liquidity in a High-Frequency World." *Review of Financial Studies*, 25(5), 1457–1493.

2. Easley, D., López de Prado, M., & O'Hara, M. (2011). "The Microstructure of the Flash Crash: Flow Toxicity, Liquidity Crashes, and the Probability of Informed Trading." *Journal of Portfolio Management*, 37(2), 118–128.

3. Synthesis Trade — https://synthesis.trade

---

**You have 48 hours. Ship it. 🚀**
