# Flowchart — TCPBacklogManager.verify() (Layer 4)

> **Kode Sumber:** `framework/security/tcp_backlog_manager.py` → class `TCPBacklogManager`, fungsi `verify()` (baris 67–115) dan `check_app_backlog()` (baris 128–193)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Micro-Freezer (Safety Pre-flight)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Mekanisme verifikasi *Network-Buffer-Aware* yang memungkinkan Micro-Freezing. Memastikan bahwa selama container di-freeze (500–1000ms), koneksi HTTP/TCP baru yang masuk tidak akan di-drop oleh kernel, melainkan ditampung di antrean (backlog) sampai container di-thaw.

```mermaid
flowchart TD
    START(["TCPBacklogManager.verify()"])

    READ_SYSCTL["Baca /proc/sys/net/core/somaxconn<br/>(host net.core.somaxconn)"]
    SYSCTL_ERR{"I/O Error?"}
    FALLBACK_SYSCTL["somaxconn = 128 (Default)"]

    CALC_EXPECTED["expected_queue = expected_rps × (max_freeze_ms/1000)<br/>(e.g. 100.0 × 1.0 = 100)"]
    CALC_MIN["min_required = expected_queue × 2"]

    COMPARE1{"somaxconn<br/>≥ required?"}
    HOST_LOW(["Return {safe: False,<br/>recommendation: 'increase somaxconn'}"])

    GET_PID["check_app_backlog(container_name, container_id)"]
    PID_ERR{"pid > 0?"}
    NO_PID(["Return {safe: True,<br/>recommendation: 'no_pid'}"])

    READ_PROC["Baca /proc/{pid}/net/tcp"]
    PROC_ERR{"File ada?"}
    NO_PROC(["Return {safe: True,<br/>recommendation: 'no_listen_sockets'}"])

    PARSE["Parse status 0A (LISTEN)<br/>Extract tx_queue (backlog hex)"]

    COMPARE2{"min(tx_queue)<br/>≥ 128?"}
    APP_LOW(["Return {safe: False,<br/>recommendation: 'app backlog too low'}"])
    APP_OK(["Return {safe: True,<br/>recommendation: 'ok'}"])

    START --> READ_SYSCTL
    READ_SYSCTL --> SYSCTL_ERR
    SYSCTL_ERR -->|Ya| FALLBACK_SYSCTL
    SYSCTL_ERR -->|Tidak| CALC_EXPECTED
    FALLBACK_SYSCTL --> CALC_EXPECTED

    CALC_EXPECTED --> CALC_MIN
    CALC_MIN --> COMPARE1
    COMPARE1 -->|Tidak| HOST_LOW
    COMPARE1 -->|Ya| GET_PID

    GET_PID --> PID_ERR
    PID_ERR -->|Tidak| NO_PID
    PID_ERR -->|Ya| READ_PROC

    READ_PROC --> PROC_ERR
    PROC_ERR -->|Tidak| NO_PROC
    PROC_ERR -->|Ya| PARSE

    PARSE --> COMPARE2
    COMPARE2 -->|Ya| APP_OK
    COMPARE2 -->|Tidak| APP_LOW
```

## Mengapa Ini Inovasi S2?

1. **Menyelesaikan Masalah Fundamental:** Micro-Freezing hanya berguna jika koneksi tidak putus saat container frozen. Tanpa verifikasi backlog, freeze bisa lebih merusak daripada throttling biasa.
2. **Dua Level Verifikasi:** Sistem mengecek BAIK kernel-level (`somaxconn`) MAUPUN app-level (`listen()` backlog) — karena aplikasi yang dikompilasi dengan `listen(fd, 5)` tetap akan drop koneksi meskipun somaxconn=4096.
3. **Matematik Kapasitas Antrean:** Secara eksplisit menghitung `expected_queue_depth = RPS × freeze_duration` — ini formula matematis yang menjembatani subsistem jaringan dengan subsistem pembekuan cgroups.

---

## Alur Logika Konseptual

### Verifikasi Kapasitas Antrean Kernel (Host Level)

```mermaid
flowchart TD
    START(["START: Pre-flight Verifikasi TCP Backlog Host"])

    BACA["Baca sysctl net.core.somaxconn"]
    GAGAL{"Apakah Terjadi<br/>I/O Error?"}
    ASUMSI["Fallback: somaxconn = default OS"]

    HITUNG_PAKET["Hitung Expected Queue:<br/>Queue = RPS × Freeze Duration"]
    HITUNG_MINIMAL["Hitung Min Required:<br/>Min = Expected Queue × 2"]

    CUKUP{"Apakah somaxconn<br/>≥ Min Required?"}
    AMAN["✅ COMPLIANT: Kapasitas Host memadai"]
    BAHAYA["⚠ NON-COMPLIANT: Kapasitas terlalu rendah<br/>(Risiko TCP Drop)"]

    SELESAI(["END: Return Status"])

    START --> BACA
    BACA --> GAGAL
    GAGAL -->|Ya| ASUMSI
    GAGAL -->|Tidak| HITUNG_PAKET
    ASUMSI --> HITUNG_PAKET
    HITUNG_PAKET --> HITUNG_MINIMAL
    HITUNG_MINIMAL --> CUKUP
    CUKUP -->|Ya| AMAN
    CUKUP -->|Tidak| BAHAYA
    AMAN --> SELESAI
    BAHAYA --> SELESAI
```

### Verifikasi Antrean Soket (Application Level)

```mermaid
flowchart TD
    START(["START: Verifikasi listen() backlog Aplikasi"])

    CARI_PROSES["Get PID utama container"]
    KETEMU{"Apakah PID<br/>Ditemukan?"}
    LEWATI(["END: Abort, Namespace Inaccessible"])

    BACA_PINTU["Baca /proc/{pid}/net/tcp<br/>Cari status 0A (LISTEN)"]
    ADA_PINTU{"Apakah Ada Soket<br/>Berstatus LISTEN?"}
    TIDAK_ADA(["END: Abort, Tidak ada layanan network"])

    CARI_TERKECIL["Identifikasi tx_queue (backlog) terkecil"]
    CUKUP{"Apakah Kapasitas<br/>≥ 128?"}

    APP_AMAN["✅ COMPLIANT: Backlog memadai"]
    APP_KECIL["⚠ NON-COMPLIANT: Parameter listen() terlalu kecil"]

    SELESAI(["END: Return Status"])

    START --> CARI_PROSES
    CARI_PROSES --> KETEMU
    KETEMU -->|Tidak| LEWATI
    KETEMU -->|Ya| BACA_PINTU
    BACA_PINTU --> ADA_PINTU
    ADA_PINTU -->|Tidak| TIDAK_ADA
    ADA_PINTU -->|Ya| CARI_TERKECIL
    CARI_TERKECIL --> CUKUP
    CUKUP -->|Ya| APP_AMAN
    CUKUP -->|Tidak| APP_KECIL

    APP_AMAN --> SELESAI
    APP_KECIL --> SELESAI
```
