# Flowchart — Monitor.get_container_stats() (Layer 2)

> **Kode Sumber:** `framework/monitor.py` → class `ContainerMonitor`, fungsi `get_container_stats()` (baris 32–105)
> **Posisi di Diagram:** Layer 2 — Monitoring Engine → Direct cgroupfs v2 Read
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma pembacaan I/O kernel langsung tanpa perantara Docker API. Metode ini memangkas latency overhead dari ~15ms (Docker API) menjadi <1ms (Sysfs Read), sangat kritikal untuk sampling rate tinggi (adaptive sampling).

```mermaid
flowchart TD
    START(["get_container_stats(container_name)"])

    RESOLVE_PATH["Resolusi cgroup path:<br/>/sys/fs/cgroup/.../docker-UID.scope"]
    CGROUP_FOUND{"Path valid?"}
    STALE_RET(["Return None<br/>(Target terminated)"])

    RETRY_LOOP["Iterasi baca (max 3 retries)"]

    READ_CPU["Baca cpu.stat<br/>Parse usage_usec"]
    READ_MEM["Baca memory.current (total)"]
    READ_INACT["Baca memory.stat<br/>Parse inactive_file"]

    CALC_MEM["Memori Efektif = memory.current - inactive_file"]

    MEM_MAX_CHECK{"memory.max == max?"}
    USE_HOST_MEM["Limit = Total Host RAM"]
    USE_LIMIT["Limit = memory.max"]

    CALC_MEM_PCT["mem_pct = (Efektif / Limit) × 100"]

    READ_FAIL{"I/O Error?"}
    RETRY{"Retries < 3?"}
    RETRY_WAIT["time.sleep(0.01)"]
    ALL_FAIL(["Return None<br/>(Max retries exceeded)"])

    HAS_PREV{"Ada prev_stats?"}
    FIRST_SAMPLE["Simpan current stats<br/>Return cpu_pct = 0.0"]

    CALC_CPU["Hitung CPU %:<br/>Δ usage_usec / Δ time"]

    SAVE_STATE["prev_stats[name] = current stats"]

    RETURN(["Return (cpu_pct, mem_pct)"])

    START --> RESOLVE_PATH
    RESOLVE_PATH --> CGROUP_FOUND
    CGROUP_FOUND -->|Tidak| STALE_RET
    CGROUP_FOUND -->|Ya| RETRY_LOOP

    RETRY_LOOP --> READ_CPU
    READ_CPU --> READ_MEM
    READ_MEM --> READ_INACT
    READ_INACT --> CALC_MEM
    CALC_MEM --> MEM_MAX_CHECK
    MEM_MAX_CHECK -->|Ya| USE_HOST_MEM
    MEM_MAX_CHECK -->|Tidak| USE_LIMIT
    USE_HOST_MEM --> CALC_MEM_PCT
    USE_LIMIT --> CALC_MEM_PCT

    READ_CPU -.-> READ_FAIL
    READ_FAIL -->|Ya| RETRY
    RETRY -->|Ya| RETRY_WAIT
    RETRY_WAIT --> RETRY_LOOP
    RETRY -->|Tidak| ALL_FAIL

    CALC_MEM_PCT --> HAS_PREV
    HAS_PREV -->|Tidak| FIRST_SAMPLE
    HAS_PREV -->|Ya| CALC_CPU

    CALC_CPU --> SAVE_STATE
    FIRST_SAMPLE --> RETURN
    SAVE_STATE --> RETURN
```

## Alur Logika Konseptual

### Akuisisi Metrik Utilisasi

```mermaid
flowchart TD
    START(["START: Akuisisi Metrik Container"])

    CARI["Resolusi path cgroupfs target"]
    KETEMU{"Apakah Path<br/>Valid?"}
    SELESAI_GAGAL(["END: Abort, Target Inaccessible"])

    BACA_CPU["Baca cpu.stat (usage_usec)"]
    BACA_RAM["Baca memory.current (RSS + Cache)"]
    KURANGI["Kalkulasi Memori Efektif:<br/>Total Memori - Reclaimable Cache"]

    GAGAL{"Apakah Terjadi<br/>I/O Error?"}
    COBA_LAGI{"Apakah Max Retries<br/>Tercapai?"}
    TUNGGU["Backoff & Retry"]
    SEMUA_GAGAL["Abort: Max Retries"]

    PERTAMA{"Apakah Pembacaan Pertama?<br/>(Belum ada baseline)"}
    NOL["CPU = 0%<br/>(Butuh t=1 untuk delta)"]
    HITUNG["Hitung CPU %:<br/>(Δ usage_usec / Δ time) × 100"]
    HITUNG_RAM["Hitung Memori %:<br/>(Efektif / Limit) × 100"]

    SIMPAN["Simpan state (t) sebagai baseline (t-1)"]
    SELESAI(["END: Return CPU%, RAM%"])

    START --> CARI
    CARI --> KETEMU
    KETEMU -->|Tidak| SELESAI_GAGAL
    KETEMU -->|Ya| BACA_CPU
    BACA_CPU --> BACA_RAM
    BACA_RAM --> KURANGI

    BACA_CPU -.-> GAGAL
    GAGAL -->|Ya| COBA_LAGI
    COBA_LAGI -->|Belum| TUNGGU
    TUNGGU --> BACA_CPU
    COBA_LAGI -->|Sudah| SEMUA_GAGAL
    SEMUA_GAGAL --> SELESAI_GAGAL

    KURANGI --> PERTAMA
    PERTAMA -->|Ya| NOL
    PERTAMA -->|Tidak| HITUNG
    NOL --> HITUNG_RAM
    HITUNG --> HITUNG_RAM
    HITUNG_RAM --> SIMPAN
    SIMPAN --> SELESAI
```

### Penyesuaian Frekuensi Pemantauan (Adaptive Sampling)

```mermaid
flowchart TD
    START(["START: Evaluasi Sampling Interval"])

    SIBUK{"Apakah Max CPU<br/>> 60%?"}
    SELESAI_SERING(["END: Interval = 10s (High Resolution)"])
    SELESAI_JARANG(["END: Interval = 30s (Low Overhead)"])

    START --> SIBUK
    SIBUK -->|Ya| SELESAI_SERING
    SIBUK -->|Tidak| SELESAI_JARANG
```
