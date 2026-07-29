# Flowchart — TCPBacklogManager.verify() (Layer 4 Extension)

> **Kode Sumber:** `framework/security/tcp_backlog_manager.py` → class `TCPBacklogManager`, fungsi `verify()` (baris 67–115) dan `check_app_backlog()` (baris 128–193)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → TCP Backlog
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **TCP Backlog Capacity Verification** yang dijalankan saat cold-start. Menghitung apakah antrean TCP host cukup besar untuk menampung paket selama freeze window, sehingga koneksi pengguna **tidak putus** meskipun container sedang frozen (menjaga SLA).

```mermaid
flowchart TD
    START(["TCPBacklogManager.__init__()"])

    READ_SOMAX["Baca /proc/sys/net/core/somaxconn<br/>Contoh: somaxconn = 4096"]
    READ_FAIL{"Gagal baca?"}
    DEFAULT["Assume default: 4096"]

    VERIFY(["verify() — Cold-start pre-flight check"])

    CALC_QUEUE["Hitung expected queue depth:<br/>expected = expected_rps × freeze_seconds<br/>= 100 req/s × (1000ms / 1000)<br/>= <b>100 paket</b>"]

    CALC_REQUIRED["Hitung required headroom:<br/>required = max(expected × 2, min_headroom)<br/>= max(200, 4096)<br/>= <b>4096</b>"]

    COMPARE{"somaxconn ≥ required?<br/>(4096 ≥ 4096?)"}

    SAFE["✅ PASSED<br/>TCP backlog cukup besar<br/>untuk menampung paket<br/>selama freeze window"]

    UNSAFE["⚠ FAILED<br/>somaxconn terlalu kecil<br/>Rekomendasi:<br/>sysctl -w net.core.somaxconn=N"]

    RETURN(["Return: safe, somaxconn,<br/>required, expected_queue_depth"])

    START --> READ_SOMAX
    READ_SOMAX --> READ_FAIL
    READ_FAIL -->|Ya| DEFAULT
    READ_FAIL -->|Tidak| VERIFY
    DEFAULT --> VERIFY

    VERIFY --> CALC_QUEUE
    CALC_QUEUE --> CALC_REQUIRED
    CALC_REQUIRED --> COMPARE
    COMPARE -->|Ya| SAFE
    COMPARE -->|Tidak| UNSAFE
    SAFE --> RETURN
    UNSAFE --> RETURN
```

---

## Flowchart — check_app_backlog() (App-Level Listen Backlog)

> **Kode Sumber:** `framework/security/tcp_backlog_manager.py` → `check_app_backlog()` (baris 128–193)

```mermaid
flowchart TD
    START2(["check_app_backlog(container_name, container_id)"])

    GET_PID["Dapatkan PID container<br/>dari Docker API"]
    PID_FAIL{"PID tersedia?"}
    SKIP(["Return: safe=True<br/>Cannot check"])

    READ_TCP["Baca /proc/{pid}/net/tcp<br/>Cari socket LISTEN (state=0A)"]
    PARSE["Parse tx_queue dari setiap<br/>LISTEN socket (hex → int)<br/>tx_queue = backlog size"]

    HAS_LISTEN{"Ada LISTEN<br/>socket?"}
    NO_LISTEN(["Return: safe=True<br/>No listen sockets"])

    FIND_MIN["lowest_backlog = min(semua tx_queue)"]
    COMPARE2{"lowest_backlog ≥<br/>min_backlog (128)?"}

    APP_SAFE["✅ App backlog cukup"]
    APP_LOW["⚠ App listen backlog terlalu kecil<br/>Micro-freeze AKAN drop koneksi<br/>meskipun somaxconn besar"]

    START2 --> GET_PID
    GET_PID --> PID_FAIL
    PID_FAIL -->|Tidak| SKIP
    PID_FAIL -->|Ya| READ_TCP
    READ_TCP --> PARSE
    PARSE --> HAS_LISTEN
    HAS_LISTEN -->|Tidak| NO_LISTEN
    HAS_LISTEN -->|Ya| FIND_MIN
    FIND_MIN --> COMPARE2
    COMPARE2 -->|Ya| APP_SAFE
    COMPARE2 -->|Tidak| APP_LOW
```

