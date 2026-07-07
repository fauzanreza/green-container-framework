# framework/tier_detector.py
# Layer 3B: Tier Detection Engine
# Sliding window of the last 120 samples. Computes spike_ratio = P95 / P50.
# Tier mapping:
#   Tier 1 (Aggressive): spike_ratio > 2.0
#   Tier 2 (Balanced):   1.5 <= spike_ratio <= 2.0
#   Tier 3 (Soft):       spike_ratio < 1.5

import numpy as np
from collections import defaultdict
from .config import (
    TIER_WINDOW,
    COLD_START_SAMPLES,
    TIER1_AGGRESSIVE_RATIO,
    TIER2_BALANCED_RATIO,
)

class TierDetector:
    def __init__(self):
        # container_name -> list of cpu_percent values (sliding window)
        self._windows: dict = defaultdict(list)

    def add_sample(self, container_name: str, cpu: float):
        """Tambahkan sampel CPU ke sliding window container."""
        window = self._windows[container_name]
        window.append(cpu)
        if len(window) > TIER_WINDOW:
            window.pop(0)

    def get_tier(self, container_name: str) -> int:
        """
        Hitung tier berdasarkan spike_ratio = p95 / p50.
        Jika data belum cukup (< COLD_START_SAMPLES), return Tier 2 (Balanced) sebagai fallback.
        Returns:
            1 for Aggressive
            2 for Balanced
            3 for Soft
        """
        window = self._windows[container_name]

        if len(window) < COLD_START_SAMPLES:
            return 2  # Fallback Tier 2 (Balanced)

        p50 = float(np.percentile(window, 50))
        p95 = float(np.percentile(window, 95))

        # Guard: hindari division by zero saat idle
        if p50 <= 0:
            return 3 # Soft

        spike_ratio = p95 / p50

        if spike_ratio > TIER1_AGGRESSIVE_RATIO:
            return 1
        elif spike_ratio >= TIER2_BALANCED_RATIO:
            return 2
        else:
            return 3

    def get_stats(self, container_name: str) -> dict:
        """Return statistik window untuk logging/reporting."""
        window = self._windows[container_name]
        if len(window) < 2:
            return {"p50": 0.0, "p95": 0.0, "spike_ratio": 0.0, "samples": len(window)}
        p50 = float(np.percentile(window, 50))
        p95 = float(np.percentile(window, 95))
        ratio = (p95 / p50) if p50 > 0 else 0.0
        return {
            "p50":         round(p50, 2),
            "p95":         round(p95, 2),
            "spike_ratio": round(ratio, 3),
            "samples":     len(window),
        }

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._windows if name not in active_containers]
        for name in dead:
            del self._windows[name]