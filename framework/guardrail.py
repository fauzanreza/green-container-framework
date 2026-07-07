# framework/guardrail.py
# Layer 3A: Real-time Guardrail
# Reactive: Triggers emergency intervention (hard CPU cap) if CPU > 80% OR RAM > 90%
# in at least 3 of the last 5 samples.
#
# Hardening: EMA pre-warning — when EMA prediction approaches the threshold,
# the effective threshold is lowered to trigger earlier (PRD §4.1 Layer 3C).

from collections import defaultdict
from .config import (
    GUARDRAIL_CPU_THRESHOLD,
    GUARDRAIL_RAM_THRESHOLD,
    GUARDRAIL_WINDOW,
    GUARDRAIL_TRIGGER_COUNT,
    PRE_WARNING_MARGIN,
)

class Guardrail:
    def __init__(self):
        # container_name -> list of booleans (True if overloaded)
        self._history: dict = defaultdict(list)

    def update(self, container_name: str, cpu: float, mem: float,
               ema_pred: float = None) -> bool:
        """
        Update rolling boolean evaluation array.
        Returns True if condition is met.

        If ema_pred is provided (full_hecf mode), uses EMA-adjusted threshold
        for earlier detection when the trend is rising toward the guardrail.
        """
        cpu_thresh = self._get_effective_cpu_threshold(ema_pred)

        history = self._history[container_name]
        is_over = (cpu > cpu_thresh) or (mem > GUARDRAIL_RAM_THRESHOLD)
        history.append(is_over)

        if len(history) > GUARDRAIL_WINDOW:
            history.pop(0)

        trigger_count = sum(1 for over in history if over)
        return trigger_count >= GUARDRAIL_TRIGGER_COUNT

    def _get_effective_cpu_threshold(self, ema_pred: float = None) -> float:
        """
        When EMA prediction is within PRE_WARNING_MARGIN of the CPU threshold,
        lower the effective threshold to provide early readiness.

        PRD §4.1 Layer 3C: "fine-tune Guardrail threshold sensitivity ahead of time
        — not applied directly as a shaping input."

        This gives the system ~1-2 samples of early warning before an actual spike
        crosses the hard threshold.
        """
        if ema_pred is None:
            return GUARDRAIL_CPU_THRESHOLD

        warning_zone = GUARDRAIL_CPU_THRESHOLD - PRE_WARNING_MARGIN
        if ema_pred >= warning_zone:
            return warning_zone

        return GUARDRAIL_CPU_THRESHOLD

    def reset(self, container_name: str):
        self._history.pop(container_name, None)

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._history if name not in active_containers]
        for name in dead:
            del self._history[name]