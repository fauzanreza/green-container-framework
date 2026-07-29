# Flowchart — MicroFreezer.apply_freeze() (Layer 4)

> **Kode Sumber:** `framework/micro_freezer.py` → class `MicroFreezer`, fungsi `apply_freeze()` (baris 32–106)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Micro-Freezer
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma pembekuan container tingkat milidetik (`cgroup.freeze`). Dioptimasi untuk mereduksi konsumsi CPU idle ke absolute 0% tanpa memutus koneksi TCP. Menggunakan eBPF untuk mendeteksi transaksi yang sedang berjalan (Safety Gate) dan `cgroup.events` untuk deteksi idle.

```mermaid
flowchart TD
    START(["apply_freeze(container_name, is_dry_run)"])

    IS_PRIORITY{"Tier-0<br/>(Prio)?"}
    EXEMPT(["Return False<br/>(Bypass)"])

    FIRST_SEEN{"Container<br/>baru?"}
    INIT_STATE["Init freeze state:<br/>is_frozen = False<br/>frozen_at = None<br/>last_activity = now"]
    FIRST_RET(["Return False"])

    IS_FROZEN{"is_frozen<br/>== True?"}

    CALC_DURATION["duration = now - frozen_at"]
    DURATION_EXCEEDED{"duration<br/>≥ 1000ms?"}
    FORCE_THAW["Force Thaw:<br/>Tulis 0 ke cgroup.freeze<br/>is_frozen = False"]
    STILL_FROZEN(["Return True<br/>(Keep frozen)"])

    CALC_IDLE["idle_time = now - last_activity"]

    POPULATED_AVAIL{"cgroup.events<br/>bisa dibaca?"}
    KERNEL_ACTIVE{"populated == 1?"}
    NOT_IDLE["Update last_activity = now"]
    KERNEL_IDLE{"idle_time<br/>≥ 2000ms?"}
    TOO_RECENT1(["Return False<br/>(Wait longer)"])
    
    FALLBACK_CHECK{"idle_time<br/>≥ 2000ms?"}
    TOO_RECENT2(["Return False<br/>(Wait longer)"])

    EBPF_CHECK{"Cek eBPF:<br/>Ada tx aktif?"}
    DEFER(["Return False<br/>(Safety defer)"])

    FIND_PATH["Resolusi cgroup path"]

    IS_DRY{"is_dry_run?"}
    DRY_LOG["Log 'Would freeze...'"]
    WRITE_FREEZE["Tulis 1 ke cgroup.freeze"]
    UPDATE_STATE["Update state:<br/>is_frozen = True<br/>frozen_at = now"]
    FREEZE_RET(["Return True"])

    START --> IS_PRIORITY
    IS_PRIORITY -->|Ya| EXEMPT
    IS_PRIORITY -->|Tidak| FIRST_SEEN
    FIRST_SEEN -->|Ya| INIT_STATE
    INIT_STATE --> FIRST_RET
    FIRST_SEEN -->|Tidak| IS_FROZEN

    IS_FROZEN -->|Ya| CALC_DURATION
    CALC_DURATION --> DURATION_EXCEEDED
    DURATION_EXCEEDED -->|"Ya (≥ 1000ms)"| FORCE_THAW
    DURATION_EXCEEDED -->|Tidak| STILL_FROZEN

    IS_FROZEN -->|Tidak| CALC_IDLE
    CALC_IDLE --> POPULATED_AVAIL

    POPULATED_AVAIL -->|Ya| KERNEL_ACTIVE
    KERNEL_ACTIVE -->|"Ya"| NOT_IDLE
    KERNEL_ACTIVE -->|"Tidak"| KERNEL_IDLE
    KERNEL_IDLE -->|"Tidak (< 2s)"| TOO_RECENT1
    KERNEL_IDLE -->|"Ya (≥ 2s)"| EBPF_CHECK

    POPULATED_AVAIL -->|Tidak| FALLBACK_CHECK
    FALLBACK_CHECK -->|"Tidak (< 2s)"| TOO_RECENT2
    FALLBACK_CHECK -->|"Ya (≥ 2s)"| EBPF_CHECK

    EBPF_CHECK -->|Ya| DEFER
    EBPF_CHECK -->|Tidak| FIND_PATH

    FIND_PATH --> IS_DRY
    IS_DRY -->|Ya| DRY_LOG
    IS_DRY -->|Tidak| WRITE_FREEZE
    DRY_LOG --> UPDATE_STATE
    WRITE_FREEZE --> UPDATE_STATE
    UPDATE_STATE --> FREEZE_RET
```