### Mengapa Ini Inovasi S2?
1. **Menyelesaikan Masalah Fundamental:** Micro-Freezing hanya berguna jika koneksi tidak putus saat container frozen. Tanpa verifikasi backlog, freeze bisa lebih merusak daripada throttling biasa.
2. **Dua Level Verifikasi:** Sistem mengecek BAIK kernel-level (`somaxconn`) MAUPUN app-level (`listen()` backlog) — karena aplikasi yang dikompilasi dengan `listen(fd, 5)` tetap akan drop koneksi meskipun somaxconn=4096.
3. **Matematik Kapasitas Antrean:** Secara eksplisit menghitung `expected_queue_depth = RPS × freeze_duration` — ini formula matematis yang menjembatani subsistem jaringan dengan subsistem pembekuan cgroups.

---

## Deskripsi Alur Berbasis Bisnis/Akademik

### Verifikasi Kapasitas Antrean Kernel (Host Level)

```mermaid
flowchart TD
    START(["Pre-flight Check:<br/>Validasi Kapasitas Antrean TCP (Backlog)"])

    BACA["Akuisisi Parameter Kernel (sysctl):<br/>Baca net.core.somaxconn (Kapasitas Maksimal TCP)"]
    GAGAL{"I/O<br/>Error?"}
    ASUMSI["Fallback: Asumsikan nilai standar OS (Default)"]

    HITUNG_PAKET["Kalkulasi Estimasi Kedalaman Antrean (Queue Depth):<br/>Expected Queue = Expected RPS × Freeze Duration<br/>(Misal: 100 req/s × 1 detik = 100 koneksi tertahan)"]
    HITUNG_MINIMAL["Kalkulasi Persyaratan Kapasitas Minimum:<br/>Minimum Required = 2 × Expected Queue<br/>(Safety Margin)"]

    CUKUP{"somaxconn aktual<br/>≥ Kapasitas Minimum?"}
    AMAN["✅ STATUS: COMPLIANT<br/>Kapasitas antrean Host memadai untuk<br/>menahan koneksi selama Micro-Freeze"]
    BAHAYA["⚠ STATUS: NON-COMPLIANT<br/>Kapasitas terlalu rendah (Risiko TCP Drop / Timeout).<br/>Membutuhkan tuning kernel (sysctl)"]

    SELESAI(["Kembalikan Status Verifikasi"])

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
    START2(["Verifikasi Soket Level Aplikasi:<br/>Validasi parameter listen() backlog di dalam Container"])

    CARI_PROSES["Resolusi PID Utama (Process ID)<br/>dari Meta-Data Container"]
    KETEMU{"PID<br/>Terdeteksi?"}
    LEWATI(["Abort operasi (Keterbatasan akses namespace)"])

    BACA_PINTU["Eksplorasi `/proc/{pid}/net/tcp`:<br/>Identifikasi soket berstatus LISTEN (State 0A)"]
    ADA_PINTU{"Soket LISTEN<br/>Tersedia?"}
    TIDAK_ADA(["Abort operasi (Tidak ada layanan jaringan terbuka)"])

    CARI_TERKECIL["Kalkulasi Bottleneck:<br/>Identifikasi kapasitas `tx_queue` terkecil dari seluruh soket aktif"]
    CUKUP{"Kapasitas<br/>≥ 128 (Minimum)? "}

    APP_AMAN["✅ STATUS: COMPLIANT<br/>Soket aplikasi dikonfigurasi dengan backlog yang memadai"]
    APP_KECIL["⚠ STATUS: NON-COMPLIANT (Aplikasi Hardcoded)<br/>Parameter listen() aplikasi terlalu kecil.<br/>Micro-Freeze akan memicu koneksi terputus secara sepihak."]

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
