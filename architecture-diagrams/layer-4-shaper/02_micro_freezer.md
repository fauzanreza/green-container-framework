# Flowchart — MicroFreezer.evaluate() (Layer 4 Extension)

> **Kode Sumber:** `framework/security/micro_freezer.py` → class `MicroFreezer`, fungsi `evaluate()` (baris 78–145), `_freeze()` (baris 147–166), `_thaw()` (baris 168–188), `_check_populated()` (baris 221–237)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → Micro-Freezing
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma **Event-Driven Micro-Freezing** yang mendeteksi idle state container melalui sinyal kernel (`cgroup.events populated=0`), lalu menulis `cgroup.freeze=1` untuk menjatuhkan CPU ke **literal 0%** tanpa mematikan container.

```mermaid
flowchart TD
    START(["MicroFreezer.evaluate(name, id, priority, cpu%)"])

    IS_PRIORITY{"Container<br/>priority = True?"}
    EXEMPT(["Return: action=none<br/>reason=priority_exempt<br/>(database/infra tidak boleh dibekukan)"])

    FIRST_SEEN{"Pertama kali<br/>melihat container ini?"}
    INIT_STATE["Inisialisasi state:<br/>frozen=False, frozen_at=0,<br/>last_activity=now"]
    FIRST_RET(["Return: action=none<br/>reason=first_seen"])

    IS_FROZEN{"State:<br/>sudah frozen?"}

    subgraph FROZEN_CHECK["Container Sudah Frozen"]
        CALC_DURATION["frozen_duration_ms =<br/>(now - frozen_at) × 1000"]
        DURATION_EXCEEDED{"duration ≥<br/>MAX_FREEZE_MS (1000ms)?"}
        FORCE_THAW["_thaw(id, reason=max_duration_reached)<br/>Tulis '0' ke cgroup.freeze"]
        THAW_RET(["Return: action=thaw<br/>reason=max_duration"])
        STILL_FROZEN(["Return: action=none<br/>reason=already_frozen"])
    end

    CALC_IDLE["idle_duration = now - last_activity"]

    subgraph IDLE_DETECT["Event-Driven Idle Detection"]
        CHECK_POPULATED["_check_populated(id)<br/>Baca cgroup.events: 'populated X'"]
        POPULATED_AVAIL{"cgroup.events<br/>available?"}
        
        KERNEL_ACTIVE{"populated = 1?<br/>(kernel says processes active)"}
        NOT_IDLE(["Return: action=none<br/>reason=populated_active"])
        
        KERNEL_IDLE{"idle_duration ≥<br/>IDLE_TRIGGER (2.0s)?"}
        TOO_RECENT1(["Return: action=none<br/>reason=depopulated_but_too_recent"])
        
        FALLBACK_CHECK{"Fallback: idle_duration ≥<br/>IDLE_TRIGGER (2.0s)?"}
        TOO_RECENT2(["Return: action=none<br/>reason=not_idle_enough"])
    end

    subgraph SAFETY["Safety Check Sebelum Freeze"]
        EBPF_CHECK{"eBPF sensor tersedia<br/>DAN container punya<br/>open connections?"}
        DEFER(["Return: action=defer<br/>reason=open_connections<br/>(transaksi DB belum selesai)"])
    end

    subgraph DO_FREEZE["Eksekusi Freeze"]
        FIND_PATH["Cari cgroup.freeze path"]
        IS_DRY{"DRY_RUN?"}
        DRY_LOG["[DRY-RUN] Log saja"]
        WRITE_FREEZE["Tulis '1' ke cgroup.freeze<br/>Container CPU → 0%"]
        UPDATE_STATE["state.frozen = True<br/>state.frozen_at = now"]
        FREEZE_RET(["Return: action=freeze<br/>reason=idle:X.Xs"])
    end

    START --> IS_PRIORITY
    IS_PRIORITY -->|Ya| EXEMPT
    IS_PRIORITY -->|Tidak| FIRST_SEEN
    FIRST_SEEN -->|Ya| INIT_STATE
    INIT_STATE --> FIRST_RET
    FIRST_SEEN -->|Tidak| IS_FROZEN

    IS_FROZEN -->|Ya| CALC_DURATION
    CALC_DURATION --> DURATION_EXCEEDED
    DURATION_EXCEEDED -->|Ya, ≥ 1000ms| FORCE_THAW
    FORCE_THAW --> THAW_RET
    DURATION_EXCEEDED -->|Tidak| STILL_FROZEN

    IS_FROZEN -->|Tidak| CALC_IDLE
    CALC_IDLE --> CHECK_POPULATED
    CHECK_POPULATED --> POPULATED_AVAIL

    POPULATED_AVAIL -->|Ya| KERNEL_ACTIVE
    KERNEL_ACTIVE -->|Ya, active| NOT_IDLE
    KERNEL_ACTIVE -->|Tidak, depopulated| KERNEL_IDLE
    KERNEL_IDLE -->|Tidak, < 2s| TOO_RECENT1
    KERNEL_IDLE -->|Ya, ≥ 2s| EBPF_CHECK

    POPULATED_AVAIL -->|Tidak| FALLBACK_CHECK
    FALLBACK_CHECK -->|Tidak, < 2s| TOO_RECENT2
    FALLBACK_CHECK -->|Ya, ≥ 2s| EBPF_CHECK

    EBPF_CHECK -->|Ya, ada transaksi| DEFER
    EBPF_CHECK -->|Tidak, aman| FIND_PATH

    FIND_PATH --> IS_DRY
    IS_DRY -->|Ya| DRY_LOG
    IS_DRY -->|Tidak| WRITE_FREEZE
    DRY_LOG --> UPDATE_STATE
    WRITE_FREEZE --> UPDATE_STATE
    UPDATE_STATE --> FREEZE_RET
```

