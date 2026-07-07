# framework/security/ddos_filter.py
# Layer 2 Extension: DDoS Packet Filtering & Traffic Separation
# Architecture §10.3, PRD §12.3
#
# Analyzes inbound packet rate to separate suspected DDoS traffic from genuine
# HttpArena/user workload BEFORE it reaches Layer 3's Tier Detector.
# Without this, a traffic-flood attack is indistinguishable from a legitimate
# spike, and would trip Tier 1/Guardrail exactly as intended traffic would.

import time
import logging
from collections import defaultdict

logger = logging.getLogger("hecf.security.ddos_filter")


class DDoSFilter:
    """
    Packet-rate analysis module for DDoS traffic separation.
    
    Tracks request rate per container and flags containers whose inbound
    request rate exceeds the configured threshold as potential DDoS targets.
    
    Output feeds Layer 3's Anti-EDoS logic (edos_guard.py) before
    traffic-derived metrics reach the Tier Detector.
    """

    def __init__(self, rate_threshold: float = 1000.0, window_seconds: float = 10.0):
        """
        Args:
            rate_threshold: Requests per second above which traffic is flagged
                           as potential DDoS. Needs empirical tuning per workload.
            window_seconds: Sliding window for rate calculation.
        """
        self._rate_threshold = rate_threshold
        self._window_seconds = window_seconds
        # container_name -> list of (timestamp, count) tuples
        self._request_log = defaultdict(list)
        # container_name -> {"is_ddos": bool, "rate": float}
        self._status = defaultdict(lambda: {"is_ddos": False, "rate": 0.0})

        logger.info(
            "DDoS filter initialized (threshold=%.0f req/s, window=%.0fs)",
            rate_threshold, window_seconds
        )

    def record_request(self, container_name: str, request_count: int = 1):
        """
        Record inbound requests for a container.
        Called from the monitoring loop or an external request counter.
        """
        now = time.time()
        log = self._request_log[container_name]
        log.append((now, request_count))

        # Trim entries outside the window
        cutoff = now - self._window_seconds
        self._request_log[container_name] = [
            (t, c) for t, c in log if t >= cutoff
        ]

    def analyze(self, container_name: str) -> dict:
        """
        Analyze current request rate for a container.
        
        Returns:
            {"is_ddos": bool, "rate": float, "threshold": float}
        """
        now = time.time()
        cutoff = now - self._window_seconds
        log = self._request_log.get(container_name, [])

        # Calculate rate over window
        total_requests = sum(c for t, c in log if t >= cutoff)
        rate = total_requests / self._window_seconds if self._window_seconds > 0 else 0.0

        is_ddos = rate > self._rate_threshold

        result = {
            "is_ddos": is_ddos,
            "rate": round(rate, 1),
            "threshold": self._rate_threshold,
        }

        self._status[container_name] = {"is_ddos": is_ddos, "rate": rate}

        if is_ddos:
            logger.warning(
                "[DDoS] %s: %.0f req/s exceeds threshold %.0f — flagging as attack traffic",
                container_name, rate, self._rate_threshold
            )

        return result

    def is_under_attack(self, container_name: str) -> bool:
        """Quick check: is this container currently flagged as DDoS target?"""
        return self._status.get(container_name, {}).get("is_ddos", False)

    def get_rate(self, container_name: str) -> float:
        """Get current request rate for a container."""
        return self._status.get(container_name, {}).get("rate", 0.0)

    def cleanup(self, active_containers: set):
        """Remove state for disappeared containers."""
        for store in [self._request_log, self._status]:
            dead = [n for n in store if n not in active_containers]
            for n in dead:
                del store[n]
