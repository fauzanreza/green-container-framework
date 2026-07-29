# Flowchart — TCP Backlog Queue Validation (Layer 4)

> **Kode Sumber:** `framework/micro_freezer.py` → class `MicroFreezer`, fungsi `_verify_tcp_backlog()` (baris 110–165)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Micro-Freezer (Safety Check)
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Mekanisme verifikasi *Network-Buffer-Aware* yang memungkinkan Micro-Freezing. Memastikan bahwa selama container di-freeze (500–1000ms), koneksi HTTP/TCP baru yang masuk tidak akan di-drop oleh kernel, melainkan ditampung di antrean (backlog) sampai container di-thaw.

```mermaid
flowchart TD
    START(["_verify_tcp_backlog(container_name)"])

    READ_SYSCTL["Baca net.core.somaxconn dari host"]
    SYSCTL_ERR{"I/O Error?"}
    FALLBACK_SYSCTL["somaxconn = 128 (Default)"]

    CALC_EXPECTED["expected_queue = RPS × FREEZE_DURATION<br/>(Misal: 100 × 1.0 = 100)"]
    CALC_MIN["min_required = expected_queue × 2"]

    COMPARE1{"somaxconn<br/>≥ min_required?"}
    HOST_LOW(["Return False<br/>(Host queue too low)"])

    GET_PID["Get PID container"]
    PID_ERR{"PID valid?"}
    NO_PID(["Return False<br/>(Cannot read namespace)"])

    READ_PROC["Baca /proc/{pid}/net/tcp"]
    PROC_ERR{"File ada?"}
    NO_PROC(["Return False<br/>(No TCP sockets)"])

    PARSE["Parse status 0A (LISTEN)<br/>Extract tx_queue (backlog)"]

    COMPARE2{"Min(tx_queue)<br/>≥ 128?"}
    APP_LOW(["Return False<br/>(App backlog too low)"])
    APP_OK(["Return True<br/>(Backlog OK, Safe to Freeze)"])

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
    START(["Pre-flight: Verifikasi TCP Backlog Host"])

    BACA["Baca sysctl net.core.somaxconn"]
    GAGAL{"I/O Error?"}
    ASUMSI["Fallback: somaxconn = default OS"]

    HITUNG_PAKET["Hitung Expected Queue:<br/>Queue = RPS × Freeze Duration"]
    HITUNG_MINIMAL["Hitung Min Required:<br/>Min = Expected Queue × 2"]

    CUKUP{"somaxconn<br/>≥ Min Required?"}
    AMAN["✅ COMPLIANT: Kapasitas Host memadai"]
    BAHAYA["⚠ NON-COMPLIANT: Kapasitas terlalu rendah<br/>(Risiko TCP Drop)"]

    SELESAI(["Return Status"])

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
    START2(["Verifikasi listen() backlog Aplikasi"])

    CARI_PROSES["Get PID utama container"]
    KETEMU{"PID ada?"}
    LEWATI(["Abort: Namespace Inaccessible"])

    BACA_PINTU["Baca /proc/{pid}/net/tcp<br/>Cari status 0A (LISTEN)"]
    ADA_PINTU{"Soket LISTEN<br/>ada?"}
    TIDAK_ADA(["Abort: Tidak ada layanan network"])

    CARI_TERKECIL["Identifikasi tx_queue (backlog) terkecil"]
    CUKUP{"Kapasitas<br/>≥ 128?"}

    APP_AMAN["✅ COMPLIANT: Backlog memadai"]
    APP_KECIL["⚠ NON-COMPLIANT: Parameter listen() terlalu kecil"]

    START2 --> CARI_PROSES
    CARI_PROSES --> KETEMU
    KETEMU -->|Tidak| LEWATI
    KETEMU -->|Ya| BACA_PINTU
    BACA_PINTU --> ADA_PINTU
    ADA_PINTU -->|Tidak| TIDAK_ADA
    ADA_PINTU -->|Ya| CARI_TERKECIL
    CARI_TERKECIL --> CUKUP
    CUKUP -->|Ya| APP_AMAN
    CUKUP -->|Tidak| APP_KECIL
```
