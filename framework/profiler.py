# framework/profiler.py
# Layer 1: Environment Profiler
# Reads host capacity and performs auto-discovery + tagging.

import os
import socket
import logging
import docker

from .config import EXCLUDED_CONTAINERS, NETWORK_INFRA_PATTERNS, CONNTRACK_MIN

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

    # === Host /proc Mount Verification (Gap #7) ===
    os_cpu = os.cpu_count() or 1
    if cpu_count != os_cpu:
        logger.critical(
            "⚠ /proc MISMATCH: /proc/cpuinfo shows %d cores but os.cpu_count()=%d. "
            "Likely reading container's own /proc instead of host's. "
            "Ensure 'pid: host' is set in docker-compose.yml.",
            cpu_count, os_cpu
        )
    else:
        logger.info("Host /proc verification PASSED (cpu_count=%d matches os.cpu_count)", cpu_count)

    # === nf_conntrack_max Pre-flight (Gap #17) ===
    try:
        with open("/proc/sys/net/netfilter/nf_conntrack_max") as f:
            conntrack_max = int(f.read().strip())
        if conntrack_max < CONNTRACK_MIN:
            logger.warning(
                "⚠ nf_conntrack_max=%d < recommended %d — new connections may be "
                "silently dropped during traffic spikes. "
                "Fix: sysctl -w net.netfilter.nf_conntrack_max=%d",
                conntrack_max, CONNTRACK_MIN, CONNTRACK_MIN
            )
        else:
            logger.info("nf_conntrack_max check PASSED (%d >= %d)", conntrack_max, CONNTRACK_MIN)
    except OSError:
        logger.debug("nf_conntrack_max not readable — skipping pre-flight check")

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
    priority_map = {}
    try:
        if os.path.exists("/app/priority_map.json"):
            import json
            with open("/app/priority_map.json", "r") as f:
                priority_map = json.load(f)
    except Exception as e:
        logger.error("Failed to read priority_map.json: %s", str(e))

    for c in running:
        name = c.name
        if self_hostname in c.id:
            continue
        if name in EXCLUDED_CONTAINERS:
            logger.debug("Skipping excluded container: %s", name)
            continue
            
        mapped_prio = priority_map.get(name)
        if mapped_prio:
            priority = mapped_prio == "high"
        else:
            priority = c.labels.get("hecf.priority") == "high"

        # === Network-Infra Auto-Priority (Gap #15) ===
        if not priority:
            image_name = ""
            try:
                image_name = (c.image.tags[0] if c.image.tags else "").lower()
            except Exception:
                pass
            for pattern in NETWORK_INFRA_PATTERNS:
                if pattern in name.lower() or pattern in image_name:
                    priority = True
                    logger.info(
                        "[AUTO-PRIORITY] %s matched pattern '%s' — forced priority=True",
                        name, pattern
                    )
                    break

        targets[name] = {
            "id": c.id,
            "priority": priority,
            "pid": c.attrs.get("State", {}).get("Pid") if hasattr(c, 'attrs') else None
        }

    logger.info("Discovered %d target container(s)", len(targets))
    return targets