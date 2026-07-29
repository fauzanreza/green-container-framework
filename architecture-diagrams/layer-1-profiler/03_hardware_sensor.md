# Flowchart — PowerSensor (Hardware Energy Detection)

> **Kode Sumber:** `framework/hardware_sensor.py` → class `PowerSensor` (baris 12–87)
> **Posisi di Diagram:** Layer 1 — Hybrid HW Sensor Detection
> **Kategori:** Tools / Data Acquisition (S1)

Mendeteksi apakah sensor daya hardware tersedia (Intel RAPL atau AMD hwmon). Jika ya, membaca Joule nyata dari motherboard. Jika tidak, fallback ke model estimasi perangkat lunak.

```mermaid
flowchart TD
    START(["PowerSensor.__init__()"])

    DETECT["_detect_sensor()"]

    CHECK_RAPL{"File ada dan readable?<br/>/sys/class/powercap/<br/>intel-rapl/intel-rapl:0/energy_uj"}
    RAPL_OK["sensor_path = rapl_path"]

    CHECK_AMD{"Scan /sys/class/hwmon/*/<br/>Cari energy1_input"}
    AMD_OK["sensor_path = hwmon path"]
    NO_SENSOR["sensor_path = None"]

    AVAILABLE{"sensor_path<br/>ditemukan?"}
    INIT_READ["Baca baseline awal<br/>_read_joules()<br/>last_joules = current"]
    LOG_OK["✅ DETECTED real power sensor"]
    LOG_FAIL["⚠ Blocked by virtualization<br/>Fallback to Software Estimation"]

    CALL(["get_power_watts() dipanggil"])
    IS_AVAIL{"available?"}
    RET_NONE["Return None<br/>(energy.py pakai model software)"]
    READ_UJ["Baca energy_uj dari sensor"]
    CALC_DELTA["ΔJoules = current - last_joules<br/>ΔTime = now - last_time"]
    CALC_WATTS["Watts = ΔJoules / ΔTime"]
    WRAP{"Counter wrap-around?<br/>(joules < last_joules)"}
    RESET["Reset baseline<br/>Return 0.0"]
    RET_WATTS(["Return Watts (rounded)"])

    START --> DETECT
    DETECT --> CHECK_RAPL
    CHECK_RAPL -->|Ya| RAPL_OK
    CHECK_RAPL -->|Tidak| CHECK_AMD
    RAPL_OK --> AVAILABLE
    CHECK_AMD -->|Ditemukan| AMD_OK
    CHECK_AMD -->|Tidak ada| NO_SENSOR
    AMD_OK --> AVAILABLE
    NO_SENSOR --> AVAILABLE

    AVAILABLE -->|Ya| INIT_READ
    AVAILABLE -->|Tidak| LOG_FAIL
    INIT_READ --> LOG_OK

    CALL --> IS_AVAIL
    IS_AVAIL -->|Tidak| RET_NONE
    IS_AVAIL -->|Ya| READ_UJ
    READ_UJ --> WRAP
    WRAP -->|Ya| RESET
    WRAP -->|Tidak| CALC_DELTA
    CALC_DELTA --> CALC_WATTS
    CALC_WATTS --> RET_WATTS
```

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Inisialisasi Deteksi Sensor Daya Perangkat Keras"])

    CARI["Eksplorasi Antarmuka Sysfs untuk<br/>Metrik Konsumsi Daya Fisik"]

    CEK_INTEL{"Ketersediaan interface<br/>Intel RAPL?"}
    INTEL_ADA["Modul Intel RAPL Terdeteksi"]

    CEK_AMD{"Ketersediaan interface<br/>AMD Energy/hwmon?"}
    AMD_ADA["Modul AMD hwmon Terdeteksi"]
    TIDAK_ADA["Sensor Perangkat Keras Absen"]

    TERSEDIA{"Resolusi<br/>Sensor?"}
    BACA_AWAL["Akuisisi nilai Joule absolut (baseline)<br/>sebagai titik referensi (t=0)"]
    BERHASIL["✅ Mode Hardware-True Tersedia<br/>(Akurasi Pengukuran Real-Time)"]
    GAGAL["⚠ Restriksi Virtualisasi / Sensor Absen<br/>(Fallback: Software Estimation Model)"]

    DIMINTA(["Siklus Permintaan Data Daya (Polling):"])
    BISA{"Status<br/>Ketersediaan?"}
    TIDAK_BISA["Kembalikan Null<br/>(Trigger Software Apportionment)"]
    BACA["Akuisisi nilai delta akumulasi energi<br/>sejak polling terakhir"]
    ANOMALI{"Deteksi Integer Overflow /<br/>Anomali Counter (Delta Negatif)?"}
    RESET["Kalibrasi ulang baseline (Reset State)"]
    HITUNG["Kalkulasi Daya (Power):<br/>Δ Energi (Joule) ÷ Δ Waktu (Detik) = Watt"]
    HASIL(["Kembalikan Estimasi Daya (Watt)"])

    START --> CARI
    CARI --> CEK_INTEL
    CEK_INTEL -->|Ya| INTEL_ADA
    CEK_INTEL -->|Tidak| CEK_AMD
    INTEL_ADA --> TERSEDIA
    CEK_AMD -->|Ya| AMD_ADA
    CEK_AMD -->|Tidak| TIDAK_ADA
    AMD_ADA --> TERSEDIA
    TIDAK_ADA --> TERSEDIA

    TERSEDIA -->|Ya| BACA_AWAL
    TERSEDIA -->|Tidak| GAGAL
    BACA_AWAL --> BERHASIL

    DIMINTA --> BISA
    BISA -->|Tidak| TIDAK_BISA
    BISA -->|Ya| BACA
    BACA --> ANOMALI
    ANOMALI -->|Ya| RESET
    ANOMALI -->|Tidak| HITUNG
    HITUNG --> HASIL
```
