# Flowchart — MicroFreezer.evaluate() (Layer 4)

> **Kode Sumber:** `framework/security/micro_freezer.py` → class `MicroFreezer`, fungsi `evaluate()`, `record_activity()`, `_freeze()`, dan `_thaw()` (baris 37–274)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Sub-second Micro-Freezing & Zero-CPU Idle Engine
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma pembekuan kontainer berbasis kernel Linux cgroups v2 (`cgroup.freeze`). Mengurangi utilisasi CPU kontainer yang menganggur ke **persis 0.0% CPU** tanpa terminasi proses atau degradasi *cold-start delay*.
- **Pendeteksian Idle Hybrid:** Mengutamakan sinyal event kernel Linux unified hierarchy (`cgroup.events` kolom `populated == 0`) dipadukan dengan jeda tenang minimum `MICRO_FREEZE_IDLE_TRIGGER_S = 0.8s`.
- **Safety Gate (eBPF / Netlink Transaksi):** Memeriksa apakah ada transaksi database atau koneksi aktif yang belum terselesaikan (`ebpf_sensor.has_open_connections()`) sebelum pembekuan dieksekusi.
- **Batas Siklus Beku Maksimal (Hard Timeout):** Maksimal durasi beku dibatasi `MICRO_FREEZE_MAX_DURATION_MS = 1000ms`. Bila terlewati, mekanisme *Force-Thaw* langsung diaktifkan untuk menjaga SLA jaringan.
- **Pencairan Sub-Milidetik:** Menulis `cgroup.freeze = 0` mencairkan kontainer dalam waktu <1ms saat request baru tiba (`record_activity`).
- **Active Memory Reclaim (`memory.reclaim`):** Pada `main.py`, pembekuan kontainer langsung memicu pembersihan cache halaman RAM tak terpakai.
- **Akumulasi Telemetri:** Durasi beku diakumulasikan (`get_cumulative_freeze_seconds`) dan dicatat ke kolom ke-16 `metrics.csv`.

