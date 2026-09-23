# framework/guardrail.py
# Layer 3A: Real-time Guardrail
# Reactive: Triggers emergency intervention (hard CPU cap) if CPU > 80% OR RAM > 90%
# in at least 3 of the last 5 samples.
#
# Hardening:
#   - EMA pre-warning — when EMA prediction approaches the threshold,
#     the effective threshold is lowered to trigger earlier (PRD §4.1 Layer 3C).
#   - Derivative filter — when d(EMA)/dt exceeds threshold AND EMA > 60%,
#     trigger proactive throttling BEFORE CPU hits 80% (B4 optimization).

import os
import logging
from collections import defaultdict
from .config import (
    GUARDRAIL_CPU_THRESHOLD,
    GUARDRAIL_RAM_THRESHOLD,
    GUARDRAIL_WINDOW,
    GUARDRAIL_TRIGGER_COUNT,
    PRE_WARNING_MARGIN,
    PSI_ENABLED,
    PSI_SOME_AVG10_THRESHOLD,
)

logger = logging.getLogger("hecf.guardrail")

# Derivative filter thresholds (B4 optimization)
# d(EMA)/dt > this value triggers proactive intervention
_DERIVATIVE_THRESHOLD = 15.0   # 15% EMA rise per sample = aggressive ramp
# EMA must be above this baseline before derivative triggers (avoid false positives on low-CPU noise)
_DERIVATIVE_EMA_FLOOR = 60.0


class Guardrail:
    def __init__(self):
        # container_name -> list of booleans (True if overloaded)
        self._history: dict = defaultdict(list)
        self._psi_elevated: dict = {}  # container_name -> bool
        self._derivative_triggered: dict = {}  # container_name -> bool

    def update(self, container_name: str, cpu: float, mem: float,
               ema_pred: float = None, ema_derivative: float = None,
               cgroup_path: str = None) -> bool:
        """
        Update rolling boolean evaluation array.
        Returns True if condition is met.

        If ema_pred is provided (full_hecf mode), uses EMA-adjusted threshold
        for earlier detection when the trend is rising toward the guardrail.

        If ema_derivative is provided (B4), triggers proactive throttling when
        the rate of change indicates imminent threshold breach.
        """
        cpu_thresh = self._get_effective_cpu_threshold(ema_pred)

        # === Derivative Filter (B4) ===
        # Pre-emptive trigger: if EMA is rising fast AND already above 60%,
        # consider it overloaded BEFORE hitting 80%
        derivative_triggered = False
        if ema_derivative is not None and ema_pred is not None:
            if ema_derivative > _DERIVATIVE_THRESHOLD and ema_pred > _DERIVATIVE_EMA_FLOOR:
                derivative_triggered = True
                logger.info(
                    "DERIVATIVE pre-trigger for %s (d_ema=%.1f > %.1f, ema=%.1f > %.1f)",
                    container_name, ema_derivative, _DERIVATIVE_THRESHOLD,
                    ema_pred, _DERIVATIVE_EMA_FLOOR
                )
        self._derivative_triggered[container_name] = derivative_triggered

        history = self._history[container_name]
        is_over = (cpu > cpu_thresh) or (mem > GUARDRAIL_RAM_THRESHOLD) or derivative_triggered
        history.append(is_over)

        if len(history) > GUARDRAIL_WINDOW:
            history.pop(0)

        trigger_count = sum(1 for over in history if over)
        triggered = trigger_count >= GUARDRAIL_TRIGGER_COUNT

        # === PSI Internal Signal (Gap #10) ===
        psi_elevated = False
        if triggered and PSI_ENABLED and cgroup_path:
            psi_val = self._read_psi(cgroup_path)
            if psi_val is not None and psi_val > PSI_SOME_AVG10_THRESHOLD:
                psi_elevated = True
                logger.info(
                    "GUARDRAIL+PSI for %s (psi_some_avg10=%.1f > %.1f)",
                    container_name, psi_val, PSI_SOME_AVG10_THRESHOLD
                )

        if triggered:
            self._psi_elevated[container_name] = psi_elevated

        return triggered

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
        self._psi_elevated.pop(container_name, None)
        self._derivative_triggered.pop(container_name, None)

    def is_psi_elevated(self, container_name: str) -> bool:
        """Check if last guardrail trigger was PSI-elevated."""
        return self._psi_elevated.get(container_name, False)

    def is_derivative_triggered(self, container_name: str) -> bool:
        """Check if the derivative filter contributed to the last evaluation."""
        return self._derivative_triggered.get(container_name, False)

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._history if name not in active_containers]
        for name in dead:
            del self._history[name]
            self._psi_elevated.pop(name, None)
            self._derivative_triggered.pop(name, None)

    @staticmethod
    def _read_psi(cgroup_path: str) -> float:
        """Read cpu.pressure some avg10 value. Returns None if unavailable."""
        psi_path = os.path.join(cgroup_path, "cpu.pressure")
        try:
            with open(psi_path) as f:
                for line in f:
                    if line.startswith("some"):
                        # Format: "some avg10=X.XX avg60=... avg300=... total=..."
                        for part in line.split():
                            if part.startswith("avg10="):
                                return float(part.split("=")[1])
        except (OSError, ValueError):
            pass
        return None