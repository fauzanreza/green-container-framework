# Diagram Konsep Besar — HECF MAPE-K Closed-Loop Control

> **Kategori:** Inovasi Algoritma (S2)
> **Sumber:** `framework/main.py` (kontrol loop utama yang menyatukan semua layer, fungsi `main()` baris 191–503)

Diagram ini menunjukkan bagaimana HECF beroperasi sebagai **sistem kontrol tertutup (Closed-Loop / MAPE-K)**: Monitor → Analyze → Plan → Execute → Kembali ke Monitor.

```mermaid
flowchart TB
    subgraph HOST["HOST OS — Linux Kernel ≥5.10, cgroups v2"]
        direction TB

        subgraph MAPE["HECF ENGINE — Closed-Loop MAPE-K Control System"]
            direction TB

            L1["<b>Layer 1: Environment Profiler</b><br/><i>profiler.py, hardware_sensor.py</i><br/>───────────────<br/>• Hardware Detection + RAPL/hwmon Sensor<br/>• Container Discovery, Auto-Exclude & Tagging<br/>• Whitelist targets.json + priority_map.json"]

            L2["<b>Layer 2: Monitoring Engine</b><br/><i>monitor.py</i><br/>───────────────<br/>• cgroupfs v2 Direct Read<br/>• memory.current − inactive_file<br/>• Adaptive Sampling (10s / 30s)"]

            L3["<b>Layer 3: Hybrid Control Engine</b><br/><i>guardrail.py, tier_detector.py, predictor.py</i><br/>───────────────<br/>• 3A: Guardrail (3-of-5 + EMA pre-warning + Derivative + PSI)<br/>• 3B: Tier Detector (P95/P50, window 120, hysteresis 3, cold-start Tier 2)<br/>• 3C: EMA Predictor (α=0.2 tetap)<br/>• Keputusan mode di main.py (+ PREEMPTIVE_SCALEUP)"]

            L4["<b>Layer 4: Adaptive Resource Shaping</b><br/><i>shaper.py, security/micro_freezer.py, security/tcp_backlog_manager.py</i><br/>───────────────<br/>• cpu.max / memory.max / memory.high / memory.swap.max<br/>• Micro-Freezing (cgroup.freeze + cgroup.events idle)<br/>• memory.reclaim + TCP Backlog Pre-flight"]

            SUP["<b>Supplementary Services</b><br/><i>energy.py, overhead_tracker.py, modes.py</i><br/>───────────────<br/>• Hybrid Energy Estimator<br/>• Overhead Tracker<br/>• Mode Selector"]

            L1 -->|"Profil Host +<br/>Daftar Container"| L2
            L2 -->|"CPU%, MEM%<br/>per container"| L3
            L3 -->|"Keputusan:<br/>action + quota + mem_ratio"| L4
            L4 -->|"Feedback:<br/>max_cpu_seen + action eskalasi"| L2
            L3 --> SUP
            L4 --> SUP
        end

        KERNEL[("Linux Kernel<br/>cgroups v2<br/>───────<br/>cpu.max, memory.max<br/>memory.high, memory.swap.max<br/>cgroup.freeze, memory.reclaim")]
        DOCKER[("Docker Daemon<br/>docker.sock")]
        SHARED[("Shared State Files<br/>targets.json, priority_map.json<br/>framework_status.json<br/>discovered_containers.json")]

        L1 <-->|"docker.from_env()"| DOCKER
        L1 <-->|"R: targets, priority<br/>W: discovered"| SHARED
        L2 <-->|"Read:<br/>cpu.stat, memory.stat"| KERNEL
        L4 -->|"Write:<br/>cpu.max, memory.*,<br/>cgroup.freeze"| KERNEL
    end

    LOCUST["🔧 LOCUST<br/>Load Generator<br/><i>locustfiles/locustfile.py</i>"]
    TARGET["📦 TARGET CONTAINERS<br/>HttpArena (FastAPI)<br/><i>http-arena/main.py</i>"]
    DASH["📊 HECF DASHBOARD<br/>Flask / Gunicorn :8092<br/><i>dashboard.py</i>"]

    LOCUST -->|"HTTP Traffic"| TARGET
    TARGET <-->|"Managed by"| DOCKER
    SUP -->|"metrics.csv"| DASH
    DASH <-->|"R/W via UI"| SHARED
```

## Penjelasan Alur MAPE-K

| Fase MAPE-K | Layer | Fungsi |
| --- | --- | --- |
| **Monitor** | Layer 1 + Layer 2 | Deteksi hardware, discover container, baca metrik CPU/MEM dari cgroupfs |
| **Analyze** | Layer 3B + 3C | Klasifikasi volatilitas (P95/P50), prediksi tren (EMA + d(EMA)/dt) |
| **Plan** | Layer 3A + logika mode `main.py` | Guardrail 3-of-5, lalu pemilihan `action`/`quota` (GUARDRAIL, PREEMPTIVE_SCALEUP, AGGRESSIVE, BALANCED, SOFT) |
| **Execute** | Layer 4 | Tulis parameter cgroups (cpu.max, memory.max/high/swap.max, cgroup.freeze, memory.reclaim) |
| **Knowledge** | Supplementary + shared state | Estimasi energi, overhead tracking, mode selector, sliding window/EMA state, `metrics.csv` |

