# Flowchart — TierDetector.get_tier() (Layer 3B)

> **Kode Sumber:** `framework/tier_detector.py` → class `TierDetector`, fungsi `add_sample()`, `get_tier()`, dan `get_stats()` (baris 25–125)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3B Analytic Tier Detection Engine (P95/P50)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Single-Window Volatility Classification** menggunakan rasio persentil beban kerja `spike_ratio = P95 / P50` pada satu jendela geser (`TIER_WINDOW = 120` sampel) per kontainer. Dilengkapi:
1. **Cold-Start Fallback:** Memaksa Tier 2 (Balanced) selama akumulasi sampel kurang dari `COLD_START_SAMPLES = 10` (5 menit pemanasan).
2. **Robust Spike Ratio:** Menggunakan P95/P50 untuk memisahkan beban *spiky* (Tier 1: > 2.0), *moderate* (Tier 2: 1.5 – 2.0), dan *smooth/idle* (Tier 3: < 1.5).
3. **Symmetric Hysteresis (3 Sampel):** Mencegah osilasi transisi tier dengan mewajibkan 3 sampel berturut-turut (`TIER_HYSTERESIS_SAMPLES = 3`) untuk perubahan tier naik maupun turun.

```mermaid
flowchart TD
    START(["TierDetector.get_tier(container_name)"])

    CHECK_COLD{"len(window) &lt;<br/>COLD_START_SAMPLES (10)?"}
    RETURN_COLD(["Return 2 (Fallback Tier 2 — Balanced)<br/>Fase Warmup Awal Server"])

    CALC_PERCENTILES["Hitung Persentil via NumPy:<br/>p50 = percentile(window, 50)<br/>p95 = percentile(window, 95)"]

    CHECK_IDLE{"p50 ≤ 0?<br/>(Kontainer Idle)"}
    RAW_TIER_3_IDLE["raw_tier = 3 (Soft)"]

    CALC_RATIO["spike_ratio = p95 / p50"]

    CHECK_TIER1{"spike_ratio &gt; 2.0<br/>(TIER1_AGGRESSIVE_RATIO)?"}
    RAW_TIER_1["raw_tier = 1 (Aggressive)"]

    CHECK_TIER2{"spike_ratio ≥ 1.5<br/>(TIER2_BALANCED_RATIO)?"}
    RAW_TIER_2["raw_tier = 2 (Balanced)"]
    RAW_TIER_3["raw_tier = 3 (Soft)"]

    CHECK_INIT_HYST{"container in<br/>_hysteresis state?"}
    INIT_HYST["_hysteresis[name] = {current: raw_tier, pending: raw_tier, count: 0}"]
    RETURN_RAW_FIRST(["Return raw_tier"])

    CHECK_SAME_CURRENT{"raw_tier ==<br/>state['current']?"}
    RESET_PENDING["state['pending'] = raw_tier<br/>state['count'] = 0"]
    RETURN_CURRENT(["Return state['current']"])

    CHECK_SAME_PENDING{"raw_tier ==<br/>state['pending']?"}
    INC_COUNT["state['count'] += 1"]
    CHECK_COUNT_REACHED{"state['count'] ≥ 3<br/>(TIER_HYSTERESIS_SAMPLES)?"}
    COMMIT_NEW_TIER["state['current'] = raw_tier<br/>state['count'] = 0"]
    RETURN_NEW_TIER(["Return raw_tier (Tier Baru Ter-commit)"])
    RETURN_HOLD_PENDING(["Return state['current'] (Tahan Tier Lama)"])

    NEW_PENDING_STATE["state['pending'] = raw_tier<br/>state['count'] = 1"]
    RETURN_HOLD_NEW(["Return state['current'] (Tahan Tier Lama)"])

    START --> CHECK_COLD
    CHECK_COLD -->|Ya| RETURN_COLD
    CHECK_COLD -->|Tidak| CALC_PERCENTILES

    CALC_PERCENTILES --> CHECK_IDLE
    CHECK_IDLE -->|Ya| RAW_TIER_3_IDLE
    CHECK_IDLE -->|Tidak| CALC_RATIO

    CALC_RATIO --> CHECK_TIER1
    CHECK_TIER1 -->|Ya| RAW_TIER_1
    CHECK_TIER1 -->|Tidak| CHECK_TIER2
    CHECK_TIER2 -->|Ya| RAW_TIER_2
    CHECK_TIER2 -->|Tidak| RAW_TIER_3

    RAW_TIER_1 --> CHECK_INIT_HYST
    RAW_TIER_2 --> CHECK_INIT_HYST
    RAW_TIER_3 --> CHECK_INIT_HYST
    RAW_TIER_3_IDLE --> CHECK_INIT_HYST

    CHECK_INIT_HYST -->|Tidak| INIT_HYST
    INIT_HYST --> RETURN_RAW_FIRST

    CHECK_INIT_HYST -->|Ya| CHECK_SAME_CURRENT
    CHECK_SAME_CURRENT -->|Ya| RESET_PENDING
    RESET_PENDING --> RETURN_CURRENT

    CHECK_SAME_CURRENT -->|Tidak| CHECK_SAME_PENDING
    CHECK_SAME_PENDING -->|Ya| INC_COUNT
    INC_COUNT --> CHECK_COUNT_REACHED
    CHECK_COUNT_REACHED -->|Ya| COMMIT_NEW_TIER
    CHECK_COUNT_REACHED -->|Tidak| RETURN_HOLD_PENDING
    COMMIT_NEW_TIER --> RETURN_NEW_TIER

    CHECK_SAME_PENDING -->|Tidak| NEW_PENDING_STATE
    NEW_PENDING_STATE --> RETURN_HOLD_NEW
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Klasifikasi Volatilitas Beban Kontainer"])

    CEK_SAMPEL{"Apakah Riwayat Sampel Kurang Dari 10? (Warm-up)"}
    FALLBACK_BALANCED(["Terapkan Tier 2 (Balanced) — Baseline Stabil Awal"])

    HITUNG_P["Hitung Nilai Statistik Distribusi Beban:<br/>• P50 (Beban Median Normal)<br/>• P95 (Beban Puncak Ekstrem)"]

    CEK_IDLE{"P50 ≤ 0 (Idle)?"}
    SET_SOFT_IDLE["Klasifikasi Mentah: Tier 3 (Soft)"]

    HITUNG_RASIO["Hitung Spike Ratio = P95 ÷ P50"]

    EVAL_RASIO{"Tingkat Volatilitas (Spike Ratio):"}
    RASIO_T1["Rasio > 2.0 → Beban Meledak-ledak (Spiky) → Tier 1 (Aggressive)"]
    RASIO_T2["1.5 ≤ Rasio ≤ 2.0 → Beban Dinamis Moderat → Tier 2 (Balanced)"]
    RASIO_T3["Rasio < 1.5 → Beban Tenang / Stabil → Tier 3 (Soft)"]

    subgraph HYSTERESIS["Mekanisme Anti-Osilasi (Symmetric Hysteresis 3 Sampel)"]
        CEK_SAMA{"Apakah Klasifikasi Mentah Sama dengan Tier Saat Ini?"}
        TETAP["Reset Antrean Transisi → Pertahankan Tier Saat Ini"]

        CEK_ANTRE{"Apakah Klasifikasi Mentah Sama dengan Antrean Transisi Sebelumnya?"}
        TAMBAH_HITUNGAN["Tambah Penghitung Konsistensi (count + 1)"]
        SUDAH_3{"Konsisten 3 Kali Berturut-turut?"}
        RESMIKAN["Resmikan Pergantian Tier (Commit)"]
        TAHAN["Tahan Pergantian (Cegah Efek Fluktuasi Singkat)"]

        MULAI_ANTRE["Buka Antrean Baru untuk Calon Tier Baru (count = 1)"]
    end

    SELESAI_TIER(["END: Return Tier Terpilih"])

    START --> CEK_SAMPEL
    CEK_SAMPEL -->|Ya| FALLBACK_BALANCED
    CEK_SAMPEL -->|Tidak| HITUNG_P

    HITUNG_P --> CEK_IDLE
    CEK_IDLE -->|Ya| SET_SOFT_IDLE
    CEK_IDLE -->|Tidak| HITUNG_RASIO

    HITUNG_RASIO --> EVAL_RASIO
    EVAL_RASIO -->|Tinggi| RASIO_T1
    EVAL_RASIO -->|Sedang| RASIO_T2
    EVAL_RASIO -->|Rendah| RASIO_T3

    SET_SOFT_IDLE --> CEK_SAMA
    RASIO_T1 --> CEK_SAMA
    RASIO_T2 --> CEK_SAMA
    RASIO_T3 --> CEK_SAMA

    CEK_SAMA -->|Ya| TETAP
    CEK_SAMA -->|Tidak| CEK_ANTRE

    CEK_ANTRE -->|Ya| TAMBAH_HITUNGAN
    TAMBAH_HITUNGAN --> SUDAH_3
    SUDAH_3 -->|Ya| RESMIKAN
    SUDAH_3 -->|Tidak| TAHAN

    CEK_ANTRE -->|Tidak| MULAI_ANTRE
    MULAI_ANTRE --> TAHAN

    TETAP --> SELESAI_TIER
    RESMIKAN --> SELESAI_TIER
    TAHAN --> SELESAI_TIER
```
