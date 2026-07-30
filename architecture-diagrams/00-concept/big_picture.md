# Diagram Konsep Besar — HECF MAPE-K Closed-Loop Control

> **Kategori:** Inovasi Algoritma (S2)
> **Sumber:** `framework/main.py` (kontrol loop utama yang menyatukan semua layer)

Diagram ini menunjukkan bagaimana HECF beroperasi sebagai **sistem kontrol tertutup (Closed-Loop / MAPE-K)**: Monitor → Analyze → Plan → Execute → Kembali ke Monitor.

```mermaid
flowchart TB
    subgraph HOST["HOST OS — Linux Kernel ≥5.10, cgroups v2"]
        direction TB

        subgraph MAPE["HECF ENGINE — Closed-Loop MAPE-K Control System"]
            direction TB

            L1["<b>Layer 1: Environment Profiler</b><br/><i>profiler.py, hardware_sensor.py</i><br/>───────────────<br/>• Hardware Detection<br/>• Container Discovery & Tagging<br/>• Cold-Start Fallback Policy"]

            L2["<b>Layer 2: Monitoring Engine</b><br/><i>monitor.py</i><br/>───────────────<br/>• cgroupfs v2 Direct Read<br/>• Adaptive Sampling<br/>• Event-Driven Idle Detection"]

            L3["<b>Layer 3: Hybrid Control Engine</b><br/><i>guardrail.py, tier_detector.py, predictor.py</i><br/>───────────────<br/>• 3A: Guardrail (3-of-5 + PSI)<br/>• 3B: Tier Detector (P95/P50)<br/>• 3C: EMA Predictor (α=0.2)"]

            L4["<b>Layer 4: Adaptive Resource Shaping</b><br/><i>shaper.py, micro_freezer.py</i><br/>───────────────<br/>• cpu.max / memory.max Write<br/>• Micro-Freezing (cgroup.freeze)<br/>• TCP Backlog Buffering"]

            SUP["<b>Supplementary Services</b><br/><i>energy.py, overhead_tracker.py, modes.py</i><br/>───────────────<br/>• Hybrid Energy Estimator<br/>• Overhead Tracker<br/>• Mode Selector"]

            L1 -->|"Profil Host +<br/>Daftar Container"| L2
            L2 -->|"CPU%, MEM%<br/>per container"| L3
            L3 -->|"Keputusan:<br/>Tier + Guardrail + EMA"| L4
            L4 -->|"Feedback:<br/>max_cpu_seen"| L2
            L3 --> SUP
            L4 --> SUP
        end

        KERNEL[("Linux Kernel<br/>cgroups v2<br/>───────<br/>cpu.max<br/>memory.max<br/>cgroup.freeze")]
        DOCKER[("Docker Daemon<br/>docker.sock")]

        L1 <-->|"docker.from_env()"| DOCKER
        L2 <-->|"Read:<br/>cpu.stat, memory.stat"| KERNEL
        L4 -->|"Write:<br/>cpu.max, memory.max,<br/>cgroup.freeze"| KERNEL
    end

    LOCUST["🔧 LOCUST<br/>Load Generator<br/><i>locustfiles/locustfile.py</i>"]
    TARGET["📦 TARGET CONTAINERS<br/>HttpArena<br/><i>http-arena/main.py</i>"]
    DASH["📊 HECF DASHBOARD<br/>Flask / Gunicorn<br/><i>dashboard.py</i>"]

    LOCUST -->|"HTTP Traffic"| TARGET
    TARGET <-->|"Managed by"| DOCKER
    SUP -->|"metrics.csv"| DASH
```

## Penjelasan Alur MAPE-K

| Fase MAPE-K | Layer | Fungsi |
| --- | --- | --- |
| **Monitor** | Layer 1 + Layer 2 | Deteksi hardware, discover container, baca metrik CPU/MEM dari cgroupfs |
| **Analyze** | Layer 3B + 3C | Klasifikasi volatilitas (P95/P50), prediksi tren (EMA) |
| **Plan** | Layer 3A | Guardrail menentukan apakah perlu intervensi darurat |
| **Execute** | Layer 4 | Tulis parameter cgroups (cpu.max, memory.max, cgroup.freeze) |
| **Knowledge** | Supplementary | Estimasi energi, overhead tracking, mode selector |

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

            L3["<b>Phase 3: Policy Analysis & Prediction</b><br/>───────────────<br/>• Evaluasi Overload Guardrail<br/>• Klasifikasi Volatilitas (P95/P50)<br/>• Prakiraan Utilisasi Masa Depan (EMA)"]

            L4["<b>Phase 4: Resource Allocation Execution</b><br/>───────────────<br/>• Modifikasi Quota (CPU & Memory)<br/>• Transisi Micro-Freeze saat Idle<br/>  (Optimasi efisiensi tanpa terminasi)"]

            SUP["<b>Supplementary Knowledge Base</b><br/>───────────────<br/>• Kalkulasi Estimasi Energi<br/>• Pencatatan HECF Overhead"]

            L1 -->|"Container Inventory<br/>& Host Profile"| L2
            L2 -->|"CPU & Memory<br/>Utilization Data"| L3
            L3 -->|"Control Decisions:<br/>Hold / Throttle / Freeze"| L4
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
