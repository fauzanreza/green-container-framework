# framework/security/duty_cycle_freezer.py
# Appendix A #7: Duty-Cycle Freeze (Aggressive)
# Rapid on/off freeze cycles for ACTIVE non-priority containers under Tier 1.
#
# Unlike Micro-Freezing (idle containers, energy saving), this is a
# defense/stability mechanism: caps aggregate CPU share of aggressive
# containers without hard quota, preserving their responsiveness during
# "on" windows while limiting their sustained impact.
#
# Pattern follows edos_guard.py ("freeze instead of throttle").

import os
import time
import logging
import threading

logger = logging.getLogger("hecf.security.duty_cycle_freezer")


class DutyCycleFreezer:
    """
    Duty-cycle freeze: rapid on/off cycles for active non-priority containers
    under Tier 1 (Aggressive). Not an energy metric — purely stability defense.

    Default cycle: 200ms frozen / 800ms running = 80% duty cycle.
    """

    def __init__(self, freeze_ms: float = 200.0, run_ms: float = 800.0,
                 dry_run: bool = False):
        self._freeze_ms = freeze_ms
        self._run_ms = run_ms
        self._dry_run = dry_run
        self._active_cycles = {}  # container_id -> threading.Event (stop signal)
        self._lock = threading.Lock()

        logger.info(
            "DutyCycleFreezer initialized (freeze=%dms, run=%dms, duty=%.0f%%)",
            freeze_ms, run_ms, (run_ms / (freeze_ms + run_ms)) * 100
        )

    def start_cycle(self, container_name: str, container_id: str):
        """Start duty-cycle freeze for a container."""
        with self._lock:
            if container_id in self._active_cycles:
                return  # Already cycling

            stop_event = threading.Event()
            self._active_cycles[container_id] = stop_event

        thread = threading.Thread(
            target=self._cycle_loop,
            args=(container_name, container_id, stop_event),
            daemon=True,
            name=f"hecf-duty-{container_name[:12]}"
        )
        thread.start()
        logger.info("[DUTY-CYCLE] Started for %s", container_name)

    def stop_cycle(self, container_id: str):
        """Stop duty-cycle freeze and ensure container is thawed."""
        with self._lock:
            stop_event = self._active_cycles.pop(container_id, None)

        if stop_event:
            stop_event.set()
            # Ensure container is thawed after stopping
            self._write_freeze(container_id, "0")
            logger.info("[DUTY-CYCLE] Stopped for %s", container_id[:12])

    def _cycle_loop(self, container_name: str, container_id: str,
                    stop_event: threading.Event):
        """Run freeze/thaw cycles until stopped."""
        while not stop_event.is_set():
            # Freeze phase
            self._write_freeze(container_id, "1")
            if stop_event.wait(self._freeze_ms / 1000.0):
                break
            # Run phase
            self._write_freeze(container_id, "0")
            if stop_event.wait(self._run_ms / 1000.0):
                break

        # Always thaw on exit
        self._write_freeze(container_id, "0")

    def _write_freeze(self, container_id: str, value: str):
        """Write to cgroup.freeze."""
        if self._dry_run:
            return

        freeze_path = self._get_freeze_path(container_id)
        if not freeze_path:
            return

        try:
            with open(freeze_path, "w") as f:
                f.write(value)
        except OSError:
            pass  # Silent — duty cycle is best-effort

    def _get_freeze_path(self, container_id: str) -> str:
        paths = [
            f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope/cgroup.freeze",
            f"/sys/fs/cgroup/docker/{container_id}/cgroup.freeze",
            f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope/cgroup.freeze",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def is_cycling(self, container_id: str) -> bool:
        with self._lock:
            return container_id in self._active_cycles

    def stop_all(self):
        """Stop all active duty cycles."""
        with self._lock:
            ids = list(self._active_cycles.keys())
        for cid in ids:
            self.stop_cycle(cid)

    def cleanup(self, active_container_ids: set):
        """Stop cycles for disappeared containers."""
        with self._lock:
            dead = [cid for cid in self._active_cycles
                    if cid not in active_container_ids]
        for cid in dead:
            self.stop_cycle(cid)
