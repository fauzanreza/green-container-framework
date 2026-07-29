# Flowchart — Guardrail.update() (Layer 3A)

> **Kode Sumber:** `framework/guardrail.py` → class `Guardrail`, fungsi `update()` (baris 30–65) dan `_get_effective_cpu_threshold()` (baris 67–85)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3A Guardrail (3-of-5 + PSI)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Reactive Debouncing** menggunakan Rolling Boolean Array. Mengevaluasi apakah kondisi overload terjadi di **minimal 3 dari 5 sampel terakhir** — mencegah reaksi terhadap micro-spike yang tidak berbahaya. Diintegrasikan dengan sinyal PSI kernel dan threshold EMA-adjusted.

```mermaid
flowchart TD
    START(["Guardrail.update(container_name, cpu, mem, ema_pred, cgroup_path)"])

    EMA_CHECK{"ema_pred<br/>disediakan?<br/>(hanya mode full_hecf)"}
    
    EMA_ZONE{"ema_pred ≥<br/>(CPU_THRESHOLD - PRE_WARNING_MARGIN)?<br/>Contoh: ema ≥ 75% jika threshold=80%, margin=5%"}
    LOWER_THRESH["cpu_thresh = CPU_THRESHOLD - PRE_WARNING_MARGIN<br/><b>= 75%</b> (EMA-adjusted, lebih sensitif)"]
    NORMAL_THRESH["cpu_thresh = CPU_THRESHOLD<br/><b>= 80%</b> (default)"]

    EVAL_OVER["Evaluasi kondisi overload:<br/>is_over = (cpu > cpu_thresh) OR (mem > RAM_THRESHOLD 90%)"]

    APPEND["Tambahkan is_over ke rolling history<br/>(boolean array, max = GUARDRAIL_WINDOW = 5)"]

    TRIM{"len(history)<br/>> 5?"}
    POP["Hapus elemen tertua<br/>history.pop(0)"]

    COUNT["trigger_count = Σ(True) dalam history"]

    TRIGGERED{"trigger_count<br/>≥ GUARDRAIL_TRIGGER_COUNT?<br/>(default: ≥ 3 dari 5)"}

    NOT_TRIGGERED(["Return False<br/>(Guardrail TIDAK aktif —<br/>beban masih aman)"])

    CHECK_PSI{"PSI_ENABLED<br/>dan cgroup_path<br/>tersedia?"}
    READ_PSI["Baca cpu.pressure<br/>Parse 'some avg10=X.XX'"]
    PSI_HIGH{"psi_avg10 ><br/>PSI_THRESHOLD (25.0)?"}
    PSI_ELEVATED["Catat GUARDRAIL+PSI<br/>(tingkat kepercayaan tinggi)"]
    PSI_NORMAL["Catat GUARDRAIL biasa"]

    RETURN_TRUE(["Return True<br/>(Guardrail AKTIF —<br/>intervensi darurat diperlukan)"])

    START --> EMA_CHECK
    EMA_CHECK -->|Tidak| NORMAL_THRESH
    EMA_CHECK -->|Ya| EMA_ZONE
    EMA_ZONE -->|Ya, mendekati threshold| LOWER_THRESH
    EMA_ZONE -->|Tidak, masih jauh| NORMAL_THRESH

    LOWER_THRESH --> EVAL_OVER
    NORMAL_THRESH --> EVAL_OVER

    EVAL_OVER --> APPEND
    APPEND --> TRIM
    TRIM -->|Ya| POP
    TRIM -->|Tidak| COUNT
    POP --> COUNT

    COUNT --> TRIGGERED
    TRIGGERED -->|Tidak, < 3 dari 5| NOT_TRIGGERED
    TRIGGERED -->|Ya, ≥ 3 dari 5| CHECK_PSI

    CHECK_PSI -->|Tidak| PSI_NORMAL
    CHECK_PSI -->|Ya| READ_PSI
    READ_PSI --> PSI_HIGH
    PSI_HIGH -->|Ya| PSI_ELEVATED
    PSI_HIGH -->|Tidak| PSI_NORMAL

    PSI_ELEVATED --> RETURN_TRUE
    PSI_NORMAL --> RETURN_TRUE
```

### Mengapa Ini Inovasi S2?
1. **Rolling Boolean Array (3-of-5):** Bukan sekadar `if cpu > 80%`. Algoritma ini mengevaluasi pola temporal — hanya memicu intervensi jika anomali **persisten**, bukan sesaat.
2. **EMA-Adjusted Threshold:** Threshold bergeser secara proaktif berdasarkan prediksi EMA dari Layer 3C. Ini adalah integrasi antar-algoritma (prediktif → reaktif).
3. **PSI Confirmation Signal:** Menggunakan sinyal *Pressure Stall Information* dari kernel Linux sebagai variabel konfirmasi tambahan, meningkatkan akurasi keputusan.

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Evaluasi Status Kritis (Overload Detection)"])

    PREDIKSI{"Integrasi Prediktor<br/>(EMA) Aktif?"}
    MENDEKATI{"Prediksi utilisasi<br/>mendekati ambang batas<br/>(Threshold)?"}
    BATAS_RENDAH["Reduksi Threshold Proaktif<br/>(Tingkatkan sensitivitas respons Guardrail)"]
    BATAS_NORMAL["Terapkan Threshold Standar"]

    CEK["Evaluasi Matriks Utilisasi:<br/>Apakah CPU ATAU Memori<br/>melampaui ambang batas?"]

    CATAT["Agregasi State (Rolling History):<br/>(Simpan ke buffer boolean 5-sampel)"]

    PENUH{"Buffer<br/>Penuh (>5)?"}
    BUANG["Eviksi state terlama (FIFO)"]

    HITUNG["Kalkulasi Bobot Anomali:<br/>Σ(State Overload) dalam buffer"]

    DARURAT{"Bobot Anomali<br/>≥ 3 dari 5?"}

    AMAN(["✅ Status Aman (Nominal)<br/>(Anomali sesaat/Transient Spike)"])

    CEK_PSI{"Kompatibilitas<br/>Pressure Stall Info (PSI)?"}
    BACA_PSI["Akuisisi Sinyal Tekanan (Stall)<br/>dari Kernel Linux"]
    PSI_TINGGI{"Stall Rate<br/>Tinggi?"}
    SANGAT_DARURAT["🚨 KONDISI KRITIS (High Confidence)<br/>(Validasi silang PSI positif)"]
    DARURAT_BIASA["🚨 KONDISI DARURAT<br/>(Beban berlebih persisten)"]

    AKTIF(["Tindakan Preventif (Guardrail) AKTIF<br/>(Restriksi CPU diinisiasi untuk mencegah Starvation)"])

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
    DARURAT -->|Tidak (< 3)| AMAN
    DARURAT -->|Ya (≥ 3)| CEK_PSI

    CEK_PSI -->|Tidak| DARURAT_BIASA
    CEK_PSI -->|Ya| BACA_PSI
    BACA_PSI --> PSI_TINGGI
    PSI_TINGGI -->|Ya| SANGAT_DARURAT
    PSI_TINGGI -->|Tidak| DARURAT_BIASA

    SANGAT_DARURAT --> AKTIF
    DARURAT_BIASA --> AKTIF
```
