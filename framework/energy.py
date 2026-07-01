# framework/energy.py
# Energy Estimation
# Ref: Jarus et al. (2014) — linear CPU-to-power model, error < 4%
# Formula: P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)
# Carbon conversion explicitly removed as per Batasan Penelitian (PRD §1.6)

from .config import P_IDLE_WATTS, P_MAX_WATTS


def estimate_power(cpu_percent: float) -> float:
    """
    Estimate power in Watts using linear model.
    P(t) = P_idle + (P_max - P_idle) × utilization
    """
    utilization = max(0.0, min(cpu_percent, 100.0)) / 100.0
    return round(P_IDLE_WATTS + (P_MAX_WATTS - P_IDLE_WATTS) * utilization, 3)


def estimate_energy(power_watt: float, duration_seconds: float) -> float:
    """Energy in kWh: E = P × t / 3600000"""
    return round((power_watt * duration_seconds) / 3_600_000, 9)


def estimate_all(cpu_percent: float, duration_seconds: float) -> dict:
    """Helper: calculates power and energy (no carbon tracking)."""
    power   = estimate_power(cpu_percent)
    energy  = estimate_energy(power, duration_seconds)
    return {
        "power_watt": power,
        "energy_kwh": energy
    }