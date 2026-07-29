# Flowchart — TierDetector.get_tier() (Layer 3B)

> **Kode Sumber:** `framework/tier_detector.py` → class `TierDetector`, fungsi `add_sample()` (baris 26–31) dan `get_tier()` (baris 33–90)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3B Tier Detector (P95/P50)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Statistical Volatility Classification** menggunakan rasio persentil P95/P50 dalam sliding window 120 sampel. Ditambah mekanisme **Hysteresis** untuk mencegah osilasi antar tier.

```mermaid
flowchart TD
    START(["TierDetector (per container)"])

    ADD["add_sample(cpu)<br/>Append ke sliding window"]
    TRIM{"len(window)<br/>> 120?"}
    POP["window.pop(0)"]

    GET_TIER(["get_tier(container_name)"])

    COLD{"len(window)<br/>< 30?"}
    COLD_FALLBACK["Return Tier 2<br/>(Insufficient data)"]

    CALC_P50["p50 = numpy.percentile(window, 50)<br/><i>Median</i>"]
    CALC_P95["p95 = numpy.percentile(window, 95)<br/><i>Spike</i>"]

    P50_ZERO{"p50 ≤ 0?<br/>(idle)"}
    IDLE_SOFT["Return Tier 3 (Soft)"]

    CALC_RATIO["spike_ratio = p95 / p50"]

    CLASSIFY{"Klasifikasi<br/>spike_ratio"}
    TIER1["raw_tier = 1 (Aggressive)<br/>spike_ratio > 2.0"]
    TIER2["raw_tier = 2 (Balanced)<br/>1.5 ≤ spike_ratio ≤ 2.0"]
    TIER3["raw_tier = 3 (Soft)<br/>spike_ratio < 1.5"]

    HYST_INIT{"State = Null?"}
    INIT_STATE["Init hysteresis state:<br/>current = raw_tier<br/>pending = raw_tier<br/>count = 3"]
    RETURN_RAW(["Return raw_tier"])

    SAME_CURRENT{"raw_tier ==<br/>state.current?"}
    RESET_PENDING["Reset pending transition<br/>count = 0"]
    RETURN_CURRENT1(["Return state.current"])

    SAME_PENDING{"raw_tier ==<br/>state.pending?"}
    INC_COUNT["state.count += 1"]
    COUNT_MET{"count ≥ 3?"}
    COMMIT["✅ Commit transisi tier:<br/>state.current = raw_tier<br/>count = 0"]
    RETURN_NEW(["Return raw_tier (baru)"])
    HOLD(["Return state.current<br/>(Hold)"])

    NEW_PENDING["state.pending = raw_tier<br/>state.count = 1"]
    RETURN_HOLD(["Return state.current<br/>(Hold)"])

    START --> ADD
    ADD --> TRIM
    TRIM -->|Ya| POP
    TRIM -->|Tidak| GET_TIER
    POP --> GET_TIER

    GET_TIER --> COLD
    COLD -->|"Ya (< 30)"| COLD_FALLBACK
    COLD -->|"Tidak (≥ 30)"| CALC_P50

    CALC_P50 --> CALC_P95
    CALC_P95 --> P50_ZERO
    P50_ZERO -->|Ya| IDLE_SOFT
    P50_ZERO -->|Tidak| CALC_RATIO
    CALC_RATIO --> CLASSIFY

    CLASSIFY -->|"ratio > 2.0"| TIER1
    CLASSIFY -->|"1.5 ≤ ratio ≤ 2.0"| TIER2
    CLASSIFY -->|"ratio < 1.5"| TIER3

    TIER1 --> HYST_INIT
    TIER2 --> HYST_INIT
    TIER3 --> HYST_INIT

    HYST_INIT -->|Ya| INIT_STATE
    INIT_STATE --> RETURN_RAW
    HYST_INIT -->|Tidak| SAME_CURRENT

    SAME_CURRENT -->|Ya| RESET_PENDING
    RESET_PENDING --> RETURN_CURRENT1

    SAME_CURRENT -->|Tidak| SAME_PENDING
    SAME_PENDING -->|Ya| INC_COUNT
    INC_COUNT --> COUNT_MET
    COUNT_MET -->|"Ya (≥ 3)"| COMMIT
    COMMIT --> RETURN_NEW
    COUNT_MET -->|Tidak| HOLD

    SAME_PENDING -->|Tidak| NEW_PENDING
    NEW_PENDING --> RETURN_HOLD
```

