# Flowchart — EMAPredictor.update() (Layer 3C)

> **Kode Sumber:** `framework/predictor.py` → class `EMAPredictor`, fungsi `update()` (baris 15–29)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3C EMA Predictor (α=0.2)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Proactive Time-Series Forecasting** menggunakan Exponential Moving Average dengan memori O(1). Hanya menyimpan satu nilai per container (Y(t-1)) — sangat ringan. Hasilnya digunakan untuk menyesuaikan sensitivitas Guardrail secara proaktif.

```mermaid
flowchart TD
    START(["EMAPredictor.update(container_name, cpu)"])

    FIRST{"Pertama kali<br/>untuk container ini?"}
    INIT["Inisialisasi:<br/>Y(0) = cpu saat ini<br/>predictions[name] = cpu"]
    RETURN_INIT(["Return cpu<br/>(prediksi pertama = observasi)"])

    GET_PREV["Ambil Y(t-1) dari predictions dict"]

    CALC["<b>Rumus EMA:</b><br/>Y(t) = α × CPU(t) + (1 - α) × Y(t-1)<br/><br/>Dengan α = 0.2 (fixed):<br/>Y(t) = 0.2 × CPU(t) + 0.8 × Y(t-1)"]

    SAVE["predictions[name] = Y(t)"]

    RETURN(["Return Y(t)<br/>(prediksi tren CPU berikutnya)"])

    START --> FIRST
    FIRST -->|Ya| INIT
    INIT --> RETURN_INIT
    FIRST -->|Tidak| GET_PREV
    GET_PREV --> CALC
    CALC --> SAVE
    SAVE --> RETURN
```

---

## Bagaimana EMA Digunakan oleh Guardrail (Integrasi 3C → 3A)

> **Kode Sumber:** `framework/guardrail.py` → `_get_effective_cpu_threshold()` (baris 67–85)

```mermaid
flowchart TD
    EMA_INPUT(["EMA prediction Y(t)<br/>dari predictor.py"])

    FEED["Dikirim ke guardrail.update()<br/>sebagai parameter ema_pred"]

    CHECK{"ema_pred ≥<br/>warning_zone?<br/>(CPU_THRESHOLD - MARGIN)<br/>Contoh: 80% - 5% = 75%"}

    LOWER["Effective threshold = 75%<br/><b>Guardrail jadi lebih sensitif</b><br/>(bereaksi lebih awal)"]
    NORMAL["Effective threshold = 80%<br/>(sensitivitas normal)"]

    RESULT(["Guardrail menggunakan<br/>threshold yang sudah disesuaikan<br/>untuk evaluasi 3-of-5"])

    EMA_INPUT --> FEED
    FEED --> CHECK
    CHECK -->|Ya, mendekati bahaya| LOWER
    CHECK -->|Tidak, masih aman| NORMAL
    LOWER --> RESULT
    NORMAL --> RESULT
```

### Mengapa Ini Inovasi S2?
1. **O(1) Memory Complexity:** Hanya menyimpan satu float per container. Tidak ada array historis, tidak ada model ML, tidak ada dependency berat.
2. **Proactive, Bukan Reactive:** EMA memprediksi tren *sebelum* CPU benar-benar melewati threshold, memberikan jeda waktu 1–2 sampel bagi Guardrail untuk bertindak lebih awal.
3. **Anti-ML by Design:** Tesis ini secara sadar menolak ML/DL karena justru akan menambah konsumsi energi (menyalahi tujuan penelitian). EMA adalah solusi matematis yang optimal untuk constraint ini.

---

## Deskripsi Alur Berbasis Bisnis/Akademik

### Forecasting Utilisasi Beban

```mermaid
flowchart TD
    START(["Inisialisasi Prediktor Utilisasi Container"])

    PERTAMA{"Pengukuran<br/>Baseline (t=0)?"}
    MULAI["Data historis absen<br/>→ Prediksi awal = Nilai aktual saat ini (t)"]
    HASIL_AWAL(["Kembalikan nilai inisialisasi"])

    AMBIL["Akuisisi nilai State Prediksi terakhir (t-1)"]
    HITUNG["Kalkulasi EMA (Exponential Moving Average):<br/>20% Observasi Aktual (t) +<br/>80% Historis Terbobot (t-1)<br/><br/>(Distribusi bobot memprioritaskan tren<br/>makro untuk mereduksi sensitivitas<br/>terhadap transient spike)"]
    SIMPAN["Perbarui State Prediksi dalam Memory"]
    HASIL(["Kembalikan Nilai Forecast<br/>(Prediksi utilisasi pada siklus t+1)"])

    START --> PERTAMA
    PERTAMA -->|Ya| MULAI
    MULAI --> HASIL_AWAL
    PERTAMA -->|Tidak| AMBIL
    AMBIL --> HITUNG
    HITUNG --> SIMPAN
    SIMPAN --> HASIL
```

### Bagaimana Ramalan Mempengaruhi Guardrail

```mermaid
flowchart TD
    RAMALAN(["Ramalan tren dari Prediktor"])

    KIRIM["Kirimkan ke Guardrail<br/>sebagai peringatan dini"]

    DEKAT{"Ramalan menunjukkan<br/>beban mendekati<br/>batas bahaya?"}
    SENSITIF["Guardrail jadi lebih sensitif<br/>(bereaksi lebih awal,<br/>sebelum beban benar-benar melonjak)"]
    BIASA["Guardrail tetap normal<br/>(tidak ada tanda bahaya)"]

    PAKAI(["Guardrail menggunakan<br/>sensitivitas yang sudah disesuaikan"])

    RAMALAN --> KIRIM
    KIRIM --> DEKAT
    DEKAT -->|Ya, mendekati bahaya| SENSITIF
    DEKAT -->|Tidak, masih jauh| BIASA
    SENSITIF --> PAKAI
    BIASA --> PAKAI
```
