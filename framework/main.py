# framework/main.py
# HECF Entry Point — Main Control Loop
#
# Core (§1-§9): 4-layer adaptive architecture — always active.
# Security (§10/§12): Security & Micro-Freezing extensions — opt-in via config.
#
# Hardening improvements:
#   - Stale detection, container cleanup, atomic CSV, EMA→guardrail wiring
#   - Memory shaping under Guardrail/Aggressive
#   - Security gate: image signing, privilege guard (cold start)
#   - Micro-Freezing: cgroup.freeze for idle non-priority containers
#   - DDoS/EDoS defense: traffic classification → freeze instead of throttle
#   - Sandbox isolation: freeze suspicious containers

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
from .modes         import OperationMode
from .config        import (
    SAMPLING_INTERVAL_LOW,
    CPU_QUOTA_GUARDRAIL,
    CPU_QUOTA_AGGRESSIVE,
    CPU_QUOTA_BALANCED,
    CPU_QUOTA_SOFT,
    STATIC_CAP_QUOTA,
    DRY_RUN,
    MODE,
    MEM_CAP_GUARDRAIL_RATIO,
    MEM_CAP_AGGRESSIVE_RATIO,
    SECURITY_ENABLED,
    MICRO_FREEZE_ENABLED,
    MICRO_FREEZE_IDLE_TRIGGER_S,
    MICRO_FREEZE_MAX_DURATION_MS,
    DDOS_PACKET_RATE_THRESHOLD,
    IMAGE_SIGNING_REQUIRED,
    ENCRYPTION_MODE,
    SOMAXCONN_MIN_HEADROOM,
)

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hecf.main")

# CSV column header
CSV_HEADER = [
    "time", "container_name", "cpu_percent", "mem_percent",
    "tier", "action", "power_watt", "energy_kwh",
    "ema_pred", "alpha", "spike_ratio", "p50", "p95",
    "overhead_cpu", "overhead_mem"
]


def _init_security(host_profile: dict):
    """
    Initialize security modules if SECURITY_ENABLED.
    Returns dict of security components (or empty dict if disabled).
    Cold-start only — these checks run once, not in the polling loop.
    """
    if not SECURITY_ENABLED and not MICRO_FREEZE_ENABLED:
        logger.info("Security extensions DISABLED (set HECF_SECURITY_ENABLED=true to enable)")
        return {}

    components = {}

    if SECURITY_ENABLED:
        logger.info("=" * 40)
        logger.info("Security Extensions ENABLED (§10/§12)")
        logger.info("=" * 40)

        # Layer 1: Image Signing
        from .security.image_signer import ImageSigner
        components["image_signer"] = ImageSigner(
            required=IMAGE_SIGNING_REQUIRED,
        )

        # Layer 1: Privilege Guard
        from .security.privilege_guard import PrivilegeGuard
        components["privilege_guard"] = PrivilegeGuard(enforce=False)

        # Layer 2: eBPF Sensor
        from .security.ebpf_sensor import EBPFSensor
        components["ebpf_sensor"] = EBPFSensor()

        # Layer 2: DDoS Filter
        from .security.ddos_filter import DDoSFilter
        components["ddos_filter"] = DDoSFilter(
            rate_threshold=DDOS_PACKET_RATE_THRESHOLD,
        )

        # Layer 3: EDoS Guard
        from .security.edos_guard import EDoSGuard
        components["edos_guard"] = EDoSGuard(
            ddos_filter=components["ddos_filter"],
        )

        # Layer 3: Encryption Calculator
        from .security.encryption_calc import EncryptionCostCalculator
        components["encryption_calc"] = EncryptionCostCalculator(
            mode=ENCRYPTION_MODE,
            host_cpu_count=host_profile.get("cpu_count", 1),
        )

        # Layer 3: Co-resident Placement (single-tenant → no-op)
        from .security.coresident_placement import CoResidentPlacement
        components["coresident"] = CoResidentPlacement(multi_tenant=False)

        # Layer 4: Sandbox Isolator
        from .security.sandbox_isolator import SandboxIsolator
        components["sandbox"] = SandboxIsolator(
            ebpf_sensor=components["ebpf_sensor"],
            dry_run=DRY_RUN,
        )

    if MICRO_FREEZE_ENABLED:
        logger.info("Micro-Freezing ENABLED (idle_trigger=%.1fs, max=%dms)",
                     MICRO_FREEZE_IDLE_TRIGGER_S, MICRO_FREEZE_MAX_DURATION_MS)

        # Layer 4: Micro-Freezer
        from .security.micro_freezer import MicroFreezer
        ebpf = components.get("ebpf_sensor")
        components["micro_freezer"] = MicroFreezer(
            idle_trigger_seconds=MICRO_FREEZE_IDLE_TRIGGER_S,
            max_freeze_duration_ms=MICRO_FREEZE_MAX_DURATION_MS,
            ebpf_sensor=ebpf,
            dry_run=DRY_RUN,
        )

        # Layer 4: TCP Backlog check (cold-start pre-flight)
        from .security.tcp_backlog_manager import TCPBacklogManager
        tcp_mgr = TCPBacklogManager(
            min_headroom=SOMAXCONN_MIN_HEADROOM,
            max_freeze_duration_ms=MICRO_FREEZE_MAX_DURATION_MS,
        )
        tcp_result = tcp_mgr.verify()
        components["tcp_backlog"] = tcp_mgr

        if not tcp_result["safe"]:
            logger.warning(
                "⚠ TCP backlog insufficient for micro-freezing — "
                "consider: %s", tcp_result["recommendation"]
            )

    # === Kategori 2 Hidden Modules (Appendix A #6-10) ===
    if SECURITY_ENABLED:
        # #6: Watchdog Auto-Thaw
        from .security.watchdog_thaw import WatchdogThaw
        watchdog = WatchdogThaw(
            max_freeze_duration_ms=MICRO_FREEZE_MAX_DURATION_MS,
            dry_run=DRY_RUN,
        )
        if MICRO_FREEZE_ENABLED:
            watchdog.start()
        components["watchdog_thaw"] = watchdog

        # #7: Duty-Cycle Freezer
        from .security.duty_cycle_freezer import DutyCycleFreezer
        components["duty_cycle_freezer"] = DutyCycleFreezer(dry_run=DRY_RUN)

        # #8: I/O Limiter
        from .security.io_limiter import IOLimiter
        components["io_limiter"] = IOLimiter(dry_run=DRY_RUN)

        # #9: Net Limiter (best-effort, requires tc)
        from .security.net_limiter import NetLimiter
        components["net_limiter"] = NetLimiter(dry_run=DRY_RUN)

        # #10: PID Limiter
        # #11: Zombie Healer (Auto-Recovery)
        from .security.zombie_healer import ZombieHealer
        components["zombie_healer"] = ZombieHealer(dry_run=DRY_RUN)

    return components


