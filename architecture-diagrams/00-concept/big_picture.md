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
|---|---|---|
| **Monitor** | Layer 1 + Layer 2 | Deteksi hardware, discover container, baca metrik CPU/MEM dari cgroupfs |
| **Analyze** | Layer 3B + 3C | Klasifikasi volatilitas (P95/P50), prediksi tren (EMA) |
| **Plan** | Layer 3A | Guardrail menentukan apakah perlu intervensi darurat |
| **Execute** | Layer 4 | Tulis parameter cgroups (cpu.max, memory.max, cgroup.freeze) |
| **Knowledge** | Supplementary | Estimasi energi, overhead tracking, mode selector |

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TB
    subgraph HOST["Node / Server Tuan Rumah (Host)"]
        direction TB

        subgraph MAPE["HECF Engine — Siklus Kontrol Otomatis (Closed-Loop)"]
            direction TB

            L1["<b>Fase 1: Penemuan & Profiling Lingkungan</b><br/>───────────────<br/>• Verifikasi kapasitas CPU dan memori Host<br/>• Identifikasi container yang sedang berjalan<br/>• Terapkan pemetaan prioritas layanan"]

            L2["<b>Fase 2: Pemantauan Metrik Terdistribusi</b><br/>───────────────<br/>• Akuisisi metrik utilisasi dari cgroups<br/>• Terapkan frekuensi sampling adaptif<br/>  (Interval rapat saat beban tinggi, renggang saat idle)"]

            L3["<b>Fase 3: Analisis Kebijakan & Prediksi</b><br/>───────────────<br/>• Evaluasi kondisi kelebihan beban (Overload Guardrail)<br/>• Klasifikasi volatilitas beban (P95/P50)<br/>• Prakiraan tren penggunaan ke depan (EMA)"]

            L4["<b>Fase 4: Eksekusi Alokasi Sumber Daya</b><br/>───────────────<br/>• Modifikasi batas atas (quota) CPU dan Memori<br/>• Transisi ke status Micro-Freeze saat kondisi idle<br/>  (Optimasi efisiensi energi tanpa terminasi proses)"]

            SUP["<b>Layanan Pendukung (Supplementary)</b><br/>───────────────<br/>• Kalkulasi estimasi konsumsi energi<br/>• Pencatatan metrik overhead kerangka kerja"]

            L1 -->|"Daftar container<br/>& profil host"| L2
            L2 -->|"Data utilisasi<br/>CPU & Memori"| L3
            L3 -->|"Keputusan kontrol:<br/>hemat / normal / darurat"| L4
            L4 -->|"Umpan balik (Feedback):<br/>kondisi terbaru"| L2
        end

        KERNEL[("Sistem Operasi Linux<br/>Manajer Sumber Daya (cgroups)")]
        DOCKER[("Docker Daemon<br/>Manajer Container")]

        L1 <-->|"Pengambilan data state container"| DOCKER
        L2 <-->|"Pembacaan langsung I/O metrik kernel"| KERNEL
        L4 -->|"Penulisan parameter kontrol batas baru"| KERNEL
    end

    LOCUST["🔧 Load Generator (Locust)<br/>(Mensimulasikan trafik sistem)"]
    TARGET["📦 Target Container<br/>(Aplikasi yang dievaluasi)"]
    DASH["📊 Dashboard Pemantauan<br/>(Visualisasi telemetri)"]

    LOCUST -->|"Injeksi trafik HTTP"| TARGET
    TARGET <-->|"Dikelola oleh"| DOCKER
    SUP -->|"Agregasi data metrik"| DASH
```
