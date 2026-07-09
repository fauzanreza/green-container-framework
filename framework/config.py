import os

# framework/config.py
# Constants for HECF (Hybrid Energy-Aware Container Framework)

# === Sampling (Layer 2) ===
SAMPLING_CPU_THRESHOLD   = float(os.getenv("HECF_SAMPLING_CPU_THRESHOLD", 60.0))
SAMPLING_INTERVAL_HIGH   = int(os.getenv("HECF_SAMPLING_INTERVAL_HIGH", 10))
SAMPLING_INTERVAL_LOW    = int(os.getenv("HECF_SAMPLING_INTERVAL_LOW", 30))

# === Guardrail (Layer 3A) ===
GUARDRAIL_WINDOW         = int(os.getenv("HECF_GUARDRAIL_WINDOW", 5))
GUARDRAIL_TRIGGER_COUNT  = int(os.getenv("HECF_GUARDRAIL_TRIGGER_COUNT", 3))
GUARDRAIL_CPU_THRESHOLD  = float(os.getenv("HECF_GUARDRAIL_CPU_THRESHOLD", 80.0))
GUARDRAIL_RAM_THRESHOLD  = float(os.getenv("HECF_GUARDRAIL_RAM_THRESHOLD", 90.0))

# === Tier Detection (Layer 3B) ===
TIER_WINDOW              = int(os.getenv("HECF_TIER_WINDOW", 120))
COLD_START_SAMPLES       = int(os.getenv("HECF_COLD_START_SAMPLES", 30))  # revised: 120×30s > 30min run
FALLBACK_TIER            = int(os.getenv("HECF_FALLBACK_TIER", 2))
TIER1_AGGRESSIVE_RATIO   = float(os.getenv("HECF_TIER1_RATIO", 2.0))
TIER2_BALANCED_RATIO     = float(os.getenv("HECF_TIER2_RATIO", 1.5))
TIER_HYSTERESIS_SAMPLES  = int(os.getenv("HECF_TIER_HYSTERESIS", 3))

# === Predictor (Layer 3C) ===
EMA_ALPHA                = float(os.getenv("HECF_EMA_ALPHA", 0.2))

# === Framework Overhead Target ===
FRAMEWORK_OVERHEAD_TARGET = float(os.getenv("HECF_OVERHEAD_TARGET", 5.0))

# === PSI Internal Guardrail Signal (Gap #10) ===
PSI_ENABLED              = os.getenv("HECF_PSI_ENABLED", "true").lower() == "true"
PSI_SOME_AVG10_THRESHOLD = float(os.getenv("HECF_PSI_THRESHOLD", 25.0))

# === Memory Soft-Brake (Gap #9) ===
MEMORY_HIGH_RATIO        = float(os.getenv("HECF_MEMORY_HIGH_RATIO", 0.85))

# === Energy Estimation ===
P_IDLE_WATTS             = float(os.getenv("HECF_P_IDLE_WATTS", 15.0))
P_MAX_WATTS              = float(os.getenv("HECF_P_MAX_WATTS", 54.0))

# === EMA Pre-Warning (Layer 3C → 3A integration) ===
# When EMA prediction is within this margin of the guardrail threshold,
# the effective threshold is lowered to trigger earlier.
# PRD §4.1 Layer 3C: "fine-tune Guardrail threshold sensitivity ahead of time"
PRE_WARNING_MARGIN       = float(os.getenv("HECF_PRE_WARNING_MARGIN", 5.0))

# === Container Shaping (Layer 4) ===
CPU_PERIOD               = 100000
STATIC_CAP_CPU_PERCENT   = float(os.getenv("HECF_STATIC_CAP_CPU_PERCENT", 80.0))
STATIC_CAP_QUOTA         = int((STATIC_CAP_CPU_PERCENT / 100.0) * CPU_PERIOD)

# Precomputed microsecond limits based on general heuristics or host capacity:
# Using same ratio pattern from previous implementation for tiers, but can be dynamic.
CPU_QUOTA_GUARDRAIL      = 50000   # 0.5 core
CPU_QUOTA_AGGRESSIVE     = 75000   # 0.75 core
CPU_QUOTA_BALANCED       = 90000   # 0.9 core
CPU_QUOTA_SOFT           = -1      # Unlimited

# === Memory Shaping (Layer 4, PRD §4.1 — --memory, --memory-swap) ===
# Ratio of host RAM to cap per non-priority container under Guardrail/Aggressive
MEM_CAP_GUARDRAIL_RATIO  = float(os.getenv("HECF_MEM_CAP_GUARDRAIL", 0.70))
MEM_CAP_AGGRESSIVE_RATIO = float(os.getenv("HECF_MEM_CAP_AGGRESSIVE", 0.80))

# === Monitor Resilience ===
MONITOR_RETRY_COUNT      = int(os.getenv("HECF_MONITOR_RETRY", 1))
MONITOR_RETRY_DELAY_MS   = int(os.getenv("HECF_MONITOR_RETRY_DELAY_MS", 100))

# ============================================================================
# Security & Micro-Freezing Extension (architecture.md §10, prd.md §12)
# All disabled by default — core system stays untouched unless explicitly enabled.
# ============================================================================

# === Security Gate Toggle ===
SECURITY_ENABLED         = os.getenv("HECF_SECURITY_ENABLED", "true").lower() == "true"

# === Micro-Freezing (Layer 4 ext, §10.5/§10.8) ===
MICRO_FREEZE_ENABLED     = os.getenv("HECF_MICRO_FREEZE_ENABLED", "true").lower() == "true"
MICRO_FREEZE_IDLE_TRIGGER_S  = float(os.getenv("HECF_MICRO_FREEZE_IDLE_S", 2.0))
MICRO_FREEZE_MAX_DURATION_MS = float(os.getenv("HECF_MICRO_FREEZE_MAX_MS", 1000.0))

# === TCP Backlog (Layer 4 ext, §10.5) ===
SOMAXCONN_MIN_HEADROOM   = int(os.getenv("HECF_SOMAXCONN_MIN", 4096))

# === Conntrack Pre-flight (Gap #17) ===
CONNTRACK_MIN            = int(os.getenv("HECF_CONNTRACK_MIN", 65536))

# === DDoS Filter (Layer 2 ext, §10.3) ===
DDOS_PACKET_RATE_THRESHOLD = float(os.getenv("HECF_DDOS_RATE_THRESHOLD", 1000.0))

# === Image Signing (Layer 1 ext, §10.2) ===
IMAGE_SIGNING_REQUIRED   = os.getenv("HECF_IMAGE_SIGNING_REQUIRED", "false").lower() == "true"

# === Encryption Mode (Layer 3 ext, §10.4) ===
ENCRYPTION_MODE          = os.getenv("HECF_ENCRYPTION_MODE", "none")

# Excluded critical infrastructure (HECF itself, logging, DBs if not tagged properly)
EXCLUDED_CONTAINERS = [
    "hecf",
    "hecf-dashboard",
    "locust"
]

# === Network-Infra Auto-Priority Patterns (Gap #15) ===
NETWORK_INFRA_PATTERNS   = ["nginx", "caddy", "traefik", "cloudflared",
                            "coredns", "haproxy", "envoy"]

# Mode selection (default_docker, static_cap, reactive_only, full_hecf)
MODE = os.getenv("HECF_MODE", "full_hecf")
DRY_RUN = os.getenv("HECF_DRY_RUN", "False").lower() == "true"