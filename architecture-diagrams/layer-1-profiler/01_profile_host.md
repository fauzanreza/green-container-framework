# Flowchart — profile_host()

> **Kode Sumber:** `framework/profiler.py` → fungsi `profile_host()` (baris 20–91)
> **Posisi di Diagram:** Layer 1 — Environment Profiler
> **Kategori:** Tools / Data Acquisition (S1)

Fungsi ini berjalan **sekali saat cold-start**. Membaca kapasitas hardware host dan menginisialisasi sensor daya.

```mermaid
flowchart TD
    START(["profile_host() dipanggil saat cold-start"])

    READ_CPU["Baca /proc/cpuinfo<br/>Hitung jumlah baris 'processor'"]
    CPU_FAIL{"OSError?"}
    CPU_FALLBACK["Fallback: os.cpu_count()"]
    CPU_OK["cpu_count = jumlah core"]

    READ_MEM["Baca /proc/meminfo<br/>Cari baris 'MemTotal'"]
    MEM_OK["mem_total_mb = MemTotal / 1024"]

    CALC_POWER["Hitung konstanta daya dinamis:<br/>P_idle = cpu_count × 3.75 W<br/>P_max = cpu_count × 13.5 W"]

    HW_SENSOR["Inisialisasi PowerSensor()<br/><i>hardware_sensor.py</i>"]
    HW_CHECK{"Sensor tersedia?<br/>(Intel RAPL / AMD hwmon)"}
    HW_YES["hw_sensor.available = True<br/>Mode: Hardware-True"]
    HW_NO["hw_sensor.available = False<br/>Mode: Software Estimation"]

    VERIFY_PROC["Verifikasi /proc Host:<br/>cpu_count == os.cpu_count()?"]
    PROC_MATCH{"Cocok?"}
    PROC_OK["✅ /proc verification PASSED"]
    PROC_FAIL["⚠ CRITICAL: /proc MISMATCH<br/>Kemungkinan membaca /proc<br/>container sendiri, bukan host"]

    CHECK_CONNTRACK["Baca /proc/sys/net/netfilter/<br/>nf_conntrack_max"]
    CT_CHECK{"≥ 65536?"}
    CT_OK["✅ conntrack check PASSED"]
    CT_WARN["⚠ WARNING: koneksi baru<br/>bisa di-drop saat traffic spike"]

    RETURN(["Return profile dict:<br/>hostname, cpu_count, mem_total_mb,<br/>p_idle_watts, p_max_watts, hw_sensor"])

    START --> READ_CPU
    READ_CPU --> CPU_FAIL
    CPU_FAIL -->|Ya| CPU_FALLBACK
    CPU_FAIL -->|Tidak| CPU_OK
    CPU_FALLBACK --> READ_MEM
    CPU_OK --> READ_MEM
    READ_MEM --> MEM_OK
    MEM_OK --> CALC_POWER
    CALC_POWER --> HW_SENSOR
    HW_SENSOR --> HW_CHECK
    HW_CHECK -->|Ya| HW_YES
    HW_CHECK -->|Tidak| HW_NO
    HW_YES --> VERIFY_PROC
    HW_NO --> VERIFY_PROC
    VERIFY_PROC --> PROC_MATCH
    PROC_MATCH -->|Ya| PROC_OK
    PROC_MATCH -->|Tidak| PROC_FAIL
    PROC_OK --> CHECK_CONNTRACK
    PROC_FAIL --> CHECK_CONNTRACK
    CHECK_CONNTRACK --> CT_CHECK
    CT_CHECK -->|Ya| CT_OK
    CT_CHECK -->|Tidak| CT_WARN
    CT_OK --> RETURN
    CT_WARN --> RETURN
```
