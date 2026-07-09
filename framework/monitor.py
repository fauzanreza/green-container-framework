# framework/monitor.py
# Layer 2: Monitoring Engine
# Reads metrics directly from cgroupfs v2 to minimize overhead (<5%).
# Adaptive sampling: 10s when CPU > 60%, 30s when normal.
#
# Hardening: retry on cgroup read failure + stale fallback (never returns None).

import os
import time
import logging
from .config import (
    SAMPLING_CPU_THRESHOLD, SAMPLING_INTERVAL_LOW, SAMPLING_INTERVAL_HIGH,
    MONITOR_RETRY_COUNT, MONITOR_RETRY_DELAY_MS,
)

logger = logging.getLogger("hecf.monitor")


class Monitor:
    def __init__(self):
        # container_name -> {"time": float, "usage_usec": int}
        self._prev_stats = {}
        self._host_mem_bytes = self._read_host_mem()

    def _read_host_mem(self) -> int:
        """Read total host RAM in bytes from /proc/meminfo."""
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb * 1024
        except OSError:
            pass
        return 4 * 1024 * 1024 * 1024  # fallback: 4 GB

    def _get_cgroup_path(self, container_id: str) -> str:
        paths = [
            f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope",
            f"/sys/fs/cgroup/docker/{container_id}",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope"
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def _read_raw_stats(self, container_name: str, cgroup_path: str) -> dict:
        """
        Read raw CPU and memory values from cgroupfs v2.
        Returns dict with raw values, or None on failure.
        """
        now = time.time()

        # === Read CPU ===
        try:
            with open(os.path.join(cgroup_path, "cpu.stat")) as f:
                usage_usec = 0
                for line in f:
                    if line.startswith("usage_usec"):
                        usage_usec = int(line.split()[1])
                        break
        except OSError as e:
            logger.error("Failed reading cpu.stat for %s: %s", container_name, e)
            return None

        # === Read Memory (memory.stat — excludes reclaimable cache) ===
        try:
            with open(os.path.join(cgroup_path, "memory.current")) as f:
                mem_current = int(f.read().strip())
        except OSError:
            mem_current = 0

        # Parse inactive_file from memory.stat to exclude reclaimable cache
        inactive_file = 0
        try:
            with open(os.path.join(cgroup_path, "memory.stat")) as f:
                for line in f:
                    if line.startswith("inactive_file"):
                        inactive_file = int(line.split()[1])
                        break
        except OSError:
            pass

        mem_usage = max(0, mem_current - inactive_file)

        try:
            with open(os.path.join(cgroup_path, "memory.max")) as f:
                val = f.read().strip()
                # "max" means no container limit → use host total RAM
                mem_limit = self._host_mem_bytes if val == "max" else int(val)
        except OSError:
            mem_limit = self._host_mem_bytes

        return {
            "time": now,
            "usage_usec": usage_usec,
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
        }

    def get_stats(self, container_name: str, container_id: str) -> dict:
        """
        Read container stats with retry on failure.
        Never returns None — returns a stale marker dict on total failure
        so the main loop can decide how to handle it.
        """
        cgroup_path = self._get_cgroup_path(container_id)
        if not cgroup_path:
            logger.error("cgroup path not found for %s (%s)", container_name, container_id)
            return self._stale_result(container_name)

        # Try reading with retry
        raw = None
        for attempt in range(1 + MONITOR_RETRY_COUNT):
            raw = self._read_raw_stats(container_name, cgroup_path)
            if raw is not None:
                break
            if attempt < MONITOR_RETRY_COUNT:
                logger.warning(
                    "Retry %d/%d for %s cgroup read...",
                    attempt + 1, MONITOR_RETRY_COUNT, container_name
                )
                time.sleep(MONITOR_RETRY_DELAY_MS / 1000.0)

        if raw is None:
            logger.warning("All cgroup reads failed for %s, returning stale", container_name)
            return self._stale_result(container_name)

        # Compute CPU percent from delta
        now = raw["time"]
        usage_usec = raw["usage_usec"]
        mem_usage = raw["mem_usage"]
        mem_limit = raw["mem_limit"]

        prev = self._prev_stats.get(container_name)
        self._prev_stats[container_name] = {"time": now, "usage_usec": usage_usec}

        if prev:
            time_delta = now - prev["time"]
            usage_delta = (usage_usec - prev["usage_usec"]) / 1_000_000.0
            cpu_percent = (usage_delta / time_delta) * 100.0 if time_delta > 0 else 0.0
        else:
            cpu_percent = 0.0

        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

        return {
            "name": container_name,
            "cpu_percent": round(max(0.0, cpu_percent), 2),
            "mem_percent": round(max(0.0, mem_percent), 2),
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
            "stale": False,
        }

    def _stale_result(self, container_name: str) -> dict:
        """Return a stale marker so the main loop can skip shaping safely."""
        return {
            "name": container_name,
            "cpu_percent": -1.0,
            "mem_percent": -1.0,
            "mem_usage": 0,
            "mem_limit": 0,
            "stale": True,
        }

    def cleanup(self, active_containers: set):
        """
        Remove tracking state for containers that no longer exist.
        Called from the main loop to prevent unbounded memory growth.
        """
        dead = [name for name in self._prev_stats if name not in active_containers]
        for name in dead:
            del self._prev_stats[name]
            logger.debug("Cleaned up monitor state for disappeared container: %s", name)


def get_adaptive_interval(cpu_percent: float) -> int:
    """
    Adaptive sampling interval.
    High CPU -> frequent sampling for responsive guardrail.
    """
    if cpu_percent >= SAMPLING_CPU_THRESHOLD:
        return SAMPLING_INTERVAL_HIGH
    return SAMPLING_INTERVAL_LOW