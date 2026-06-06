# framework/tier_detector.py
# Layer 3B: Tier Detection Engine
# Ref: Hossain et al. (2022) — online profiling dengan sliding window
# Ref: Dogani et al. (2023) — klasifikasi workload berbasis karakteristik resource
#
# Menggunakan rasio p95/p50 (spike_ratio) dari sliding window CPU utilization
# untuk mengklasifikasikan host ke dalam 3 tier:
#   Tier 1 (Aggressive): spike_ratio > 2.0 → workload sangat spike
#   Tier 2 (Balanced):   spike_ratio 1.5–2.0 → workload moderat
#   Tier 3 (Soft):       spike_ratio < 1.5 → workload stabil

import numpy as np
from collections import defaultdict
from .config import (
    SLIDING_WINDOW_SIZE,
    TIER_MIN_SAMPLES,
    TIER_AGGRESSIVE_RATIO,
    TIER_BALANCED_RATIO,
)

# Tier constants
TIER_AGGRESSIVE = "aggressive"
TIER_BALANCED   = "balanced"
TIER_SOFT       = "soft"


class TierDetector:
    def __init__(self):
        # container_name → list of cpu_percent values (sliding window)
        self._windows: dict = defaultdict(list)

    def add_sample(self, container_name: str, cpu: float):
        """Tambahkan sampel CPU ke sliding window container."""
        window = self._windows[container_name]
        window.append(cpu)
        if len(window) > SLIDING_WINDOW_SIZE:
            window.pop(0)

    def get_tier(self, container_name: str) -> str:
        """
        Hitung tier berdasarkan spike_ratio = p95 / p50.
        Jika data belum cukup (< TIER_MIN_SAMPLES), return TIER_BALANCED sebagai fallback.
        Ini adalah Layer 1 Fallback Policy sebelum sliding window terisi.
        """
        window = self._windows[container_name]

        if len(window) < TIER_MIN_SAMPLES:
            return TIER_BALANCED  # Fallback Tier 2 (aman)

        p50 = float(np.percentile(window, 50))
        p95 = float(np.percentile(window, 95))

        # Guard: hindari division by zero saat idle
        if p50 <= 0:
            return TIER_SOFT

        spike_ratio = p95 / p50

        if spike_ratio > TIER_AGGRESSIVE_RATIO:
            return TIER_AGGRESSIVE
        elif spike_ratio >= TIER_BALANCED_RATIO:
            return TIER_BALANCED
        else:
            return TIER_SOFT

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