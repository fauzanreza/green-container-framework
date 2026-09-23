# framework/tier_detector.py
# Layer 3B: Dual-Window Tier Detection Engine
#
# Two-window architecture for responsive spike detection:
#   Short Window (10 samples) — burst detection with fast-path escalation
#   Long Window  (60 samples) — baseline trend for stable tier classification
#
# Tier mapping:
#   Tier 1 (Aggressive): spike_ratio > 2.0
#   Tier 2 (Balanced):   1.5 <= spike_ratio <= 2.0
#   Tier 3 (Soft):       spike_ratio < 1.5
#
# Asymmetric Hysteresis:
#   Escalation (Soft→Aggressive):   1 sample  — react fast to threats
#   De-escalation (Aggressive→Soft): 5 samples — confirm stability before releasing

import numpy as np
from collections import defaultdict
from .config import (
    TIER_SHORT_WINDOW,
    TIER_LONG_WINDOW,
    COLD_START_SAMPLES,
    TIER1_AGGRESSIVE_RATIO,
    TIER2_BALANCED_RATIO,
    TIER_HYSTERESIS_ESCALATE,
    TIER_HYSTERESIS_DEESCALATE,
)


class TierDetector:
    def __init__(self):
        # Dual-window storage per container
        self._short_windows: dict = defaultdict(list)  # burst detection (10 samples)
        self._long_windows: dict = defaultdict(list)    # baseline trending (60 samples)
        # Hysteresis state: container_name -> {"current": int, "pending": int, "count": int}
        self._hysteresis: dict = {}

    def add_sample(self, container_name: str, cpu: float):
        """Tambahkan sampel CPU ke kedua sliding windows."""
        # Short window
        short = self._short_windows[container_name]
        short.append(cpu)
        if len(short) > TIER_SHORT_WINDOW:
            short.pop(0)

        # Long window
        long_ = self._long_windows[container_name]
        long_.append(cpu)
        if len(long_) > TIER_LONG_WINDOW:
            long_.pop(0)

    def get_tier(self, container_name: str) -> int:
        """
        Dual-window tier classification:
        1. Fast-path: if short window shows spike_ratio > 2.0, escalate to Tier 1
           immediately (skip hysteresis for escalation).
        2. Normal path: use long window for stable tier classification with
           asymmetric hysteresis (fast escalate, slow de-escalate).

        Returns:
            1 for Aggressive
            2 for Balanced
            3 for Soft
        """
        short = self._short_windows[container_name]
        long_ = self._long_windows[container_name]

        # Cold-start guard: need minimum samples before tier detection activates
        total_samples = len(long_)
        if total_samples < COLD_START_SAMPLES:
            return 2  # Fallback Tier 2 (Balanced)

        # === Fast-Path: Short Window Burst Detection ===
        # If short window has enough data and shows spike, escalate immediately
        if len(short) >= 5:
            p50_s = float(np.percentile(short, 50))
            p95_s = float(np.percentile(short, 95))
            if p50_s > 0:
                short_ratio = p95_s / p50_s
                if short_ratio > TIER1_AGGRESSIVE_RATIO:
                    # Immediate escalation — skip hysteresis for fast response
                    if container_name in self._hysteresis:
                        self._hysteresis[container_name]["current"] = 1
                        self._hysteresis[container_name]["pending"] = 1
                        self._hysteresis[container_name]["count"] = 0
                    else:
                        self._hysteresis[container_name] = {
                            "current": 1, "pending": 1, "count": 0
                        }
                    return 1  # Aggressive — fast-path

        # === Normal Path: Long Window Baseline Classification ===
        p50 = float(np.percentile(long_, 50))
        p95 = float(np.percentile(long_, 95))

        # Guard: hindari division by zero saat idle
        if p50 <= 0:
            raw_tier = 3  # Soft

        else:
            spike_ratio = p95 / p50

            if spike_ratio > TIER1_AGGRESSIVE_RATIO:
                raw_tier = 1
            elif spike_ratio >= TIER2_BALANCED_RATIO:
                raw_tier = 2
            else:
                raw_tier = 3

        # === Asymmetric Hysteresis ===
        # Escalation (tier going DOWN numerically = more aggressive): fast
        # De-escalation (tier going UP numerically = more relaxed): slow
        if container_name not in self._hysteresis:
            self._hysteresis[container_name] = {
                "current": raw_tier, "pending": raw_tier, "count": 0
            }
            return raw_tier

        state = self._hysteresis[container_name]
        if raw_tier == state["current"]:
            # Still at current tier — reset any pending transition
            state["pending"] = raw_tier
            state["count"] = 0
            return state["current"]

        # Determine direction and required hysteresis threshold
        is_escalation = raw_tier < state["current"]  # lower tier number = more aggressive
        threshold = TIER_HYSTERESIS_ESCALATE if is_escalation else TIER_HYSTERESIS_DEESCALATE

        if raw_tier == state["pending"]:
            # Same pending tier — increment counter
            state["count"] += 1
            if state["count"] >= threshold:
                state["current"] = raw_tier
                state["count"] = 0
                return raw_tier
            return state["current"]  # Hold previous tier
        else:
            # New different pending tier — start fresh count
            state["pending"] = raw_tier
            state["count"] = 1
            # Check if single sample is enough (for escalation with threshold=1)
            if 1 >= threshold:
                state["current"] = raw_tier
                state["count"] = 0
                return raw_tier
            return state["current"]  # Hold previous tier

    def get_stats(self, container_name: str) -> dict:
        """Return statistik dari kedua windows untuk logging/reporting."""
        short = self._short_windows[container_name]
        long_ = self._long_windows[container_name]

        # Use long window for primary stats (backward compatible)
        if len(long_) < 2:
            return {"p50": 0.0, "p95": 0.0, "spike_ratio": 0.0,
                    "samples": len(long_), "short_ratio": 0.0}

        p50 = float(np.percentile(long_, 50))
        p95 = float(np.percentile(long_, 95))
        ratio = (p95 / p50) if p50 > 0 else 0.0

        # Short window stats for diagnostic logging
        short_ratio = 0.0
        if len(short) >= 2:
            sp50 = float(np.percentile(short, 50))
            sp95 = float(np.percentile(short, 95))
            short_ratio = (sp95 / sp50) if sp50 > 0 else 0.0

        return {
            "p50":         round(p50, 2),
            "p95":         round(p95, 2),
            "spike_ratio": round(ratio, 3),
            "samples":     len(long_),
            "short_ratio": round(short_ratio, 3),
        }

    def cleanup(self, active_containers: set):
        """Remove tracking state for containers that no longer exist."""
        dead = [name for name in self._long_windows if name not in active_containers]
        for name in dead:
            del self._long_windows[name]
            self._short_windows.pop(name, None)
            self._hysteresis.pop(name, None)