# framework/security/watchdog_thaw.py
# Appendix A #6: Watchdog Auto-Thaw
# Monitors cgroup.freeze state; force-thaws containers stuck frozen beyond
# 2× MICRO_FREEZE_MAX_DURATION_MS. Safety-net for kernel race conditions
# or missed thaw signals.
#
# Pattern: identical to sandbox_isolator.py's immediate-freeze mechanism,
# but in reverse — detects stuck-frozen state and recovers.

import os
import time
import logging
import threading

logger = logging.getLogger("hecf.security.watchdog_thaw")


class WatchdogThaw:
    """
    External watchdog that monitors cgroup.freeze state for all tracked
    containers. If any container remains frozen beyond the safety timeout
    (2× max_freeze_duration), force-writes cgroup.freeze = 0.

    Runs as a background daemon thread — does not block the main loop.
    """

    def __init__(self, max_freeze_duration_ms: float = 1000.0,
                 check_interval_s: float = 0.5, dry_run: bool = False):
        self._timeout_ms = max_freeze_duration_ms * 2.0
        self._check_interval = check_interval_s
        self._dry_run = dry_run
        self._tracked = {}  # container_id -> {"frozen_at": float}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        logger.info(
            "WatchdogThaw initialized (timeout=%.0fms, interval=%.1fs)",
            self._timeout_ms, self._check_interval
        )

    def start(self):
        """Start the watchdog background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="hecf-watchdog-thaw")
        self._thread.start()
        logger.info("Watchdog thaw thread started")

    def stop(self):
        """Stop the watchdog background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("Watchdog thaw thread stopped")

    def track_freeze(self, container_id: str):
        """Record that a container was frozen (called by MicroFreezer)."""
        with self._lock:
            self._tracked[container_id] = {"frozen_at": time.time()}

    def track_thaw(self, container_id: str):
        """Record that a container was thawed normally."""
        with self._lock:
            self._tracked.pop(container_id, None)

    def _run(self):
        """Background loop: check for stuck-frozen containers."""
        while self._running:
            time.sleep(self._check_interval)
            self._check_stuck()

    def _check_stuck(self):
        """Check all tracked containers for stuck-frozen state."""
        now = time.time()
        with self._lock:
            stuck = []
            for cid, state in self._tracked.items():
                elapsed_ms = (now - state["frozen_at"]) * 1000
                if elapsed_ms >= self._timeout_ms:
                    stuck.append(cid)

            for cid in stuck:
                self._force_thaw(cid)
                del self._tracked[cid]

    def _force_thaw(self, container_id: str):
        """Force-write cgroup.freeze = 0 for a stuck container."""
        freeze_path = self._get_freeze_path(container_id)
        if not freeze_path:
            logger.warning("Cannot force-thaw %s: cgroup.freeze not found",
                          container_id[:12])
            return

        if self._dry_run:
            logger.warning("[DRY-RUN] WATCHDOG would force-thaw %s",
                          container_id[:12])
            return

        try:
            with open(freeze_path, "w") as f:
                f.write("0")
            logger.warning(
                "⚠ WATCHDOG force-thawed %s (stuck beyond %.0fms timeout)",
                container_id[:12], self._timeout_ms
            )
        except OSError as e:
            logger.error("Watchdog force-thaw failed for %s: %s",
                        container_id[:12], e)

    def _get_freeze_path(self, container_id: str) -> str:
        """Find the cgroup.freeze file for a container."""
        paths = [
            f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope/cgroup.freeze",
            f"/sys/fs/cgroup/docker/{container_id}/cgroup.freeze",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope/cgroup.freeze",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def cleanup(self, active_container_ids: set):
        """Remove tracking for disappeared containers."""
        with self._lock:
            dead = [cid for cid in self._tracked
                    if cid not in active_container_ids]
            for cid in dead:
                del self._tracked[cid]
