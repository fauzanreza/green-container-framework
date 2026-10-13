# Flowchart — EMAPredictor.update() (Layer 3C)

> **Kode Sumber:** `framework/predictor.py` → class `EMAPredictor`, fungsi `update()` dan `get_derivative()` (baris 12–66)
> **Posisi di Diagram:** Layer 3 — Hybrid Control Engine → 3C Proactive Prediction Engine (Fixed-Alpha EMA)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Lightweight Proactive Time-Series Forecasting** menggunakan Exponential Moving Average dengan **konstanta pemulus tetap $\alpha = 0.2$** (`EMA_ALPHA = 0.2`). Memenuhi batasan ketat tesis:
- Kompleksitas waktu $O(1)$ dan memori $O(1)$ per kontainer.
- Bebas dari pustaka machine learning berat (Scikit-Learn, PyTorch, TensorFlow).
- Menyediakan sinyal turunan pertama tren beban kerja:
  $$\frac{d(\text{EMA})}{dt} = \text{EMA}(t) - \text{EMA}(t-1)$$
  yang diintegrasikan langsung ke Layer 3A (Guardrail) untuk pencegahan lonjakan secara proaktif.

```mermaid
flowchart TD
    START(["EMAPredictor.update(container_name, cpu)"])

    CHECK_FIRST{"container_name in<br/>_predictions?"}
    INIT_FIRST["_predictions[name] = cpu<br/>Return round(cpu, 2)"]
    RETURN_INIT(["Return Nilai CPU Pertama"])

    STORE_PREV["y_prev = _predictions[name]<br/>_prev_ema[name] = y_prev"]

    CALC_EMA["Hitung Rumus Pemulusan Eksponensial:<br/>Y(t) = 0.2 × cpu + 0.8 × y_prev"]

    SAVE_NEW["_predictions[name] = Y(t)"]
    RETURN_PRED(["Return round(Y(t), 2)"])

    START --> CHECK_FIRST
    CHECK_FIRST -->|Tidak (Perdana)| INIT_FIRST
    INIT_FIRST --> RETURN_INIT
    CHECK_FIRST -->|Ya| STORE_PREV
    STORE_PREV --> CALC_EMA
    CALC_EMA --> SAVE_NEW
    SAVE_NEW --> RETURN_PRED
```

---

## Integrasi Sinyal EMA → Guardrail (Layer 3C ke Layer 3A)

```mermaid
flowchart TD
    CALC_DERIV(["EMAPredictor.get_derivative(name):<br/>d(EMA)/dt = Y(t) − Y(t-1)"])

    FEED_INPUT["Diteruskan ke Guardrail.update():<br/>• ema_pred = Y(t)<br/>• ema_derivative = d(EMA)/dt"]

    subgraph PROAKTIF_1["Intervensi Proaktif 1: Penurunan Ambang Batas (Pre-Warning)"]
        CEK_ZONE{"ema_pred ≥ 75.0%<br/>(Ambang 80% - Margin 5%)?"}
        TURUN_THRESH["cpu_thresh diturunkan dari 80% → 75%<br/>(Lebih waspada sebelum spike tembus limit)"]
        TETAP_THRESH["cpu_thresh tetap 80%"]
    end

    subgraph PROAKTIF_2["Intervensi Proaktif 2: Pemicu Laju Lonjakan Curam"]
        CEK_DERIV_SURGE{"d(EMA)/dt &gt; 5.0<br/>DAN ema_pred &gt; 50.0%?"}
        SURGE_TRIGGER["derivative_triggered = True<br/>(Langsung dihitung sebagai sampel overload)"]
        SURGE_IGNORE["derivative_triggered = False"]
    end

    EVAL_GUARDRAIL["Evaluasi Debouncing 3-of-5 pada Guardrail"]

    CALC_DERIV --> FEED_INPUT
    FEED_INPUT --> CEK_ZONE
    CEK_ZONE -->|Ya| TURUN_THRESH
    CEK_ZONE -->|Tidak| TETAP_THRESH

    TURUN_THRESH --> CEK_DERIV_SURGE
    TETAP_THRESH --> CEK_DERIV_SURGE

    CEK_DERIV_SURGE -->|Ya| SURGE_TRIGGER
    CEK_DERIV_SURGE -->|Tidak| SURGE_IGNORE

    SURGE_TRIGGER --> EVAL_GUARDRAIL
    SURGE_IGNORE --> EVAL_GUARDRAIL
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Peramalan Tren Utilisasi Masa Depan"])

    CEK_BARU{"Apakah Kontainer Baru Pertama Kali Dilihat?"}
    SET_DASAR["Set Nilai Prediksi Awal = Nilai CPU Saat Ini"]

    AMBIL_LAMA["Ambil Nilai Prediksi Sampel Sebelumnya Y(t-1)"]
    SIMPAN_DERIV["Simpan Nilai Lama untuk Komputasi Kemiringan Tren"]

    HITUNG_FORMULA["Penerapan Rumus Matematika EMA (α = 0.2):<br/>Prediksi Baru = 0.2 × CPU Aktual + 0.8 × Prediksi Lama"]

    UPDATE_STORAGE["Simpan Hasil Prediksi Baru"]

    HITUNG_TURUNAN["Hitung Kemiringan Tren:<br/>dEMA/dt = Prediksi Baru − Prediksi Lama"]

    SELESAI(["END: Return {Prediksi EMA, Turunan Tren}"]):::done

    START --> CEK_BARU
    CEK_BARU -->|Ya| SET_DASAR
    CEK_BARU -->|Tidak| AMBIL_LAMA
    SET_DASAR --> SELESAI

    AMBIL_LAMA --> SIMPAN_DERIV
    SIMPAN_DERIV --> HITUNG_FORMULA
    HITUNG_FORMULA --> UPDATE_STORAGE
    UPDATE_STORAGE --> HITUNG_TURUNAN
    HITUNG_TURUNAN --> SELESAI
```
