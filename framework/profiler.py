# framework/profiler.py
# Layer 1: Environment Profiler
# Reads host capacity and performs auto-discovery + tagging.

import os
import socket
import logging
import docker

from .config import EXCLUDED_CONTAINERS

logger = logging.getLogger("hecf.profiler")


from .hardware_sensor import PowerSensor

def profile_host() -> dict:
    """Read CPU and RAM capacity from /proc filesystem and detect hardware sensors."""
    try:
        with open("/proc/cpuinfo") as f:
            cpu_count = sum(1 for line in f if line.strip().startswith("processor"))
    except OSError:
        cpu_count = os.cpu_count() or 1

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

    # Calculate dynamic power estimation constants
    # Using 3.75W idle and 13.5W max per core as a baseline multiplier (scales to 15W/54W for 4 cores)
    p_idle_watts = round(cpu_count * 3.75, 1)
    p_max_watts = round(cpu_count * 13.5, 1)

    # Initialize Hardware Power Sensor (Layer 1 Hybrid)
    hw_sensor = PowerSensor()

    profile = {
        "hostname":     socket.gethostname(),
        "cpu_count":    cpu_count,
        "mem_total_mb": mem_total_mb,
        "p_idle_watts": p_idle_watts,
        "p_max_watts": p_max_watts,
        "hw_sensor":    hw_sensor,
    }

    logger.info(
        "Host profile: hostname=%s, CPU=%d cores, RAM=%d MB, P_idle=%.1fW, P_max=%.1fW, HW_Sensor=%s",
        profile["hostname"], profile["cpu_count"], profile["mem_total_mb"],
        profile["p_idle_watts"], profile["p_max_watts"], hw_sensor.available
    )
    return profile


def discover_containers() -> dict:
    """
    Auto-discover all running containers, filter excluded ones.
    Returns: dict mapping container_name to metadata:
      {
         "name1": {"id": "long_id", "priority": False},
         ...
      }
    """
    self_hostname = socket.gethostname()

    try:
        client = docker.from_env()
        running = client.containers.list()
    except Exception as e:
        logger.error("Failed to connect to Docker daemon: %s", str(e))
        return {}

    targets = {}
    for c in running:
        name = c.name
        if self_hostname in c.id:
            continue
        if name in EXCLUDED_CONTAINERS:
            logger.debug("Skipping excluded container: %s", name)
            continue
            
        priority = c.labels.get("hecf.priority") == "high"
        targets[name] = {
            "id": c.id,
            "priority": priority
        }

    logger.info("Discovered %d target container(s)", len(targets))
    return targets