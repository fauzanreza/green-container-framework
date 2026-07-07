# framework/security/encryption_calc.py
# Layer 3 Extension: Dynamic Encryption Cost Calculator
# Architecture §10.4, PRD §12.4
#
# Estimates CPU cost of hybrid encryption (AES-RSA / AES-ECC / ABE) for
# inter-container data transfers. Feeds the estimate into Layer 3's constraint
# calculation BEFORE the transfer is greenlit.
#
# Keeps encrypted data-in-transit from silently pushing a low-spec host
# over its CPU budget.
#
# Invoked only at the moment of an actual transfer — NOT every polling cycle
# (prd.md §12.8 overhead defense).

import logging

logger = logging.getLogger("hecf.security.encryption_calc")

# Empirical CPU cost estimates per MB of data (percentage of 1 core-second)
# These are conservative estimates for entry-level server hardware.
_ENCRYPTION_COST_TABLE = {
    "none":     0.0,
    "aes_rsa":  0.15,   # AES-256-CBC + RSA-2048: ~0.15% CPU per MB
    "aes_ecc":  0.08,   # AES-256-GCM + ECC-P256: ~0.08% CPU per MB  
    "abe":      0.35,   # Attribute-Based Encryption: ~0.35% CPU per MB
}


class EncryptionCostCalculator:
    """
    Dynamic encryption cost estimator.
    
    Before any inter-container data transfer, estimates the CPU overhead
    of encrypting the payload and checks if the host has budget for it.
    
    Prevents encrypted transfers from silently blowing the host's CPU budget
    on a resource-constrained server.
    """

    def __init__(self, mode: str = "none", host_cpu_count: int = 1):
        """
        Args:
            mode: Encryption mode — "none", "aes_rsa", "aes_ecc", or "abe".
            host_cpu_count: Number of host CPU cores (for budget calculation).
        """
        self._mode = mode if mode in _ENCRYPTION_COST_TABLE else "none"
        self._host_cpu_count = max(1, host_cpu_count)
        logger.info(
            "Encryption cost calculator initialized (mode=%s, host_cpus=%d)",
            self._mode, self._host_cpu_count
        )

    def estimate_cost(self, data_size_mb: float) -> dict:
        """
        Estimate CPU cost of encrypting a data transfer.
        
        Args:
            data_size_mb: Size of data to encrypt in megabytes.
            
        Returns:
            {"cpu_cost_percent": float, "duration_estimate_ms": float,
             "mode": str, "affordable": bool}
        """
        cost_per_mb = _ENCRYPTION_COST_TABLE.get(self._mode, 0.0)
        total_cost = cost_per_mb * data_size_mb

        # Estimate time in ms (assuming 1 core dedicated)
        # Cost is % of 1 core-second, so 0.15% for 1MB ≈ 1.5ms
        duration_ms = total_cost * 10.0  # rough conversion

        # Check if affordable within 5% overhead budget across all cores
        max_budget_percent = 5.0 * self._host_cpu_count
        affordable = total_cost < max_budget_percent

        result = {
            "cpu_cost_percent": round(total_cost, 4),
            "duration_estimate_ms": round(duration_ms, 2),
            "mode": self._mode,
            "data_size_mb": data_size_mb,
            "affordable": affordable,
        }

        if not affordable:
            logger.warning(
                "[ENCRYPTION] Transfer of %.1f MB with %s would cost %.2f%% CPU — "
                "exceeds budget (max %.1f%%)",
                data_size_mb, self._mode, total_cost, max_budget_percent
            )
        else:
            logger.debug(
                "[ENCRYPTION] Transfer of %.1f MB with %s: %.2f%% CPU, ~%.1fms",
                data_size_mb, self._mode, total_cost, duration_ms
            )

        return result

    def is_transfer_safe(self, data_size_mb: float,
                         current_cpu_percent: float = 0.0) -> bool:
        """
        Quick check: can we afford this encrypted transfer right now?
        
        Args:
            data_size_mb: Size of data to encrypt.
            current_cpu_percent: Current host CPU utilization.
        """
        if self._mode == "none":
            return True

        estimate = self.estimate_cost(data_size_mb)
        headroom = 100.0 - current_cpu_percent
        return estimate["cpu_cost_percent"] < headroom

    @property
    def mode(self) -> str:
        return self._mode
