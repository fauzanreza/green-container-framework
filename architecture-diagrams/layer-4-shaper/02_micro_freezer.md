# Flowchart — MicroFreezer.evaluate() (Layer 4)

> **Kode Sumber:** `framework/security/micro_freezer.py` → class `MicroFreezer`, fungsi `evaluate()` (baris 78–145) dan `record_activity()` (baris 62–76)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4B Micro-Freezer
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma pembekuan container tingkat milidetik (`cgroup.freeze`). Dioptimasi untuk mereduksi konsumsi CPU idle ke absolute 0% tanpa memutus koneksi TCP. Menggunakan eBPF untuk mendeteksi transaksi yang sedang berjalan (Safety Gate) dan `cgroup.events` untuk deteksi idle. Terintegrasi dengan **Active Memory Reclaim** (`memory.reclaim`) untuk membebaskan page cache saat idle.

```mermaid
flowchart TD
    START(["evaluate(container_name, container_id, priority, cpu_percent)"])

    IS_PRIORITY{"priority<br/>== True?"}
    EXEMPT(["Return {action: 'none',<br/>reason: 'priority_exempt'}"])

    FIRST_SEEN{"container_id<br/>in state?"}
    INIT_STATE["Init state[container_id]:<br/>frozen=False, frozen_at=0.0<br/>last_activity=now"]
    FIRST_RET(["Return {action: 'none',<br/>reason: 'first_seen'}"])

    IS_FROZEN{"state['frozen']<br/>== True?"}

    CALC_DURATION["frozen_duration_ms = (now - frozen_at) × 1000"]
    DURATION_EXCEEDED{"frozen_duration_ms<br/>≥ max_freeze_ms?"}
    FORCE_THAW["Force Thaw: _thaw(id, reason='max_duration')<br/>Catat cumulative_freeze_s<br/>state.frozen = False"]
    STILL_FROZEN(["Return {action: 'none',<br/>reason: 'already_frozen'}"])

    CALC_IDLE["idle_duration = now - state.last_activity"]

    POPULATED_AVAIL{"_check_populated(id)<br/>returns value?"}
    KERNEL_ACTIVE{"populated<br/>== True?"}
    NOT_IDLE["Return {action: 'none',<br/>reason: 'populated_active'}"]
    KERNEL_IDLE{"idle_duration<br/>≥ 0.8s (idle_trigger)?"}
    TOO_RECENT1(["Return {action: 'none',<br/>reason: 'depopulated_but_too_recent'}"])
    
    FALLBACK_CHECK{"idle_duration<br/>≥ 0.8s (idle_trigger)?"}
    TOO_RECENT2(["Return {action: 'none',<br/>reason: 'not_idle_enough'}"])

    EBPF_CHECK{"ebpf_sensor.has_open_connections(id)?"}
    DEFER(["Return {action: 'defer',<br/>reason: 'open_connections'}"])

    FIND_PATH["Resolusi cgroup.freeze path"]

    IS_DRY{"dry_run?"}
    DRY_LOG["Log '[DRY-RUN] Would FREEZE...'"]
    WRITE_FREEZE["Tulis '1' ke cgroup.freeze<br/>via _freeze(name, id)<br/>Trigger memory.reclaim"]
    UPDATE_STATE["Update state[id]:<br/>frozen=True, frozen_at=now"]
    FREEZE_RET(["Return {action: 'freeze',<br/>reason: 'idle:{duration}s'}"])

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
    KERNEL_IDLE -->|"Tidak (< 0.8s)"| TOO_RECENT1
    KERNEL_IDLE -->|"Ya (≥ 0.8s)"| EBPF_CHECK

    POPULATED_AVAIL -->|Tidak| FALLBACK_CHECK
    FALLBACK_CHECK -->|"Tidak (< 0.8s)"| TOO_RECENT2
    FALLBACK_CHECK -->|"Ya (≥ 0.8s)"| EBPF_CHECK

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

1. **Event-Driven vs Polling:** Idle detection menggunakan sinyal kernel (`cgroup.events populated=0`) — bukan polling CPU%. Ini menghilangkan false-idle dan false-active antar interval sampling. Waktu tunggu ditekan menjadi 0.8s untuk memaksimalkan capture state idle.
2. **Literal 0% CPU:** Tidak ada teknik cgroups throttling yang bisa mencapai 0% CPU. Hanya `cgroup.freeze` yang bisa — dan ini eksklusif cgroups v2.
3. **Active Memory Reclaim:** Tidak hanya menghemat CPU, pembekuan otomatis memicu `memory.reclaim` (kernel ≥ 6.1) untuk menekan footprint RAM container yang sedang idle tanpa membunuhnya.
4. **Safety Gate (eBPF):** Sebelum freeze, mengecek apakah ada transaksi database yang belum selesai. Mencegah data corruption.
5. **Hard Duration Cap:** Freeze dibatasi 500–1000ms per siklus. Dikombinasikan dengan TCP Backlog buffering (lihat flowchart berikutnya). Durasi freeze ini diakumulasikan dan dilacak per container untuk perhitungan energi.

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

        CUKUP_LAMA{"Apakah Idle Terjadi<br/>≥ 800ms?"}
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
        TULIS_BEKU["❄️ Inisiasi Freeze (cgroup.freeze=1)"]
        RECLAIM["Trigger memory.reclaim<br/>(Bebaskan Page Cache)"]
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
    TULIS_BEKU --> RECLAIM
    RECLAIM --> TANDAI
    TANDAI --> SELESAI
```
