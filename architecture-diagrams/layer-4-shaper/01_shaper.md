# Flowchart — shape_container() (Layer 4 — Cgroups Writer)

> **Kode Sumber:** `framework/shaper.py` → fungsi `shape_container()` (baris 33–81), `_write_cpu()` (baris 84–116), `_write_memory()` (baris 119–150)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → cpu.max, memory.max, memory.high, zram
> **Kategori:** Tools / Aktuator (S1)

Fungsi ini adalah **aktuator**. Ia tidak membuat keputusan — ia hanya mengeksekusi keputusan dari Layer 3. Menulis parameter ke file cgroups v2 di Linux kernel.

```mermaid
flowchart TD
    START(["shape_container(name, id, priority,<br/>cpu_quota, mem_ratio, host_mem_bytes)"])

    IS_PRIORITY{"Container<br/>priority = True<br/>DAN cpu_quota > 0?"}
    SHIELD["[SHIELD] Skip hard cap<br/>Priority container dilindungi<br/>Return True"]

    IS_DRY{"DRY_RUN?"}
    DRY_LOG["[DRY-RUN] Log saja,<br/>tidak menulis ke cgroup"]

    FIND_CGROUP["Cari cgroup path:<br/>/sys/fs/cgroup/system.slice/docker-{id}.scope"]
    CGROUP_FOUND{"Path<br/>ditemukan?"}
    SKIP["Skip shaping<br/>Return False"]

    subgraph CPU_SHAPE["CPU Shaping"]
        CPU_CHECK{"cpu_quota<br/>≤ 0?"}
        CPU_REMOVE["Tulis 'max' ke cpu.max<br/>(hapus limit, CPU unlimited)"]
        CPU_SET["Tulis '{quota} {period}' ke cpu.max<br/>Contoh: '50000 100000' = 0.5 core"]
        CPU_VALIDATE["Read-back validation:<br/>Baca cpu.max kembali<br/>Cocokkan dengan yang ditulis"]
        CPU_MISMATCH{"Validasi<br/>gagal?"}
        CPU_RETRY["Retry tulis sekali lagi"]
    end

    subgraph MEM_SHAPE["Memory Shaping (non-priority only)"]
        MEM_CHECK{"mem_ratio diberikan<br/>DAN NOT priority<br/>DAN host_mem > 0?"}
        MEM_SKIP["Skip memory shaping"]
        MEM_CALC["mem_bytes = host_mem × mem_ratio<br/>Contoh: 5547MB × 0.70 = 3883MB"]
        MEM_WRITE["Tulis mem_bytes ke memory.max"]
        MEM_HIGH["Tulis memory.high = mem_bytes × 0.85<br/>(soft-brake sebelum OOM)"]
        SWAP_CHECK["Cek zram availability"]
        ZRAM_AVAIL{"zram-backed<br/>swap ada?"}
        SWAP_ALLOW["memory.swap.max = min(mem_bytes, zram_size)<br/>(izinkan compressed swap)"]
        SWAP_DISABLE["memory.swap.max = 0<br/>(disable swap — cegah disk thrashing)"]
    end

    RETURN(["Return True/False"])

    START --> IS_PRIORITY
    IS_PRIORITY -->|Ya| SHIELD
    IS_PRIORITY -->|Tidak| IS_DRY
    IS_DRY -->|Ya| DRY_LOG
    IS_DRY -->|Tidak| FIND_CGROUP
    FIND_CGROUP --> CGROUP_FOUND
    CGROUP_FOUND -->|Tidak| SKIP
    CGROUP_FOUND -->|Ya| CPU_CHECK

    CPU_CHECK -->|Ya, unlimited| CPU_REMOVE
    CPU_CHECK -->|Tidak, ada limit| CPU_SET
    CPU_REMOVE --> CPU_VALIDATE
    CPU_SET --> CPU_VALIDATE
    CPU_VALIDATE --> CPU_MISMATCH
    CPU_MISMATCH -->|Ya| CPU_RETRY
    CPU_MISMATCH -->|Tidak| MEM_CHECK
    CPU_RETRY --> MEM_CHECK

    MEM_CHECK -->|Tidak| MEM_SKIP
    MEM_CHECK -->|Ya| MEM_CALC
    MEM_CALC --> MEM_WRITE
    MEM_WRITE --> MEM_HIGH
    MEM_HIGH --> SWAP_CHECK
    SWAP_CHECK --> ZRAM_AVAIL
    ZRAM_AVAIL -->|Ya| SWAP_ALLOW
    ZRAM_AVAIL -->|Tidak| SWAP_DISABLE

    MEM_SKIP --> RETURN
    SWAP_ALLOW --> RETURN
    SWAP_DISABLE --> RETURN
```

