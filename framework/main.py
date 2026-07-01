# framework/main.py
# HECF Entry Point — Main Control Loop

import os
import time
import logging
import csv
import json

from .profiler      import profile_host, discover_containers
from .monitor       import Monitor, get_adaptive_interval
from .guardrail     import Guardrail
from .tier_detector import TierDetector
from .predictor     import EMAPredictor
from .shaper        import shape_container
from .energy        import estimate_all
from .overhead_tracker import OverheadTracker
from .config        import (
    SAMPLING_INTERVAL_LOW,
    CPU_QUOTA_GUARDRAIL,
    CPU_QUOTA_AGGRESSIVE,
    CPU_QUOTA_BALANCED,
    CPU_QUOTA_SOFT,
    STATIC_CAP_QUOTA,
    DRY_RUN,
    MODE
)

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hecf.main")


def main():
    logger.info("=" * 60)
    logger.info("HECF v2.0 — Hybrid Energy-Aware Container Framework")
    logger.info("MODE: %s", MODE)
    if DRY_RUN:
        logger.info("[DRY RUN] No actual resource changes will be applied.")
    logger.info("=" * 60)

    # === Layer 1: Environment Profiler ===
    host_profile = profile_host()

    # === CSV Initialization ===
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")
    csv_is_new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if csv_is_new:
            writer.writerow([
                "time", "container_name", "cpu_percent", "mem_percent", 
                "tier", "action", "power_watt", "energy_kwh", 
                "ema_pred", "alpha", "spike_ratio", "p50", "p95", 
                "overhead_cpu", "overhead_mem"
            ])

    # === Initialize Components ===
    monitor = Monitor()
    guardrail = Guardrail()
    tier_detector = TierDetector()
    predictor = EMAPredictor()
    overhead_tracker = OverheadTracker()

    current_interval = SAMPLING_INTERVAL_LOW
    logger.info("Framework started. Waiting %d seconds for first sample...", current_interval)

    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "framework_status.json")

    while True:
        # Dashboard toggle
        is_active = True
        if os.path.exists(status_file):
            try:
                with open(status_file, "r") as sf:
                    st = json.load(sf)
                    is_active = st.get("active", True)
            except:
                pass

        time.sleep(current_interval)

        # Layer 1/2: Discover containers & tags
        env_targets = os.getenv("HECF_TARGETS", "").strip()
        targets_meta = discover_containers()
        
        if env_targets:
            allowed = [t.strip() for t in env_targets.split(",") if t.strip()]
            targets_meta = {k: v for k, v in targets_meta.items() if k in allowed}

        if not targets_meta:
            logger.warning("No target containers discovered. Waiting %ds...", current_interval)
            continue

        max_cpu_seen = 0.0
        overhead = overhead_tracker.get_overhead()

        for name, meta in targets_meta.items():
            cid = meta["id"]
            priority = meta["priority"]

            # Layer 2: Monitor
            stats = monitor.get_stats(name, cid)
            if not stats:
                logger.debug("Failed to read stats for %s, skipping", name)
                continue

            cpu = stats["cpu_percent"]
            mem = stats["mem_percent"]
            max_cpu_seen = max(max_cpu_seen, cpu)

            # Layer 3B & 3C
            tier_detector.add_sample(name, cpu)
            tier_int = tier_detector.get_tier(name)
            tier_stats = tier_detector.get_stats(name)
            
            ema_pred = predictor.update(name, cpu)
            alpha = predictor.get_alpha(name)

            # Layer 3A
            guardrail_active = guardrail.update(name, cpu, mem)

            # Mode Selection Logic
            action = "OBSERVE"
            quota = -1
            
            if not is_active or MODE == "default_docker":
                action = "OBSERVE"
                quota = CPU_QUOTA_SOFT
                tier_str = "N/A"
            elif MODE == "static_cap":
                action = "STATIC"
                quota = STATIC_CAP_QUOTA
                tier_str = "N/A"
            elif MODE == "reactive_only":
                tier_str = "N/A"
                if guardrail_active:
                    action = "GUARDRAIL"
                    quota = CPU_QUOTA_GUARDRAIL
                else:
                    action = "SOFT"
                    quota = CPU_QUOTA_SOFT
            else:
                # full_hecf
                tier_map = {1: "AGGRESSIVE", 2: "BALANCED", 3: "SOFT"}
                tier_str = tier_map.get(tier_int, "SOFT")
                
                if guardrail_active:
                    action = "GUARDRAIL"
                    quota = CPU_QUOTA_GUARDRAIL
                elif tier_int == 1:
                    action = "AGGRESSIVE"
                    quota = CPU_QUOTA_AGGRESSIVE
                elif tier_int == 2:
                    action = "BALANCED"
                    quota = CPU_QUOTA_BALANCED
                else:
                    action = "SOFT"
                    quota = CPU_QUOTA_SOFT

            # Layer 4: Shaper
            shape_container(name, cid, priority, quota)

            # Energy Estimator
            energy_data = estimate_all(cpu, current_interval)

            # Logging
            logger.info(
                "%s (Prio:%s) | CPU=%.1f%% MEM=%.1f%% | Tier=%s | "
                "EMA=%.1f | Action=%s | P=%.1fW | OH=%.1f%%",
                name, priority, cpu, mem, tier_str, 
                ema_pred, action, energy_data["power_watt"], overhead["cpu_percent"]
            )

            # CSV
            try:
                with open(csv_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        name,
                        f"{cpu:.1f}",
                        f"{mem:.1f}",
                        tier_str,
                        action,
                        f"{energy_data['power_watt']:.1f}",
                        f"{energy_data['energy_kwh']:.9f}",
                        f"{ema_pred:.1f}",
                        f"{alpha:.3f}",
                        f"{tier_stats['spike_ratio']:.2f}",
                        f"{tier_stats['p50']:.1f}",
                        f"{tier_stats['p95']:.1f}",
                        f"{overhead['cpu_percent']:.2f}",
                        f"{overhead['mem_usage_mb']:.2f}"
                    ])
            except Exception as e:
                logger.error("Failed writing to CSV: %s", e)

            if guardrail_active and MODE in ["reactive_only", "full_hecf"]:
                logger.warning("⚠ GUARDRAIL triggered for %s", name)

        current_interval = get_adaptive_interval(max_cpu_seen)


if __name__ == "__main__":
    main()