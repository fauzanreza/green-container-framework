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
