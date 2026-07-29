# Flowchart — Monitor.get_stats() & Adaptive Sampling

> **Kode Sumber:** `framework/monitor.py` → class `Monitor`, fungsi `get_stats()` (baris 102–155) dan `get_adaptive_interval()` (baris 179–186)
> **Posisi di Diagram:** Layer 2 — Monitoring Engine
> **Kategori:** Tools / Data Acquisition (S1) + Inovasi Metode (Adaptive Sampling)

Membaca CPU dan Memory langsung dari cgroupfs v2 (bypass Docker REST API). Algoritma **Adaptive Sampling** mengubah interval polling berdasarkan beban.

```mermaid
flowchart TD
    START(["get_stats(container_name, container_id)"])

    FIND_CGROUP["_get_cgroup_path(container_id)<br/>Cari di:<br/>1. /sys/fs/cgroup/system.slice/docker-{id}.scope<br/>2. /sys/fs/cgroup/docker/{id}<br/>3. /sys/fs/cgroup/system.slice/docker.service/..."]
    
    CGROUP_FOUND{"Path<br/>ditemukan?"}
    STALE_RET["Return stale result:<br/>cpu=-1, mem=-1, stale=True<br/>(main loop akan skip shaping)"]

    RETRY_LOOP["Baca cgroupfs dengan retry<br/>attempt = 0..MONITOR_RETRY_COUNT"]

    READ_CPU["Baca cpu.stat:<br/>cari baris 'usage_usec'"]
    READ_MEM_CURRENT["Baca memory.current:<br/>mem_current = bytes"]
    READ_MEM_STAT["Baca memory.stat:<br/>cari 'inactive_file'<br/>(reclaimable page-cache)"]
    CALC_MEM["mem_usage = max(0,<br/>mem_current - inactive_file)"]
    READ_MEM_MAX["Baca memory.max"]
    MEM_MAX_CHECK{"Nilai = 'max'?"}
    USE_HOST_MEM["mem_limit = host_total_RAM"]
    USE_LIMIT["mem_limit = nilai integer"]

    READ_FAIL{"Gagal baca?"}
    RETRY{"Masih ada<br/>retry?"}
    RETRY_WAIT["Tunggu MONITOR_RETRY_DELAY_MS"]
    ALL_FAIL["Semua retry gagal"]

    HAS_PREV{"Ada prev_stats<br/>untuk container ini?"}
    FIRST_SAMPLE["cpu_percent = 0.0<br/>(sampel pertama)"]
    CALC_CPU["time_delta = now - prev_time<br/>usage_delta = (usage_usec - prev_usec) / 1,000,000<br/>cpu_percent = (usage_delta / time_delta) × 100"]
    CALC_MEM_PCT["mem_percent = (mem_usage / mem_limit) × 100"]

    SAVE["Simpan prev_stats:<br/>time, usage_usec"]

    RETURN(["Return:<br/>cpu_percent, mem_percent,<br/>mem_usage, mem_limit, stale=False"])

    START --> FIND_CGROUP
    FIND_CGROUP --> CGROUP_FOUND
    CGROUP_FOUND -->|Tidak| STALE_RET
    CGROUP_FOUND -->|Ya| RETRY_LOOP

    RETRY_LOOP --> READ_CPU
    READ_CPU --> READ_MEM_CURRENT
    READ_MEM_CURRENT --> READ_MEM_STAT
    READ_MEM_STAT --> CALC_MEM
    CALC_MEM --> READ_MEM_MAX
    READ_MEM_MAX --> MEM_MAX_CHECK
    MEM_MAX_CHECK -->|Ya| USE_HOST_MEM
    MEM_MAX_CHECK -->|Tidak| USE_LIMIT

    READ_CPU --> READ_FAIL
    READ_FAIL -->|Ya| RETRY
    RETRY -->|Ya| RETRY_WAIT
    RETRY_WAIT --> RETRY_LOOP
    RETRY -->|Tidak| ALL_FAIL
    ALL_FAIL --> STALE_RET

    USE_HOST_MEM --> HAS_PREV
    USE_LIMIT --> HAS_PREV
    HAS_PREV -->|Tidak| FIRST_SAMPLE
    HAS_PREV -->|Ya| CALC_CPU
    FIRST_SAMPLE --> CALC_MEM_PCT
    CALC_CPU --> CALC_MEM_PCT
    CALC_MEM_PCT --> SAVE
    SAVE --> RETURN
```

---

## Flowchart — Adaptive Sampling Interval

> **Kode Sumber:** `framework/monitor.py` → `get_adaptive_interval()` (baris 179–186)
> **Kategori:** Inovasi Metode (S2) — Optimasi overhead monitoring

