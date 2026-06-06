# framework/monitor.py
# Layer 2: Monitoring Engine
# Ref: Dinga et al. (2023) — overhead monitoring < 5%
# Adaptive sampling: 10s saat CPU tinggi, 30s saat normal

import docker
from .config import CPU_HIGH_THRESHOLD_SAMPLE, SAMPLING_INTERVAL_NORMAL, SAMPLING_INTERVAL_HIGH


def get_container_stats(container_name: str) -> dict:
    """
    Ambil statistik CPU dan memori dari Docker Stats API.
    Mengembalikan dict dengan cpu_percent, mem_percent, dll.
    Mengembalikan None jika container tidak ditemukan atau error stats.
    """
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        return None

    try:
        raw = container.stats(stream=False)
    except Exception:
        return None

    # === CPU % Calculation ===
    # Ref: Docker Stats API documentation
    # Perlu guard: precpu_stats bisa kosong di sample pertama
    try:
        cpu_delta = (
            raw["cpu_stats"]["cpu_usage"]["total_usage"]
            - raw["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            raw["cpu_stats"].get("system_cpu_usage", 0)
            - raw["precpu_stats"].get("system_cpu_usage", 0)
        )
        # percpu_usage bisa tidak ada di beberapa versi Docker (cgroups v2)
        num_cpus = len(
            raw["cpu_stats"]["cpu_usage"].get("percpu_usage") or [1]
        )
        if system_delta > 0 and cpu_delta >= 0:
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
        else:
            cpu_percent = 0.0
    except (KeyError, ZeroDivisionError, TypeError):
        cpu_percent = 0.0

    # === Memory % Calculation ===
    try:
        mem_stats = raw.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        # 'cache' perlu dikurangi di cgroups v1 agar akurat
        cache = mem_stats.get("stats", {}).get("cache", 0)
        mem_usage = max(0, mem_usage - cache)
        mem_limit = mem_stats.get("limit", 1)
        mem_percent = (mem_usage / mem_limit * 100.0) if mem_limit > 0 else 0.0
    except (KeyError, ZeroDivisionError, TypeError):
        mem_percent = 0.0
        mem_usage = 0
        mem_limit = 1

    return {
        "name":        container_name,
        "cpu_percent": round(cpu_percent, 2),
        "mem_percent": round(mem_percent, 2),
        "mem_usage":   mem_usage,
        "mem_limit":   mem_limit,
    }


def get_adaptive_interval(cpu_percent: float) -> int:
    """
    Adaptive sampling interval.
    Ref: Dinga et al. (2023) — frekuensi monitoring dijaga overhead < 5%
    CPU tinggi → sampling lebih sering untuk guardrail responsif.
    """
    if cpu_percent >= CPU_HIGH_THRESHOLD_SAMPLE:
        return SAMPLING_INTERVAL_HIGH
    return SAMPLING_INTERVAL_NORMAL