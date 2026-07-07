# framework/security/privilege_guard.py
# Layer 1 Extension: Minimum Privileges Enforcement
# Architecture §10.2, PRD §12.2
#
# Reads each container's runtime privilege flags via Docker API.
# Rejects/flags any non-priority container requesting privileged mode.
# Shares the priority/non-priority tag from profiler.py — no new tagging system.
#
# Runs ONCE per container at cold start.

import logging

logger = logging.getLogger("hecf.security.privilege_guard")


class PrivilegeGuard:
    """
    Minimum Privileges Enforcement.
    
    Checks that non-priority containers are NOT running with host-root
    privileges. Shrinks blast radius if a frontend container is compromised.
    
    Priority containers (e.g. databases) are allowed to run privileged
    since they may need it for legitimate I/O operations.
    """

    def __init__(self, enforce: bool = True):
        """
        Args:
            enforce: If True, flagged containers are excluded from management.
                     If False, flagged containers are warned but still managed.
        """
        self._enforce = enforce
        self._checked = {}  # container_id -> {"safe": bool, "reason": str}
        logger.info("Privilege guard initialized (enforce=%s)", enforce)

    def check_container(self, container_name: str, container_id: str,
                        priority: bool, privileged: bool = False,
                        cap_add: list = None) -> dict:
        """
        Check a container's privilege level.
        Called once per container at Layer 1 discovery.

        Args:
            container_name: Human-readable name.
            container_id: Docker container long ID.
            priority: True if container is tagged as priority.
            privileged: True if container runs with --privileged flag.
            cap_add: List of added Linux capabilities (e.g. ["SYS_ADMIN"]).

        Returns:
            {"safe": bool, "reason": str, "warnings": list}
        """
        if container_id in self._checked:
            return self._checked[container_id]

        warnings = []

        # Priority containers are allowed to run privileged
        if priority:
            result = {"safe": True, "reason": "priority_exempt", "warnings": []}
            self._checked[container_id] = result
            logger.debug("[EXEMPT] %s is priority — privilege check skipped", container_name)
            return result

        # Non-priority: check for privileged mode
        if privileged:
            warnings.append("non-priority container running with --privileged")
            logger.warning(
                "[PRIVILEGE] %s: non-priority container running PRIVILEGED — "
                "this increases blast radius if compromised",
                container_name
            )

        # Check for dangerous capabilities
        dangerous_caps = {"SYS_ADMIN", "SYS_PTRACE", "NET_ADMIN", "SYS_RAWIO"}
        if cap_add:
            risky = set(cap_add) & dangerous_caps
            if risky:
                warnings.append(f"dangerous capabilities: {risky}")
                logger.warning(
                    "[PRIVILEGE] %s: has dangerous capabilities %s",
                    container_name, risky
                )

        safe = len(warnings) == 0
        result = {
            "safe": safe,
            "reason": "clean" if safe else "privilege_violation",
            "warnings": warnings,
        }
        self._checked[container_id] = result

        if safe:
            logger.info("[SAFE] %s passes privilege check", container_name)

        return result

    def should_exclude(self, container_id: str) -> bool:
        """
        Returns True if the container should be excluded from HECF management
        due to privilege violations (only when enforce=True).
        """
        if not self._enforce:
            return False
        cached = self._checked.get(container_id)
        if cached is None:
            return False
        return not cached["safe"]
