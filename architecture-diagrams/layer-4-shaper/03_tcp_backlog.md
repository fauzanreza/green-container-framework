# Flowchart — TCPBacklogManager (Layer 4)

> **Kode Sumber:** `framework/security/tcp_backlog_manager.py` → class `TCPBacklogManager`, fungsi `verify()` dan `check_app_backlog()` (baris 24–194)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Network-Buffer Headroom Pre-flight Verifier
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Mekanisme verifikasi kapasitas antrean jaringan kernel (*Network-Buffer-Aware Verification*) yang menjadi prasyarat keamanan operasi Micro-Freezing. Memastikan bahwa saat kontainer non-priority dibekukan (500–1000ms), paket permintaan HTTP/TCP baru yang masuk tidak di-drop oleh kernel melainkan ditampung di antrean buffer soket host sampai kontainer dicairkan (<1ms).
- **Tingkat 1 — Pre-Flight Kernel Host (`verify`):** Berjalan saat cold start `_init_security()` di `main.py`. Membaca `/proc/sys/net/core/somaxconn`. Menghitung kedalaman antrean ekspektasi $Q = \text{RPS} \times t_{\text{freeze}}$ dan membandingkannya terhadap ambang batas minimal $\max(2Q, 4096)$.
- **Tingkat 2 — Pemeriksaan Soket Aplikasi (`check_app_backlog`):** Membaca `/proc/<pid>/net/tcp` proses kontainer untuk memastikan soket server dengan status `LISTEN` (kode hex `0A`) memiliki backlog `listen(fd, backlog)` minimal $\ge 128$.

