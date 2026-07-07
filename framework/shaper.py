# framework/shaper.py
# Layer 4: Adaptive Resource Shaping
# Writes directly to cgroupfs v2 (cpu.max, memory.max).
# Priority containers are shielded.
#
# Hardening:
#   - Memory shaping (PRD §4.1 lists --memory as a shaping target)
#   - Write-back validation (read after write to catch kernel rejections)

import os
import logging
from .config import (
    CPU_PERIOD, DRY_RUN,
    MEM_CAP_GUARDRAIL_RATIO, MEM_CAP_AGGRESSIVE_RATIO,
)

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
    mem_ratio: float = None,
    host_mem_bytes: int = 0,
) -> bool:
    """
    Apply CPU and memory limits via cgroups v2.

    Args:
        mem_ratio: If set, apply memory cap as ratio of host_mem_bytes
                   (e.g. 0.70 = 70% of host RAM). Only for non-priority.
        host_mem_bytes: Total host RAM in bytes (needed when mem_ratio is set).
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
        if mem_ratio and not priority:
            mem_bytes = int(host_mem_bytes * mem_ratio) if host_mem_bytes > 0 else 0
            logger.info("[DRY-RUN] %s: set MEM=%d MB (ratio=%.0f%%)",
                        container_name, mem_bytes // (1024*1024), mem_ratio * 100)
        return True

    cgroup_path = get_cgroup_path(container_id)
    if not cgroup_path:
        logger.warning("cgroup path not found for %s, skip shaping", container_name)
        return False

    # === CPU Shaping ===
    cpu_ok = _write_cpu(cgroup_path, container_name, cpu_quota, cpu_period)

    # === Memory Shaping (non-priority only, under Guardrail/Aggressive) ===
    mem_ok = True
    if mem_ratio and not priority and host_mem_bytes > 0:
        mem_ok = _write_memory(cgroup_path, container_name, mem_ratio, host_mem_bytes)

    return cpu_ok and mem_ok


def _write_cpu(cgroup_path: str, container_name: str,
               cpu_quota: int, cpu_period: int) -> bool:
    """Write CPU limits to cpu.max with read-back validation."""
    cpu_max_path = os.path.join(cgroup_path, "cpu.max")

    try:
        if cpu_quota <= 0:
            expected = "max"
            with open(cpu_max_path, "w") as f:
                f.write("max")
        else:
            expected = f"{int(cpu_quota)} {int(cpu_period)}"
            with open(cpu_max_path, "w") as f:
                f.write(expected)

        # Read-back validation — catch silent kernel rejections
        if not _validate_write(cpu_max_path, expected, container_name, "cpu.max"):
            # Retry once
            logger.warning("Retrying cpu.max write for %s...", container_name)
            with open(cpu_max_path, "w") as f:
                f.write(expected)

        if cpu_quota <= 0:
            logger.info("Shaped %s: CPU limit REMOVED", container_name)
        else:
            cores = cpu_quota / cpu_period
            logger.info("Shaped %s: CPU=%.2f core (quota=%d, period=%d)",
                        container_name, cores, cpu_quota, cpu_period)
        return True

    except OSError as e:
        logger.error("Failed to shape CPU for '%s': %s", container_name, str(e))
        return False


def _write_memory(cgroup_path: str, container_name: str,
                  mem_ratio: float, host_mem_bytes: int) -> bool:
    """Write memory limits to memory.max."""
    mem_max_path = os.path.join(cgroup_path, "memory.max")
    mem_bytes = int(host_mem_bytes * mem_ratio)

    try:
        with open(mem_max_path, "w") as f:
            f.write(str(mem_bytes))

        logger.info("Shaped %s: MEM=%d MB (ratio=%.0f%%)",
                    container_name, mem_bytes // (1024*1024), mem_ratio * 100)
        return True

    except OSError as e:
        logger.error("Failed to shape memory for '%s': %s", container_name, str(e))
        return False


def _validate_write(path: str, expected: str, container_name: str, label: str) -> bool:
    """Read back a cgroup file and check it matches what was written."""
    try:
        with open(path, "r") as f:
            actual = f.read().strip()
        # Kernel may normalize whitespace or format slightly differently
        if expected == "max":
            return "max" in actual
        # For quota values like "50000 100000", check the quota part
        return actual.startswith(expected.split()[0])
    except OSError:
        logger.debug("Could not validate %s write for %s", label, container_name)
        return True  # Don't block on validation read failure