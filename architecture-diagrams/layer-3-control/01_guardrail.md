# Flowchart — Guardrail.update() (Layer 3A)

> **Kode Sumber:** `framework/guardrail.py` → class `Guardrail`, fungsi `update()` (baris 30–65) dan `_get_effective_cpu_threshold()` (baris 67–85)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3A Guardrail (3-of-5 + PSI)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Reactive Debouncing** menggunakan Rolling Boolean Array. Mengevaluasi apakah kondisi overload terjadi di **minimal 3 dari 5 sampel terakhir** — mencegah reaksi terhadap micro-spike yang tidak berbahaya. Diintegrasikan dengan sinyal PSI kernel dan threshold EMA-adjusted.

```mermaid
flowchart TD
    START(["Guardrail.update(container_name, cpu, mem, ema_pred, cgroup_path)"])

    EMA_CHECK{"ema_pred<br/>tersedia?"}
    
    EMA_ZONE{"ema_pred ≥<br/>warning_zone?<br/>e.g. ≥ 75%"}
    LOWER_THRESH["cpu_thresh = 75%<br/>(EMA-adjusted)"]
    NORMAL_THRESH["cpu_thresh = 80%<br/>(default)"]

    EVAL_OVER["Evaluasi overload:<br/>is_over = cpu > thresh OR mem > 90%"]

    APPEND["Append is_over ke rolling history<br/>(boolean array, max 5)"]

    TRIM{"len(history)<br/>> 5?"}
    POP["Pop elemen tertua"]

    COUNT["trigger_count = Σ(True)"]

    TRIGGERED{"trigger_count<br/>≥ 3?"}

    NOT_TRIGGERED(["Return False<br/>(Guardrail OFF)"])

    CHECK_PSI{"PSI_ENABLED<br/>& cgroup_path?"}
    READ_PSI["Baca cpu.pressure<br/>Parse avg10"]
    PSI_HIGH{"psi_avg10 ><br/>25.0?"}
    PSI_ELEVATED["Log GUARDRAIL+PSI<br/>(high confidence)"]
    PSI_NORMAL["Log GUARDRAIL"]

    RETURN_TRUE(["Return True<br/>(Guardrail ON)"])

    START --> EMA_CHECK
    EMA_CHECK -->|Tidak| NORMAL_THRESH
    EMA_CHECK -->|Ya| EMA_ZONE
    EMA_ZONE -->|Ya| LOWER_THRESH
    EMA_ZONE -->|Tidak| NORMAL_THRESH

    LOWER_THRESH --> EVAL_OVER
    NORMAL_THRESH --> EVAL_OVER

    EVAL_OVER --> APPEND
    APPEND --> TRIM
    TRIM -->|Ya| POP
    TRIM -->|Tidak| COUNT
    POP --> COUNT

    COUNT --> TRIGGERED
    TRIGGERED -->|"Tidak (< 3)"| NOT_TRIGGERED
    TRIGGERED -->|"Ya (≥ 3)"| CHECK_PSI

    CHECK_PSI -->|Tidak| PSI_NORMAL
    CHECK_PSI -->|Ya| READ_PSI
    READ_PSI --> PSI_HIGH
    PSI_HIGH -->|Ya| PSI_ELEVATED
    PSI_HIGH -->|Tidak| PSI_NORMAL

    PSI_ELEVATED --> RETURN_TRUE
    PSI_NORMAL --> RETURN_TRUE
```

## Mengapa Ini Inovasi S2?

1. **Rolling Boolean Array (3-of-5):** Bukan sekadar `if cpu > 80%`. Algoritma ini mengevaluasi pola temporal — hanya memicu intervensi jika anomali **persisten**, bukan sesaat.
2. **EMA-Adjusted Threshold:** Threshold bergeser secara proaktif berdasarkan prediksi EMA dari Layer 3C. Ini adalah integrasi antar-algoritma (prediktif → reaktif).
3. **PSI Confirmation Signal:** Menggunakan sinyal *Pressure Stall Information* dari kernel Linux sebagai variabel konfirmasi tambahan, meningkatkan akurasi keputusan.

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Overload Detection"])

    PREDIKSI{"Apakah EMA Prediktor<br/>Aktif?"}
    MENDEKATI{"Apakah Prediksi EMA<br/>Mendekati Threshold?"}
    BATAS_RENDAH["Turunkan threshold<br/>(lebih sensitif)"]
    BATAS_NORMAL["Threshold standar"]

    CEK["Evaluasi utilisasi:<br/>CPU atau Memori > threshold?"]

    CATAT["Simpan ke rolling history<br/>(buffer boolean, 5 sampel)"]

    PENUH{"Apakah Buffer<br/>> 5 Sampel?"}
    BUANG["Hapus entry terlama (FIFO)"]

    HITUNG["Hitung Σ overload dalam buffer"]

    DARURAT{"Apakah Overload Terjadi<br/>≥ 3 dari 5 Sampel?"}

    SELESAI_AMAN(["END: ✅ Normal (Transient Spike)"])

    CEK_PSI{"Apakah Sinyal PSI<br/>Tersedia?"}
    BACA_PSI["Baca sinyal stall dari kernel"]
    PSI_TINGGI{"Apakah Stall Rate<br/>PSI Tinggi?"}
    SANGAT_DARURAT["🚨 Kritis (high confidence)<br/>PSI terkonfirmasi"]
    DARURAT_BIASA["🚨 Darurat<br/>(overload persisten)"]

    SELESAI_AKTIF(["END: Guardrail AKTIF → Restriksi CPU"])

    START --> PREDIKSI
    PREDIKSI -->|Tidak| BATAS_NORMAL
    PREDIKSI -->|Ya| MENDEKATI
    MENDEKATI -->|Ya| BATAS_RENDAH
    MENDEKATI -->|Tidak| BATAS_NORMAL

    BATAS_RENDAH --> CEK
    BATAS_NORMAL --> CEK
    CEK --> CATAT
    CATAT --> PENUH
    PENUH -->|Ya| BUANG
    PENUH -->|Tidak| HITUNG
    BUANG --> HITUNG

    HITUNG --> DARURAT
    DARURAT -->|"Tidak (< 3)"| SELESAI_AMAN
    DARURAT -->|"Ya (≥ 3)"| CEK_PSI

    CEK_PSI -->|Tidak| DARURAT_BIASA
    CEK_PSI -->|Ya| BACA_PSI
    BACA_PSI --> PSI_TINGGI
    PSI_TINGGI -->|Ya| SANGAT_DARURAT
    PSI_TINGGI -->|Tidak| DARURAT_BIASA

    SANGAT_DARURAT --> SELESAI_AKTIF
    DARURAT_BIASA --> SELESAI_AKTIF
```
