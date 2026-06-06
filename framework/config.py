# framework/config.py
# Konstanta HGCF — sesuaikan dengan hardware target

# === Sampling ===
SAMPLING_INTERVAL_NORMAL = 30   # detik saat CPU < 60%
SAMPLING_INTERVAL_HIGH   = 10   # detik saat CPU >= 60%
CPU_HIGH_THRESHOLD_SAMPLE = 60.0  # % untuk switch ke sampling cepat

# === Guardrail (Layer 3A) ===
# Ref: Ahmad et al. (2025), Lorido-Botran (2014), Xu & Buyya (2019)
GUARDRAIL_CPU_THRESHOLD   = 80.0  # % CPU overload threshold
GUARDRAIL_MEM_THRESHOLD   = 90.0  # % memory overload threshold
GUARDRAIL_WINDOW          = 5     # jumlah sampel terakhir yang dievaluasi
GUARDRAIL_CONSECUTIVE     = 3     # dari GUARDRAIL_WINDOW sampel, berapa yang boleh melebihi

# === Tier Detection (Layer 3B) ===
# Ref: Hossain et al. (2022) — klasifikasi berbasis p95/p50 ratio
SLIDING_WINDOW_SIZE       = 120   # jumlah sampel untuk sliding window CPU
TIER_MIN_SAMPLES          = 120   # minimum sampel sebelum tier detection aktif
TIER_AGGRESSIVE_RATIO     = 2.0   # p95/p50 > 2.0 → Tier 1 (Aggressive)
TIER_BALANCED_RATIO       = 1.5   # p95/p50 antara 1.5-2.0 → Tier 2 (Balanced)

# === AFMV Predictor (Layer 3C) ===
# Ref: Hossain et al. (2022) — Adaptive Filter-based Moving Average
# Formula: Y(k) = (1-α) × MV_w(k-1) + α × u(k)
# α ditentukan dari STDEV window: STDEV tinggi → α besar
AFMV_WINDOW_SIZE          = 5     # w dalam paper Hossain et al. (w=5 terbukti terbaik)
AFMV_ALPHA_MIN            = 0.05
AFMV_ALPHA_MAX            = 0.50
# Normalisasi STDEV ke alpha: alpha = clip(stdev / AFMV_STDEV_SCALE, min, max)
AFMV_STDEV_SCALE          = 20.0  # STDEV=20 → alpha=1.0 (sebelum clip)

# === Energy Estimation (Layer 4) ===
# Ref: Jarus et al. (2014) — model linear CPU-to-power, error < 4%
# Hardware target: Intel i3 Gen 4 (i3-4130 atau sejenisnya)
P_IDLE                    = 15.0  # Watt (idle power)
P_MAX                     = 65.0  # Watt (TDP-based, sesuai proposal)
CARBON_INTENSITY          = 0.78  # kgCO2/kWh (grid Indonesia, PLN)

# === Container Shaping (Layer 4) ===
# cpu_quota dalam microseconds per cpu_period
CPU_PERIOD                = 100000  # 100ms (standar Linux cgroups)
# Kuota per tier (dalam microseconds):
# 0.5 core = 50000, 0.75 core = 75000, 0.9 core = 90000
CPU_QUOTA_GUARDRAIL       = 50000   # Guardrail aktif: 0.5 core
CPU_QUOTA_AGGRESSIVE      = 75000   # Tier 1 Aggressive: 0.75 core
CPU_QUOTA_BALANCED        = 90000   # Tier 2 Balanced: 0.9 core
CPU_QUOTA_SOFT            = -1      # Tier 3 Soft: hapus limit (unlimited)

# === Excluded Containers ===
# Jangan di-shape container-container kritis ini
EXCLUDED_CONTAINERS = [
    "hgcf",
    "beszel-hub",
    "beszel-agent",
    "cloudflared-tunnel",
    "ollama",
    "locust",
    "mysql-db",       # database jangan di-throttle
    "bench-postgres",
]

# === DRY RUN ===
# True = hanya print keputusan, tidak benar-benar shape container
# Set False setelah verifikasi log bersih > 10 menit
DRY_RUN = True