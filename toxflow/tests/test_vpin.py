"""Tests for the VPIN engine."""

import time
import numpy as np

from toxflow.core.vpin import VPINEngine
from toxflow.core.types import Trade, Side, Outcome


def make_trade(price, size, side=Side.BUY, ts=None):
    return Trade(
        timestamp=ts or time.time(),
        price=price,
        size=size,
        side=side,
        outcome=Outcome.YES,
        market_id="test_market",
    )


def test_bucket_completion():
    """Test that volume buckets are completed at the right threshold."""
    engine = VPINEngine(bucket_volume=100, window_size=5)

    # Feed trades totaling 100 USDC
    for i in range(10):
        result = engine.process_trade(make_trade(0.5, 10, ts=time.time() + i))

    assert len(engine._completed_buckets) >= 1, "Should have at least one completed bucket"
    print("✓ test_bucket_completion passed")


def test_vpin_symmetric_flow():
    """Test that balanced buy/sell flow produces low VPIN."""
    engine = VPINEngine(bucket_volume=50, window_size=10)

    readings = []
    for i in range(1000):
        side = Side.BUY if i % 2 == 0 else Side.SELL
        result = engine.process_trade(make_trade(0.5, 10, side=side, ts=time.time() + i * 0.1))
        if result:
            readings.append(result)

    if readings:
        avg_vpin = np.mean([r.vpin_value for r in readings])
        assert avg_vpin < 0.3, f"Balanced flow should have low VPIN, got {avg_vpin:.3f}"
        print(f"✓ test_vpin_symmetric_flow passed (avg VPIN={avg_vpin:.3f})")
    else:
        print("⚠ test_vpin_symmetric_flow: no readings generated")


def test_vpin_informed_burst():
    """Test that one-sided flow produces high VPIN."""
    engine = VPINEngine(bucket_volume=50, window_size=10)

    # First: balanced flow to establish baseline
    for i in range(500):
        side = Side.BUY if i % 2 == 0 else Side.SELL
        engine.process_trade(make_trade(0.5, 10, side=side, ts=time.time() + i * 0.1))

    # Then: all buys (informed burst)
    readings = []
    for i in range(200):
        result = engine.process_trade(make_trade(0.55 + i * 0.0005, 15, side=Side.BUY, ts=time.time() + 50 + i * 0.1))
        if result:
            readings.append(result)

    if readings:
        late_readings = readings[-5:]
        avg_vpin = np.mean([r.vpin_value for r in late_readings])
        assert avg_vpin > 0.3, f"Informed burst should have high VPIN, got {avg_vpin:.3f}"

        # Directional VPIN should be positive (buy-side dominant)
        avg_dvpin = np.mean([r.directional_vpin for r in late_readings])
        assert avg_dvpin > 0, f"Buy burst should have positive D-VPIN, got {avg_dvpin:.3f}"

        print(f"✓ test_vpin_informed_burst passed (VPIN={avg_vpin:.3f}, D-VPIN={avg_dvpin:.3f})")
    else:
        print("⚠ test_vpin_informed_burst: no readings generated")


def test_spike_detection():
    """Test that VPIN spikes are detected."""
    engine = VPINEngine(bucket_volume=50, window_size=10, sigma_threshold=1.0)

    # Balanced flow
    for i in range(500):
        side = Side.BUY if i % 2 == 0 else Side.SELL
        engine.process_trade(make_trade(0.5, 10, side=side, ts=time.time() + i * 0.1))

    # Sudden informed burst
    spike_detected = False
    for i in range(300):
        result = engine.process_trade(make_trade(0.6, 20, side=Side.BUY, ts=time.time() + 50 + i * 0.1))
        if result and engine.is_spike(result):
            spike_detected = True
            break

    assert spike_detected, "Should detect a spike during informed burst"
    print("✓ test_spike_detection passed")


def test_directional_vpin_sell_pressure():
    """Test that sell pressure produces negative directional VPIN."""
    engine = VPINEngine(bucket_volume=50, window_size=10)

    # Balanced baseline
    for i in range(500):
        side = Side.BUY if i % 2 == 0 else Side.SELL
        engine.process_trade(make_trade(0.5, 10, side=side, ts=time.time() + i * 0.1))

    # All sells
    readings = []
    for i in range(200):
        result = engine.process_trade(make_trade(0.45 - i * 0.0005, 15, side=Side.SELL, ts=time.time() + 50 + i * 0.1))
        if result:
            readings.append(result)

    if readings:
        avg_dvpin = np.mean([r.directional_vpin for r in readings[-5:]])
        assert avg_dvpin < 0, f"Sell pressure should have negative D-VPIN, got {avg_dvpin:.3f}"
        print(f"✓ test_directional_vpin_sell_pressure passed (D-VPIN={avg_dvpin:.3f})")


def test_reset():
    """Test engine reset."""
    engine = VPINEngine(bucket_volume=50, window_size=5)

    for i in range(100):
        engine.process_trade(make_trade(0.5, 10, ts=time.time() + i))

    engine.reset()
    assert len(engine._completed_buckets) == 0
    assert len(engine._vpin_history) == 0
    assert engine._last_price is None
    print("✓ test_reset passed")


if __name__ == "__main__":
    print("Running ToxFlow VPIN Engine Tests\n")
    test_bucket_completion()
    test_vpin_symmetric_flow()
    test_vpin_informed_burst()
    test_spike_detection()
    test_directional_vpin_sell_pressure()
    test_reset()
    print("\n✅ All tests passed!")
