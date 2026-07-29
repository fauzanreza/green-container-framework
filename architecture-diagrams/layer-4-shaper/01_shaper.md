# Flowchart — Shaper.apply_shaping() (Layer 4)

> **Kode Sumber:** `framework/shaper.py` → class `ContainerShaper`, fungsi `apply_shaping()` (baris 31–123)
> **Posisi di Diagram:** Layer 4 — Adaptive Resource Shaping → 4A Cgroups Writer
> **Kategori:** 🛠️ TOOLS & INFRASTRUKTUR (S1)

Shaper bertugas sebagai eksekutor. Menerima input dari Layer 3 (Tier & Limit) dan menulisnya ke file `/sys/fs/cgroup/cpu.max` dan `memory.max`. Layer ini bersifat "bodoh", murni I/O bound.

```mermaid
flowchart TD
    START(["apply_shaping(container_name, cpu_quota, mem_ratio)"])

    PRIO{"Container<br/>Tier-0 (Prio)?"}
    SKIP(["Return (Bypass)"])

    DRY_RUN{"DRY_RUN_MODE?"}
    LOG_ONLY["Log 'Would shape...'"]
    RETURN_DRY(["Return"])

    RESOLVE_PATH["Resolusi cgroup path"]
    PATH_FOUND{"Path valid?"}
    ABORT(["Return (Target terminated)"])

    CPU_QUOTA{"cpu_quota<br/>ditentukan?"}
    WRITE_UNLIMITED["Tulis 'max 100000' ke cpu.max<br/>(Unlimited)"]
    WRITE_LIMITED["Tulis '{quota} 100000' ke cpu.max<br/>(Throttled)"]

    VERIFY_CPU["Baca ulang cpu.max untuk verifikasi"]
    CPU_ERR{"I/O Error?"}
    RETRY_CPU["Retry max 3 kali"]

    MEM_RATIO{"mem_ratio<br/>ditentukan?"}
    RETURN(["Return"])

    CALC_MEM["mem_limit = host_ram * mem_ratio"]
    WRITE_MEM["Tulis ke memory.max"]
    WRITE_HIGH["Tulis ke memory.high (soft limit)"]

    ZRAM_AVAIL{"ZRAM (Swap)<br/>Aktif?"}
    SWAP_ALLOW["Tulis mem_limit ke memory.swap.max"]
    SWAP_DISABLE["Tulis 0 ke memory.swap.max"]

    START --> PRIO
    PRIO -->|Ya| SKIP
    PRIO -->|Tidak| DRY_RUN
    DRY_RUN -->|Ya| LOG_ONLY
    LOG_ONLY --> RETURN_DRY
    DRY_RUN -->|Tidak| RESOLVE_PATH

    RESOLVE_PATH --> PATH_FOUND
    PATH_FOUND -->|Tidak| ABORT
    PATH_FOUND -->|Ya| CPU_QUOTA

    CPU_QUOTA -->|Tidak| WRITE_UNLIMITED
    CPU_QUOTA -->|Ya| WRITE_LIMITED
    WRITE_UNLIMITED --> VERIFY_CPU
    WRITE_LIMITED --> VERIFY_CPU

    VERIFY_CPU --> CPU_ERR
    CPU_ERR -->|Ya| RETRY_CPU
    RETRY_CPU --> MEM_RATIO
    CPU_ERR -->|Tidak| MEM_RATIO

    MEM_RATIO -->|Tidak| RETURN
    MEM_RATIO -->|Ya| CALC_MEM
    CALC_MEM --> WRITE_MEM
    WRITE_MEM --> WRITE_HIGH
    WRITE_HIGH --> ZRAM_AVAIL

    ZRAM_AVAIL -->|Ya| SWAP_ALLOW
    ZRAM_AVAIL -->|Tidak| SWAP_DISABLE

    SWAP_ALLOW --> RETURN
    SWAP_DISABLE --> RETURN
```

## Catatan

Meskipun ini dikategorikan sebagai Tools (S1), perhatikan bahwa **nilai yang ditulis** (`cpu_quota`, `mem_ratio`) berasal dari keputusan algoritmik Layer 3. Shaper hanyalah "tangan" yang mengeksekusi perintah "otak".

---

## Alur Logika Konseptual

```mermaid
flowchart TD
    START(["Inisiasi Eksekusi Cgroups"])

    PENTING{"Prioritas<br/>Kritikal?"}
    LINDUNGI["🛡️ Bypass Eksklusi (Infrastruktur/DB)"]

    SIMULASI{"Dry-Run<br/>Mode?"}
    CATAT["Log eksekusi (Simulasi)"]

    CARI["Resolusi path cgroupfs"]
    KETEMU{"Path valid?"}
    LEWATI["Abort: Inaccessible"]

    subgraph CPU["Modulasi Kuota CPU"]
    CEK_CPU{"Ada batas CPU?"}
    BEBASKAN["cpu.max = 'max 100000'<br/>(Relaksasi Quota)"]
    BATASI["cpu.max = '[kuota] 100000'<br/>(Terapkan Quota)"]
    VERIFIKASI["Validasi I/O (Read-back)"]
    GAGAL{"I/O Error?"}
    COBA_LAGI["Retry Tulis Ulang"]
    end

    subgraph RAM["Modulasi Batas Memori (Low-Priority)"]
    PERLU_RAM{"Ada batas Memori?"}
    LEWAT_RAM["Bypass Modulasi RAM"]
    HITUNG_RAM["Hitung Resolusi Memori"]
    TULIS_RAM["Tulis memory.max"]
    REM_PERINGATAN["Terapkan memory.high (Soft Limit)"]
    CEK_SWAP{"ZRAM (Swap)<br/>Aktif?"}
    IZINKAN_SWAP["memory.swap.max = limit"]
    LARANG_SWAP["memory.swap.max = 0<br/>(Isolasi Swap)"]
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
