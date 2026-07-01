# framework/profiler.py
# Layer 1: Environment Profiler
# Reads host capacity and performs auto-discovery + tagging.

import os
import socket
import logging
import docker

from .config import EXCLUDED_CONTAINERS

logger = logging.getLogger("hecf.profiler")


def profile_host() -> dict:
    """Read CPU and RAM capacity from /proc filesystem."""
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