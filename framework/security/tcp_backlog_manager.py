# framework/security/tcp_backlog_manager.py
# Layer 4 Extension: TCP Backlog Headroom Verification
# Architecture §10.5, PRD §12.5
#
# At Layer 1 cold start, inspects the host's net.core.somaxconn value and
# confirms there's enough headroom to queue inbound SYN/request packets
# for the maximum expected freeze duration without saturating.
#
# During an active freeze, new packets simply queue in the kernel's existing
# TCP backlog — this module's job is PRE-FLIGHT VERIFICATION, not active
# packet handling.
#
# Challenge addressed (architecture §12.9, Challenge 1):
# If a container is frozen too long during a traffic storm, the TCP backlog
# can saturate and the kernel starts dropping SYN packets → client timeouts
# instead of the "invisible pause" the design intends.

import os
import logging

logger = logging.getLogger("hecf.security.tcp_backlog")


class TCPBacklogManager:
    """
    TCP Backlog Headroom Verification.
    
    Checks that the host's somaxconn value has enough headroom to queue
    inbound packets during a micro-freeze cycle without packet loss.
    
    This is a cold-start-only check, not a runtime monitor.
    """

    # Default minimum somaxconn for safe micro-freezing
    DEFAULT_MIN_HEADROOM = 4096

    def __init__(self, min_headroom: int = None,
                 max_freeze_duration_ms: float = 1000.0,
                 expected_rps: float = 100.0):
        """
        Args:
            min_headroom: Minimum somaxconn value to consider safe.
            max_freeze_duration_ms: Maximum freeze duration from micro_freezer config.
            expected_rps: Expected peak requests per second per container.
        """
        self._min_headroom = min_headroom or self.DEFAULT_MIN_HEADROOM
        self._max_freeze_ms = max_freeze_duration_ms
        self._expected_rps = expected_rps
        self._current_somaxconn = self._read_somaxconn()
        self._verified = False
        self._safe = False

        logger.info(
            "TCP Backlog Manager initialized (somaxconn=%d, min_headroom=%d)",
            self._current_somaxconn, self._min_headroom
        )

    def _read_somaxconn(self) -> int:
        """Read current net.core.somaxconn value."""
        try:
            with open("/proc/sys/net/core/somaxconn") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            logger.warning("Cannot read somaxconn — assuming default 4096")
            return 4096

    def verify(self) -> dict:
        """
        Run the pre-flight verification at cold start.
        
        Calculates expected queue depth during a freeze and checks against
        the current somaxconn value.
        
        Returns:
            {"safe": bool, "somaxconn": int, "required": int,
             "expected_queue_depth": int, "recommendation": str}
        """
        # Calculate expected packets queued during max freeze duration
        freeze_seconds = self._max_freeze_ms / 1000.0
        expected_queue_depth = int(self._expected_rps * freeze_seconds)

        # Need headroom above the expected queue depth
        required = max(expected_queue_depth * 2, self._min_headroom)

        self._safe = self._current_somaxconn >= required
        self._verified = True

        result = {
            "safe": self._safe,
            "somaxconn": self._current_somaxconn,
            "required": required,
            "expected_queue_depth": expected_queue_depth,
        }

        if self._safe:
            result["recommendation"] = "ok"
            logger.info(
                "[TCP] Backlog check PASSED: somaxconn=%d >= required=%d "
                "(expected queue depth=%d during %dms freeze)",
                self._current_somaxconn, required,
                expected_queue_depth, self._max_freeze_ms
            )
        else:
            result["recommendation"] = (
                f"increase somaxconn to {required}: "
                f"sysctl -w net.core.somaxconn={required}"
            )
            logger.warning(
                "[TCP] Backlog check FAILED: somaxconn=%d < required=%d — "
                "micro-freezing may cause packet drops. "
                "Recommendation: sysctl -w net.core.somaxconn=%d",
                self._current_somaxconn, required, required
            )

        return result

    @property
    def is_safe(self) -> bool:
        """Returns True if backlog headroom is sufficient for micro-freezing."""
        if not self._verified:
            self.verify()
        return self._safe

    @property
    def somaxconn(self) -> int:
        return self._current_somaxconn
