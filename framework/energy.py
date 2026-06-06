# framework/energy.py
# Energy & Carbon Estimation
# Ref: Jarus et al. (2014) — model linear CPU-to-power, error < 4%
# Formula: P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)
# Ref proposal: P_idle=15W, P_max=65W (Intel i3 Gen 4, TDP-based)
# Carbon: CO2e(t) = E(t) × CI, CI=0.78 kg CO2e/kWh (PLN Indonesia)

from .config import P_IDLE, P_MAX, CARBON_INTENSITY


def estimate_power(cpu_percent: float) -> float:
    """
    Estimasi daya dalam Watt menggunakan model linear Jarus et al. (2014).
    P(t) = P_idle + (P_max - P_idle) × utilization
    Error model: < 4% pada berbagai kelas server HPC.
    """
    utilization = max(0.0, min(cpu_percent, 100.0)) / 100.0
    return round(P_IDLE + (P_MAX - P_IDLE) * utilization, 3)


def estimate_energy(power_watt: float, duration_seconds: float) -> float:
    """Energi dalam kWh: E = P × t / 3600000"""
    return round((power_watt * duration_seconds) / 3_600_000, 9)


def estimate_carbon(energy_kwh: float) -> float:
    """Emisi dalam kg CO2e: C = E × CI"""
    return round(energy_kwh * CARBON_INTENSITY, 6)


def estimate_all(cpu_percent: float, duration_seconds: float) -> dict:
    """Helper: hitung power, energy, carbon sekaligus."""
    power   = estimate_power(cpu_percent)
    energy  = estimate_energy(power, duration_seconds)
    carbon  = estimate_carbon(energy)
    return {
        "power_watt":  power,
        "energy_kwh":  energy,
        "carbon_kgco2": carbon,
    }