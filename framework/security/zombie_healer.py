# framework/security/zombie_healer.py
# Security & Auto-Heal Extension
# Detects silent deadlocks (zombies) via cgroups OOM events and TCP rx_queue buildup,
# then auto-heals them (by restarting) alongside other security features.

import os
import time
import logging

logger = logging.getLogger("hecf.security.zombie_healer")

class ZombieHealer:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._tracked = {} # container_id -> {"rx_queue": int, "stuck_count": int}

    def evaluate(self, name: str, cid: str, priority: bool, pid: int = None) -> dict:
        """
        Evaluate if a container is a zombie.
        Returns: {"action": "heal"|"none", "reason": str}
        """
        # 1. Check OOM (cgroups v2 memory.events)
        oom_crashed = False
        oom_paths = [
            f"/sys/fs/cgroup/system.slice/docker-{cid}.scope/memory.events",
            f"/sys/fs/cgroup/docker/{cid}/memory.events",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{cid}.scope/memory.events"
        ]
        
        for p in oom_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        lines = f.readlines()
                        for line in lines:
                            if line.startswith("oom_kill") or line.startswith("oom"):
                                parts = line.split()
                                if len(parts) >= 2 and int(parts[1]) > 0:
                                    oom_crashed = True
                                    break
                except Exception:
                    pass
                break
                
        if oom_crashed:
            logger.critical("[ZOMBIE] %s (%s) has OOM'd silently! Triggering heal.", name, cid[:12])
            return {"action": "heal", "reason": "OOM"}

        # 2. Check TCP rx_queue starvation
        if pid:
            try:
                tcp_path = f"/proc/{pid}/net/tcp"
                if os.path.exists(tcp_path):
                    with open(tcp_path, "r") as f:
                        lines = f.readlines()
                        
                    max_rx = 0
                    for line in lines[1:]: # skip header
                        parts = line.split()
                        if len(parts) >= 4:
                            state = parts[3]
                            if state == "0A": # LISTEN
                                queue_str = parts[4] # tx:rx (hex)
                                tx, rx = queue_str.split(":")
                                max_rx = max(max_rx, int(rx, 16))
                    
                    if cid not in self._tracked:
                        self._tracked[cid] = {"rx_queue": max_rx, "stuck_count": 0}
                    else:
                        prev_rx = self._tracked[cid]["rx_queue"]
                        # If rx_queue is consistently greater than 0 and not decreasing
                        if max_rx > 0 and max_rx >= prev_rx:
                            self._tracked[cid]["stuck_count"] += 1
                        else:
                            self._tracked[cid]["stuck_count"] = 0
                            
                        self._tracked[cid]["rx_queue"] = max_rx
                        
                        if self._tracked[cid]["stuck_count"] >= 3:
                            logger.critical("[ZOMBIE] %s (%s) TCP rx_queue starvation (stuck at %d)! Triggering heal.", name, cid[:12], max_rx)
                            return {"action": "heal", "reason": "TCP_STARVATION"}
            except Exception:
                pass
                
        return {"action": "none"}

    def heal(self, name: str, cid: str):
        if self.dry_run:
            logger.warning("[DRY-RUN] Would heal %s", name)
            return
            
        logger.warning("🚑 [HEAL] Attempting automatic recovery (restart) for %s", name)
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(cid)
            container.restart(timeout=5)
            logger.info("[HEAL] Successfully restarted %s", name)
            
            # Reset tracking after heal
            if cid in self._tracked:
                self._tracked[cid]["stuck_count"] = 0
                self._tracked[cid]["rx_queue"] = 0
                
        except Exception as e:
            logger.error("[HEAL] Failed to restart %s: %s", name, e)
            
    def cleanup(self, active_container_ids: set):
        dead = [cid for cid in self._tracked if cid not in active_container_ids]
        for cid in dead:
            del self._tracked[cid]
