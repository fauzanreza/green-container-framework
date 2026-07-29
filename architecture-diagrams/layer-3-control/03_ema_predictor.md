# Flowchart — EMAPredictor.update() (Layer 3C)

> **Kode Sumber:** `framework/predictor.py` → class `EMAPredictor`, fungsi `update()` (baris 15–29)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3C EMA Predictor (α=0.2)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Proactive Time-Series Forecasting** menggunakan Exponential Moving Average dengan memori O(1). Hanya menyimpan satu nilai per container (Y(t-1)) — sangat ringan. Hasilnya digunakan untuk menyesuaikan sensitivitas Guardrail secara proaktif.

```mermaid
flowchart TD
    START(["EMAPredictor.update(container_name, cpu)"])

    FIRST{"Container baru?"}
    INIT["Init: Y(0) = cpu<br/>predictions[name] = cpu"]
    RETURN_INIT(["Return cpu"])

    GET_PREV["Get Y(t-1) dari predictions"]

    CALC["<b>EMA Formula:</b><br/>Y(t) = α × CPU(t) + (1-α) × Y(t-1)<br/><br/>α = 0.2:<br/>Y(t) = 0.2 × CPU(t) + 0.8 × Y(t-1)"]

    SAVE["Simpan predictions[name] = Y(t)"]

    RETURN(["Return Y(t)"])

    START --> FIRST
    FIRST -->|Ya| INIT
    INIT --> RETURN_INIT
    FIRST -->|Tidak| GET_PREV
    GET_PREV --> CALC
    CALC --> SAVE
    SAVE --> RETURN
```

---

## Integrasi EMA → Guardrail (3C → 3A)

> **Kode Sumber:** `framework/guardrail.py` → `_get_effective_cpu_threshold()` (baris 67–85)

```mermaid
flowchart TD
    EMA_INPUT(["EMA prediction Y(t)"])

    FEED["Input ke guardrail.update()<br/>sebagai ema_pred"]

    CHECK{"ema_pred ≥<br/>warning_zone?<br/>(THRESHOLD - MARGIN)<br/>e.g. 80% - 5% = 75%"}

    LOWER["threshold = 75%<br/><b>Sensitivitas naik</b>"]
    NORMAL["threshold = 80%<br/>(default)"]

    RESULT(["Guardrail pakai threshold<br/>adjusted untuk evaluasi 3-of-5"])

    EMA_INPUT --> FEED
    FEED --> CHECK
    CHECK -->|Ya| LOWER
    CHECK -->|Tidak| NORMAL
    LOWER --> RESULT
    NORMAL --> RESULT
```

## Mengapa Ini Inovasi S2?

1. **O(1) Memory Complexity:** Hanya menyimpan satu float per container. Tidak ada array historis, tidak ada model ML, tidak ada dependency berat.
2. **Proactive, Bukan Reactive:** EMA memprediksi tren *sebelum* CPU benar-benar melewati threshold, memberikan jeda waktu 1–2 sampel bagi Guardrail untuk bertindak lebih awal.
3. **Anti-ML by Design:** Tesis ini secara sadar menolak ML/DL karena justru akan menambah konsumsi energi (menyalahi tujuan penelitian). EMA adalah solusi matematis yang optimal untuk constraint ini.

---

## Alur Logika Konseptual

### Forecasting Utilisasi Beban

```mermaid
flowchart TD
    START(["Init Prediktor"])

    PERTAMA{"Baseline (t=0)?"}
    MULAI["Tidak ada data historis<br/>→ Prediksi = nilai aktual"]
    HASIL_AWAL(["Return inisialisasi"])

    AMBIL["Get state prediksi terakhir (t-1)"]
    HITUNG["Hitung EMA:<br/>20% observasi aktual +<br/>80% historis terbobot<br/><br/>Bobot prioritas ke tren makro<br/>untuk reduksi sensitivitas<br/>terhadap transient spike"]
    SIMPAN["Update state prediksi"]
    HASIL(["Return forecast (t+1)"])

    START --> PERTAMA
    PERTAMA -->|Ya| MULAI
    MULAI --> HASIL_AWAL
    PERTAMA -->|Tidak| AMBIL
    AMBIL --> HITUNG
    HITUNG --> SIMPAN
    SIMPAN --> HASIL
```

### Integrasi EMA → Guardrail

```mermaid
flowchart TD
    RAMALAN(["EMA Forecast"])

    KIRIM["Kirim prediksi ke Guardrail"]

    DEKAT{"Prediksi mendekati<br/>threshold?"}
    SENSITIF["Guardrail lebih sensitif<br/>(threshold diturunkan)"]
    BIASA["Guardrail normal"]

    PAKAI(["Guardrail pakai<br/>threshold adjusted"])

    RAMALAN --> KIRIM
    KIRIM --> DEKAT
    DEKAT -->|Ya| SENSITIF
    DEKAT -->|Tidak| BIASA
    SENSITIF --> PAKAI
    BIASA --> PAKAI
```
