# Flowchart — EnergyEstimator.get_energy() (Supplementary)

> **Kode Sumber:** `framework/energy.py` → class `EnergyEstimator`, fungsi `get_container_energy()` (baris 30–75)
> **Posisi di Diagram:** Supplementary Services → Estimator Konsumsi Daya
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Model hibrida cerdas (Smart Hybrid Model) yang dapat menukar metode pengukuran daya (fisik vs estimasi perangkat lunak) secara dinamis, mengalokasikan (apportionment) daya tingkat host ke kontainer individu, dan mengintegrasikan daya (Watt) seiring waktu menjadi energi murni (kWh).

```mermaid
flowchart TD
    START(["get_container_energy(container, cpu_pct, elapsed)"])

    HW_CHECK{"Hardware Sensor<br/>(RAPL/hwmon)<br/>Aktif?"}
    HW_TOTAL["Baca daya host aktual (Watt)"]
    HW_FRAC["Kalkulasi fraksi CPU:<br/>cpu_pct / (core_count × 100)"]
    HW_ALLOC["Alokasikan daya:<br/>Daya Container = host_watt × fraksi"]

    SW_UTIL["Hitung utilisasi termodulasi:<br/>util = cpu_pct / (core_count × 100)"]
    SW_MODEL["Model Linier (Jarus et al.):<br/>Daya = P_idle + (P_max - P_idle) × util"]

    POWER_RES["power_w = Daya Kontainer (Watt)"]

    CALC_ENERGY["Integrasi ke kWh:<br/>energy_kwh = power_w × elapsed / 3,600,000"]

    RETURN(["Return (power_w, energy_kwh)"])

    START --> HW_CHECK
    HW_CHECK -->|"Ya (Sensor Fisik)"| HW_TOTAL
    HW_TOTAL --> HW_FRAC
    HW_FRAC --> HW_ALLOC
    HW_ALLOC --> POWER_RES

    HW_CHECK -->|"Tidak (Fallback)"| SW_UTIL
    SW_UTIL --> SW_MODEL
    SW_MODEL --> POWER_RES

    POWER_RES --> CALC_ENERGY
    CALC_ENERGY --> RETURN
```

## Mengapa Ini Inovasi S2?

1. **Hybrid Adaptive Model:** Secara otomatis mendeteksi dan memilih mode terbaik (hardware atau software) tanpa konfigurasi manual.
2. **Proportional Power Apportionment:** Sensor hardware hanya melaporkan total daya CPU package. Algoritma ini secara matematis membagi total tersebut ke setiap container berdasarkan proporsi penggunaan CPU mereka.
3. **Self-Calibrating:** P_idle dan P_max bukan konstanta tetap — mereka dihitung secara dinamis dari jumlah core fisik host, sehingga model skala otomatis dari 2-core hingga 16-core.

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Estimasi Energi Container"])

    SENSOR{"Sensor Hardware<br/>(Sysfs) Aktif?"}

    subgraph CARA_A["Mode A — Pengukuran Hardware (Hardware-True)"]
        BACA_TOTAL["Baca Package Power Host (aktual)"]
        HITUNG_BAGIAN["Hitung Proporsi CPU (Fraction):<br/>CPU Container ÷ Total CPU Host"]
        DAYA_HW["Alokasi Daya (Apportionment):<br/>Daya Container = Daya Host × Proporsi CPU"]
    end

    subgraph CARA_B["Mode B — Pemodelan Software (Software Estimation)"]
        PERKIRAAN["Terapkan Linear Power Model:<br/>P(t) = P_idle + (P_max - P_idle) × Util"]
        CATATAN["P_idle & P_max dikalibrasi dinamis<br/>sesuai topologi CPU host"]
    end

    DAYA["Konsolidasi Daya (Watt)"]

    ENERGI["Integrasi ke Energi (kWh):<br/>E (kWh) = Daya (W) × Waktu (s) / 3.6e6"]

    HASIL(["Return Metadata:<br/>• Instantaneous Power (W)<br/>• Energi (kWh)"])

    START --> SENSOR
    SENSOR -->|"Ya (Hardware)"| BACA_TOTAL
    BACA_TOTAL --> HITUNG_BAGIAN
    HITUNG_BAGIAN --> DAYA_HW
    DAYA_HW --> DAYA

    SENSOR -->|"Tidak (Software)"| PERKIRAAN
    PERKIRAAN --> CATATAN
    CATATAN --> DAYA

    DAYA --> ENERGI
    ENERGI --> HASIL
```
