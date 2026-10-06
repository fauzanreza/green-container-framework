# framework/predictor.py
# Layer 3C: Lightweight Prediction Engine — fixed-alpha EMA (alpha = EMA_ALPHA = 0.2)
#
# O(1) time and memory per update.
# Also exposes EMA derivative (d_ema/dt) for Guardrail pre-emptive triggering.

import numpy as np
from collections import defaultdict
from .config import EMA_ALPHA


class EMAPredictor:
    def __init__(self):
        # container_name -> previous EMA prediction Y(t-1)
        self._predictions: dict = defaultdict(float)
        # container_name -> previous EMA value (for derivative computation)
        self._prev_ema: dict = {}

    def update(self, container_name: str, cpu: float) -> float:
        """
        Update EMA with new CPU value.
        Formula: Y(t) = alpha * cpu + (1 - alpha) * Y(t-1)
        """
        if container_name not in self._predictions:
            # Initialize with current CPU for the first sample
            self._predictions[container_name] = cpu
            return round(cpu, 2)

        # Store previous EMA for derivative computation
        y_prev = self._predictions[container_name]
        self._prev_ema[container_name] = y_prev

        # EMA update with fixed alpha
        y_new = EMA_ALPHA * cpu + (1 - EMA_ALPHA) * y_prev
        self._predictions[container_name] = y_new

        return round(y_new, 2)

    def get_prediction(self, container_name: str) -> float:
        """Return the last EMA prediction."""
        return round(self._predictions[container_name], 2)

    def get_alpha(self, container_name: str) -> float:
        """Return current adaptive alpha for the container."""
        return EMA_ALPHA

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
            self._prev_ema.pop(name, None)