### Mengapa Ini Inovasi S2?
1. **Event-Driven vs Polling:** Idle detection menggunakan sinyal kernel (`cgroup.events populated=0`) — bukan polling CPU%. Ini menghilangkan false-idle dan false-active antar interval sampling.
2. **Literal 0% CPU:** Tidak ada teknik cgroups throttling yang bisa mencapai 0% CPU. Hanya `cgroup.freeze` yang bisa — dan ini eksklusif cgroups v2.
3. **Safety Gate (eBPF):** Sebelum freeze, mengecek apakah ada transaksi database yang belum selesai. Mencegah data corruption.
4. **Hard Duration Cap:** Freeze dibatasi 500–1000ms per siklus. Dikombinasikan dengan TCP Backlog buffering (lihat flowchart berikutnya).

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Evaluasi Kelayakan Micro-Freeze"])

    PENTING{"Validasi Prioritas<br/>Target Container?"}
    TIDAK_BOLEH(["❌ Eksekusi Ditolak<br/>(Bypass: Layanan Kritikal / Tier-0)"])

    BARU{"Status Tracking<br/>Initial (New)?"}
    CATAT_BARU["Inisialisasi State Tracking<br/>(Insufficient Data)"]
    PERTAMA_SELESAI(["Tunda eksekusi ke siklus (t+1)"])

    SUDAH_BEKU{"Status Aktif ==<br/>FROZEN?"}

    subgraph CEK_DURASI["Fase Evaluasi Durasi Freeze"]
        BERAPA_LAMA["Kalkulasi Durasi Freeze Aktual<br/>(Δt = Waktu Sekarang - Waktu Freeze)"]
        TERLALU_LAMA{"Durasi > Ambang Batas<br/>Maksimal (1000ms)?"}
        BANGUNKAN["⏰ Inisiasi Force-Thaw (Unfreeze)<br/>(Mitigasi risiko koneksi TCP putus)"]
        MASIH_OK(["Durasi Optimal<br/>(Pertahankan status FROZEN)"])
    end

    HITUNG_IDLE["Kalkulasi Durasi Idle (Δt sejak aktivitas terakhir)"]

    subgraph DETEKSI["Fase Deteksi Idle Berbasis Event (Kernel-Level)"]
        TANYA_KERNEL["Interogasi cgroup.events:<br/>Sinyal 'populated' dari Kernel"]
        BISA_TANYA{"Integritas<br/>cgroup v2?"}

        AKTIF{"Sinyal 'populated' == 1?<br/>(Terdapat proses aktif)"}
        BELUM_IDLE(["Container Aktif: Abort Freeze"])

        CUKUP_LAMA{"Durasi Idle ≥<br/>Trigger Threshold (2000ms)?"}
        BARU_SAJA(["Transisi terlalu dini<br/>(Risiko False-Idle)"])

        FALLBACK{"Fallback (Polling):<br/>Durasi Idle ≥ Threshold?"}
        BARU_SAJA2(["Transisi terlalu dini<br/>(Risiko False-Idle)"])
    end

    subgraph KEAMANAN["Fase Verifikasi Safety Gate (eBPF)"]
        CEK_TRANSAKSI{"Monitoring Koneksi Terbuka:<br/>Terdapat Transaksi Aktif?"}
        TUNDA(["⏸️ Defer Eksekusi<br/>(Menghindari korupsi data / interupsi I/O)"])
    end

    subgraph BEKUKAN["Fase Eksekusi State Mutation"]
        SIMULASI{"Dry-Run<br/>Mode?"}
        CATAT_SAJA["Log Eksekusi Saja (Simulasi)"]
        TULIS_BEKU["❄️ Inisiasi Freeze (Commit):<br/>Tulis '1' ke cgroup.freeze<br/>(Reduksi CPU → 0% seketika<br/>dengan Resume Latency < 1ms)"]
        TANDAI["Perbarui Tracking State = FROZEN"]
        BEKU_SELESAI(["Siklus Freeze Selesai<br/>(Energi Berhasil Dihemat)"])
    end

    START --> PENTING
    PENTING -->|Ya| TIDAK_BOLEH
    PENTING -->|Tidak| BARU
    BARU -->|Ya| CATAT_BARU
    CATAT_BARU --> PERTAMA_SELESAI
    BARU -->|Tidak| SUDAH_BEKU

    SUDAH_BEKU -->|Ya| BERAPA_LAMA
    BERAPA_LAMA --> TERLALU_LAMA
    TERLALU_LAMA -->|Ya| BANGUNKAN
    TERLALU_LAMA -->|Tidak| MASIH_OK

    SUDAH_BEKU -->|Tidak| HITUNG_IDLE
    HITUNG_IDLE --> TANYA_KERNEL
    TANYA_KERNEL --> BISA_TANYA

    BISA_TANYA -->|Ya| AKTIF
    AKTIF -->|Ya (Aktif)| BELUM_IDLE
    AKTIF -->|Tidak (Idle)| CUKUP_LAMA
    CUKUP_LAMA -->|Belum| BARU_SAJA
    CUKUP_LAMA -->|Sudah| CEK_TRANSAKSI

    BISA_TANYA -->|Tidak| FALLBACK
    FALLBACK -->|Belum| BARU_SAJA2
    FALLBACK -->|Sudah| CEK_TRANSAKSI

    CEK_TRANSAKSI -->|Ya, Terbuka| TUNDA
    CEK_TRANSAKSI -->|Tidak, Aman| SIMULASI

    SIMULASI -->|Ya| CATAT_SAJA
    SIMULASI -->|Tidak| TULIS_BEKU
    CATAT_SAJA --> TANDAI
    TULIS_BEKU --> TANDAI
    TANDAI --> BEKU_SELESAI
```
