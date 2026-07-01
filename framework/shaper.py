# framework/shaper.py
# Layer 4: Adaptive Resource Shaping
# Writes directly to cgroupfs v2 (cpu.max). Priority containers are shielded.

import os
import logging
from .config import CPU_PERIOD, DRY_RUN

logger = logging.getLogger("hecf.shaper")


def get_cgroup_path(container_id: str) -> str:
    paths = [
        f"/sys/fs/cgroup/system.slice/docker-{container_id}.scope",
        f"/sys/fs/cgroup/docker/{container_id}",
        f"/sys/fs/cgroup/system.slice/docker.service/docker-{container_id}.scope"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def shape_container(
    container_name: str,
    container_id: str,
    priority: bool,
    cpu_quota: int,
    cpu_period: int = CPU_PERIOD,
    dry_run: bool = DRY_RUN,
) -> bool:
    """
    Apply CPU limits via cgroups v2.
    """
    # Priority containers are shielded from hard caps (except if unlimited/soft)
    if priority and cpu_quota > 0:
        logger.info("[SHIELD] %s is priority container, skipping hard cap.", container_name)
        return True

    if dry_run:
        if cpu_quota <= 0:
            logger.info("[DRY-RUN] %s: remove CPU limit", container_name)
        else:
            cores = cpu_quota / cpu_period
            logger.info("[DRY-RUN] %s: set CPU=%.2f core (quota=%d)", container_name, cores, cpu_quota)
        return True

    cgroup_path = get_cgroup_path(container_id)
    if not cgroup_path:
        logger.warning("cgroup path not found for %s, skip shaping", container_name)
        return False

    cpu_max_path = os.path.join(cgroup_path, "cpu.max")
    
    try:
        with open(cpu_max_path, "w") as f:
            if cpu_quota <= 0:
                f.write("max")
            else:
                f.write(f"{int(cpu_quota)} {int(cpu_period)}")
                
        if cpu_quota <= 0:
            logger.info("Shaped %s: CPU limit REMOVED", container_name)
        else:
            cores = cpu_quota / cpu_period
            logger.info("Shaped %s: CPU=%.2f core (quota=%d, period=%d)",
                        container_name, cores, cpu_quota, cpu_period)
        return True
    except OSError as e:
        logger.error("Failed to shape container '%s': %s", container_name, str(e))
        return False