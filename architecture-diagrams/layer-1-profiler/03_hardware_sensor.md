# Flowchart — Profiler.read_host_power() (Layer 1)

> **Kode Sumber:** `framework/profiler.py` → class `EnvironmentProfiler`, fungsi `read_host_power()` (baris 172–215)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → RAPL/hwmon Sensor Reader
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Sistem pembaca sensor energi tingkat silikon. Jika didukung oleh motherboard, metode ini memberikan data konsumsi daya absolut (True Power) dengan margin error <2%, jauh lebih akurat dibandingkan dengan Software Power Estimation.

```mermaid
flowchart TD
    START(["read_host_power()"])

    AVAILABLE{"hw_sensor_available<br/>== True?"}
    NOT_AVAILABLE(["Return None<br/>(Trigger Software Model)"])

    TRY_RAPL["Coba Intel RAPL:<br/>Baca /sys/class/powercap/intel-rapl:0/energy_uj"]
    RAPL_SUCCESS{"Berhasil?"}

    CALC_RAPL["Hitung delta energy_uj dengan bacaan sebelumnya<br/>Konversi µJ ke Watt (Joule/s)"]

    TRY_HWMON["Coba HWMON (AMD/Generic):<br/>Iterasi /sys/class/hwmon/hwmon*/power1_input"]
    HWMON_SUCCESS{"Berhasil?"}

    CALC_HWMON["Konversi mikrowatt ke Watt"]

    NO_SENSOR["Log Error: Sensor read failed"]

    RETURN_POWER(["Return host_power_watts"])

    START --> AVAILABLE
    AVAILABLE -->|Tidak| NOT_AVAILABLE
    AVAILABLE -->|Ya| TRY_RAPL

    TRY_RAPL --> RAPL_SUCCESS
    RAPL_SUCCESS -->|Ya| CALC_RAPL
    RAPL_SUCCESS -->|Tidak| TRY_HWMON

    TRY_HWMON --> HWMON_SUCCESS
    HWMON_SUCCESS -->|Ya| CALC_HWMON
    HWMON_SUCCESS -->|Tidak| NO_SENSOR

    CALC_RAPL --> RETURN_POWER
    CALC_HWMON --> RETURN_POWER
    NO_SENSOR --> NOT_AVAILABLE
```

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Akuisisi Metrik Daya Host"])

    CEK_STATUS{"Apakah Sensor<br/>Power Aktif?"}
    SELESAI_LEWAT(["END: Abort, Gunakan Software Model"])

    subgraph INTEL["Jalur Intel RAPL"]
        BACA_INTEL["Baca register energy_uj"]
        STATUS_INTEL{"Apakah Pembacaan<br/>I/O Sukses?"}
        HITUNG_INTEL["Konversi Microjoules → Watt (Δ / waktu)"]
    end

    subgraph AMD_GENERIC["Jalur HWMON (AMD / Universal)"]
        BACA_AMD["Baca register power1_input"]
        STATUS_AMD{"Apakah Pembacaan<br/>I/O Sukses?"}
        HITUNG_AMD["Konversi Microwatts → Watt"]
    end

    GAGAL["Hardware Error: Kembalikan None"]

    SELESAI(["END: Return True Power (Watt)"])

    START --> CEK_STATUS
    CEK_STATUS -->|Tidak| SELESAI_LEWAT
    CEK_STATUS -->|Ya| BACA_INTEL

    BACA_INTEL --> STATUS_INTEL
    STATUS_INTEL -->|Ya| HITUNG_INTEL
    STATUS_INTEL -->|Tidak| BACA_AMD

    BACA_AMD --> STATUS_AMD
    STATUS_AMD -->|Ya| HITUNG_AMD
    STATUS_AMD -->|Tidak| GAGAL

    HITUNG_INTEL --> SELESAI
    HITUNG_AMD --> SELESAI
    GAGAL --> SELESAI_LEWAT
```
