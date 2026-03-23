"""
Signal Compositor — Combines VPIN Toxicity + Synthesis AI Forecasts

The core innovation: neither VPIN nor Synthesis alone provides a reliable
trading signal. But when both agree (informed flow + AI forecast point
the same direction), the composite signal is significantly stronger.

Composite Signal Formula:
    signal = toxicity_weight × vpin_z_score × direction_agreement × synth_edge
    
    where:
    - toxicity_weight: sigmoid(z_score - threshold) → 0 to 1
    - direction_agreement: 1 if VPIN direction matches Synthesis edge, -0.5 if not
    - synth_edge: |ai_prob - market_prob| (magnitude of Synthesis disagreement)
"""

import numpy as np
from typing import Optional
from toxflow.core.types import (
    VPINReading, SynthesisSignal, CompositeSignal, Outcome
)
from toxflow.core.vpin import VPINEngine


class SignalCompositor:
    """
    Combines VPIN toxicity readings with Synthesis AI forecasts
    to generate composite trading signals.
    """

    def __init__(
        self,
        vpin_z_threshold: float = 0.5,        # min z-score to consider signal
        min_synthesis_edge: float = 0.03,      # min 3% edge from Synthesis
        agreement_bonus: float = 2.0,          # multiplier when signals agree
        disagreement_penalty: float = 0.3,     # multiplier when signals disagree
        min_composite_strength: float = 0.15,  # min strength to trigger trade
        max_position_pct: float = 0.10,        # max 10% of capital per trade
        base_position_pct: float = 0.02,       # base 2% position size
    ):
        self.vpin_z_threshold = vpin_z_threshold
        self.min_synthesis_edge = min_synthesis_edge
        self.agreement_bonus = agreement_bonus
        self.disagreement_penalty = disagreement_penalty
        self.min_composite_strength = min_composite_strength
        self.max_position_pct = max_position_pct
        self.base_position_pct = base_position_pct

    def generate_signal(
        self,
        vpin_reading: VPINReading,
        vpin_engine: VPINEngine,
        synthesis_signal: Optional[SynthesisSignal] = None,
        market_id: str = "",
        capital: float = 10000.0,
    ) -> CompositeSignal:
        """
        Generate a composite trading signal from VPIN and Synthesis data.
        """
        z_score = vpin_engine.get_z_score(vpin_reading)
        
        # Toxicity component: sigmoid activation above threshold
        toxicity_score = self._sigmoid(z_score - self.vpin_z_threshold, k=2.0)
        
        # Direction from VPIN: positive d_vpin → informed flow buying YES
        vpin_direction = np.sign(vpin_reading.directional_vpin)
        vpin_direction_magnitude = abs(vpin_reading.directional_vpin)
        
        # Synthesis component
        synth_edge = 0.0
        synth_direction = 0.0
        direction_agreement = 1.0
        
        if synthesis_signal is not None:
            synth_edge = abs(synthesis_signal.edge)
            synth_direction = np.sign(synthesis_signal.edge)
            
            # Check agreement
            if vpin_direction != 0 and synth_direction != 0:
                if vpin_direction == synth_direction:
                    direction_agreement = self.agreement_bonus
                else:
                    direction_agreement = self.disagreement_penalty
        
        # Composite strength — additive model
        # Each component contributes independently, then scaled by agreement
        if synthesis_signal is not None:
            # Toxicity (0-1) contributes 50%, direction clarity 25%, synth edge 25%
            raw_strength = (
                0.50 * toxicity_score +
                0.25 * vpin_direction_magnitude +
                0.25 * min(synth_edge * 5.0, 1.0)  # scale 20% edge → 1.0
            )
            composite_strength = raw_strength * direction_agreement
            # Overall direction: weighted combination
            direction = (
                0.6 * vpin_direction * vpin_direction_magnitude +
                0.4 * synth_direction * min(synth_edge * 5.0, 1.0)
            )
        else:
            # VPIN only (no Synthesis data available)
            composite_strength = (
                0.60 * toxicity_score +
                0.40 * vpin_direction_magnitude
            )
            direction = vpin_direction * vpin_direction_magnitude
        
        # Clamp
        composite_strength = float(np.clip(composite_strength, 0, 1))
        direction = float(np.clip(direction, -1, 1))
        
        # Trade decision
        should_trade = composite_strength >= self.min_composite_strength
        recommended_side = None
        recommended_size = 0.0
        
        if should_trade:
            recommended_side = Outcome.YES if direction > 0 else Outcome.NO
            # Position sizing: scale by signal strength
            size_pct = self.base_position_pct + (
                (self.max_position_pct - self.base_position_pct) *
                composite_strength
            )
            recommended_size = capital * size_pct
        
        return CompositeSignal(
            timestamp=vpin_reading.timestamp,
            market_id=market_id,
            vpin=vpin_reading,
            synthesis=synthesis_signal,
            toxicity_score=toxicity_score,
            direction=direction,
            composite_strength=composite_strength,
            should_trade=should_trade,
            recommended_side=recommended_side,
            recommended_size=recommended_size,
        )

    @staticmethod
    def _sigmoid(x: float, k: float = 1.0) -> float:
        """Sigmoid activation function."""
        return 1.0 / (1.0 + np.exp(-k * x))
