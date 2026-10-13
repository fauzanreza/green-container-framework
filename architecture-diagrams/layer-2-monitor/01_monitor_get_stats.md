# Flowchart — Monitor.get_stats() (Layer 2)

> **Kode Sumber:** `framework/monitor.py` → class `Monitor`, fungsi `get_stats()`, `_read_raw_stats()`, dan `get_adaptive_interval()` (baris 19–186)
> **Posisi di Diagram:** Layer 2 — Monitoring Engine → Direct cgroupfs v2 Read & Adaptive Polling
> **Kategori:** 🌟 INOVASI ALGORITMA (S2)

Algoritma pembacaan telemetri kernel secara langsung tanpa perantara Docker REST API. Membaca `cpu.stat` (akumulasi mikrodetik pemrosesan CPU) dan `memory.current` dikurangi `inactive_file` dari `memory.stat` untuk mengecualikan page cache kernel yang dapat direklamasi. Dilengkapi mekanisme retry (`MONITOR_RETRY_COUNT=1`, jeda 100ms) dan penanda `stale: True` agar main control loop tidak melakukan pemotongan kuota saat kontainer mati.

```mermaid
flowchart TD
    START(["get_stats(container_name, container_id)"])

    RESOLVE["Resolusi Path cgroupfs v2:<br/>1. /sys/fs/cgroup/system.slice/docker-{id}.scope<br/>2. /sys/fs/cgroup/docker/{id}<br/>3. /sys/fs/cgroup/system.slice/docker.service/docker-{id}.scope"]
    PATH_FOUND{"Path valid?"}
    STALE_PATH(["Return _stale_result():<br/>{cpu_percent: -1.0, mem_percent: -1.0, stale: True}"])

    RETRY_LOOP["Loop Pembacaan Raw Stats:<br/>attempt = 0 s.d. MONITOR_RETRY_COUNT (1+1=2)"]

    READ_CPU["1. Buka cpu.stat → parse baris 'usage_usec'"]
    READ_MEM_CURR["2. Buka memory.current → mem_current"]
    READ_MEM_STAT["3. Buka memory.stat → parse 'inactive_file'"]
    CALC_MEM_ACTUAL["mem_usage = max(0, mem_current - inactive_file)<br/>(Memori Efektif tanpa reclaimable cache)"]

    READ_MEM_MAX["4. Buka memory.max:<br/>Jika 'max' / error → pakai _host_mem_bytes (dari /proc/meminfo)<br/>Selain itu → int(val)"]

    READ_ERR{"OSError saat baca<br/>cpu.stat / memory?"}
    RETRY_CHECK{"attempt &lt;<br/>MONITOR_RETRY_COUNT?"}
    SLEEP_RETRY["time.sleep(MONITOR_RETRY_DELAY_MS / 1000.0)<br/>(Default: 100ms)"]
    STALE_FAIL(["Log warning: Semua read gagal<br/>Return _stale_result()"])

    CHECK_PREV{"Container ada di<br/>_prev_stats?"}
    FIRST_SAMPLE["cpu_percent = 0.0<br/>(Belum ada delta waktu t_0)"]

    CALC_DELTAS["time_delta = now - prev['time']<br/>usage_delta = (usage_usec - prev['usage_usec']) / 1,000,000.0<br/>cpu_percent = (usage_delta / time_delta) × 100.0"]

    CALC_MEM_PCT["mem_percent = (mem_usage / mem_limit) × 100.0"]

    SAVE_STATE["_prev_stats[name] = {'time': now, 'usage_usec': usage_usec}"]

    RETURN(["Return {name, cpu_percent, mem_percent,<br/>mem_usage, mem_limit, stale: False}"])

    START --> RESOLVE
    RESOLVE --> PATH_FOUND
    PATH_FOUND -->|Tidak| STALE_PATH
    PATH_FOUND -->|Ya| RETRY_LOOP

    RETRY_LOOP --> READ_CPU
    READ_CPU --> READ_ERR
    READ_ERR -->|Ya| RETRY_CHECK
    RETRY_CHECK -->|Ya| SLEEP_RETRY
    SLEEP_RETRY --> RETRY_LOOP
    RETRY_CHECK -->|Tidak| STALE_FAIL

    READ_ERR -->|Tidak| READ_MEM_CURR
    READ_MEM_CURR --> READ_MEM_STAT
    READ_MEM_STAT --> CALC_MEM_ACTUAL
    CALC_MEM_ACTUAL --> READ_MEM_MAX
    READ_MEM_MAX --> CHECK_PREV

    CHECK_PREV -->|Tidak| FIRST_SAMPLE
    CHECK_PREV -->|Ya| CALC_DELTAS

    FIRST_SAMPLE --> CALC_MEM_PCT
    CALC_DELTAS --> CALC_MEM_PCT
    CALC_MEM_PCT --> SAVE_STATE
    SAVE_STATE --> RETURN
```

