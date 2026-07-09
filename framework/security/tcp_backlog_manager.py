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

    def check_app_backlog(self, container_name: str, container_id: str) -> dict:
        """
        Check app-level listen backlog via /proc/<pid>/net/tcp (Gap #16).
        Even if somaxconn=4096, an app compiled with listen(fd, 5) will still
        drop connections during a freeze window.

        Returns: {"safe": bool, "min_backlog": int, "recommendation": str}
        """
        min_backlog = 128  # Minimum safe backlog for micro-freezing

        # Try to find container's init PID
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            pid = container.attrs.get("State", {}).get("Pid", 0)
        except Exception:
            return {"safe": True, "min_backlog": -1,
                    "recommendation": "could_not_check"}

        if not pid or pid <= 0:
            return {"safe": True, "min_backlog": -1,
                    "recommendation": "no_pid"}

        # Parse /proc/<pid>/net/tcp for LISTEN sockets (state=0A)
        tcp_path = f"/proc/{pid}/net/tcp"
        try:
            lowest_backlog = float("inf")
            with open(tcp_path) as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 5 and parts[3] == "0A":  # LISTEN state
                        # tx_queue:rx_queue — tx_queue for LISTEN = backlog
                        queues = parts[4].split(":")
                        tx_queue = int(queues[0], 16)
                        if tx_queue > 0:
                            lowest_backlog = min(lowest_backlog, tx_queue)

            if lowest_backlog == float("inf"):
                return {"safe": True, "min_backlog": -1,
                        "recommendation": "no_listen_sockets"}

            safe = lowest_backlog >= min_backlog
            result = {
                "safe": safe,
                "min_backlog": lowest_backlog,
            }

            if safe:
                result["recommendation"] = "ok"
                logger.debug("[TCP] App backlog check PASSED for %s (min=%d)",
                            container_name, lowest_backlog)
            else:
                result["recommendation"] = (
                    f"app listen backlog={lowest_backlog} < {min_backlog} — "
                    f"micro-freeze may drop connections"
                )
                logger.warning(
                    "[TCP] App backlog LOW for %s: min_backlog=%d < %d",
                    container_name, lowest_backlog, min_backlog
                )
            return result

        except OSError:
            return {"safe": True, "min_backlog": -1,
                    "recommendation": "tcp_not_readable"}
