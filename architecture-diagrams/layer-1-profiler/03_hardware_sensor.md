# Flowchart — hardware_sensor.PowerSensor (Layer 1)

> **Kode Sumber:** `framework/hardware_sensor.py` → class `PowerSensor`, fungsi `_detect_sensor()`, `_read_joules()`, dan `get_power_watts()` (baris 12–97)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → Hardware Power Sensor Detection & Acquisition
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Modul pembaca sensor daya fisik tingkat motherboard/silikon. Mendeteksi register energi Intel RAPL (`/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`) atau AMD Energy (`/sys/class/hwmon/*/energy1_input`). Dilengkapi perlindungan pembacaan baseline pertama dan unwrap register counter saat overflow (`max_energy_range_uj`). Jika tidak tersedia (misal di cloud VPS tanpa virtual RAPL), modul fallback dengan aman dan mengembalikan `None`.

```mermaid
flowchart TD
    START(["PowerSensor.__init__()"])

    DETECT["_detect_sensor():<br/>Cari path register daya"]

    CHECK_RAPL["1. Cek Intel RAPL:<br/>/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj<br/>(exists & os.access R_OK)"]
    RAPL_FOUND{"RAPL ada &<br/>bisa dibaca?"}
    SET_RAPL["sensor_path = rapl_path"]

    CHECK_HWMON["2. Cek AMD hwmon:<br/>Iterasi /sys/class/hwmon/*/energy1_input<br/>(exists & os.access R_OK)"]
    HWMON_FOUND{"hwmon ada &<br/>bisa dibaca?"}
    SET_HWMON["sensor_path = hwmon_path"]
    NO_SENSOR["sensor_path = None"]

    INIT_CHECK{"sensor_path<br/>!= None?"}
    SET_AVAIL_TRUE["available = True<br/>Panggil _read_joules() untuk baseline reading"]
    SET_AVAIL_FALSE["available = False<br/>Log warning fallback software model"]

    READ_START(["get_power_watts()"])
    CHECK_ACTIVE{"available<br/>== True?"}
    RETURN_NONE(["Return None<br/>(Trigger Software Linear Model di energy.py)"])

    READ_JOULES["_read_joules():<br/>Buka sensor_path, baca microjoules<br/>joules = microjoules / 1,000,000.0<br/>now = time.time()"]
    FIRST_READ{"last_joules<br/>is None?"}
    SET_BASELINE["last_joules = joules<br/>last_time = now<br/>Return 0.0"]

    WRAP_CHECK{"joules &lt;<br/>last_joules?<br/>(Counter wrap-around)"}
    UNWRAP["Baca max_energy_range_uj<br/>joules += max_range / 1,000,000.0"]

    CALC_DELTA["delta_j = joules - last_joules<br/>delta_t = now - last_time<br/>last_joules = joules, last_time = now"]
    DELTA_TIME{"delta_t &gt; 0?"}
    CALC_WATTS["watts = delta_j / delta_t"]
    ZERO_WATTS["watts = 0.0"]

    READ_ERROR{"OSError /<br/>Exception?"}
    HANDLE_ERR["Log error, set available = False<br/>Return 0.0"]

    RETURN_WATTS(["Return round(watts, 3) (Satuan: Watt)"])

    START --> DETECT
    DETECT --> CHECK_RAPL
    CHECK_RAPL --> RAPL_FOUND
    RAPL_FOUND -->|Ya| SET_RAPL
    RAPL_FOUND -->|Tidak| CHECK_HWMON
    CHECK_HWMON --> HWMON_FOUND
    HWMON_FOUND -->|Ya| SET_HWMON
    HWMON_FOUND -->|Tidak| NO_SENSOR

    SET_RAPL --> INIT_CHECK
    SET_HWMON --> INIT_CHECK
    NO_SENSOR --> INIT_CHECK

    INIT_CHECK -->|Ya| SET_AVAIL_TRUE
    INIT_CHECK -->|Tidak| SET_AVAIL_FALSE

    READ_START --> CHECK_ACTIVE
    CHECK_ACTIVE -->|Tidak| RETURN_NONE
    CHECK_ACTIVE -->|Ya| READ_JOULES

    READ_JOULES --> READ_ERROR
    READ_ERROR -->|Ya| HANDLE_ERR
    HANDLE_ERR --> RETURN_NONE
    READ_ERROR -->|Tidak| FIRST_READ

    FIRST_READ -->|Ya| SET_BASELINE
    SET_BASELINE --> RETURN_WATTS
    FIRST_READ -->|Tidak| WRAP_CHECK

    WRAP_CHECK -->|Ya| UNWRAP
    WRAP_CHECK -->|Tidak| CALC_DELTA
    UNWRAP --> CALC_DELTA

    CALC_DELTA --> DELTA_TIME
    DELTA_TIME -->|Ya| CALC_WATTS
    DELTA_TIME -->|Tidak| ZERO_WATTS
    CALC_WATTS --> RETURN_WATTS
    ZERO_WATTS --> RETURN_WATTS
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Inisialisasi & Pembacaan Daya Fisik Host"])

    subgraph DETEKSI["Fase Deteksi Sensor (Cold-Start)"]
        CEK_INTEL["1. Pindai Driver Intel RAPL (/sys/class/powercap/intel-rapl)"]
        KETEMU_INTEL{"Driver Intel<br/>Aktif?"}
        PAKAI_INTEL["Pilih Jalur Intel (energy_uj)"]

        CEK_AMD["2. Pindai Driver AMD/Generic (/sys/class/hwmon/*/energy1_input)"]
        KETEMU_AMD{"Driver AMD<br/>Aktif?"}
        PAKAI_AMD["Pilih Jalur AMD hwmon"]

        TIDAK_ADA["Sensor Tidak Ditemukan / Lingkungan Cloud VPS Terisolasi"]
    end

    subgraph AKUISISI["Fase Pembacaan Real-Time (get_power_watts)"]
        BACA_ENERGY["Baca Nilai Microjoules Terkini dari Virtual File Kernel"]
        CEK_PERTAMA{"Apakah Pembacaan Perdana?"}
        SIMPAN_DASAR["Simpan sebagai Nilai Dasar (t_0) → Watt = 0.0"]

        CEK_WRAP{"Apakah Nilai Counter Berkurang?<br/>(Register 32-bit/64-bit Overflow)"}
        PULIHKAN_WRAP["Unwrap Counter dengan Konstanta max_energy_range_uj"]

        HITUNG_WATT["Kalkulasi Daya Rata-Rata:<br/>Daya (Watt) = Δ Energi (Joule) ÷ Δ Waktu (detik)"]
    end

    SELESAI_NILAI(["END: Return Daya Aktual Host (Watt)"])
    SELESAI_FALLBACK(["END: Return None → Aktifkan Software Power Model"])

    START --> CEK_INTEL
    CEK_INTEL --> KETEMU_INTEL
    KETEMU_INTEL -->|Ya| PAKAI_INTEL
    KETEMU_INTEL -->|Tidak| CEK_AMD
    CEK_AMD --> KETEMU_AMD
    KETEMU_AMD -->|Ya| PAKAI_AMD
    KETEMU_AMD -->|Tidak| TIDAK_ADA

    PAKAI_INTEL --> BACA_ENERGY
    PAKAI_AMD --> BACA_ENERGY
    TIDAK_ADA --> SELESAI_FALLBACK

    BACA_ENERGY --> CEK_PERTAMA
    CEK_PERTAMA -->|Ya| SIMPAN_DASAR
    SIMPAN_DASAR --> SELESAI_NILAI
    CEK_PERTAMA -->|Tidak| CEK_WRAP

    CEK_WRAP -->|Ya| PULIHKAN_WRAP
    CEK_WRAP -->|Tidak| HITUNG_WATT
    PULIHKAN_WRAP --> HITUNG_WATT

    HITUNG_WATT --> SELESAI_NILAI
```
