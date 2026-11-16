# framework/energy.py
# Energy Estimation — Multi-Component Additive Model (CPU + DRAM)
# Ref:
#   1. Jarus et al. (2014) — linear CPU-to-power model
#   2. Kansal et al. (Joulemeter, ACM SIGMETRICS) & CNCF Kepler — DRAM power modeling (~0.38 W/GB for DDR3/DDR4)
# Formula:
#   P_cpu(t)   = P_idle + (P_max - P_idle) × CPU_utilization(t)
#   P_dram(t)  = RAM_used_GB(t) × P_dram_per_gb
#   P_total(t) = P_cpu(t) + P_dram(t)
# Carbon conversion explicitly removed as per Batasan Penelitian (PRD §1.6)

def estimate_power(cpu_percent: float, p_idle: float, p_max: float,
                    hw_power: float = None, cpu_count: int = 1,
                    is_frozen: bool = False,
                    memory_bytes: int = 0,
                    p_dram_per_gb: float = 0.38) -> float:
    """
    Estimate total container power in Watts using an additive multi-component model:
        P_total(t) = P_cpu(t) + P_dram(t)

    Where:
        P_cpu(t) is calculated via Hardware Apportionment (RAPL) or Linear Model (Jarus et al., 2014).
        P_dram(t) is calculated as RAM_used_GB × p_dram_per_gb (Kansal et al., CNCF Kepler default 0.38 W/GB).

    Args:
        cpu_percent: Container CPU usage percentage (e.g. 50.0 for 50%).
        p_idle: Baseline idle host power in Watts.
        p_max: Maximum host power in Watts.
        hw_power: Physical sensor power in Watts (if available).
        cpu_count: Physical core count of the host.
        is_frozen: If True, container is in Micro-Freeze state. Frozen containers consume 0% CPU,
                   returning p_idle as CPU baseline + active DRAM retention power.
        memory_bytes: Container working set memory in bytes (from cgroup memory.current - inactive_file).
        p_dram_per_gb: Active DRAM power draw coefficient (Watts per GB).
    """
    # Calculate DRAM active footprint (Kansal et al. / Kepler standard ~0.38W/GB)
    ram_gb = max(0.0, float(memory_bytes)) / (1024.0 ** 3)
    p_dram = ram_gb * p_dram_per_gb

    if hw_power is not None and hw_power > 0:
        # Hardware-True: Proportional Power Apportionment (RAPL)
        # Container_Power = Total_HW_Watts * (Container_CPU% / Total_CPU_Capacity) + P_dram(t)
        total_capacity = float(max(1, cpu_count) * 100.0)
        if is_frozen:
            fraction = 0.0
        else:
            fraction = max(0.0, cpu_percent) / total_capacity
        
        calculated_cpu = hw_power * fraction
        return round(calculated_cpu + p_dram, 3)

    # Micro-Frozen container = 0% CPU. In software fallback (lacking physical sensors),
    # fall back to the host's idle power as the baseline CPU footprint + DRAM retention power.
    if is_frozen:
        return round(p_idle + p_dram, 3)
    else:
        # Software Fallback: Additive Linear Model (Jarus et al. + Kansal et al.)
        # P_cpu(t) = P_idle + (P_max - P_idle) × utilization
        utilization = max(0.0, min(cpu_percent, 100.0)) / 100.0
        calculated_cpu = p_idle + (p_max - p_idle) * utilization
        if calculated_cpu <= 0.0:
            calculated_cpu = p_idle
        return round(calculated_cpu + p_dram, 3)


def estimate_energy(power_watt: float, duration_seconds: float) -> float:
    """Energy in kWh: E = P × t / 3600000"""
    return round((power_watt * duration_seconds) / 3_600_000, 9)


def estimate_all(cpu_percent: float, duration_seconds: float, p_idle: float, p_max: float,
                  hw_power: float = None, cpu_count: int = 1,
                  is_frozen: bool = False,
                  memory_bytes: int = 0,
                  p_dram_per_gb: float = 0.38) -> dict:
    """
    Helper: calculates power and energy (no carbon tracking).
    Returns dict with total power, energy, and individual CPU/DRAM power components.
    """
    ram_gb = max(0.0, float(memory_bytes)) / (1024.0 ** 3)
    p_dram = round(ram_gb * p_dram_per_gb, 3)
    power = estimate_power(
        cpu_percent, p_idle, p_max, hw_power, cpu_count, is_frozen, memory_bytes, p_dram_per_gb
    )
    p_cpu = round(max(0.0, power - p_dram), 3)
    energy = estimate_energy(power, duration_seconds)
    return {
        "power_watt": power,
        "energy_kwh": energy,
        "p_cpu_watt": p_cpu,
        "p_dram_watt": p_dram,
    }