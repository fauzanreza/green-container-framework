# Flowchart — energy.estimate_all() (Supplementary)

> **Kode Sumber:** `framework/energy.py` → fungsi `estimate_power()`, `estimate_energy()`, dan `estimate_all()` (baris 7–75)
> **Posisi di Diagram:** Supplementary Services → Estimator Konsumsi Daya (Hybrid Hardware/Software Model + Additive DRAM)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Model estimasi konsumsi energi hibrida (Joule dan kWh, tanpa konversi emisi karbon sesuai batasan penelitian proposal). Menggunakan **Additive Multi-Component Model** ($P_{\text{total}} = P_{\text{cpu}} + P_{\text{dram}}$) yang menggabungkan Jarus et al. (2014) untuk CPU dan Kansal et al. (Joulemeter) / CNCF Kepler ($C_{\text{dram}} = 0.38\text{ W/GB}$) untuk memori:

1. **Komponen DRAM ($P_{\text{dram}}$):** Dihitung dari working set memory kontainer (`memory.current - inactive_file`):
   $$P_{\text{dram}}(t) = \text{RAM}_{\text{used\_GB}}(t) \times C_{\text{dram}}$$
2. **Tier A — Hardware-True Mode (Motherboard Physical Sensors):** Bila sensor perangkat keras (Intel RAPL / AMD hwmon) terdeteksi, alokasi CPU proporsional ditambahkan ke footprint DRAM:
   $$P_{\text{container}}(t) = \left[ P_{\text{hw\_total}} \times \left( \frac{\text{CPU}_{\text{container}}\%}{\text{Host Cores} \times 100\%} \right) \right] + P_{\text{dram}}(t)$$
3. **Tier B — Software Estimation Mode (Cloud VPS / Hypervisor):** Menggunakan model linier terkalibrasi dinamis untuk CPU ditambah footprint DRAM:
   $$P_{\text{total}}(t) = \left[ P_{\text{idle}} + (P_{\text{max}} - P_{\text{idle}}) \times U_{\text{CPU}}(t) \right] + P_{\text{dram}}(t)$$
   dengan $P_{\text{idle}} = \text{cores} \times 3.75\text{W}$ dan $P_{\text{max}} = \text{cores} \times 13.5\text{W}$.
4. **Penanganan Status Micro-Frozen (`is_frozen=True`):** Mengembalikan baseline daya idle host ($P_{\text{idle}}$) ditambah daya retensi DRAM aktif ($P_{\text{dram}}$) sebagai footprint dasar kontainer, menjaga konsistensi dataset telemetri tanpa nilai nol anomali.
5. **Integrasi Energi (kWh):** Dihitung per interval waktu:
   $$E_{\text{kWh}} = \frac{P_{\text{watt}} \times \Delta t_{\text{seconds}}}{3.600.000}$$