```mermaid
flowchart TD
    START_VERIFY(["TCPBacklogManager.verify()<br/>(Cold-Start Pre-flight di main.py)"])

    READ_SOMAX["Baca /proc/sys/net/core/somaxconn"]
    READ_ERR{"I/O Error?"}
    FALLBACK_SOMAX["somaxconn = 4096 (Default)"]
    SOMAX_VAL["current_somaxconn tersimpan"]

    CALC_QUEUE["freeze_seconds = max_freeze_duration_ms / 1000.0<br/>expected_queue_depth = int(expected_rps × freeze_seconds)<br/>(e.g. 100 RPS × 1.0s = 100 paket)"]

    CALC_REQ["required = max(expected_queue_depth × 2, min_headroom 4096)<br/>(Default required = 4096)"]

    COMPARE_HOST{"current_somaxconn<br/>≥ required?"}
    HOST_SAFE["safe = True<br/>recommendation = 'ok'<br/>Log Info: TCP Backlog PASSED"]
    HOST_UNSAFE["safe = False<br/>recommendation = 'sysctl -w net.core.somaxconn=...' <br/>Log Warning: TCP Backlog INSUFFICIENT"]

    RETURN_HOST(["Return dict(safe, somaxconn, required,<br/>expected_queue_depth, recommendation)"])

    START_APP(["check_app_backlog(name, id)<br/>(Pemeriksaan Tingkat Soket Kontainer)"])

    GET_PID["Ambil PID kontainer via Docker attrs:<br/>pid = container.attrs['State']['Pid']"]
    CHECK_PID{"pid &gt; 0?"}
    PID_NOT_FOUND(["Return {safe: True, min_backlog: -1,<br/>recommendation: 'no_pid'}"])

    READ_TCP["Buka /proc/{pid}/net/tcp<br/>Cari baris berstatus '0A' (LISTEN)"]
    TCP_EXISTS{"File net/tcp ada<br/>& ada soket LISTEN?"}
    NO_SOCKETS(["Return {safe: True, min_backlog: -1,<br/>recommendation: 'no_listen_sockets'}"])

    PARSE_QUEUE["Parse tx_queue dari tx_queue:rx_queue (hex)<br/>lowest_backlog = min(tx_queue)"]

    CHECK_APP_SAFE{"lowest_backlog<br/>≥ 128 (min_backlog)?"}
    APP_SAFE["safe = True, recommendation = 'ok'<br/>Log Debug: App backlog PASSED"]
    APP_UNSAFE["safe = False<br/>recommendation = 'app listen backlog too low'<br/>Log Warning: Parameter listen() terlalu kecil"]

    RETURN_APP(["Return dict(safe, min_backlog, recommendation)"])

    START_VERIFY --> READ_SOMAX
    READ_SOMAX --> READ_ERR
    READ_ERR -->|Ya| FALLBACK_SOMAX
    READ_ERR -->|Tidak| SOMAX_VAL
    FALLBACK_SOMAX --> CALC_QUEUE
    SOMAX_VAL --> CALC_QUEUE

    CALC_QUEUE --> CALC_REQ
    CALC_REQ --> COMPARE_HOST

    COMPARE_HOST -->|Ya| HOST_SAFE
    COMPARE_HOST -->|Tidak| HOST_UNSAFE
    HOST_SAFE --> RETURN_HOST
    HOST_UNSAFE --> RETURN_HOST

    START_APP --> GET_PID
    GET_PID --> CHECK_PID
    CHECK_PID -->|Tidak| PID_NOT_FOUND
    CHECK_PID -->|Ya| READ_TCP

    READ_TCP --> TCP_EXISTS
    TCP_EXISTS -->|Tidak| NO_SOCKETS
    TCP_EXISTS -->|Ya| PARSE_QUEUE

    PARSE_QUEUE --> CHECK_APP_SAFE
    CHECK_APP_SAFE -->|Ya| APP_SAFE
    CHECK_APP_SAFE -->|Tidak| APP_UNSAFE
    APP_SAFE --> RETURN_APP
    APP_UNSAFE --> RETURN_APP
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Verifikasi Headroom Antrean TCP"])

    subgraph LEVEL_1["Level 1: Verifikasi Kernel Host (net.core.somaxconn)"]
        BACA_HOST["Baca Nilai sysctl somaxconn"]
        HITUNG_ESTIMASI["Hitung Beban Masuk Selama Kontainer Membeku:<br/>Paket Masuk = Laju Request (RPS) × Durasi Beku (detik)"]
        HITUNG_MIN_BUFFER["Hitung Ambang Batas Aman:<br/>Ambang = max(2 × Paket Masuk, 4096)"]
        CEK_HOST{"Apakah somaxconn Host ≥ Ambang?"}
        HOST_OK["✅ Kernel Host Mampu Menampung Permintaan Selama Freeze"]
        HOST_DROP["⚠ Peringatan: Risiko Paket SYN Dibuang Kernel saat Freeze"]
    end

    subgraph LEVEL_2["Level 2: Verifikasi Parameter listen() Aplikasi"]
        BACA_SOKET["Periksa Tabel Soket Jaringan Proses (/proc/pid/net/tcp)"]
        CARI_LISTEN["Identifikasi Soket Aktif dalam Status LISTEN (0A)"]
        CEK_LIMIT_APP{"Apakah Antrean Soket Aplikasi ≥ 128?"}
        APP_OK["✅ Backlog Aplikasi Cukup Kuat"]
        APP_DROP["⚠ Peringatan: Backlog Aplikasi Terlalu Dangkal (< 128)"]
    end

    SELESAI(["END: Status Keamanan Penyangga Jaringan Terkonfirmasi"])

    START --> BACA_HOST
    BACA_HOST --> HITUNG_ESTIMASI
    HITUNG_ESTIMASI --> HITUNG_MIN_BUFFER
    HITUNG_MIN_BUFFER --> CEK_HOST

    CEK_HOST -->|Ya| HOST_OK
    CEK_HOST -->|Tidak| HOST_DROP

    HOST_OK --> BACA_SOKET
    HOST_DROP --> BACA_SOKET

    BACA_SOKET --> CARI_LISTEN
    CARI_LISTEN --> CEK_LIMIT_APP

    CEK_LIMIT_APP -->|Ya| APP_OK
    CEK_LIMIT_APP -->|Tidak| APP_DROP

    APP_OK --> SELESAI
    APP_DROP --> SELESAI
```
