# framework/security/io_limiter.py
# Appendix A #8: I/O Bandwidth Isolation
# Writes io.max to cgroupfs to cap per-container disk I/O bandwidth.
# Prevents a single container from monopolizing host I/O during
# database-heavy workloads.
#
# Outside the 5 tracked metrics (§9) — hardening only.

import os
import logging

logger = logging.getLogger("hecf.security.io_limiter")


class IOLimiter:
    """
    I/O bandwidth isolation via cgroups v2 io.max.
    Caps read/write bandwidth per container to prevent I/O monopolization.

    Hidden feature — not part of the 5 evaluated metrics.
    """

    # Default limits: 50 MB/s read, 30 MB/s write per non-priority container
    DEFAULT_RBPS = 50 * 1024 * 1024  # 50 MB/s
    DEFAULT_WBPS = 30 * 1024 * 1024  # 30 MB/s

    def __init__(self, read_bps: int = None, write_bps: int = None,
                 dry_run: bool = False):
        self._read_bps = read_bps or self.DEFAULT_RBPS
        self._write_bps = write_bps or self.DEFAULT_WBPS
        self._dry_run = dry_run
        self._applied = set()

        logger.info(
            "IOLimiter initialized (read=%d MB/s, write=%d MB/s)",
            self._read_bps // (1024 * 1024),
            self._write_bps // (1024 * 1024)
        )

    def apply(self, container_name: str, container_id: str,
              priority: bool) -> bool:
        """Apply I/O limits to a non-priority container."""
        if priority:
            return True  # Never limit priority containers

        if container_id in self._applied:
            return True  # Already applied

        cgroup_path = self._get_cgroup_path(container_id)
        if not cgroup_path:
            logger.debug("No cgroup path for %s — skip io.max", container_name)
            return False

        io_max_path = os.path.join(cgroup_path, "io.max")
        if not os.path.exists(io_max_path):
            logger.debug("io.max not available for %s", container_name)
            return False

        # Detect block device major:minor from the container's cgroup
        major_minor = self._detect_block_device()
        if not major_minor:
            logger.debug("Could not detect block device for io.max")
            return False

        value = f"{major_minor} rbps={self._read_bps} wbps={self._write_bps}"

        if self._dry_run:
            logger.info("[DRY-RUN] Would write io.max for %s: %s",
                       container_name, value)
            self._applied.add(container_id)
            return True

        try:
            with open(io_max_path, "w") as f:
                f.write(value)
            self._applied.add(container_id)
            logger.info("[IO] Applied io.max for %s: read=%d MB/s write=%d MB/s",
                       container_name,
                       self._read_bps // (1024 * 1024),
                       self._write_bps // (1024 * 1024))
            return True
        except OSError as e:
            logger.error("Failed to write io.max for %s: %s", container_name, e)
            return False

    def _detect_block_device(self) -> str:
        """Detect the primary block device's major:minor number."""
        try:
            # Read from /proc/partitions for the root device
            with open("/proc/partitions") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 4 and parts[3] in ("sda", "vda", "nvme0n1"):
                        return f"{parts[0]}:{parts[1]}"
        except OSError:
            pass
        # Fallback: common values
        return "8:0"  # sda

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
