# framework/predictor.py
# Layer 3C: Lightweight Prediction Engine — EMA
# Fixed-alpha (0.2) EMA, O(1) memory. 
# Used to fine-tune Guardrail threshold sensitivity ahead of time.

from collections import defaultdict
from .config import EMA_ALPHA


class EMAPredictor:
    def __init__(self):
        # container_name -> previous EMA prediction Y(t-1)
        self._predictions: dict = defaultdict(float)

    def update(self, container_name: str, cpu: float) -> float:
        """
        Update EMA with new CPU value. O(1) memory, only needs Y(t-1).
        Formula: Y(t) = alpha * cpu + (1 - alpha) * Y(t-1)
        """
        if container_name not in self._predictions:
            # Initialize with current CPU for the first sample
            self._predictions[container_name] = cpu
            return round(cpu, 2)
            
        y_prev = self._predictions[container_name]
        y_new = EMA_ALPHA * cpu + (1 - EMA_ALPHA) * y_prev
        self._predictions[container_name] = y_new
        
        return round(y_new, 2)

    def get_prediction(self, container_name: str) -> float:
        """Return the last EMA prediction."""
        return round(self._predictions[container_name], 2)

    def get_alpha(self, container_name: str) -> float:
        """Return alpha (fixed for EMA)."""
        return EMA_ALPHA

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._predictions if name not in active_containers]
        for name in dead:
            del self._predictions[name]