---

## Alur Logika Konseptual

### 1. Akuisisi Metrik Kernel Langsung

```mermaid
flowchart TD
    START(["START: Akuisisi Telemetri Kontainer"])

    CARI_PATH["Temukan direktori cgroup v2 kontainer pada hierarki unified"]
    VALID{"Direktori Ditemukan?"}
    ABORT_STALE(["END: Return Status Stale (Abaikan Siklus Ini)"])

    BACA_STAT["Baca cpu.stat (akumulasi pemakaian CPU dalam mikrodetik)"]
    BACA_RAM["Baca memory.current dan memory.stat"]
    KURANGI_CACHE["Kalkulasi RAM Riil:<br/>Penggunaan RAM = memory.current − inactive_file"]

    GAGAL_BACA{"I/O Error?"}
    COBA_ULANG{"Masih Ada Kuota Retry?<br/>(MONITOR_RETRY_COUNT=1)"}
    JEDA_ULANG["Jeda 100ms dan Coba Kembali"]
    TOTAL_GAGAL["Semua Percobaan Gagal → Return Stale"]

    CEK_BASELINE{"Apakah Ada Baseline Sampel Sebelumnya?"}
    CPU_NOL["Set CPU% = 0.0 (Titik Referensi Awal)"]
    HITUNG_CPU["Hitung CPU% dari Laju Pertambahan Mikrodetik:<br/>CPU% = (Δ usage_usec ÷ 1.000.000 ÷ Δ waktu) × 100"]

    HITUNG_RAM["Hitung RAM% Terhadap Limit (memory.max atau Total Host RAM)"]
    SIMPAN_STATE["Simpan Timestamp & Penggunaan untuk Perhitungan Siklus Berikutnya"]

    SELESAI(["END: Return Metrik {CPU%, RAM%, Stale: False}"])

    START --> CARI_PATH
    CARI_PATH --> VALID
    VALID -->|Tidak| ABORT_STALE
    VALID -->|Ya| BACA_STAT

    BACA_STAT --> GAGAL_BACA
    GAGAL_BACA -->|Ya| COBA_ULANG
    COBA_ULANG -->|Ya| JEDA_ULANG
    JEDA_ULANG --> BACA_STAT
    COBA_ULANG -->|Tidak| TOTAL_GAGAL
    TOTAL_GAGAL --> ABORT_STALE

    GAGAL_BACA -->|Tidak| BACA_RAM
    BACA_RAM --> KURANGI_CACHE
    KURANGI_CACHE --> CEK_BASELINE

    CEK_BASELINE -->|Tidak| CPU_NOL
    CEK_BASELINE -->|Ya| HITUNG_CPU

    CPU_NOL --> HITUNG_RAM
    HITUNG_CPU --> HITUNG_RAM
    HITUNG_RAM --> SIMPAN_STATE
    SIMPAN_STATE --> SELESAI
```

---

### 2. Penyesuaian Interval Pemantauan Adaptif (`get_adaptive_interval`)

```mermaid
flowchart TD
    START_INTERVAL(["get_adaptive_interval(cpu_percent)"])

    CEK_BEBAN{"cpu_percent ≥ 60.0%<br/>(SAMPLING_CPU_THRESHOLD)?"}
    INTERVAL_10S(["Return 10s (SAMPLING_INTERVAL_HIGH)<br/>Resolusi tinggi saat sistem sibuk"])
    INTERVAL_30S(["Return 30s (SAMPLING_INTERVAL_LOW)<br/>Minim overhead saat sistem tenang"])

    START_INTERVAL --> CEK_BEBAN
    CEK_BEBAN -->|Ya| INTERVAL_10S
    CEK_BEBAN -->|Tidak| INTERVAL_30S
```
