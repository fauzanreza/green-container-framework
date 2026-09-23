# framework/predictor.py
# Layer 3C: Lightweight Prediction Engine — Adaptive Alpha EMA
#
# Enhanced EMA with dynamic alpha based on CPU variance:
#   - High variance (spike detected) → alpha = 0.8 (fast response)
#   - Medium variance              → alpha = 0.4 (moderate tracking)
#   - Low variance (stable)        → alpha = 0.05 (noise suppression)
#
# O(1) memory per update. Maintains a small recent-samples buffer (10 values)
# for variance computation — total memory is O(N_containers × 10).
#
# Also exposes EMA derivative (d_ema/dt) for Guardrail pre-emptive triggering.

import numpy as np
from collections import defaultdict
from .config import EMA_ALPHA


# Variance thresholds for adaptive alpha
_VARIANCE_HIGH = 400.0    # sqrt(400)=20% CPU swing → spike detected
_VARIANCE_MEDIUM = 100.0  # sqrt(100)=10% CPU swing → moderate activity
_ALPHA_HIGH = 0.8         # Fast response during spikes
_ALPHA_MEDIUM = 0.4       # Moderate tracking
_ALPHA_LOW = 0.05         # Noise suppression during stability
_VARIANCE_WINDOW = 10     # Number of recent samples for variance computation


class EMAPredictor:
    def __init__(self):
        # container_name -> previous EMA prediction Y(t-1)
        self._predictions: dict = defaultdict(float)
        # container_name -> list of recent CPU samples (for variance computation)
        self._recent_samples: dict = defaultdict(list)
        # container_name -> current adaptive alpha
        self._alphas: dict = defaultdict(lambda: EMA_ALPHA)
        # container_name -> previous EMA value (for derivative computation)
        self._prev_ema: dict = {}

    def update(self, container_name: str, cpu: float) -> float:
        """
        Update EMA with new CPU value using adaptive alpha.
        Formula: Y(t) = alpha(t) * cpu + (1 - alpha(t)) * Y(t-1)

        Alpha is dynamically selected based on variance of recent samples:
        - High variance → alpha=0.8 (react fast to spikes)
        - Low variance  → alpha=0.05 (suppress noise)
        """
        # Compute adaptive alpha from recent variance
        alpha = self._compute_adaptive_alpha(container_name, cpu)
        self._alphas[container_name] = alpha

        if container_name not in self._predictions:
            # Initialize with current CPU for the first sample
            self._predictions[container_name] = cpu
            return round(cpu, 2)

        # Store previous EMA for derivative computation
        y_prev = self._predictions[container_name]
        self._prev_ema[container_name] = y_prev

        # EMA update with adaptive alpha
        y_new = alpha * cpu + (1 - alpha) * y_prev
        self._predictions[container_name] = y_new

        return round(y_new, 2)

    def _compute_adaptive_alpha(self, container_name: str, cpu: float) -> float:
        """
        Adaptive alpha based on variance of recent CPU samples.
        O(1) amortized: maintains a fixed-size sliding window.

        - Spike detected (variance > 400, ~20% CPU swing) → alpha = 0.8
        - Moderate activity (variance > 100)               → alpha = 0.4
        - Stable traffic (variance ≤ 100)                  → alpha = 0.05
        """
        history = self._recent_samples[container_name]
        history.append(cpu)
        if len(history) > _VARIANCE_WINDOW:
            history.pop(0)

        if len(history) < 3:
            return EMA_ALPHA  # default during warmup

        variance = float(np.var(history))
        if variance > _VARIANCE_HIGH:
            return _ALPHA_HIGH
        elif variance > _VARIANCE_MEDIUM:
            return _ALPHA_MEDIUM
        else:
            return _ALPHA_LOW

    def get_prediction(self, container_name: str) -> float:
        """Return the last EMA prediction."""
        return round(self._predictions[container_name], 2)

    def get_alpha(self, container_name: str) -> float:
        """Return current adaptive alpha for the container."""
        return self._alphas.get(container_name, EMA_ALPHA)

    def get_derivative(self, container_name: str) -> float:
        """
        Return the EMA derivative: d(EMA)/dt = EMA(t) - EMA(t-1).
        Positive = rising trend, negative = falling.
        Uses EMA-smoothed values (not raw CPU) for noise resistance.

        Returns 0.0 if insufficient data.
        """
        current = self._predictions.get(container_name)
        prev = self._prev_ema.get(container_name)
        if current is None or prev is None:
            return 0.0
        return round(current - prev, 2)

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._predictions if name not in active_containers]
        for name in dead:
            del self._predictions[name]
            self._recent_samples.pop(name, None)
            self._alphas.pop(name, None)
            self._prev_ema.pop(name, None)