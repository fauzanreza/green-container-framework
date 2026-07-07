# framework/security/edos_guard.py
# Layer 3 Extension: Anti-EDoS Logic
# Architecture §10.4, PRD §12.4
#
# If Layer 2 flags incoming load as DDoS-sourced, Layer 3 does NOT fall back
# to passive throttling (which would help the attacker degrade SLA cheaply).
# Instead it instructs Layer 4 to isolate/freeze the specific container.
#
# Prevents HECF's own adaptive throttling from being weaponized into an
# Economic Denial of Sustainability (EDoS) attack.

import logging

logger = logging.getLogger("hecf.security.edos_guard")


class EDoSGuard:
    """
    Anti-EDoS (Economic Denial of Sustainability) Logic.
    
    When a container is under DDoS attack (detected by ddos_filter.py),
    this module overrides the normal Guardrail/Tier throttling path and
    instead instructs the shaper to isolate/freeze the container.
    
    Rationale: passive throttling under an active DDoS just helps the
    attacker convert the flood into an EDoS attack on the operator's
    energy bill — the server wastes CPU processing garbage while
    legitimate requests get degraded.
    """

    def __init__(self, ddos_filter=None):
        """
        Args:
            ddos_filter: Reference to DDoSFilter instance from Layer 2.
        """
        self._ddos_filter = ddos_filter
        # container_name -> {"isolated": bool, "reason": str}
        self._isolation_state = {}
        logger.info("Anti-EDoS guard initialized")

    def evaluate(self, container_name: str, container_id: str,
                 priority: bool) -> dict:
        """
        Evaluate whether a container should be isolated due to EDoS conditions.
        
        Args:
            container_name: Human-readable name.
            container_id: Docker container long ID.
            priority: True if container is priority (databases).
            
        Returns:
            {"action": str, "reason": str}
            action is one of: "normal", "isolate", "freeze"
        """
        # Priority containers are never isolated by EDoS logic
        if priority:
            return {"action": "normal", "reason": "priority_exempt"}

        # Check DDoS status from Layer 2
        if self._ddos_filter and self._ddos_filter.is_under_attack(container_name):
            rate = self._ddos_filter.get_rate(container_name)
            logger.warning(
                "[EDoS] %s under attack (%.0f req/s) — instructing FREEZE "
                "instead of passive throttle",
                container_name, rate
            )
            self._isolation_state[container_name] = {
                "isolated": True,
                "reason": f"edos_defense:ddos_rate={rate:.0f}",
            }
            return {
                "action": "freeze",
                "reason": f"ddos_detected:{rate:.0f}req/s",
            }

        # No DDoS → allow normal Guardrail/Tier behavior
        if container_name in self._isolation_state:
            del self._isolation_state[container_name]

        return {"action": "normal", "reason": "no_attack"}

    def is_isolated(self, container_name: str) -> bool:
        """Check if a container is currently EDoS-isolated."""
        state = self._isolation_state.get(container_name)
        return state is not None and state.get("isolated", False)

    def cleanup(self, active_containers: set):
        """Remove state for disappeared containers."""
        dead = [n for n in self._isolation_state if n not in active_containers]
        for n in dead:
            del self._isolation_state[n]
