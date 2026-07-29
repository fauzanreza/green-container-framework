# Flowchart — Hybrid Energy Estimator

> **Kode Sumber:** `framework/energy.py` → fungsi `estimate_power()` (baris 7–21), `estimate_energy()` (baris 24–26), `estimate_all()` (baris 29–36)
> **Posisi di Diagram:** Supplementary Services → Energy Estimator
> **Kategori:** 🌟 INOVASI MODEL MATEMATIKA (S2)

Model **Hybrid Hardware/Software Energy Estimation** dengan algoritma **Proportional Power Apportionment** untuk mengalokasikan konsumsi daya total host ke masing-masing container secara proporsional.

```mermaid
flowchart TD
    START(["estimate_power(cpu%, p_idle, p_max, hw_power, cpu_count)"])

    HW_CHECK{"hw_power tersedia<br/>DAN hw_power > 0?<br/>(sensor hardware aktif)"}

    subgraph TIER_A["Tier A — Hardware-True Mode"]
        HW_TOTAL["Total daya REAL dari sensor<br/>hw_power = ΔJoules / ΔTime (Watt)"]
        CALC_FRACTION["fraction = cpu% / (cpu_count × 100)<br/>Contoh: 25% / (4 × 100) = 0.0625"]
        CALC_HW_POWER["<b>Proportional Power Apportionment:</b><br/>Container_Power = hw_power × fraction<br/>Contoh: 45W × 0.0625 = 2.8125W"]
    end

    subgraph TIER_B["Tier B — Software Estimation Mode"]
        SW_UTIL["utilization = cpu% / 100<br/>Contoh: 25% → 0.25"]
        CALC_SW_POWER["<b>Linear CPU-to-Power Model</b><br/>(Jarus et al., 2014, error < 4%):<br/><br/>P(t) = P_idle + (P_max - P_idle) × utilization<br/><br/>Contoh (4-core host):<br/>P = 15.0 + (54.0 - 15.0) × 0.25<br/>P = 15.0 + 9.75 = <b>24.75 W</b>"]
        SW_NOTE["P_idle dan P_max dihitung dinamis:<br/>P_idle = cpu_count × 3.75W<br/>P_max = cpu_count × 13.5W"]
    end

    POWER_RESULT["power_watt = hasil perhitungan"]

    ENERGY(["estimate_energy(power_watt, duration_seconds)"])
    CALC_ENERGY["<b>Energy = Power × Time / 3,600,000</b><br/><br/>E(kWh) = P(W) × t(s) / 3,600,000<br/><br/>Contoh: 24.75W × 30s / 3,600,000<br/>= 0.000000206 kWh"]

    RETURN(["Return:<br/>power_watt, energy_kwh<br/>(Tidak ada konversi karbon/CO2e)"])

    START --> HW_CHECK
    HW_CHECK -->|Ya, sensor tersedia| HW_TOTAL
    HW_TOTAL --> CALC_FRACTION
    CALC_FRACTION --> CALC_HW_POWER
    CALC_HW_POWER --> POWER_RESULT

    HW_CHECK -->|Tidak, fallback software| SW_UTIL
    SW_UTIL --> CALC_SW_POWER
    CALC_SW_POWER --> SW_NOTE
    SW_NOTE --> POWER_RESULT

    POWER_RESULT --> ENERGY
    ENERGY --> CALC_ENERGY
    CALC_ENERGY --> RETURN
```

### Mengapa Ini Inovasi S2?
1. **Hybrid Adaptive Model:** Secara otomatis mendeteksi dan memilih mode terbaik (hardware atau software) tanpa konfigurasi manual.
2. **Proportional Power Apportionment:** Sensor hardware hanya melaporkan total daya CPU package. Algoritma ini secara matematis membagi total tersebut ke setiap container berdasarkan proporsi penggunaan CPU mereka.
3. **Self-Calibrating:** P_idle dan P_max bukan konstanta tetap — mereka dihitung secara dinamis dari jumlah core fisik host, sehingga model skala otomatis dari 2-core hingga 16-core.

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Estimasi Konsumsi Energi Container"])

    SENSOR{"Validasi Hardware:<br/>Sensor Daya Fisik<br/>(Sysfs) Terdeteksi?"}

    subgraph CARA_A["Mode A — Pengukuran Hardware (Hardware-True)"]
        BACA_TOTAL["Akuisisi Daya Total Host (Package Power)<br/>berdasarkan metrik fisik aktual"]
        HITUNG_BAGIAN["Kalkulasi Proporsi CPU (Fraction):<br/>Utilisasi CPU Target ÷ Total Kapasitas CPU Host<br/>(Misal: 25% CPU pada Host 4-Core = 25% ÷ 400% = 0.0625)"]
        DAYA_HW["Alokasi Daya Proporsional (Apportionment):<br/>Daya Container = Daya Total Host × Proporsi CPU<br/>(Misal: 45 W × 0.0625 = 2.81 Watt)"]
    end

    subgraph CARA_B["Mode B — Pemodelan Software (Software Estimation)"]
        PERKIRAAN["Terapkan Linear Power Model<br/>(Berdasarkan Jarus et al., 2014):<br/><br/>P(t) = P_idle + (P_max - P_idle) × Utilisasi<br/><br/>Contoh:<br/>15.0 W + (54.0 - 15.0) × 0.25<br/>= 15.0 + 9.75 = 24.75 Watt"]
        CATATAN["Parameter P_idle dan P_max dikalibrasi<br/>secara dinamis sesuai topologi core CPU host"]
    end

    DAYA["Hasil Estimasi Daya (Watt) Terkonsolidasi"]

    ENERGI["Kalkulasi Energi Akumulatif (Integration over time):<br/>E (kWh) = Daya (W) × Waktu (s) / 3,600,000<br/><br/>Contoh: 24.75 W × 30s / 3,600,000<br/>= 0.000000206 kWh"]

    HASIL(["Return Metadata Metrik:<br/>• Instantaneous Power (Watt)<br/>• Akumulasi Energi (kWh)"])

    START --> SENSOR
    SENSOR -->|Ya, Sensor Fisik| BACA_TOTAL
    BACA_TOTAL --> HITUNG_BAGIAN
    HITUNG_BAGIAN --> DAYA_HW
    DAYA_HW --> DAYA

    SENSOR -->|Tidak, Fallback| PERKIRAAN
    PERKIRAAN --> CATATAN
    CATATAN --> DAYA

    DAYA --> ENERGI
    ENERGI --> HASIL
```