```mermaid
flowchart TD
    INPUT(["get_adaptive_interval(max_cpu_seen)"])

    CHECK{"max_cpu_seen<br/>≥ SAMPLING_CPU_THRESHOLD<br/>(default: 60%)"}
    HIGH["Return SAMPLING_INTERVAL_HIGH<br/><b>10 detik</b><br/>(polling lebih sering saat beban tinggi)"]
    LOW["Return SAMPLING_INTERVAL_LOW<br/><b>30 detik</b><br/>(polling jarang saat beban rendah)"]

    INPUT --> CHECK
    CHECK -->|Ya, CPU tinggi| HIGH
    CHECK -->|Tidak, CPU rendah| LOW
```

### Penjelasan Inovasi Adaptive Sampling
Monitoring konvensional menggunakan interval tetap (misal selalu 5 detik). Ini boros overhead saat server idle. Pendekatan HECF menyesuaikan frekuensi sampling secara dinamis berdasarkan kondisi CPU terakhir — sehingga overhead monitoring turun secara otomatis saat beban rendah, dan responsivitas naik saat beban tinggi.

---

## Deskripsi Alur Berbasis Bisnis/Akademik

### Akuisisi Metrik Utilisasi

```mermaid
flowchart TD
    START(["Inisialisasi Akuisisi Metrik per Container"])

    CARI["Resolusi path cgroupfs<br/>untuk container target"]
    KETEMU{"Path<br/>Valid?"}
    TIDAK_BISA["Abort: Target Terminated /<br/>Cgroup Namespace Inaccessible"]

    BACA_CPU["Akuisisi nilai cpu.stat<br/>(usage_usec)"]
    BACA_RAM["Akuisisi nilai memory.current<br/>(RSS + Cache)"]
    KURANGI["Kalkulasi Memori Efektif:<br/>Reduksi page-cache yang reclaimable<br/>(inactive_file) dari total memori"]

    GAGAL{"I/O Error?"}
    COBA_LAGI{"Batas Retry<br/>Tercapai?"}
    TUNGGU["Backoff & Retry (Jitter Delay)"]
    SEMUA_GAGAL["Max Retries Exceeded"]

    PERTAMA{"Pengukuran<br/>Baseline (t=0)?"}
    NOL["Utilisasi CPU = 0%<br/>(Membutuhkan sampel t=1 untuk kalkulasi delta)"]
    HITUNG["Kalkulasi Utilisasi CPU:<br/>(Δ usage_usec / Δ time) × 100"]
    HITUNG_RAM["Kalkulasi Utilisasi Memori:<br/>(Memori Efektif / Limit Maksimal) × 100"]

    SIMPAN["Simpan state (usage_usec, time)<br/>sebagai baseline iterasi berikutnya"]
    HASIL(["Kembalikan Objek Metrik:<br/>Persentase CPU, Persentase RAM"])

    START --> CARI
    CARI --> KETEMU
    KETEMU -->|Tidak| TIDAK_BISA
    KETEMU -->|Ya| BACA_CPU
    BACA_CPU --> BACA_RAM
    BACA_RAM --> KURANGI

    BACA_CPU --> GAGAL
    GAGAL -->|Ya| COBA_LAGI
    COBA_LAGI -->|Ya| TUNGGU
    TUNGGU --> BACA_CPU
    COBA_LAGI -->|Tidak| SEMUA_GAGAL
    SEMUA_GAGAL --> TIDAK_BISA

    KURANGI --> PERTAMA
    PERTAMA -->|Ya| NOL
    PERTAMA -->|Tidak| HITUNG
    NOL --> HITUNG_RAM
    HITUNG --> HITUNG_RAM
    HITUNG_RAM --> SIMPAN
    SIMPAN --> HASIL
```

### Penyesuaian Frekuensi Pemantauan (Adaptive Sampling)

```mermaid
flowchart TD
    INPUT(["Evaluasi Interval Sampling"])

    SIBUK{"Indikasi Beban Tinggi?<br/>(Max CPU > 60%)"}
    SERING["Frekuensi Sampling: <b>Tinggi (10 detik)</b><br/>(Meningkatkan resolusi pengamatan pada trafik padat)"]
    JARANG["Frekuensi Sampling: <b>Rendah (30 detik)</b><br/>(Mereduksi overhead sistem pada saat idle)"]

    INPUT --> SIBUK
    SIBUK -->|Ya, Beban Puncak| SERING
    SIBUK -->|Tidak, Idle/Normal| JARANG
```
