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
COLD_START_SAMPLES       = int(os.getenv("HECF_COLD_START_SAMPLES", 120))
FALLBACK_TIER            = int(os.getenv("HECF_FALLBACK_TIER", 2))
TIER1_AGGRESSIVE_RATIO   = float(os.getenv("HECF_TIER1_RATIO", 2.0))
TIER2_BALANCED_RATIO     = float(os.getenv("HECF_TIER2_RATIO", 1.5))

# === Predictor (Layer 3C) ===
EMA_ALPHA                = float(os.getenv("HECF_EMA_ALPHA", 0.2))

# === Framework Overhead Target ===
FRAMEWORK_OVERHEAD_TARGET = float(os.getenv("HECF_OVERHEAD_TARGET", 5.0))

# === Energy Estimation ===
P_IDLE_WATTS             = float(os.getenv("HECF_P_IDLE_WATTS", 15.0))
P_MAX_WATTS              = float(os.getenv("HECF_P_MAX_WATTS", 54.0))

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

# Excluded critical infrastructure (HECF itself, logging, DBs if not tagged properly)
EXCLUDED_CONTAINERS = [
    "hecf",
    "hecf-dashboard",
    "locust"
]

# Mode selection (default_docker, static_cap, reactive_only, full_hecf)
MODE = os.getenv("HECF_MODE", "full_hecf")
DRY_RUN = os.getenv("HECF_DRY_RUN", "False").lower() == "true"