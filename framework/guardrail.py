# framework/guardrail.py
# Layer 3A: Real-time Guardrail
# Reactive: Triggers emergency intervention (hard CPU cap) if CPU > 80% OR RAM > 90%
# in at least 3 of the last 5 samples.

from collections import defaultdict
from .config import (
    GUARDRAIL_CPU_THRESHOLD,
    GUARDRAIL_RAM_THRESHOLD,
    GUARDRAIL_WINDOW,
    GUARDRAIL_TRIGGER_COUNT,
)

class Guardrail:
    def __init__(self):
        # container_name -> list of booleans (True if overloaded)
        self._history: dict = defaultdict(list)

    def update(self, container_name: str, cpu: float, mem: float) -> bool:
        """
        Update rolling boolean evaluation array.
        Returns True if condition is met.
        """
        history = self._history[container_name]
        is_over = (cpu > GUARDRAIL_CPU_THRESHOLD) or (mem > GUARDRAIL_RAM_THRESHOLD)
        history.append(is_over)

        if len(history) > GUARDRAIL_WINDOW:
            history.pop(0)

        trigger_count = sum(1 for over in history if over)
        return trigger_count >= GUARDRAIL_TRIGGER_COUNT

    def reset(self, container_name: str):
        self._history.pop(container_name, None)