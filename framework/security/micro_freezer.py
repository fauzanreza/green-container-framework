# framework/security/micro_freezer.py
# Layer 4 Extension: Micro-Freezing via cgroup.freeze
# Architecture §10.5, PRD §12.5
#
# When a non-priority container has a silent window (no inbound requests)
# longer than ~2 seconds, writes `1` to cgroup.freeze to drop CPU to 0%
# while keeping it resident in RAM. Writing `0` on the next request thaws
# it in under 1ms — no cold-start delay.
#
# SAFETY CHECK (hard requirement, §10.5):
# Before freezing, queries ebpf_sensor to confirm no uncommitted database
# transaction is in flight. If one exists, freeze is deferred.
#
# HARD TIMING CONSTRAINT (§10.6):
# Freeze duration capped at 500–1000ms max per cycle.
# Requires cgroups v2 (v1 freezer is unsafe — see architecture §10.6).

import os
import time
import logging

logger = logging.getLogger("hecf.security.micro_freezer")


class MicroFreezer:
    """
    Micro-Freezing engine: drops idle non-priority containers to literal 0% CPU
    via cgroup.freeze (cgroups v2 only).
    
    Goes beyond vertical scaling — an idle container hits 0% CPU instead of
    just a lower quota, which is the mechanism behind the claimed additional
    10-20% idle-state energy saving beyond the baseline target.
    
    Thaw is sub-millisecond since memory state is never evicted.
    """

    def __init__(self, idle_trigger_seconds: float = 2.0,
                 max_freeze_duration_ms: float = 1000.0,
                 ebpf_sensor=None, dry_run: bool = False):
        """
        Args:
            idle_trigger_seconds: Silence window before freeze-eligible (§10.8).
            max_freeze_duration_ms: Hard cap per freeze cycle (§10.6).
            ebpf_sensor: Reference to EBPFSensor for transaction safety check.
            dry_run: If True, log actions but don't write to cgroup.freeze.
        """
        self._idle_trigger = idle_trigger_seconds
        self._max_freeze_ms = max_freeze_duration_ms
        self._ebpf_sensor = ebpf_sensor
        self._dry_run = dry_run

        # container_id -> {"frozen": bool, "frozen_at": float, "last_activity": float,
        #                  "populated": bool}
        self._state = {}

        logger.info(
            "Micro-Freezer initialized (idle_trigger=%.1fs, max_freeze=%dms, "
            "dry_run=%s, idle_mode=event+fallback)",
            idle_trigger_seconds, max_freeze_duration_ms, dry_run
        )

    def record_activity(self, container_id: str):
        """Record that a container had activity (request, I/O, etc.)."""
        now = time.time()
        if container_id not in self._state:
            self._state[container_id] = {
                "frozen": False,
                "frozen_at": 0.0,
                "last_activity": now,
            }
        else:
            self._state[container_id]["last_activity"] = now

            # If container was frozen and now has activity → thaw it
            if self._state[container_id]["frozen"]:
                self._thaw(container_id, reason="new_activity")

    def evaluate(self, container_name: str, container_id: str,
                 priority: bool, cpu_percent: float) -> dict:
        """
        Evaluate whether a container should be frozen.
        
        Args:
            container_name: Human-readable name.
            container_id: Docker container long ID.
            priority: True if priority (never freeze).
            cpu_percent: Current CPU utilization.
            
        Returns:
            {"action": str, "reason": str}
            action: "none", "freeze", "thaw", "defer"
        """
        # Never freeze priority containers (databases)
        if priority:
            return {"action": "none", "reason": "priority_exempt"}

        now = time.time()
        state = self._state.get(container_id)

        if state is None:
            self._state[container_id] = {
                "frozen": False, "frozen_at": 0.0, "last_activity": now,
            }
            return {"action": "none", "reason": "first_seen"}

        # If already frozen, check if max duration exceeded → force thaw
        if state["frozen"]:
            frozen_duration_ms = (now - state["frozen_at"]) * 1000
            if frozen_duration_ms >= self._max_freeze_ms:
                self._thaw(container_id, reason="max_duration_reached")
                return {"action": "thaw", "reason": f"max_duration:{frozen_duration_ms:.0f}ms"}
            return {"action": "none", "reason": "already_frozen"}

        # Check idle duration
        idle_duration = now - state["last_activity"]

        # === Event-Driven Idle Detection (Gap #2) ===
        # Primary: check cgroup.events 'populated' field
        # populated=0 means kernel confirms no active processes in cgroup
        populated = self._check_populated(container_id)
        if populated is not None:
            # Event-driven mode available
            if populated:
                # Kernel says processes are active — not idle
                return {"action": "none", "reason": "populated_active"}
            # populated=0 AND idle duration met — safe to freeze
            if idle_duration < self._idle_trigger:
                return {"action": "none", "reason": f"depopulated_but_too_recent:{idle_duration:.1f}s"}
        else:
            # Fallback: polling-based idle check (cgroup.events unavailable)
            if idle_duration < self._idle_trigger:
                return {"action": "none", "reason": f"not_idle_enough:{idle_duration:.1f}s"}

        # Container is idle long enough → check safety before freezing
        # SAFETY CHECK: no uncommitted database transaction in flight
        if self._ebpf_sensor and self._ebpf_sensor.has_open_connections(container_id):
            logger.debug(
                "[DEFER] %s has open connections — deferring freeze until transaction completes",
                container_name
            )
            return {"action": "defer", "reason": "open_connections"}

        # Safe to freeze
        self._freeze(container_name, container_id)
        return {"action": "freeze", "reason": f"idle:{idle_duration:.1f}s"}

    def _freeze(self, container_name: str, container_id: str):
        """Write 1 to cgroup.freeze to drop container to 0% CPU."""
        freeze_path = self._get_freeze_path(container_id)
        if not freeze_path:
            logger.warning("Cannot freeze %s: cgroup.freeze path not found", container_name)
            return

        if self._dry_run:
            logger.info("[DRY-RUN] Would FREEZE %s via %s", container_name, freeze_path)
        else:
            try:
                with open(freeze_path, "w") as f:
                    f.write("1")
                logger.info("[FROZEN] %s → 0%% CPU (cgroup.freeze=1)", container_name)
            except OSError as e:
                logger.error("Failed to freeze %s: %s", container_name, e)
                return

        self._state[container_id]["frozen"] = True
        self._state[container_id]["frozen_at"] = time.time()

    def _thaw(self, container_id: str, reason: str = ""):
        """Write 0 to cgroup.freeze to resume container (sub-1ms)."""
        # Always update internal state first — even if the file doesn't exist
        # (e.g. dry_run mode, dev machine, or container already removed)
        self._state[container_id]["frozen"] = False
        self._state[container_id]["frozen_at"] = 0.0

        freeze_path = self._get_freeze_path(container_id)
        if not freeze_path:
            logger.debug("No cgroup.freeze path for %s — state updated only", container_id[:12])
            return

        if self._dry_run:
            logger.info("[DRY-RUN] Would THAW %s (reason: %s)", container_id[:12], reason)
        else:
            try:
                with open(freeze_path, "w") as f:
                    f.write("0")
                logger.info("[THAWED] %s (reason: %s)", container_id[:12], reason)
            except OSError as e:
                logger.error("Failed to thaw %s: %s", container_id[:12], e)

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

    def is_frozen(self, container_id: str) -> bool:
        """Check if a container is currently frozen."""
        state = self._state.get(container_id)
        return state is not None and state.get("frozen", False)

    def thaw_all(self):
        """Emergency thaw: unfreeze all containers."""
        for cid, state in self._state.items():
            if state["frozen"]:
                self._thaw(cid, reason="emergency_thaw_all")

    def cleanup(self, active_containers_ids: set):
        """Remove state for disappeared containers."""
        dead = [cid for cid in self._state if cid not in active_containers_ids]
        for cid in dead:
            if self._state[cid]["frozen"]:
                self._thaw(cid, reason="container_disappeared")
            del self._state[cid]

    def _check_populated(self, container_id: str):
        """
        Read cgroup.events 'populated' field (Gap #2).
        Returns True if populated (processes active), False if depopulated,
        None if cgroup.events is unavailable.
        """
        events_path = self._get_events_path(container_id)
        if not events_path:
            return None
        try:
            with open(events_path) as f:
                for line in f:
                    if line.startswith("populated"):
                        return int(line.split()[1]) == 1
        except (OSError, ValueError, IndexError):
            pass
        return None

    def _get_events_path(self, container_id: str) -> str:
        """Find the cgroup.events file for a container."""
        paths = [
            f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope/cgroup.events",
            f"/sys/fs/cgroup/docker/{container_id}/cgroup.events",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope/cgroup.events",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None
