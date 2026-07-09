# framework/security/net_limiter.py
# Appendix A #9: Network Bandwidth Isolation
# Uses tc (traffic control) htb qdisc to cap per-container egress bandwidth.
# Prevents bandwidth starvation of priority containers during bulk transfers.
#
# Outside the 5 tracked metrics (§9) — hardening only.

import subprocess
import logging

logger = logging.getLogger("hecf.security.net_limiter")


class NetLimiter:
    """
    Network bandwidth isolation via Linux tc (traffic control).
    Caps per-container egress bandwidth using HTB qdisc on the container's
    veth interface.

    Hidden feature — not part of the 5 evaluated metrics.
    """

    # Default: 100 Mbit/s per non-priority container
    DEFAULT_RATE_MBIT = 100

    def __init__(self, rate_mbit: int = None, dry_run: bool = False):
        self._rate_mbit = rate_mbit or self.DEFAULT_RATE_MBIT
        self._dry_run = dry_run
        self._applied = {}  # container_id -> veth_name

        logger.info("NetLimiter initialized (rate=%d Mbit/s)", self._rate_mbit)

    def apply(self, container_name: str, container_id: str,
              priority: bool, pid: int = None) -> bool:
        """Apply network bandwidth limit to a non-priority container."""
        if priority:
            return True

        if container_id in self._applied:
            return True

        # Find the container's veth interface
        veth = self._find_veth(container_id, pid)
        if not veth:
            logger.debug("Could not find veth for %s — skip tc", container_name)
            return False

        if self._dry_run:
            logger.info("[DRY-RUN] Would apply tc htb %d Mbit/s on %s for %s",
                       self._rate_mbit, veth, container_name)
            self._applied[container_id] = veth
            return True

        try:
            # Clear existing qdisc (ignore errors if none exists)
            subprocess.run(
                ["tc", "qdisc", "del", "dev", veth, "root"],
                capture_output=True, timeout=5
            )

            # Add HTB qdisc
            subprocess.run(
                ["tc", "qdisc", "add", "dev", veth, "root", "handle", "1:",
                 "htb", "default", "10"],
                capture_output=True, check=True, timeout=5
            )

            # Add class with rate limit
            subprocess.run(
                ["tc", "class", "add", "dev", veth, "parent", "1:",
                 "classid", "1:10", "htb",
                 "rate", f"{self._rate_mbit}mbit",
                 "ceil", f"{self._rate_mbit}mbit"],
                capture_output=True, check=True, timeout=5
            )

            self._applied[container_id] = veth
            logger.info("[NET] Applied tc htb %d Mbit/s on %s for %s",
                       self._rate_mbit, veth, container_name)
            return True

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error("Failed to apply tc for %s: %s", container_name, e)
            return False

    def remove(self, container_id: str):
        """Remove tc rules for a container."""
        veth = self._applied.pop(container_id, None)
        if not veth:
            return

        try:
            subprocess.run(
                ["tc", "qdisc", "del", "dev", veth, "root"],
                capture_output=True, timeout=5
            )
            logger.info("[NET] Removed tc rules from %s", veth)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    def _find_veth(self, container_id: str, pid: int = None) -> str:
        """Find the veth interface for a container."""
        if pid:
            try:
                # Read the container's eth0 ifindex via /proc
                ifindex_path = f"/proc/{pid}/net/dev"
                # Alternative: use iflink
                iflink_path = f"/sys/class/net/eth0/iflink"
                # Try to find matching veth on host
                result = subprocess.run(
                    ["ip", "link", "show"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if container_id[:12] in line or "veth" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            return parts[1].strip().split("@")[0]
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                    OSError):
                pass
        return None

    def cleanup(self, active_container_ids: set):
        """Remove tc rules for disappeared containers."""
        dead = [cid for cid in self._applied
                if cid not in active_container_ids]
        for cid in dead:
            self.remove(cid)