---

## Alur Logika Konseptual

```mermaid
flowchart TB
    subgraph HOST["Server Host"]
        direction TB

        subgraph MAPE["HECF Engine — Closed-Loop Control Cycle"]
            direction TB

            L1["<b>Phase 1: Environment Discovery & Profiling</b><br/>───────────────<br/>• Verifikasi Host CPU & Memory capacity<br/>• Identifikasi Active Containers<br/>• Terapkan Service Priority Mapping"]

            L2["<b>Phase 2: Distributed Metric Monitoring</b><br/>───────────────<br/>• Akuisisi utilisasi dari cgroups<br/>• Terapkan Adaptive Sampling<br/>  (Interval rapat saat beban tinggi)"]

            L3["<b>Phase 3: Policy Analysis & Prediction</b><br/>───────────────<br/>• Evaluasi Overload & Derivative Pre-emption<br/>• Klasifikasi Volatilitas (P95/P50 Single-Window)<br/>• Prakiraan Utilisasi Masa Depan (EMA α=0.2)<br/>• Pre-emptive Scale-Up saat burst"]

            L4["<b>Phase 4: Resource Allocation Execution</b><br/>───────────────<br/>• Modifikasi Quota (CPU & Memory)<br/>• Transisi Micro-Freeze saat Idle<br/>  (Optimasi efisiensi tanpa terminasi)"]

            SUP["<b>Supplementary Knowledge Base</b><br/>───────────────<br/>• Kalkulasi Estimasi Energi<br/>• Pencatatan HECF Overhead"]

            L1 -->|"Container Inventory<br/>& Host Profile"| L2
            L2 -->|"CPU & Memory<br/>Utilization Data"| L3
            L3 -->|"Control Decisions:<br/>Release / Throttle / Freeze"| L4
            L4 -->|"State Feedback:<br/>Latest utilization metrics"| L2
        end

        KERNEL[("Linux OS<br/>Resource Manager (cgroups)")]
        DOCKER[("Docker Daemon<br/>Container Runtime API")]

        L1 <-->|"Fetch Container State"| DOCKER
        L2 <-->|"Direct I/O Metric Read"| KERNEL
        L4 -->|"Write Control Parameters"| KERNEL
    end

    LOCUST["🔧 Load Generator (Locust)<br/>(Mensimulasikan Web Traffic)"]
    TARGET["📦 Target Container<br/>(Aplikasi dalam pengujian)"]
    DASH["📊 Monitoring Dashboard<br/>(Visualisasi Telemetri)"]

    LOCUST -->|"Injeksi HTTP Requests"| TARGET
    TARGET <-->|"Dikelola oleh"| DOCKER
    SUP -->|"Agregasi Data Telemetri"| DASH
```

---

## 🗂️ Pemetaan Konsep ke File Kode (Daftar Isi Algoritma)

File ini berfungsi sebagai **Master Daftar Isi**. Berikut adalah penjelasan bagaimana setiap blok konseptual di atas diwujudkan dalam file *codingan* (Python) yang ada di dalam folder `framework/`:

### 1. File Utama (Orkestrator)
*   **`framework/main.py`**
    *   **Peran:** Jantung dari sistem HECF. File ini berisi loop utama `main()` (baris 191–503) dengan loop per-container (baris 271–478) yang terus menerus mengeksekusi siklus MAPE-K untuk setiap kontainer.
    *   **Interaksi:** Memanggil fungsi-fungsi dari Layer 1, 2, 3, dan 4 secara berurutan, serta berisi **logika keputusan mode** (baris 357–410) yang menerjemahkan output Layer 3 menjadi `action`, `quota`, dan `mem_ratio`.

### 2. Layer 1: Environment Profiler (Monitor - Awal)
*   **`framework/profiler.py`**: `profile_host()` membaca `/proc/cpuinfo` dan `/proc/meminfo`, menghitung `P_idle`/`P_max`, memverifikasi mount `/proc` host, dan mengecek `nf_conntrack_max`. `discover_containers()` mencari kontainer via Docker API, menerapkan auto-exclude (port kritis/daftar EXCLUDED), auto-priority (port HTTP/DNS dan pola nama infra jaringan), membaca `priority_map.json` + `targets.json`, serta menulis `discovered_containers.json`.
*   **`framework/hardware_sensor.py`**: Class `PowerSensor` yang mendeteksi Intel RAPL (`energy_uj`) atau AMD/hwmon (`energy1_input`) dan mengonversi ΔJoule/Δt menjadi Watt.