```mermaid
flowchart TD
    START(["MicroFreezer.evaluate(name, id, priority, cpu)"])

    CHECK_PRIO{"priority == True?<br/>(Database / Infra)"}
    EXEMPT(["Return {action: 'none',<br/>reason: 'priority_exempt'}"])

    CHECK_FIRST{"container_id in<br/>_state tracking?"}
    INIT_STATE["_state[id] = {frozen: False, frozen_at: 0.0, last_activity: now}"]
    FIRST_RET(["Return {action: 'none',<br/>reason: 'first_seen'}"])

    CHECK_CURRENT_FROZEN{"_state[id]['frozen']<br/>== True?"}

    CALC_FROZEN_MS["frozen_duration_ms = (now - frozen_at) × 1000"]
    CHECK_MAX_DURATION{"frozen_duration_ms ≥ 1000ms<br/>(max_freeze_duration_ms)?"}
    DO_FORCE_THAW["_thaw(id, reason='max_duration_reached'):<br/>Akumulasi durasi ke _cumulative_freeze_seconds<br/>Tulis '0' ke cgroup.freeze<br/>state['frozen'] = False"]
    RETURN_THAW(["Return {action: 'thaw',<br/>reason: 'max_duration:...ms'}"])
    STILL_FROZEN(["Return {action: 'none',<br/>reason: 'already_frozen'}"])

    CALC_IDLE["idle_duration = now - state['last_activity']"]

    CHECK_EVENTS["_check_populated(id):<br/>Baca file cgroup.events"]
    POPULATED_FOUND{"cgroup.events<br/>tersedia?"}

    KERNEL_ACTIVE{"populated == 1?<br/>(Kernel: proses aktif)"}
    ABORT_POPULATED["Return {action: 'none',<br/>reason: 'populated_active'}"]

    KERNEL_IDLE{"idle_duration ≥ 0.8s<br/>(MICRO_FREEZE_IDLE_TRIGGER_S)?"}
    ABORT_TOO_RECENT_1["Return {action: 'none',<br/>reason: 'depopulated_but_too_recent'}"]

    FALLBACK_IDLE{"idle_duration ≥ 0.8s<br/>(Fallback Polling)?"}
    ABORT_TOO_RECENT_2["Return {action: 'none',<br/>reason: 'not_idle_enough'}"]

    CHECK_SAFETY{"ebpf_sensor != None DAN<br/>ebpf_sensor.has_open_connections(id)?"}
    DEFER_FREEZE(["Return {action: 'defer',<br/>reason: 'open_connections'}<br/>Tunda beku agar transaksi DB aman"])

    CHECK_DRY{"dry_run == True?"}
    DRY_FREEZE["Log [DRY-RUN] Would FREEZE"]
    REAL_FREEZE["_freeze(name, id):<br/>Tulis '1' ke cgroup.freeze"]

    UPDATE_FROZEN["_state[id]['frozen'] = True<br/>_state[id]['frozen_at'] = now"]
    RETURN_FREEZE(["Return {action: 'freeze',<br/>reason: 'idle:...s'}<br/><i>Di main.py: memicu reclaim_memory()</i>"])

    START --> CHECK_PRIO
    CHECK_PRIO -->|Ya| EXEMPT
    CHECK_PRIO -->|Tidak| CHECK_FIRST

    CHECK_FIRST -->|Tidak| INIT_STATE
    INIT_STATE --> FIRST_RET
    CHECK_FIRST -->|Ya| CHECK_CURRENT_FROZEN

    CHECK_CURRENT_FROZEN -->|Ya| CALC_FROZEN_MS
    CALC_FROZEN_MS --> CHECK_MAX_DURATION
    CHECK_MAX_DURATION -->|Ya| DO_FORCE_THAW
    DO_FORCE_THAW --> RETURN_THAW
    CHECK_MAX_DURATION -->|Tidak| STILL_FROZEN

    CHECK_CURRENT_FROZEN -->|Tidak| CALC_IDLE
    CALC_IDLE --> CHECK_EVENTS
    CHECK_EVENTS --> POPULATED_FOUND

    POPULATED_FOUND -->|Ya| KERNEL_ACTIVE
    KERNEL_ACTIVE -->|Ya| ABORT_POPULATED
    KERNEL_ACTIVE -->|Tidak| KERNEL_IDLE
    KERNEL_IDLE -->|Tidak| ABORT_TOO_RECENT_1
    KERNEL_IDLE -->|Ya| CHECK_SAFETY

    POPULATED_FOUND -->|Tidak| FALLBACK_IDLE
    FALLBACK_IDLE -->|Tidak| ABORT_TOO_RECENT_2
    FALLBACK_IDLE -->|Ya| CHECK_SAFETY

    CHECK_SAFETY -->|Ya| DEFER_FREEZE
    CHECK_SAFETY -->|Tidak| CHECK_DRY

    CHECK_DRY -->|Ya| DRY_FREEZE
    CHECK_DRY -->|Tidak| REAL_FREEZE
    DRY_FREEZE --> UPDATE_FROZEN
    REAL_FREEZE --> UPDATE_FROZEN
    UPDATE_FROZEN --> RETURN_FREEZE
```

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["START: Evaluasi Keputusan Pembekuan (Micro-Freezing)"])

    CEK_PRIO{"Apakah Kontainer Memiliki Tag Prioritas?<br/>(Database/Proxy)"}
    LEWAT_PRIO(["Bypass: Kebal Pembekuan"])

    CEK_STATUS_BEKU{"Apakah Kontainer Sedang Dalam Status FROZEN?"}

    subgraph PENGAWAS_WAKTU["1. Pengawas Batas Durasi Maksimal (Timeout Watchdog)"]
        HITUNG_LAMA_BEKU["Hitung Durasi Pembekuan (milidetik)"]
        LEBIH_1000MS{"Durasi ≥ 1000ms?"}
        PAKSA_CAIR["⏰ Paksa Cairkan (Force-Thaw):<br/>Tulis '0' ke cgroup.freeze & Akumulasi Durasi"]
        TETAP_BEKU["Pertahankan Status Beku"]
    end

    subgraph DETEKSI_IDLE["2. Pendeteksian Keadaan Menganggur (Event Kernel)"]
        TANYA_KERNEL["Periksa Event Kernel (cgroup.events)"]
        KERNEL_ADA{"Dukungan Kernel v2 Ada?"}
        PROSES_AKTIF{"Kernel: populated == 1?<br/>(Masih Ada Proses Berjalan)"}
        BATAL_AKTIF["Batal: Kontainer Sedang Aktif Memproses"]

        TENANG_08S{"Apakah Masa Tenang Beban ≥ 0.8 Detik?"}
        BATAL_SEBENTAR["Batal: Durasi Tenang Belum Cukup"]
    end

    subgraph GERBANG_KEAMANAN["3. Gerbang Integritas Transaksi (eBPF)"]
        CEK_TRANSAKSI{"Apakah eBPF Mendeteksi Koneksi / Transaksi DB Aktif?"}
        TUNDA_BEKU["⏸️ Tunda Pembekuan: Cegah Korupsi Data In-Flight"]
    end

    subgraph EKSEKUSI_FREEZE["4. Eksekusi Pembekuan & Reklamasi Memori"]
        TULIS_FREEZE["❄️ Bekukan Kontainer: Tulis '1' ke cgroup.freeze"]
        REKLAMASI_RAM["Picu memory.reclaim = 0 untuk Membebaskan Page Cache RAM"]
        CATAT_TELEMETRI["Update Status = FROZEN & Catat Timestamp"]
    end

    SELESAI(["END: Status Kontainer 0.0% CPU (State di RAM Tetap Utuh)"])

    START --> CEK_PRIO
    CEK_PRIO -->|Ya| LEWAT_PRIO
    CEK_PRIO -->|Tidak| CEK_STATUS_BEKU

    CEK_STATUS_BEKU -->|Ya| HITUNG_LAMA_BEKU
    HITUNG_LAMA_BEKU --> LEBIH_1000MS
    LEBIH_1000MS -->|Ya| PAKSA_CAIR
    LEBIH_1000MS -->|Tidak| TETAP_BEKU

    CEK_STATUS_BEKU -->|Tidak| TANYA_KERNEL
    TANYA_KERNEL --> KERNEL_ADA

    KERNEL_ADA -->|Ya| PROSES_AKTIF
    PROSES_AKTIF -->|Ya| BATAL_AKTIF
    PROSES_AKTIF -->|Tidak| TENANG_08S

    KERNEL_ADA -->|Tidak| TENANG_08S

    TENANG_08S -->|Tidak| BATAL_SEBENTAR
    TENANG_08S -->|Ya| CEK_TRANSAKSI

    CEK_TRANSAKSI -->|Ya| TUNDA_BEKU
    CEK_TRANSAKSI -->|Tidak| TULIS_FREEZE

    TULIS_FREEZE --> REKLAMASI_RAM
    REKLAMASI_RAM --> CATAT_TELEMETRI
    CATAT_TELEMETRI --> SELESAI

    PAKSA_CAIR --> SELESAI
    TETAP_BEKU --> SELESAI
    BATAL_AKTIF --> SELESAI
    BATAL_SEBENTAR --> SELESAI
    TUNDA_BEKU --> SELESAI
```