def main():
    logger.info("=" * 60)
    logger.info("HECF v2.1 — Hybrid Energy-Aware Container Framework")
    logger.info("MODE: %s", MODE)
    if not OperationMode.is_valid(MODE):
        logger.warning("Unrecognized MODE '%s', falling back to full_hecf", MODE)
    if DRY_RUN:
        logger.info("[DRY RUN] No actual resource changes will be applied.")
    logger.info("=" * 60)

    # === Layer 1: Environment Profiler ===
    host_profile = profile_host()
    host_mem_bytes = host_profile.get("mem_total_mb", 0) * 1024 * 1024
    p_idle = host_profile.get("p_idle_watts", 15.0)
    p_max = host_profile.get("p_max_watts", 54.0)
    cpu_count = host_profile.get("cpu_count", 1)
    hw_sensor = host_profile.get("hw_sensor", None)

    # === Security Extensions Init (cold-start, §10) ===
    security = _init_security(host_profile)

    # === CSV Initialization ===
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)

    # === Initialize Core Components ===
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
            except Exception:
                pass

        time.sleep(current_interval)
        
        # Read true hardware power if available
        total_hw_power = None
        if hw_sensor and hw_sensor.available:
            total_hw_power = hw_sensor.get_power_watts()

        # Layer 1/2: Discover containers & tags
        env_targets = os.getenv("HECF_TARGETS", "").strip().strip('"').strip("'")
        targets_meta = discover_containers()
        
        if env_targets:
            allowed = [t.strip() for t in env_targets.split(",") if t.strip()]
            targets_meta = {k: v for k, v in targets_meta.items() if k in allowed}

        # === Security Gate: Cold-start checks on newly discovered containers ===
        if security:
            targets_meta = _apply_security_gates(targets_meta, security)

        if not targets_meta:
            logger.warning("No target containers discovered. Waiting %ds...", current_interval)
            continue

        max_cpu_seen = 0.0
        overhead = overhead_tracker.get_overhead()
        seen_containers = set()
        seen_container_ids = set()
        csv_rows = []

        for name, meta in targets_meta.items():
            cid = meta["id"]
            priority = meta["priority"]
            pid = meta.get("pid")
            seen_containers.add(name)
            seen_container_ids.add(cid)

            # === Security Layer: Zombie Healer (if enabled) ===
            healed = False
            if "zombie_healer" in security:
                heal_result = security["zombie_healer"].evaluate(name, cid, priority, pid)
                if heal_result["action"] == "heal":
                    security["zombie_healer"].heal(name, cid)
                    healed = True
                    # Skip normal shaping if we just healed it
                    
            if healed:
                continue

            # Layer 2: Monitor
            stats = monitor.get_stats(name, cid)

            # Stale detection — skip shaping if we can't read the container's state
            if stats.get("stale", False):
                logger.warning(
                    "⚠ STALE reading for %s — skipping shaping (container may be dying)",
                    name
                )
                continue

            cpu = stats["cpu_percent"]
            mem = stats["mem_percent"]
            max_cpu_seen = max(max_cpu_seen, cpu)

            # === Security Layer 2: eBPF scan (if enabled) ===
            if "ebpf_sensor" in security:
                security["ebpf_sensor"].scan_container(name, cid)

            # === Security Layer 4: Sandbox check (if enabled) ===
            if "sandbox" in security:
                sandbox_result = security["sandbox"].evaluate(name, cid)
                if sandbox_result["action"] == "isolate":
                    logger.critical("🔒 SANDBOX: %s isolated — skipping normal control", name)
                    csv_rows.append([
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        name,
                        f"{cpu:.1f}",
                        f"{mem:.1f}",
                        "N/A",
                        "SANDBOX",
                        "0.0",
                        "0.000000000",
                        "0.0",
                        "0.000",
                        "0.00",
                        "0.0",
                        "0.0",
                        f"{overhead['cpu_percent']:.2f}",
                        f"{overhead['mem_usage_mb']:.2f}"
                    ])
                    continue  # Skip all normal shaping for sandboxed containers

            # Layer 3B & 3C
            tier_detector.add_sample(name, cpu)
            tier_int = tier_detector.get_tier(name)
            tier_stats = tier_detector.get_stats(name)
            
            ema_pred = predictor.update(name, cpu)
            alpha = predictor.get_alpha(name)

            # === Security Layer 3: EDoS check (if enabled) ===
            edos_action = "normal"
            if "edos_guard" in security:
                edos_result = security["edos_guard"].evaluate(name, cid, priority)
                edos_action = edos_result["action"]

            # Layer 3A — pass EMA prediction for pre-warning (full_hecf only)
            # Also pass cgroup_path for PSI internal signal (Gap #10)
            ema_for_guardrail = ema_pred if OperationMode.is_predictor_enabled(MODE) else None
            cgroup_path = monitor._get_cgroup_path(cid)
            guardrail_active = guardrail.update(
                name, cpu, mem, ema_pred=ema_for_guardrail, cgroup_path=cgroup_path
            )

            # Mode Selection Logic
            action = "OBSERVE"
            quota = -1
            mem_ratio = None

            # EDoS override: freeze instead of throttle
            if edos_action == "freeze":
                action = "EDOS_FREEZE"
                # Micro-freezer handles the actual cgroup.freeze write
                if "micro_freezer" in security:
                    security["micro_freezer"]._freeze(name, cid)
                tier_str = "N/A"
            elif not is_active or MODE == OperationMode.DEFAULT_DOCKER:
                action = "OBSERVE"
                quota = CPU_QUOTA_SOFT
                tier_str = "N/A"
            elif MODE == OperationMode.STATIC_CAP:
                action = "STATIC"
                quota = STATIC_CAP_QUOTA
                tier_str = "N/A"
            elif MODE == OperationMode.REACTIVE_ONLY:
                tier_str = "N/A"
                if guardrail_active:
                    action = "GUARDRAIL"
                    quota = CPU_QUOTA_GUARDRAIL
                    mem_ratio = MEM_CAP_GUARDRAIL_RATIO
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
                    mem_ratio = MEM_CAP_GUARDRAIL_RATIO
                elif tier_int == 1:
                    action = "AGGRESSIVE"
                    quota = CPU_QUOTA_AGGRESSIVE
                    mem_ratio = MEM_CAP_AGGRESSIVE_RATIO
                elif tier_int == 2:
                    action = "BALANCED"
                    quota = CPU_QUOTA_BALANCED
                else:
                    action = "SOFT"
                    quota = CPU_QUOTA_SOFT

            # === Security Layer 4: Micro-Freezing (if enabled) ===
            if "micro_freezer" in security and action not in ("EDOS_FREEZE",):
                mf = security["micro_freezer"]
                # Record activity for containers that are active
                if cpu > 1.0:
                    mf.record_activity(cid)
                # Evaluate freeze eligibility
                freeze_result = mf.evaluate(name, cid, priority, cpu)
                if freeze_result["action"] == "freeze":
                    action = "MICRO_FREEZE"
                    # Don't apply quota shaping — container is frozen at 0% CPU
                    quota = -1
                elif freeze_result["action"] == "thaw":
                    logger.info("[THAW] %s thawed — resuming normal shaping", name)

            # Layer 4: Shaper — now with memory shaping
            if action not in ("MICRO_FREEZE", "EDOS_FREEZE"):
                shape_container(
                    name, cid, priority, quota,
                    mem_ratio=mem_ratio,
                    host_mem_bytes=host_mem_bytes,
                )

            # Energy Estimator
            energy_data = estimate_all(
                cpu, current_interval, p_idle, p_max,
                hw_power=total_hw_power, cpu_count=cpu_count
            )

            # Logging
            logger.info(
                "%s (Prio:%s) | CPU=%.1f%% MEM=%.1f%% | Tier=%s | "
                "EMA=%.1f | Action=%s | P=%.1fW | OH=%.1f%%",
                name, priority, cpu, mem, tier_str, 
                ema_pred, action, energy_data["power_watt"], overhead["cpu_percent"]
            )

            # Collect CSV row (written atomically after the loop)
            csv_rows.append([
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

            if guardrail_active and OperationMode.is_guardrail_enabled(MODE):
                logger.warning("⚠ GUARDRAIL triggered for %s", name)

        # === Post-loop: Atomic CSV write ===
        if csv_rows:
            _write_csv_atomic(csv_path, csv_rows)

        # === Post-loop: Container disappearance cleanup ===
        monitor.cleanup(seen_containers)
        guardrail.cleanup(seen_containers)
        tier_detector.cleanup(seen_containers)
        predictor.cleanup(seen_containers)

        # Security cleanup
        for key in ("ddos_filter", "edos_guard", "sandbox", "zombie_healer"):
            if key in security:
                security[key].cleanup(
                    seen_container_ids if key in ("sandbox", "zombie_healer") else seen_containers
                )
        if "micro_freezer" in security:
            security["micro_freezer"].cleanup(seen_container_ids)

        current_interval = get_adaptive_interval(max_cpu_seen)


def _apply_security_gates(targets_meta: dict, security: dict) -> dict:
    """
    Apply cold-start security checks (image signing, privilege guard).
    Filters out containers that fail required checks.
    """
    filtered = {}

    for name, meta in targets_meta.items():
        cid = meta["id"]
        priority = meta["priority"]

        # Image signing check
        if "image_signer" in security:
            signer = security["image_signer"]
            # Get image info from Docker
            try:
                import docker
                client = docker.from_env()
                container = client.containers.get(cid)
                image_id = container.image.id if container.image else ""
                image_attrs = container.image.attrs if container.image else {}
            except Exception:
                image_id = ""
                image_attrs = {}

            result = signer.verify_container(name, cid, image_id, image_attrs)
            if not result["trusted"] and signer.required:
                logger.warning("[GATE] %s REJECTED — untrusted image", name)
                continue

        # Privilege guard check
        if "privilege_guard" in security:
            guard = security["privilege_guard"]
            try:
                import docker
                client = docker.from_env()
                container = client.containers.get(cid)
                host_config = container.attrs.get("HostConfig", {})
                privileged = host_config.get("Privileged", False)
                cap_add = host_config.get("CapAdd") or []
            except Exception:
                privileged = False
                cap_add = []

            guard.check_container(name, cid, priority, privileged, cap_add)
            if guard.should_exclude(cid):
                logger.warning("[GATE] %s EXCLUDED — privilege violation", name)
                continue

        filtered[name] = meta

        # === Hidden Module Cold-Start Application (Appendix A #8, #10) ===
        if "pids_limiter" in security:
            security["pids_limiter"].apply(name, cid, priority)
        if "io_limiter" in security:
            security["io_limiter"].apply(name, cid, priority)

    return filtered


def _write_csv_atomic(csv_path: str, rows: list):
    """
    Write CSV rows atomically: write to .tmp then rename.
    Prevents CSV corruption if the process is killed mid-write.
    """
    tmp_path = csv_path + ".tmp"
    try:
        existing_lines = []
        if os.path.exists(csv_path):
            with open(csv_path, "r", newline="") as f:
                existing_lines = f.readlines()

        with open(tmp_path, "w", newline="") as f:
            for line in existing_lines:
                f.write(line)
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)

        os.replace(tmp_path, csv_path)

    except Exception as e:
        logger.error("Failed writing to CSV: %s", e)
        try:
            with open(csv_path, "a", newline="") as f:
                writer = csv.writer(f)
                for row in rows:
                    writer.writerow(row)
        except Exception as e2:
            logger.error("Fallback CSV write also failed: %s", e2)


if __name__ == "__main__":
    main()