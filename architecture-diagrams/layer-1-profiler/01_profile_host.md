# Flowchart — profiler.profile_host() (Layer 1)

> **Kode Sumber:** `framework/profiler.py` → fungsi `profile_host()` (baris 20–91)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → Host Detection
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Sistem profilasi otomatis host saat cold-start. Membaca topologi CPU dan memori secara dinamis dari `/proc`, menginisialisasi modul sensor perangkat keras (`hardware_sensor.PowerSensor`), memverifikasi namespace host (`pid: host`), dan melakukan pre-flight check batas `nf_conntrack_max`.

```mermaid
flowchart TD
    START(["profile_host()"])

    CPU_TRY["Deteksi Core:<br/>baca /proc/cpuinfo<br/>(hitung baris 'processor')"]
    CPU_ERR{"I/O Error?"}
    CPU_FALLBACK["Fallback:<br/>os.cpu_count() atau 1"]
    CPU_OK["Simpan cpu_count"]

    RAM_TRY["Deteksi RAM:<br/>baca MemTotal dari /proc/meminfo"]
    RAM_OK["mem_total_mb = mem_total_kb // 1024"]

    ENERGY_CONST["Hitung konstanta linear power model:<br/>p_idle_watts = round(cpu_count × 3.75, 1)<br/>p_max_watts = round(cpu_count × 13.5, 1)"]

    SENSOR_INIT["Inisialisasi Hardware Power Sensor:<br/>hw_sensor = PowerSensor()"]

    NS_CHECK["Verifikasi Mount /proc Host:<br/>os_cpu = os.cpu_count() or 1<br/>cross-check cpu_count == os_cpu"]
    NS_MATCH{"cpu_count ==<br/>os_cpu?"}
    NS_WARN["Log Critical: /proc MISMATCH!<br/>Pastikan 'pid: host' di docker-compose"]
    NS_OK["Log Info: /proc verification PASSED"]

    NET_CHECK["Pre-flight nf_conntrack_max:<br/>baca /proc/sys/net/netfilter/nf_conntrack_max"]
    NET_WARN{"conntrack_max<br/>&lt; 65536 (CONNTRACK_MIN)?"}
    WARN_LOG["Log Warning: Risiko packet drop<br/>sysctl -w net.netfilter.nf_conntrack_max=65536"]
    NET_OK["Log Info: nf_conntrack_max check PASSED"]
    NET_SKIP["OSError: conntrack tidak terbaca (skip)"]

    RETURN(["Return dict(<br/>hostname, cpu_count, mem_total_mb,<br/>p_idle_watts, p_max_watts, hw_sensor)"])

    START --> CPU_TRY
    CPU_TRY --> CPU_ERR
    CPU_ERR -->|Ya| CPU_FALLBACK
    CPU_ERR -->|Tidak| CPU_OK
    CPU_FALLBACK --> RAM_TRY
    CPU_OK --> RAM_TRY
    RAM_TRY --> RAM_OK
    RAM_OK --> ENERGY_CONST
    ENERGY_CONST --> SENSOR_INIT
    SENSOR_INIT --> NS_CHECK
    NS_CHECK --> NS_MATCH
    NS_MATCH -->|Tidak| NS_WARN
    NS_MATCH -->|Ya| NS_OK
    NS_WARN --> NET_CHECK
    NS_OK --> NET_CHECK
    NET_CHECK --> NET_WARN
    NET_WARN -->|Ya| WARN_LOG
    NET_WARN -->|Tidak| NET_OK
    NET_CHECK -.->|OSError| NET_SKIP
    WARN_LOG --> RETURN
    NET_OK --> RETURN
    NET_SKIP --> RETURN
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Host Profiling (Cold-Start)"])

    CEK_CPU["Deteksi Topologi CPU (Logical Cores) via /proc/cpuinfo"]
    CPU_GAGAL{"Eksekusi<br/>Gagal?"}
    CPU_CADANGAN["Fallback: os.cpu_count()"]
    CPU_DAPAT["Host Cores terverifikasi"]

    CEK_RAM["Deteksi Kapasitas RAM via /proc/meminfo"]
    RAM_DAPAT["Host RAM terverifikasi (MB)"]

    HITUNG_DAYA["Kalkulasi Konstanta Estimasi Daya:<br/>• Baseline (P_idle) = cores × 3.75W<br/>• Max (P_max) = cores × 13.5W"]

    CEK_SENSOR["Inisialisasi PowerSensor (RAPL/hwmon)"]

    CEK_ASLI["Verifikasi Host /proc Namespace:<br/>cross-check os.cpu_count() vs /proc/cpuinfo"]
    ASLI{"Jumlah Core<br/>Match?"}
    ASLI_OK["✅ /proc Verification PASSED"]
    ASLI_GAGAL["⚠ Log Critical: /proc MISMATCH<br/>(periksa konfigurasi pid: host)"]

    CEK_JARINGAN["Verifikasi Pre-flight nf_conntrack_max<br/>(threshold: 65536)"]
    JARINGAN{"nf_conntrack_max<br/>≥ 65536?"}
    JARINGAN_OK["✅ Conntrack OK"]
    JARINGAN_WARN["⚠ Peringatan: Risiko connection drop"]

    SELESAI(["Profil Host Terbentuk (Siap Digunakan)"])

    START --> CEK_CPU
    CEK_CPU --> CPU_GAGAL
    CPU_GAGAL -->|Ya| CPU_CADANGAN
    CPU_GAGAL -->|Tidak| CPU_DAPAT
    CPU_CADANGAN --> CEK_RAM
    CPU_DAPAT --> CEK_RAM
    CEK_RAM --> RAM_DAPAT
    RAM_DAPAT --> HITUNG_DAYA
    HITUNG_DAYA --> CEK_SENSOR
    CEK_SENSOR --> CEK_ASLI
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
