# framework/security/pids_limiter.py
# Appendix A #10: Process Bomb Protection
# Writes pids.max to each non-priority container's cgroup at cold start.
# Prevents fork-bomb or thread-leak DoS.
#
# Pattern identical to privilege_guard.py (cold-start-only, flags non-priority).

import os
import logging

logger = logging.getLogger("hecf.security.pids_limiter")


class PidsLimiter:
    """
    Process bomb protection via cgroups v2 pids.max.
    Caps maximum concurrent processes/threads per non-priority container.

    Cold-start-only check — runs once per container discovery, not in
    the polling loop. Hidden feature — not part of the 5 evaluated metrics.
    """

    # Default: 512 processes per non-priority container
    DEFAULT_MAX_PIDS = 512

    def __init__(self, max_pids: int = None, dry_run: bool = False):
        self._max_pids = max_pids or self.DEFAULT_MAX_PIDS
        self._dry_run = dry_run
        self._applied = set()

        logger.info("PidsLimiter initialized (max_pids=%d)", self._max_pids)

    def apply(self, container_name: str, container_id: str,
              priority: bool) -> bool:
        """Apply pids.max limit to a non-priority container."""
        if priority:
            logger.debug("Skipping pids.max for priority container %s",
                        container_name)
            return True

        if container_id in self._applied:
            return True

        cgroup_path = self._get_cgroup_path(container_id)
        if not cgroup_path:
            logger.debug("No cgroup path for %s — skip pids.max",
                        container_name)
            return False

        pids_max_path = os.path.join(cgroup_path, "pids.max")
        if not os.path.exists(pids_max_path):
            logger.debug("pids.max not available for %s", container_name)
            return False

        if self._dry_run:
            logger.info("[DRY-RUN] Would write pids.max=%d for %s",
                       self._max_pids, container_name)
            self._applied.add(container_id)
            return True

        try:
            with open(pids_max_path, "w") as f:
                f.write(str(self._max_pids))
            self._applied.add(container_id)
            logger.info("[PIDS] Applied pids.max=%d for %s",
                       self._max_pids, container_name)
            return True
        except OSError as e:
            logger.error("Failed to write pids.max for %s: %s",
                        container_name, e)
            return False

    def get_current(self, container_id: str) -> int:
        """Read current pids.current for a container."""
        cgroup_path = self._get_cgroup_path(container_id)
        if not cgroup_path:
            return -1

        try:
            with open(os.path.join(cgroup_path, "pids.current")) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return -1

    def _get_cgroup_path(self, container_id: str) -> str:
        paths = [
            f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope",
            f"/sys/fs/cgroup/docker/{container_id}",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def cleanup(self, active_container_ids: set):
        """Remove tracking for disappeared containers."""
        self._applied = self._applied & active_container_ids