```mermaid
flowchart TD
    START(["estimate_all(cpu_percent, duration_seconds,<br/>p_idle, p_max, hw_power, cpu_count, is_frozen,<br/>memory_bytes, p_dram_per_gb)"])

    CALC_DRAM["ram_gb = memory_bytes / (1024³)<br/>p_dram = ram_gb × p_dram_per_gb (0.38 W/GB)"]

    CHECK_FROZEN{"is_frozen == True?<br/>(Kontainer sedang Micro-Frozen)"}
    SET_IDLE_POWER["power_watt = round(p_idle + p_dram, 3)<br/>(Baseline Footprint Host + Retensi DRAM)"]

    CHECK_HW{"hw_power != None<br/>DAN hw_power > 0?<br/>(Tier A: Sensor Fisik Aktif)"}

    subgraph HW_MODE["Tier A: Hardware Proportional Apportionment"]
        CALC_CAPACITY["total_capacity = float(cpu_count × 100.0)"]
        CALC_FRACTION["fraction = max(0.0, cpu_percent) / total_capacity"]
        CALC_HW_WATT["calculated_cpu = hw_power × fraction"]
        CHECK_HW_ZERO{"calculated_cpu ≤ 0.0?"}
        HW_FALLBACK_IDLE["power_watt = round(p_idle + p_dram, 3)"]
        HW_FINAL["power_watt = round(calculated_cpu + p_dram, 3)"]
    end

    subgraph SW_MODE["Tier B: Software Additive Estimation (Jarus + Kansal)"]
        CALC_UTIL["utilization = max(0.0, min(cpu_percent, 100.0)) / 100.0"]
        CALC_SW_WATT["calculated_cpu = p_idle + (p_max - p_idle) × utilization"]
        CHECK_SW_ZERO{"calculated_cpu ≤ 0.0?"}
        SW_FALLBACK_IDLE["power_watt = round(p_idle + p_dram, 3)"]
        SW_FINAL["power_watt = round(calculated_cpu + p_dram, 3)"]
    end

    CALC_KWH["estimate_energy(power_watt, duration_seconds):<br/>energy_kwh = round((power_watt × duration_seconds) / 3,600,000, 9)"]

    RETURN(["Return dict(<br/>power_watt, energy_kwh, p_cpu_watt, p_dram_watt)"])

    START --> CALC_DRAM
    CALC_DRAM --> CHECK_FROZEN
    CHECK_FROZEN -->|Ya| SET_IDLE_POWER
    CHECK_FROZEN -->|Tidak| CHECK_HW

    CHECK_HW -->|Ya| CALC_CAPACITY
    CALC_CAPACITY --> CALC_FRACTION
    CALC_FRACTION --> CALC_HW_WATT
    CALC_HW_WATT --> CHECK_HW_ZERO
    CHECK_HW_ZERO -->|Ya| HW_FALLBACK_IDLE
    CHECK_HW_ZERO -->|Tidak| HW_FINAL

    CHECK_HW -->|Tidak| CALC_UTIL
    CALC_UTIL --> CALC_SW_WATT
    CALC_SW_WATT --> CHECK_SW_ZERO
    CHECK_SW_ZERO -->|Ya| SW_FALLBACK_IDLE
    CHECK_SW_ZERO -->|Tidak| SW_FINAL

    SET_IDLE_POWER --> CALC_KWH
    HW_FALLBACK_IDLE --> CALC_KWH
    HW_FINAL --> CALC_KWH
    SW_FALLBACK_IDLE --> CALC_KWH
    SW_FINAL --> CALC_KWH

    CALC_KWH --> RETURN
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Estimasi Konsumsi Daya & Energi"])
    HITUNG_DRAM["Hitung Daya DRAM: P_dram = RAM_used_GB × 0.38 W/GB"]

    CEK_BEKU{"Apakah Kontainer Dalam Status Micro-Frozen?"}
    DAYA_IDLE["Daya = Baseline Idle Host (P_idle) + P_dram"]

    CEK_SENSOR_FISIK{"Apakah Sinyal Daya Fisik Host Tersedia? (RAPL/hwmon)"}

    subgraph JALUR_HARDWARE["Mode A: Proportional Apportionment + DRAM"]
        BACA_DAYA_TOTAL["Dapatkan Daya Listrik Aktual Seluruh Socket CPU Host (Watt)"]
        HITUNG_PORSI["Hitung Porsi Penggunaan CPU Kontainer terhadap Kapasitas Total Host"]
        ALOKASI_PORSI["Alokasikan Daya: P_cpu = Daya Host × Porsi CPU<br/>Total = P_cpu + P_dram"]
    end

    subgraph JALUR_SOFTWARE["Mode B: Model Aditif Multi-Komponen (Jarus + Kansal)"]
        HITUNG_UTILISASI["Hitung Utilisasi Relatif CPU Kontainer (0.0 s.d. 1.0)"]
        INTERPOLASI_DAYA["Kalkulasi Daya CPU: P_cpu = P_idle + (P_max − P_idle) × Utilisasi<br/>Total = P_cpu + P_dram"]
        KALIBRASI_DINAMIS["Catatan: P_idle & P_max terkalibrasi otomatis sesuai jumlah core"]
    end

    INTEGRASI_ENERGI["Integrasi Daya ke Satuan Energi Kumulatif:<br/>Energi (kWh) = Daya (Watt) × Durasi Interval (detik) ÷ 3.600.000"]

    SELESAI(["END: Return Metrik Daya (Watt) dan Energi (kWh)"])

    START --> HITUNG_DRAM
    HITUNG_DRAM --> CEK_BEKU
    CEK_BEKU -->|Ya| DAYA_IDLE
    CEK_BEKU -->|Tidak| CEK_SENSOR_FISIK

    CEK_SENSOR_FISIK -->|Ya| BACA_DAYA_TOTAL
    BACA_DAYA_TOTAL --> HITUNG_PORSI
    HITUNG_PORSI --> ALOKASI_PORSI
    ALOKASI_PORSI --> INTEGRASI_ENERGI

    CEK_SENSOR_FISIK -->|Tidak| HITUNG_UTILISASI
    HITUNG_UTILISASI --> INTERPOLASI_DAYA
    INTERPOLASI_DAYA --> INTEGRASI_ENERGI

    DAYA_IDLE --> INTEGRASI_ENERGI
    INTEGRASI_ENERGI --> SELESAI
```
