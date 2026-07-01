# framework/overhead_tracker.py
# Framework Overhead Tracker
# Measures HECF's own CPU/RAM footprint.

import os
import time
import socket
import logging

logger = logging.getLogger("hecf.overhead")

class OverheadTracker:
    def __init__(self):
        self._prev_time = None
        self._prev_usage = 0
        self._cgroup_path = None
        self._init_path()
        
    def _init_path(self):
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(socket.gethostname())
            long_id = container.id
            
            paths = [
                f"/sys/fs/cgroup/system.slice/docker-{long_id}.scope",
                f"/sys/fs/cgroup/docker/{long_id}",
                f"/sys/fs/cgroup/system.slice/docker.service/docker-{long_id}.scope"
            ]
            for p in paths:
                if os.path.exists(p):
                    self._cgroup_path = p
                    break
        except Exception as e:
            logger.error("Failed to initialize overhead tracker: %s", str(e))
            
    def get_overhead(self) -> dict:
        if not self._cgroup_path:
            return {"cpu_percent": 0.0, "mem_usage_mb": 0.0}
            
        now = time.time()
        
        try:
            with open(os.path.join(self._cgroup_path, "cpu.stat")) as f:
                usage_usec = 0
                for line in f:
                    if line.startswith("usage_usec"):
                        usage_usec = int(line.split()[1])
                        break
        except OSError:
            usage_usec = 0
            
        try:
            with open(os.path.join(self._cgroup_path, "memory.current")) as f:
                mem_usage = int(f.read().strip())
        except OSError:
            mem_usage = 0
            
        cpu_percent = 0.0
        if self._prev_time:
            dt = now - self._prev_time
            du = (usage_usec - self._prev_usage) / 1_000_000.0
            if dt > 0:
                cpu_percent = (du / dt) * 100.0
                
        self._prev_time = now
        self._prev_usage = usage_usec
        
        return {
            "cpu_percent": round(max(0.0, cpu_percent), 2),
            "mem_usage_mb": round(mem_usage / (1024 * 1024), 2)
        }