### Catatan
Meskipun ini dikategorikan sebagai Tools (S1), perhatikan bahwa **nilai yang ditulis** (`cpu_quota`, `mem_ratio`) berasal dari keputusan algoritmik Layer 3. Shaper hanyalah "tangan" yang mengeksekusi perintah "otak".

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Inisiasi Parameter Kontrol (Cgroups Writer)"])

    PENTING{"Prioritas<br/>Kritikal?"}
    LINDUNGI["🛡️ Eksklusi: Bypass Shaping<br/>(Prioritas Infrastruktur / Database)"]

    SIMULASI{"Dry-Run<br/>Mode?"}
    CATAT["Log Eksekusi Saja<br/>(Tanpa Mutasi State Cgroups)"]

    CARI["Resolusi path cgroupfs container target"]
    KETEMU{"Path<br/>Valid?"}
    LEWATI["Abort iterasi:<br/>Cgroup Namespace Inaccessible"]

    subgraph CPU["Modulasi Kuota CPU"]
    CEK_CPU{"Terdapat Target<br/>Batas CPU?"}
    BEBASKAN["Relaksasi Quota (Unlimited):<br/>cpu.max = 'max 100000'"]
    BATASI["Tulis Parameter Quota Baru:<br/>cpu.max = '[kuota] 100000'"]
    VERIFIKASI["Validasi I/O (Read-back):<br/>Konfirmasi komit kernel"]
    GAGAL{"I/O<br/>Error?"}
    COBA_LAGI["Eksekusi Retry (Tulis Ulang)"]
    end

    subgraph RAM["Modulasi Batas Memori (Low-Priority Only)"]
    PERLU_RAM{"Terdapat Target<br/>Batas Memori?"}
    LEWAT_RAM["Bypass Modulasi Memori"]
    HITUNG_RAM["Kalkulasi Resolusi Memori:<br/>Misal: (Memori Aktif / 0.70)"]
    TULIS_RAM["Tulis ke memory.max"]
    REM_PERINGATAN["Terapkan memory.high (Soft Limit):<br/>(Memicu kernel page-reclaim proaktif)"]
    CEK_SWAP{"Ketersediaan<br/>ZRAM (Swap kompresi)?"}
    IZINKAN_SWAP["Konfigurasi memory.swap.max:<br/>Alokasi ZRAM proporsional"]
    LARANG_SWAP["Isolasi Swap (memory.swap.max = 0):<br/>Cegah latensi disk I/O"]
    end

    SELESAI(["Eksekusi Cgroups Selesai"])

    START --> PENTING
    PENTING -->|Ya| LINDUNGI
    PENTING -->|Tidak| SIMULASI
    SIMULASI -->|Ya| CATAT
    SIMULASI -->|Tidak| CARI
    CARI --> KETEMU
    KETEMU -->|Tidak| LEWATI
    KETEMU -->|Ya| CEK_CPU

    CEK_CPU -->|Tidak| BEBASKAN
    CEK_CPU -->|Ya| BATASI
    BEBASKAN --> VERIFIKASI
    BATASI --> VERIFIKASI
    VERIFIKASI --> GAGAL
    GAGAL -->|Ya| COBA_LAGI
    GAGAL -->|Tidak| PERLU_RAM
    COBA_LAGI --> PERLU_RAM

    PERLU_RAM -->|Tidak| LEWAT_RAM
    PERLU_RAM -->|Ya| HITUNG_RAM
    HITUNG_RAM --> TULIS_RAM
    TULIS_RAM --> REM_PERINGATAN
    REM_PERINGATAN --> CEK_SWAP
    CEK_SWAP -->|Ya| IZINKAN_SWAP
    CEK_SWAP -->|Tidak| LARANG_SWAP

    LEWAT_RAM --> SELESAI
    IZINKAN_SWAP --> SELESAI
    LARANG_SWAP --> SELESAI
```
