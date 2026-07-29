# Flowchart — Profiler.profile_host() (Layer 1)

> **Kode Sumber:** `framework/profiler.py` → class `EnvironmentProfiler`, fungsi `profile_host()` (baris 35–88)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → Host Detection
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Sistem profilasi otomatis. Menghindari hardcoding parameter. Mendeteksi topologi CPU dan memori secara dinamis agar model estimasi energi bisa melakukan self-calibration sesuai server tempat HECF dijalankan (mendukung portabilitas).

```mermaid
flowchart TD
    START(["profile_host()"])

    CPU_TRY["Deteksi Core:<br/>baca /sys/devices/system/cpu/online"]
    CPU_ERR{"I/O Error?"}
    CPU_FALLBACK["Fallback:<br/>os.cpu_count()"]
    CPU_OK["Simpan host_cores"]

    RAM_TRY["Deteksi RAM:<br/>baca MemTotal dari /proc/meminfo"]
    RAM_OK["Simpan host_ram"]

    ENERGY_CONST["Set konstanta linear power model:<br/>p_idle = core_count × 3.75W<br/>p_max = core_count × 13.5W"]

    RAPL_CHECK["Deteksi Hardware Sensor:<br/>cek /sys/class/powercap/intel-rapl"]
    RAPL_FOUND{"Sensor ada?"}
    RAPL_YES["Set hw_sensor_available = True"]
    RAPL_NO["Set hw_sensor_available = False"]

    NS_CHECK["Validasi Namespace:<br/>baca /proc/1/cgroup"]
    NS_MATCH{"Sesuai?"}
    NS_WARN["Log Warning: Namespace mismatch!"]
    NS_OK["Log Info: Namespace OK"]

    NET_CHECK["Deteksi Batas Netfilter:<br/>baca nf_conntrack_max"]
    NET_WARN{"nf_conntrack_max<br/>< 131072?"}
    WARN_LOG["Log Warning: Risiko packet drop"]
    NET_OK["Log Info: Conntrack OK"]

    RETURN(["Return dict(host_cores, host_ram, dll)"])

    START --> CPU_TRY
    CPU_TRY --> CPU_ERR
    CPU_ERR -->|Ya| CPU_FALLBACK
    CPU_ERR -->|Tidak| CPU_OK
    CPU_FALLBACK --> RAM_TRY
    CPU_OK --> RAM_TRY
    RAM_TRY --> RAM_OK
    RAM_OK --> ENERGY_CONST
    ENERGY_CONST --> RAPL_CHECK
    RAPL_CHECK --> RAPL_FOUND
    RAPL_FOUND -->|Ya| RAPL_YES
    RAPL_FOUND -->|Tidak| RAPL_NO
    RAPL_YES --> NS_CHECK
    RAPL_NO --> NS_CHECK
    NS_CHECK --> NS_MATCH
    NS_MATCH -->|Tidak| NS_WARN
    NS_MATCH -->|Ya| NS_OK
    NS_WARN --> NET_CHECK
    NS_OK --> NET_CHECK
    NET_CHECK --> NET_WARN
    NET_WARN -->|Ya| WARN_LOG
    NET_WARN -->|Tidak| NET_OK
    WARN_LOG --> RETURN
    NET_OK --> RETURN
```

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Host Profiling (Cold-Start)"])

    CEK_CPU["Deteksi Topologi CPU (Logical Processors)"]
    CPU_GAGAL{"Eksekusi<br/>Gagal?"}
    CPU_CADANGAN["Fallback: API OS (os.cpu_count)"]
    CPU_DAPAT["Host Cores terverifikasi"]

    CEK_RAM["Deteksi Kapasitas RAM"]
    RAM_DAPAT["Host RAM terverifikasi"]

    HITUNG_DAYA["Kalkulasi Konstanta Estimasi Daya:<br/>• Baseline (P_idle) = cores × 3.75W<br/>• Max (P_max) = cores × 13.5W"]

    CEK_SENSOR["Deteksi Hardware Sensor (RAPL/hwmon)"]
    SENSOR_ADA{"Sensor<br/>Tersedia?"}
    SENSOR_YA["✅ Mode Hardware-True"]
    SENSOR_TIDAK["⚠ Fallback: Software Estimation"]

    CEK_ASLI["Verifikasi Cgroup Namespace (/proc/1/cgroup)"]
    ASLI{"Sesuai?"}
    ASLI_OK["✅ Validasi Namespace Sukses"]
    ASLI_GAGAL["⚠ Peringatan: Inkonsistensi Namespace"]

    CEK_JARINGAN["Verifikasi Kapasitas nf_conntrack"]
    JARINGAN{"Kapasitas<br/>Memadai?"}
    JARINGAN_OK["✅ Kapasitas Conntrack Memadai"]
    JARINGAN_WARN["⚠ Peringatan: Risiko packet drop"]

    SELESAI(["Profil Host Terbentuk (Ready)"])

    START --> CEK_CPU
    CEK_CPU --> CPU_GAGAL
    CPU_GAGAL -->|Ya| CPU_CADANGAN
    CPU_GAGAL -->|Tidak| CPU_DAPAT
    CPU_CADANGAN --> CEK_RAM
    CPU_DAPAT --> CEK_RAM
    CEK_RAM --> RAM_DAPAT
    RAM_DAPAT --> HITUNG_DAYA
    HITUNG_DAYA --> CEK_SENSOR
    CEK_SENSOR --> SENSOR_ADA
    SENSOR_ADA -->|Ya| SENSOR_YA
    SENSOR_ADA -->|Tidak| SENSOR_TIDAK
    SENSOR_YA --> CEK_ASLI
    SENSOR_TIDAK --> CEK_ASLI
    CEK_ASLI --> ASLI
    ASLI -->|Ya| ASLI_OK
    ASLI -->|Tidak| ASLI_GAGAL
    ASLI_OK --> CEK_JARINGAN
    ASLI_GAGAL --> CEK_JARINGAN
    CEK_JARINGAN --> JARINGAN
    JARINGAN -->|Ya| JARINGAN_OK
    JARINGAN -->|Tidak| JARINGAN_WARN
    JARINGAN_OK --> SELESAI
    JARINGAN_WARN --> SELESAI
```