## Mengapa Ini Inovasi S2?

1. **P95/P50 Spike Ratio:** Bukan menggunakan rata-rata (mean) yang sensitif terhadap outlier. Rasio persentil ini adalah metode statistik robust untuk mendeteksi *burstiness* beban kerja web secara real-time.
2. **Sliding Window 120 Sampel:** Memberikan konteks historis yang cukup panjang tanpa mengonsumsi memori berlebih.
3. **Hysteresis (3 sampel stabil):** Algoritma anti-osilasi dari teori kontrol — tier baru hanya di-commit jika konsisten selama 3 evaluasi berturut-turut. Mencegah *flapping* yang menyebabkan overhead percuma.

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Klasifikasi Volatilitas (Tiering)"])

    SIMPAN["Agregasi CPU (Sliding Window, max 120)"]
    TERLALU_BANYAK{"Size > 120?"}
    HAPUS_LAMA["Eviksi data terlama (FIFO)"]

    TENTUKAN(["Evaluasi Volatilitas"])

    CUKUP_DATA{"Sampel ≥ 30?"}
    BELUM_CUKUP["Fallback Tier 2<br/>(Insufficient data)"]

    IDLE{"Deteksi Idle?"}
    MODE_SANTAI["Terapkan Tier 3 (Soft)"]

    BANDINGKAN["Kalkulasi Statistik:<br/>P50 (Median) & P95 (Spike)"]
    RASIO["Kalkulasi Spike Ratio:<br/>P95 ÷ P50"]

    KATEGORI{"Klasifikasi Rasio"}
    MELONJAK["Rasio > 2.0 → Tier 1 (Aggressive)"]
    SEDANG["1.5 ≤ Rasio ≤ 2.0 → Tier 2 (Balanced)"]
    STABIL["Rasio < 1.5 → Tier 3 (Soft)"]

    PERTAMA{"Initial State?"}
    LANGSUNG["Terapkan Tier Awal"]

    SAMA{"New Tier == Current Tier?"}
    TETAP["State Stabil"]

    KONSISTEN{"Hysteresis Check:<br/>Konsisten 3 siklus?"}
    UBAH["✅ Commit Tier Baru"]
    TAHAN["Hold (Transisi ditunda)"]

    START --> SIMPAN
    SIMPAN --> TERLALU_BANYAK
    TERLALU_BANYAK -->|Ya| HAPUS_LAMA
    TERLALU_BANYAK -->|Tidak| TENTUKAN
    HAPUS_LAMA --> TENTUKAN

    TENTUKAN --> CUKUP_DATA
    CUKUP_DATA -->|Tidak| BELUM_CUKUP
    CUKUP_DATA -->|Ya| IDLE
    IDLE -->|Ya| MODE_SANTAI
    IDLE -->|Tidak| BANDINGKAN
    BANDINGKAN --> RASIO
    RASIO --> KATEGORI

    KATEGORI -->|Sangat Fluktuatif| MELONJAK
    KATEGORI -->|Moderat| SEDANG
    KATEGORI -->|Stabil| STABIL

    MELONJAK --> PERTAMA
    SEDANG --> PERTAMA
    STABIL --> PERTAMA

    PERTAMA -->|Ya| LANGSUNG
    PERTAMA -->|Tidak| SAMA
    SAMA -->|Ya| TETAP
    SAMA -->|Tidak| KONSISTEN
    KONSISTEN -->|"Ya (3 siklus)"| UBAH
    KONSISTEN -->|"Belum (Hold)"| TAHAN
```
