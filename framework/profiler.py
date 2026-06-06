# framework/profiler.py
# Layer 1: Environment Profiler
# Ref: Kaiser et al. (2023), Mahmud & Toosi (2021)
# Membaca kapasitas hardware host dari /proc/cpuinfo dan /proc/meminfo.
# Juga melakukan auto-discovery container yang aktif (exclude blacklist).

import os
import socket
import logging
import docker

from .config import EXCLUDED_CONTAINERS

logger = logging.getLogger("hgcf.profiler")


def profile_host() -> dict:
    """
    Baca kapasitas CPU dan RAM host dari /proc filesystem.
    Dijalankan sekali saat framework start.
    """
    # CPU count dari /proc/cpuinfo
    try:
        with open("/proc/cpuinfo") as f:
            cpu_count = sum(1 for line in f if line.strip().startswith("processor"))
    except OSError:
        cpu_count = os.cpu_count() or 1

    # RAM dari /proc/meminfo
    mem_total_kb = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total_kb = int(line.split()[1])
                    break
    except OSError:
        pass

    mem_total_mb = mem_total_kb // 1024

    profile = {
        "hostname":     socket.gethostname(),
        "cpu_count":    cpu_count,
        "mem_total_mb": mem_total_mb,
    }

    logger.info(
        "Host profile: hostname=%s, CPU=%d cores, RAM=%d MB",
        profile["hostname"], profile["cpu_count"], profile["mem_total_mb"]
    )
    return profile


def discover_containers() -> list:
    """
    Auto-discover semua container yang sedang running,
    kecuali yang ada di EXCLUDED_CONTAINERS.
    Juga exclude diri sendiri (container HGCF itu sendiri).
    """
    # Hostname container HGCF = container ID (Docker default)
    self_hostname = socket.gethostname()

    try:
        client = docker.from_env()
        running = client.containers.list()
    except Exception as e:
        logger.error("Gagal koneksi Docker daemon: %s", str(e))
        return []

    targets = []
    for c in running:
        name = c.name
        # Skip diri sendiri
        if self_hostname in c.id:
            continue
        # Skip blacklist
        if name in EXCLUDED_CONTAINERS:
            logger.debug("Skip excluded container: %s", name)
            continue
        targets.append(name)

    logger.info("Discovered %d target container(s): %s", len(targets), targets)
    return targets