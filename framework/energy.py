# framework/energy.py
# Energy Estimation
# Ref: Jarus et al. (2014) — linear CPU-to-power model, error < 4%
# Formula: P(t) = P_idle + (P_max - P_idle) × CPU_utilization(t)
# Carbon conversion explicitly removed as per Batasan Penelitian (PRD §1.6)

def estimate_power(cpu_percent: float, p_idle: float, p_max: float, hw_power: float = None, cpu_count: int = 1) -> float:
    """
    Estimate power in Watts using either Hardware Apportionment or Linear Software Model.
    """
    if hw_power is not None and hw_power > 0:
        # Hardware-True: Proportional Power Apportionment
        # Container Power = Total HW Power * (Container CPU / Total CPU Capacity)
        total_capacity = float(cpu_count * 100.0)
        fraction = max(0.0, cpu_percent) / total_capacity
        return round(hw_power * fraction, 3)
    else:
        # Software Fallback: Linear Model
        # P(t) = P_idle + (P_max - P_idle) × utilization
        utilization = max(0.0, min(cpu_percent, 100.0)) / 100.0
        return round(p_idle + (p_max - p_idle) * utilization, 3)


def estimate_energy(power_watt: float, duration_seconds: float) -> float:
    """Energy in kWh: E = P × t / 3600000"""
    return round((power_watt * duration_seconds) / 3_600_000, 9)


def estimate_all(cpu_percent: float, duration_seconds: float, p_idle: float, p_max: float, hw_power: float = None, cpu_count: int = 1) -> dict:
    """Helper: calculates power and energy (no carbon tracking)."""
    power   = estimate_power(cpu_percent, p_idle, p_max, hw_power, cpu_count)
    energy  = estimate_energy(power, duration_seconds)
    return {
        "power_watt": power,
        "energy_kwh": energy
    }