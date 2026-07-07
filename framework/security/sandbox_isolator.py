# framework/security/sandbox_isolator.py
# Layer 4 Extension: Sandbox Threat Isolation & Freeze
# Architecture §10.5, PRD §12.5
#
# Independent trigger path from Micro-Freezing: if ebpf_sensor flags
# malware-like behavior (execution of unrecognized binary, anomalous
# syscall pattern), this module immediately freezes the offending container
# via the same cgroup.freeze mechanism, regardless of its energy state.
#
# Localizes a security incident at the kernel/scheduler level without
# requiring a full container restart or host-level intervention.

import os
import time
import logging

logger = logging.getLogger("hecf.security.sandbox")


class SandboxIsolator:
    """
    Sandbox Threat Isolation.
    
    Uses the same cgroup.freeze mechanism as the Micro-Freezer, but triggered
    by security signals (suspicious exec, anomalous syscalls) rather than
    idle-state energy optimization.
    
    The frozen container is kept in memory for forensic analysis — no data
    is lost and no restart is needed until an operator reviews the incident.
    """

    def __init__(self, ebpf_sensor=None, dry_run: bool = False):
        """
        Args:
            ebpf_sensor: Reference to EBPFSensor for threat detection signals.
            dry_run: If True, log actions but don't freeze containers.
        """
        self._ebpf_sensor = ebpf_sensor
        self._dry_run = dry_run
        # container_id -> {"isolated": bool, "reason": str, "timestamp": float}
        self._isolated = {}

        logger.info("Sandbox isolator initialized (dry_run=%s)", dry_run)

    def evaluate(self, container_name: str, container_id: str) -> dict:
        """
        Check if a container should be sandboxed due to security threats.
        
        Args:
            container_name: Human-readable name.
            container_id: Docker container long ID.
            
        Returns:
            {"action": str, "reason": str}
            action: "none", "isolate"
        """
        # Already isolated
        if container_id in self._isolated and self._isolated[container_id]["isolated"]:
            return {"action": "none", "reason": "already_isolated"}

        # Check eBPF sensor for suspicious activity
        if self._ebpf_sensor and self._ebpf_sensor.has_suspicious_activity(container_id):
            self._isolate(container_name, container_id, reason="suspicious_exec")
            return {
                "action": "isolate",
                "reason": "suspicious_exec_detected",
            }

        return {"action": "none", "reason": "clean"}

    def _isolate(self, container_name: str, container_id: str, reason: str):
        """Immediately freeze a container for security isolation."""
        freeze_path = self._get_freeze_path(container_id)

        if self._dry_run:
            logger.warning(
                "[DRY-RUN] Would SANDBOX-ISOLATE %s (reason: %s)",
                container_name, reason
            )
        elif freeze_path:
            try:
                with open(freeze_path, "w") as f:
                    f.write("1")
                logger.critical(
                    "🔒 [ISOLATED] %s SANDBOXED — reason: %s — "
                    "container frozen for forensic analysis",
                    container_name, reason
                )
            except OSError as e:
                logger.error("Failed to sandbox %s: %s", container_name, e)
                return
        else:
            logger.warning(
                "Cannot sandbox %s: cgroup.freeze path not found",
                container_name
            )
            return

        self._isolated[container_id] = {
            "isolated": True,
            "reason": reason,
            "timestamp": time.time(),
            "container_name": container_name,
        }

    def release(self, container_id: str, operator_approval: bool = False):
        """
        Release a sandboxed container (requires operator approval in production).
        
        Args:
            container_id: Docker container long ID.
            operator_approval: Must be True to release (safety interlock).
        """
        if not operator_approval:
            logger.warning(
                "Cannot release sandboxed container without operator approval"
            )
            return

        state = self._isolated.get(container_id)
        if not state or not state["isolated"]:
            return

        freeze_path = self._get_freeze_path(container_id)
        if freeze_path and not self._dry_run:
            try:
                with open(freeze_path, "w") as f:
                    f.write("0")
            except OSError as e:
                logger.error("Failed to release sandbox: %s", e)
                return

        logger.warning(
            "🔓 [RELEASED] %s released from sandbox (was isolated for: %s)",
            state.get("container_name", container_id[:12]),
            state.get("reason", "unknown")
        )
        self._isolated[container_id] = {"isolated": False, "reason": "", "timestamp": 0}

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

    def is_isolated(self, container_id: str) -> bool:
        """Check if a container is currently sandboxed."""
        state = self._isolated.get(container_id)
        return state is not None and state.get("isolated", False)

    def get_incidents(self) -> list:
        """Return list of all current security incidents."""
        return [
            {
                "container_id": cid,
                "container_name": state.get("container_name", "unknown"),
                "reason": state.get("reason", ""),
                "timestamp": state.get("timestamp", 0),
            }
            for cid, state in self._isolated.items()
            if state.get("isolated", False)
        ]

    def cleanup(self, active_containers_ids: set):
        """Remove state for disappeared containers (auto-release)."""
        dead = [cid for cid in self._isolated if cid not in active_containers_ids]
        for cid in dead:
            del self._isolated[cid]