### 3. Layer 2: Monitoring Engine (Monitor - Lanjutan)
*   **`framework/monitor.py`**: Membaca langsung _virtual file_ cgroups (`cpu.stat`, `memory.current`, `memory.stat`, `memory.max`) untuk mendapatkan % CPU dan % memori efektif tiap kontainer (dengan 1× retry dan penanda *stale*). Juga menyediakan `get_adaptive_interval()` (≥ 60% → 10s, selain itu 30s).

### 4. Layer 3: Hybrid Control Engine (Analyze & Plan)
Layer ini adalah otak kecerdasan (S2) dari HECF yang terdiri dari 3 algoritma yang saling bekerjasama:
*   **`framework/tier_detector.py` (3B)**: Menganalisa data dari Layer 2 dengan satu sliding window 120 sampel, menghitung `spike_ratio = P95/P50`, lalu menentukan Tier 1 (spiky), Tier 2, atau Tier 3 (tenang) dengan hysteresis simetris 3 sampel. Selama < 10 sampel, selalu mengembalikan Tier 2 (cold-start fallback).
*   **`framework/predictor.py` (3C)**: Menggunakan EMA dengan alpha tetap 0.2 untuk memprediksi CPU dan menghitung kecepatan tren naiknya (`d(EMA)/dt`).
*   **`framework/guardrail.py` (3A)**: Menerima CPU, RAM, serta EMA dan turunannya dari `predictor.py` (hanya di mode `full_hecf`). EMA ≥ 75% menurunkan threshold CPU dari 80% ke 75%; turunan > 5.0 dengan EMA > 50% dihitung sebagai sampel overload. Guardrail aktif jika ≥ 3 dari 5 sampel terakhir overload. Sinyal PSI hanya dicatat sebagai konfirmasi.

### 5. Layer 4: Adaptive Resource Shaping (Execute)
*   **`framework/shaper.py`**: Menerima `quota` dan `mem_ratio` dari `main.py`, lalu menulis `cpu.max` (dengan floor 0.2 core dan validasi read-back) serta — khusus non-priority di bawah GUARDRAIL/AGGRESSIVE — `memory.max`, `memory.high` (0.85×), dan `memory.swap.max` (berbasis zram). Juga menyediakan `reclaim_memory()` untuk `memory.reclaim`.
*   **`framework/security/micro_freezer.py`**: Mengevaluasi kontainer non-priority; bila idle ≥ 0.8s (berdasarkan timestamp aktivitas terakhir + `cgroup.events populated`) dan tidak ada koneksi terbuka (eBPF/proc), menulis `cgroup.freeze = 1`. `main.py` lalu memanggil `reclaim_memory()`.
*   **`framework/security/tcp_backlog_manager.py`**: Pre-flight cold-start yang memastikan `somaxconn` cukup menampung antrean selama freeze.

### 6. Supplementary (Knowledge / Pendukung)
*   **`framework/energy.py`**: Estimasi daya (Watt) dan energi (kWh) per kontainer — mode hardware (apportionment) atau software (model linear Jarus et al.).
*   **`framework/overhead_tracker.py`**: Mengukur CPU dan RAM container HECF sendiri dari cgroup-nya.
*   **`framework/modes.py`**: Menyimpan pilihan mode eksperimen (`default_docker`, `static_cap`, `reactive_only`, `full_hecf`).

*Untuk melihat alur loop yang menyambungkan semua file ini, silakan lanjut ke file `main_control_loop.md`.*

---

## 📖 Glosarium (Keterangan Istilah Teknis)

Untuk mempermudah pemahaman arsitektur, berikut adalah penjelasan singkat mengenai istilah-istilah teknis yang digunakan:

*   **MAPE-K (Monitor, Analyze, Plan, Execute, Knowledge)**: Model arsitektur sistem otonom yang secara terus-menerus memantau kondisi, menganalisis data, merencanakan tindakan, dan mengeksekusi penyesuaian secara terotomatisasi.
*   **cgroups v2**: Fitur manajemen sumber daya pada kernel Linux yang berfungsi untuk mengukur dan membatasi alokasi komputasi (seperti CPU dan Memori) untuk setiap *container*.
*   **PSI (Pressure Stall Information)**: Metrik bawaan kernel Linux yang memberikan indikasi langsung mengenai tingkat saturasi atau kepadatan antrean pemrosesan sistem.
*   **P95 / P50 (Percentile)**: Metrik statistik distribusi beban. P50 (Median) merepresentasikan beban normal, sedangkan P95 mengindikasikan lonjakan beban ekstrem (*spiky workload*).
*   **EMA (Exponential Moving Average)**: Algoritma peramalan (*forecasting*) yang memberikan bobot lebih besar pada data terbaru untuk memprediksi tren pemakaian sumber daya secara *real-time*.
*   **RAPL (Running Average Power Limit)**: Antarmuka sensor energi prosesor Intel (`/sys/class/powercap/intel-rapl`). Pada AMD, padanannya dibaca dari `hwmon` (`energy1_input`). Keduanya memberi penghitung energi (Joule) yang dikonversi menjadi Watt.