## Mengapa Ini Inovasi S2?

1. **Event-Driven vs Polling:** Idle detection menggunakan sinyal kernel (`cgroup.events populated=0`) — bukan polling CPU%. Ini menghilangkan false-idle dan false-active antar interval sampling.
2. **Literal 0% CPU:** Tidak ada teknik cgroups throttling yang bisa mencapai 0% CPU. Hanya `cgroup.freeze` yang bisa — dan ini eksklusif cgroups v2.
3. **Safety Gate (eBPF):** Sebelum freeze, mengecek apakah ada transaksi database yang belum selesai. Mencegah data corruption.
4. **Hard Duration Cap:** Freeze dibatasi 500–1000ms per siklus. Dikombinasikan dengan TCP Backlog buffering (lihat flowchart berikutnya).

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Evaluasi Micro-Freeze"])

    PENTING{"Validasi Prioritas?"}
    TIDAK_BOLEH(["❌ Bypass: Tier-0"])

    BARU{"Tracking Initial?"}
    CATAT_BARU["Inisialisasi State Tracking"]
    PERTAMA_SELESAI(["Tunda ke siklus (t+1)"])

    SUDAH_BEKU{"Status FROZEN?"}

    subgraph CEK_DURASI["Fase Evaluasi Durasi Freeze"]
        BERAPA_LAMA["Hitung Durasi Freeze (Δt)"]
        TERLALU_LAMA{"Durasi > 1000ms?"}
        BANGUNKAN["⏰ Force-Thaw (Unfreeze)"]
        MASIH_OK(["Pertahankan FROZEN"])
    end

    HITUNG_IDLE["Hitung Durasi Idle (Δt)"]

    subgraph DETEKSI["Fase Deteksi Idle (Kernel-Level)"]
        TANYA_KERNEL["Cek cgroup.events 'populated'"]
        BISA_TANYA{"cgroup v2 support?"}

        AKTIF{"populated == 1?"}
        BELUM_IDLE(["Container Aktif → Abort"])

        CUKUP_LAMA{"Idle ≥ 2000ms?"}
        BARU_SAJA(["False-Idle Risk → Abort"])

        FALLBACK{"Polling: Idle ≥ Threshold?"}
        BARU_SAJA2(["False-Idle Risk → Abort"])
    end

    subgraph KEAMANAN["Fase Safety Gate (eBPF)"]
        CEK_TRANSAKSI{"Ada transaksi<br/>aktif terbuka?"}
        TUNDA(["⏸️ Defer Eksekusi (Mencegah I/O corrupt)"])
    end

    subgraph BEKUKAN["Fase Eksekusi State"]
        SIMULASI{"Dry-Run Mode?"}
        CATAT_SAJA["Log Eksekusi Saja"]
        TULIS_BEKU["❄️ Inisiasi Freeze (Commit 1 ke cgroup.freeze)"]
        TANDAI["Update Tracking State = FROZEN"]
        BEKU_SELESAI(["Siklus Freeze Selesai"])
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
    AKTIF -->|"Ya"| BELUM_IDLE
    AKTIF -->|"Tidak"| CUKUP_LAMA
    CUKUP_LAMA -->|"Belum"| BARU_SAJA
    CUKUP_LAMA -->|"Sudah"| CEK_TRANSAKSI

    BISA_TANYA -->|Tidak| FALLBACK
    FALLBACK -->|"Belum"| BARU_SAJA2
    FALLBACK -->|"Sudah"| CEK_TRANSAKSI

    CEK_TRANSAKSI -->|Ya| TUNDA
    CEK_TRANSAKSI -->|Tidak| SIMULASI

    SIMULASI -->|Ya| CATAT_SAJA
    SIMULASI -->|Tidak| TULIS_BEKU
    CATAT_SAJA --> TANDAI
    TULIS_BEKU --> TANDAI
    TANDAI --> BEKU_SELESAI
```
