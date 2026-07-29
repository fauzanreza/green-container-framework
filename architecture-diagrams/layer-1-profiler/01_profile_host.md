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

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Inisialisasi Sistem (Cold-Start)"])

    CEK_CPU["Deteksi Topologi CPU:<br/>Hitung jumlah logical processor pada host"]
    CPU_GAGAL{"Eksekusi<br/>Gagal?"}
    CPU_CADANGAN["Fallback: Kalkulasi alternatif<br/>menggunakan API sistem operasi"]
    CPU_DAPAT["Kapasitas CPU (core_count) terverifikasi"]

    CEK_RAM["Deteksi Kapasitas Memori:<br/>Evaluasi total RAM pada host"]
    RAM_DAPAT["Kapasitas Memori terverifikasi"]

    HITUNG_DAYA["Kalkulasi Konstanta Estimasi Daya:<br/>• Baseline Idle (P_idle) = core_count × 3.75 Watt<br/>• Kapasitas Maksimal (P_max) = core_count × 13.5 Watt"]

    CEK_SENSOR["Deteksi Sensor Daya Perangkat Keras:<br/>(Eksplorasi modul Intel RAPL / AMD hwmon)"]
    SENSOR_ADA{"Sensor<br/>Tersedia?"}
    SENSOR_YA["✅ Mode Hardware-True:<br/>Pengukuran daya riil teraktivasi"]
    SENSOR_TIDAK["⚠ Sensor Absen:<br/>Mode Software Estimation teraktivasi"]

    CEK_ASLI["Verifikasi Integritas File Sistem (/proc):<br/>Validasi namespace mount point"]
    ASLI{"Kesesuaian<br/>Data?"}
    ASLI_OK["✅ Validasi Namespace Berhasil"]
    ASLI_GAGAL["⚠ PERINGATAN KRITIS: Inkonsistensi Namespace!<br/>Indikasi isolasi file sistem parsial"]

    CEK_JARINGAN["Verifikasi Kapasitas Koneksi (Conntrack):<br/>Evaluasi batas netfilter pada kernel"]
    JARINGAN{"Kapasitas<br/>Memadai?"}
    JARINGAN_OK["✅ Kapasitas Conntrack Memadai"]
    JARINGAN_WARN["⚠ PERINGATAN: Kapasitas Terbatas!<br/>Risiko packet drop pada trafik tinggi"]

    SELESAI(["Profil Konfigurasi Host Terbentuk<br/>Sistem siap beroperasi"])

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
