# framework/monitor.py
# Layer 2: Monitoring Engine
# Reads metrics directly from cgroupfs v2 to minimize overhead (<5%).
# Adaptive sampling: 10s when CPU > 60%, 30s when normal.

import os
import time
import logging
from .config import SAMPLING_CPU_THRESHOLD, SAMPLING_INTERVAL_LOW, SAMPLING_INTERVAL_HIGH

logger = logging.getLogger("hecf.monitor")


class Monitor:
    def __init__(self):
        # container_name -> {"time": float, "usage_usec": int}
        self._prev_stats = {}
        
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

    def get_stats(self, container_name: str, container_id: str) -> dict:
        cgroup_path = self._get_cgroup_path(container_id)
        if not cgroup_path:
            logger.error("cgroup path not found for %s (%s)", container_name, container_id)
            return None
            
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
            
        # === Read Memory ===
        try:
            with open(os.path.join(cgroup_path, "memory.current")) as f:
                mem_usage = int(f.read().strip())
        except OSError:
            mem_usage = 0
            
        try:
            with open(os.path.join(cgroup_path, "memory.max")) as f:
                val = f.read().strip()
                if val == "max":
                    mem_limit = 1
                else:
                    mem_limit = int(val)
        except OSError:
            mem_limit = 1
            
        prev = self._prev_stats.get(container_name)
        self._prev_stats[container_name] = {"time": now, "usage_usec": usage_usec}
        
        if prev:
            time_delta = now - prev["time"]
            usage_delta = (usage_usec - prev["usage_usec"]) / 1_000_000.0 # convert to seconds
            if time_delta > 0:
                cpu_percent = (usage_delta / time_delta) * 100.0
            else:
                cpu_percent = 0.0
        else:
            cpu_percent = 0.0
            
        if mem_limit > 1:
            mem_percent = (mem_usage / mem_limit) * 100.0
        else:
            mem_percent = 0.0 # Avoid division by max/1
            
        return {
            "name": container_name,
            "cpu_percent": round(max(0.0, cpu_percent), 2),
            "mem_percent": round(max(0.0, mem_percent), 2),
            "mem_usage": mem_usage,
            "mem_limit": mem_limit
        }


def get_adaptive_interval(cpu_percent: float) -> int:
    """
    Adaptive sampling interval.
    High CPU -> frequent sampling for responsive guardrail.
    """
    if cpu_percent >= SAMPLING_CPU_THRESHOLD:
        return SAMPLING_INTERVAL_HIGH
    return SAMPLING_INTERVAL_LOW