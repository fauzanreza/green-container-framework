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
    START(["START: Evaluasi Micro-Freeze"])

    PENTING{"Apakah Prioritas<br/>Kritikal?"}
    SELESAI_TIDAK_BOLEH(["END: ❌ Bypass (Tier-0)"])

    BARU{"Apakah Tracking<br/>Initial (Baru)?"}
    CATAT_BARU["Inisialisasi State Tracking"]
    SELESAI_PERTAMA(["END: Tunda ke Siklus (t+1)"])

    SUDAH_BEKU{"Apakah Status<br/>Sudah FROZEN?"}

    subgraph CEK_DURASI["Fase Evaluasi Durasi Freeze"]
        BERAPA_LAMA["Hitung Durasi Freeze (Δt)"]
        TERLALU_LAMA{"Apakah Durasi Freeze<br/>> 1000ms?"}
        SELESAI_BANGUNKAN(["END: ⏰ Force-Thaw (Unfreeze)"])
        SELESAI_MASIH_OK(["END: Pertahankan FROZEN"])
    end

    HITUNG_IDLE["Hitung Durasi Idle (Δt)"]

    subgraph DETEKSI["Fase Deteksi Idle (Kernel-Level)"]
        TANYA_KERNEL["Cek cgroup.events 'populated'"]
        BISA_TANYA{"Apakah Host Mendukung<br/>cgroup v2?"}

        AKTIF{"Apakah populated == 1?<br/>(Container Aktif)"}
        SELESAI_BELUM_IDLE(["END: Container Aktif → Abort"])

        CUKUP_LAMA{"Apakah Idle Terjadi<br/>≥ 2000ms?"}
        SELESAI_BARU_SAJA(["END: False-Idle Risk → Abort"])

        FALLBACK{"Apakah Polling Idle<br/>≥ Threshold?"}
        SELESAI_BARU_SAJA2(["END: False-Idle Risk → Abort"])
    end

    subgraph KEAMANAN["Fase Safety Gate (eBPF)"]
        CEK_TRANSAKSI{"Apakah Ada Transaksi DB<br/>Aktif Terbuka?"}
        SELESAI_TUNDA(["END: ⏸️ Defer Eksekusi (Mencegah I/O Corrupt)"])
    end

    subgraph BEKUKAN["Fase Eksekusi State"]
        SIMULASI{"Apakah DRY_RUN<br/>Mode Aktif?"}
        CATAT_SAJA["Log Eksekusi Saja"]
        TULIS_BEKU["❄️ Inisiasi Freeze (Commit 1 ke cgroup.freeze)"]
        TANDAI["Update Tracking State = FROZEN"]
        SELESAI(["END: Siklus Freeze Selesai"])
    end

    START --> PENTING
    PENTING -->|Ya| SELESAI_TIDAK_BOLEH
    PENTING -->|Tidak| BARU
    BARU -->|Ya| CATAT_BARU
    CATAT_BARU --> SELESAI_PERTAMA
    BARU -->|Tidak| SUDAH_BEKU

    SUDAH_BEKU -->|Ya| BERAPA_LAMA
    BERAPA_LAMA --> TERLALU_LAMA
    TERLALU_LAMA -->|Ya| SELESAI_BANGUNKAN
    TERLALU_LAMA -->|Tidak| SELESAI_MASIH_OK

    SUDAH_BEKU -->|Tidak| HITUNG_IDLE
    HITUNG_IDLE --> TANYA_KERNEL
    TANYA_KERNEL --> BISA_TANYA

    BISA_TANYA -->|Ya| AKTIF
    AKTIF -->|"Ya"| SELESAI_BELUM_IDLE
    AKTIF -->|"Tidak"| CUKUP_LAMA
    CUKUP_LAMA -->|"Belum"| SELESAI_BARU_SAJA
    CUKUP_LAMA -->|"Sudah"| CEK_TRANSAKSI

    BISA_TANYA -->|Tidak| FALLBACK
    FALLBACK -->|"Belum"| SELESAI_BARU_SAJA2
    FALLBACK -->|"Sudah"| CEK_TRANSAKSI

    CEK_TRANSAKSI -->|Ya| SELESAI_TUNDA
    CEK_TRANSAKSI -->|Tidak| SIMULASI

    SIMULASI -->|Ya| CATAT_SAJA
    SIMULASI -->|Tidak| TULIS_BEKU
    CATAT_SAJA --> TANDAI
    TULIS_BEKU --> TANDAI
    TANDAI --> SELESAI
```
