# framework/security/coresident_placement.py
# Layer 3 Extension: Secure Co-resident Placement
# Architecture §10.4, PRD §12.4
#
# Multi-tenant-only module. Applies a co-residency-aware placement strategy
# to keep high-risk tenants away from sensitive ones, reducing side-channel exposure.
#
# COMPLIANCE NOTE (architecture.md §10.4):
# Literature specifies SecCPS (reinforcement learning) or SecCDS (genetic algorithm),
# both of which conflict with §5's "stdlib + NumPy only" constraint.
# This implementation uses a simple heuristic placement rule instead — compliant
# with constraints while still providing the co-residency awareness.
#
# Out of scope for the single-tenant home-server target in §2, but included
# for completeness per the architecture document.

import logging
from collections import defaultdict

logger = logging.getLogger("hecf.security.coresident")


class CoResidentPlacement:
    """
    Secure Co-resident Placement (heuristic, non-ML compliant version).
    
    Uses a simple risk-scoring heuristic instead of RL (SecCPS) or GA (SecCDS)
    to stay compliant with the stdlib + NumPy only constraint.
    
    For single-tenant deployments (§2 target), this module effectively no-ops.
    For multi-tenant, it provides placement recommendations based on
    container risk labels and isolation priorities.
    """

    # Risk levels for container classification
    RISK_LOW = "low"
    RISK_MEDIUM = "medium"
    RISK_HIGH = "high"

    def __init__(self, multi_tenant: bool = False):
        """
        Args:
            multi_tenant: If False, this module is a no-op (single-tenant mode).
        """
        self._multi_tenant = multi_tenant
        # container_name -> {"risk": str, "tenant": str, "sensitive": bool}
        self._container_profiles = {}
        # Groups that should NOT be co-resident
        self._isolation_pairs = []

        if multi_tenant:
            logger.info("Co-resident placement ENABLED (multi-tenant mode)")
        else:
            logger.info("Co-resident placement DISABLED (single-tenant mode)")

    def register_container(self, container_name: str, tenant: str = "default",
                           risk: str = "low", sensitive: bool = False):
        """
        Register a container's security profile for placement decisions.
        
        Args:
            container_name: Container name.
            tenant: Tenant identifier (for multi-tenant grouping).
            risk: Risk level — "low", "medium", or "high".
            sensitive: If True, this container handles sensitive data.
        """
        self._container_profiles[container_name] = {
            "risk": risk,
            "tenant": tenant,
            "sensitive": sensitive,
        }

    def add_isolation_rule(self, container_a: str, container_b: str):
        """
        Mark two containers as requiring isolation from each other.
        Used to prevent side-channel exposure between high-risk and sensitive.
        """
        self._isolation_pairs.append((container_a, container_b))

    def check_placement(self, container_name: str) -> dict:
        """
        Check if a container's current placement is safe.
        
        Returns:
            {"safe": bool, "warnings": list, "recommendation": str}
        """
        if not self._multi_tenant:
            return {"safe": True, "warnings": [], "recommendation": "single_tenant_mode"}

        profile = self._container_profiles.get(container_name)
        if not profile:
            return {"safe": True, "warnings": [], "recommendation": "unregistered"}

        warnings = []

        # Check isolation rules
        for a, b in self._isolation_pairs:
            if container_name in (a, b):
                other = b if container_name == a else a
                if other in self._container_profiles:
                    warnings.append(
                        f"co-resident with isolated pair: {other}"
                    )

        # Check if high-risk is co-resident with sensitive
        if profile["risk"] == self.RISK_HIGH:
            for name, other_profile in self._container_profiles.items():
                if name != container_name and other_profile.get("sensitive"):
                    if other_profile["tenant"] != profile["tenant"]:
                        warnings.append(
                            f"high-risk container co-resident with sensitive: {name}"
                        )

        safe = len(warnings) == 0
        return {
            "safe": safe,
            "warnings": warnings,
            "recommendation": "relocate" if not safe else "ok",
        }

    @property
    def is_active(self) -> bool:
        return self._multi_tenant
