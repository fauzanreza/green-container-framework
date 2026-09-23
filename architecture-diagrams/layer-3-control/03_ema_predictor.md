# Flowchart — EMAPredictor.update() (Layer 3C)

> **Kode Sumber:** `framework/predictor.py` → class `EMAPredictor`, fungsi `update()` (baris 15–29)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3C EMA Predictor (Adaptive α)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Proactive Time-Series Forecasting** menggunakan Exponential Moving Average dengan *Adaptive Alpha* berdasarkan varians CPU. Alpha bergeser dinamis antara 0.05 (stabil) hingga 0.8 (lonjakan) untuk pelacakan cepat. Hasilnya (dan turunannya d(EMA)/dt) digunakan untuk memicu pemotongan proaktif di Guardrail.

```mermaid
flowchart TD
    START(["EMAPredictor.update(container_name, cpu)"])

    FIRST{"Container baru?"}
    INIT["Init: Y(0) = cpu<br/>predictions[name] = cpu"]
    RETURN_INIT(["Return cpu"])

    GET_PREV["Get Y(t-1) dari predictions"]
    
    CALC_VAR["Hitung varians dari 10 sampel terakhir:<br/>High > 400 → α=0.8<br/>Med > 100 → α=0.4<br/>Low ≤ 100 → α=0.05"]

    CALC["<b>EMA Formula:</b><br/>Y(t) = α(t) × CPU(t) + (1-α(t)) × Y(t-1)"]

    SAVE["Simpan predictions[name] = Y(t)"]

    RETURN(["Return Y(t)"])

    START --> FIRST
    FIRST -->|Ya| INIT
    INIT --> RETURN_INIT
    FIRST -->|Tidak| GET_PREV
    GET_PREV --> CALC_VAR
    CALC_VAR --> CALC
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

1. **Adaptive Alpha:** Tidak lagi terjebak trade-off antara noise vs responsiveness. Saat stabil α=0.05 (menekan noise), saat ada burst α=0.8 (bereaksi 16× lebih cepat).
2. **Derivative-Based Proactivity:** Menghasilkan sinyal d(EMA)/dt yang memungkinkan Guardrail memotong spike *sebelum* CPU mencapai limit atas, menekan kemungkinan OOM/starvation di level host.
3. **Anti-ML by Design:** Tesis ini secara sadar menolak ML/DL karena justru akan menambah konsumsi energi (menyalahi tujuan penelitian). EMA + Varians adalah solusi matematis yang ringan namun sangat optimal.

---

## Alur Logika Konseptual

### Forecasting Utilisasi Beban

```mermaid
flowchart TD
    START(["START: Inisialisasi Prediktor"])

    PERTAMA{"Container Baru?<br/>(Belum ada riwayat)"}
    MULAI["Gunakan nilai CPU aktual<br/>sebagai nilai historis awal"]
    
    AMBIL["Ambil nilai prediksi<br/>sebelumnya Y(t-1)"]
    VARIANS{"Hitung Varians<br/>10 Sampel Terakhir"}
    
    ALPHA_TINGGI["Varians Tinggi (Burst):<br/>Gunakan Alpha 0.8"]
    ALPHA_RENDAH["Varians Rendah (Stabil):<br/>Gunakan Alpha 0.05"]
    
    HITUNG["Hitung EMA Baru:<br/>α * Aktual + (1-α) * Historis"]
    SIMPAN["Simpan Y(t) dan sediakan d(EMA)/dt<br/>untuk Guardrail"]
    
    SELESAI(["END: Kembalikan Prediksi Y(t)"])

    START --> PERTAMA
    PERTAMA -->|Ya| MULAI
    MULAI --> SELESAI
    PERTAMA -->|Tidak| AMBIL
    AMBIL --> VARIANS
    VARIANS -->|Spike| ALPHA_TINGGI
    VARIANS -->|Stabil| ALPHA_RENDAH
    
    ALPHA_TINGGI --> HITUNG
    ALPHA_RENDAH --> HITUNG
    HITUNG --> SIMPAN
    SIMPAN --> SELESAI
```

### Integrasi EMA → Guardrail

```mermaid
flowchart TD
    START(["START: Evaluasi Guardrail"])

    KIRIM["Terima Prediksi EMA Y(t)"]

    DEKAT{"Apakah Prediksi Y(t)<br/>mendekati Threshold<br/>(Masuk Warning Zone)?"}
    SENSITIF["Tingkatkan Sensitivitas:<br/>Turunkan threshold Guardrail"]
    BIASA["Gunakan threshold<br/>Guardrail normal"]

    PAKAI["Terapkan threshold untuk<br/>evaluasi 3-of-5 rule"]
    
    SELESAI(["END: Selesai Evaluasi"])

    START --> KIRIM
    KIRIM --> DEKAT
    DEKAT -->|Ya| SENSITIF
    DEKAT -->|Tidak| BIASA
    SENSITIF --> PAKAI
    BIASA --> PAKAI
    PAKAI --> SELESAI
```
