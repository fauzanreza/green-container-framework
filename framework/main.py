# framework/main.py
# HGCF Entry Point — Main Control Loop
# Menyatukan semua layer: Profiler → Monitor → Guardrail → TierDetector → AFMV → Shaper → Energy

import os
import time
import logging
import csv

from .profiler      import profile_host, discover_containers
from .monitor       import get_container_stats, get_adaptive_interval
from .guardrail     import Guardrail
from .tier_detector import TierDetector, TIER_AGGRESSIVE, TIER_BALANCED, TIER_SOFT
from .predictor     import AFMVPredictor
from .shaper        import shape_container
from .energy        import estimate_all
from .config        import (
    SAMPLING_INTERVAL_NORMAL,
    CPU_QUOTA_GUARDRAIL,
    CPU_QUOTA_AGGRESSIVE,
    CPU_QUOTA_BALANCED,
    CPU_QUOTA_SOFT,
    DRY_RUN,
)

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hgcf.main")


def main():
    logger.info("=" * 60)
    logger.info("HGCF v1.0 — Hybrid Green Container Framework")
    if DRY_RUN:
        logger.info("MODE: DRY RUN (tidak ada perubahan resource aktual)")
        logger.info("Set DRY_RUN=False di config.py setelah verifikasi log")
    logger.info("=" * 60)

    # === Layer 1: Environment Profiler ===
    host_profile = profile_host()

    # === CSV Initialization ===
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")
    csv_is_new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if csv_is_new:
            writer.writerow(["time", "container_name", "cpu_percent", "mem_percent", "tier", "action", "power_watt", "carbon_co2", "afmv_pred", "alpha", "spike_ratio", "p50", "p95"])

    # === Inisialisasi komponen Layer 3 ===
    guardrail    = Guardrail()
    tier_detector = TierDetector()
    predictor    = AFMVPredictor()

    # Interval awal sebelum ada data CPU
    current_interval = SAMPLING_INTERVAL_NORMAL

    logger.info("Framework started. Menunggu %d detik sebelum sampling pertama...", current_interval)

    # Flag for UI toggle
    status_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "framework_status.json")
    import json

    while True:
        # Check toggle status
        is_active = True
        if os.path.exists(status_file):
            try:
                with open(status_file, "r") as sf:
                    st = json.load(sf)
                    is_active = st.get("active", True)
            except:
                pass

        time.sleep(current_interval)

        # === Layer 2: Discover containers (setiap iterasi agar deteksi container baru) ===
        # Baca dari env var jika ada, otherwise auto-discover
        env_targets = os.getenv("HGCF_TARGETS", "").strip()
        if env_targets:
            target_names = [t.strip() for t in env_targets.split(",") if t.strip()]
        else:
            target_names = discover_containers()

        if not target_names:
            logger.warning("Tidak ada target container. Tunggu %ds...", current_interval)
            continue

        max_cpu_seen = 0.0

        for name in target_names:
            # === Layer 2: Monitor ===
            stats = get_container_stats(name)
            if stats is None:
                logger.debug("Container '%s' tidak bisa diread, skip", name)
                continue

            cpu = stats["cpu_percent"]
            mem = stats["mem_percent"]
            max_cpu_seen = max(max_cpu_seen, cpu)

            # === Layer 3B: Tier Detection (update window) ===
            tier_detector.add_sample(name, cpu)
            tier = tier_detector.get_tier(name)
            tier_stats = tier_detector.get_stats(name)

            # === Layer 3C: AFMV Prediction ===
            afmv_pred = predictor.update(name, cpu)
            alpha = predictor.get_alpha(name)

            # === Layer 3A: Real-time Guardrail ===
            guardrail_active = guardrail.update(name, cpu, mem)

            # === Layer 4: Adaptive Resource Shaping ===
            if not is_active:
                action = "INACTIVE"
                quota = CPU_QUOTA_SOFT
            elif guardrail_active:
                action = "GUARDRAIL"
                quota = CPU_QUOTA_GUARDRAIL
            elif tier == TIER_AGGRESSIVE:
                action = "AGGRESSIVE"
                quota = CPU_QUOTA_AGGRESSIVE
            elif tier == TIER_BALANCED:
                action = "BALANCED"
                quota = CPU_QUOTA_BALANCED
            else:  # TIER_SOFT
                action = "SOFT"
                quota = CPU_QUOTA_SOFT

            shape_container(name, cpu_quota=quota)

            # === Energy Estimation ===
            energy_data = estimate_all(cpu, current_interval)

            # === Logging ===
            logger.info(
                "%s | CPU=%.1f%% MEM=%.1f%% | Tier=%s(p50=%.1f p95=%.1f ratio=%.2f) "
                "| AFMV=%.1f(α=%.3f) | Action=%s | P=%.1fW C=%.4fkgCO2",
                name, cpu, mem,
                tier, tier_stats["p50"], tier_stats["p95"], tier_stats["spike_ratio"],
                afmv_pred, alpha,
                action,
                energy_data["power_watt"], energy_data["carbon_kgco2"],
            )

            # Write to CSV
            try:
                with open(csv_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        name,
                        f"{cpu:.1f}",
                        f"{mem:.1f}",
                        tier,
                        action,
                        f"{energy_data['power_watt']:.1f}",
                        f"{energy_data['carbon_kgco2']:.4f}",
                        f"{afmv_pred:.1f}",
                        f"{alpha:.3f}",
                        f"{tier_stats['spike_ratio']:.2f}",
                        f"{tier_stats['p50']:.1f}",
                        f"{tier_stats['p95']:.1f}"
                    ])
            except Exception as e:
                logger.error("Gagal menulis ke CSV: %s", e)

            if guardrail_active:
                logger.warning("⚠ GUARDRAIL aktif untuk %s (CPU=%.1f%% MEM=%.1f%%)", name, cpu, mem)

        # === Adaptive sampling interval untuk iterasi berikutnya ===
        current_interval = get_adaptive_interval(max_cpu_seen)


if __name__ == "__main__":
    main()