# Diagram Tools — Infrastruktur Teknologi HECF

> **Kategori:** Tools / Engineering Support (S1)
> **Sumber:** `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `http-arena/`, `experiments/run_experiment.py`

Diagram ini menunjukkan **tumpukan teknologi (technology stack)** yang digunakan HECF — Docker, Linux Kernel, Locust, HttpArena — dan bagaimana mereka terhubung secara infrastruktur. Ini BUKAN algoritma, melainkan *tools* yang menjadi wadah eksekusi algoritma.

```mermaid
flowchart LR
    subgraph KERNEL_API["Linux Kernel API (Read/Write)"]
        direction TB
        SOCK["/var/run/docker.sock<br/>(Docker Daemon API)"]
        CGROUP["/sys/fs/cgroup/<br/>(cpu.stat, cpu.max, memory.*,<br/>cgroup.freeze, cgroup.events)"]
        PROC["/proc/<br/>(cpuinfo, meminfo, stat,<br/>loadavg, uptime, sys/net)"]
        RAPL["/sys/class/powercap/ + /sys/class/hwmon/<br/>(energy_uj / energy1_input)<br/>terlihat via privileged: true"]
    end

    subgraph DOCKER_COMPOSE["docker-compose.yml — Orkestrasi Container"]
        direction TB
        HECF_SVC["<b>Service: hecf</b><br/><i>python -m framework.main</i><br/>(privileged: true, pid: host, mem 128M)"]
        DASH_SVC["<b>Service: hecf-dashboard</b><br/><i>dashboard.py</i><br/>(Gunicorn 1 worker × 2 threads, Port 8092, mem 256M)"]
        BENCH_SVC["<b>Service: bench-json</b><br/><i>http-arena/main.py</i> (FastAPI + Uvicorn)<br/>(Port 8000, label hecf.priority=low)"]
    end

    subgraph VOLUMES["Shared Volumes (File-based IPC)"]
        direction TB
        CSV["metrics.csv"]
        TARGETS["targets.json"]
        PRIO["priority_map.json"]
        DISC["discovered_containers.json"]
        STATUS["framework_status.json"]
    end

    subgraph LOAD_GEN["Load Generation Tools"]
        LOCUST["🔧 Locust (container locust-master)<br/><i>locustfile.py</i><br/>4 profil: Low/Med/High/Spike"]
        RUNNER["experiments/run_experiment.py<br/>2 kondisi × 3 workload × 4 intensitas × 3 replikasi"]
    end

    %% Hubungan Kernel -> Docker Services
    SOCK <-->|"docker.from_env()"| HECF_SVC
    CGROUP <-->|"R/W"| HECF_SVC
    PROC -->|"R"| HECF_SVC
    RAPL -->|"R"| HECF_SVC

    SOCK -.->|"R (ro) — live container list"| DASH_SVC
    PROC -.->|"R (ro) — htop panel"| DASH_SVC

    %% Hubungan Docker Services -> Shared Volumes
    HECF_SVC -->|"W"| CSV
    HECF_SVC -->|"R"| TARGETS
    HECF_SVC -->|"R"| PRIO
    HECF_SVC -->|"W"| DISC
    HECF_SVC -->|"R"| STATUS

    DASH_SVC -->|"R"| CSV
    DASH_SVC <-->|"R/W"| TARGETS
    DASH_SVC <-->|"R/W"| PRIO
    DASH_SVC -->|"R (fallback)"| DISC
    DASH_SVC <-->|"R/W (toggle)"| STATUS

    %% Hubungan Load Generator -> Target
    RUNNER -->|"docker exec locust-master"| LOCUST
    RUNNER -->|"HECF_MODE + docker compose up -d hecf"| HECF_SVC
    LOCUST -->|"HTTP Requests"| BENCH_SVC
```

> **Catatan:** `experiments/run_experiment.py` menjalankan `docker compose` dari direktori `../portfolio-app` (compose utama server), tempat container `locust-master` berada. `docker-compose.yml` di repo ini hanya mendefinisikan `hecf`, `hecf-dashboard`, dan `bench-json`.

## Pemetaan File → Infrastruktur

| File | Peran | Kategori |
| --- | --- | --- |
| `docker-compose.yml` | Konfigurasi deployment 3 service (`hecf`, `hecf-dashboard`, `bench-json`) | Infrastruktur |
| `Dockerfile` | Build image Python 3.10-slim + dependencies, `CMD python -m framework.main` | Infrastruktur |
| `requirements.txt` | docker, numpy, requests, pytest, locust, Flask, gunicorn | Infrastruktur |
| `dashboard.py` | Web UI visualisasi 5 metrik + Managed Containers + htop panel | Tools (S1) |
| `http-arena/main.py` | Benchmark workload FastAPI (`/` JSON, `/static/dummy.txt`, `/db`) | Tools (S1) |
| `locustfiles/locustfile.py` | Generator beban lalu lintas (`WORKLOAD_TYPE` = json/static/db/all) | Tools (S1) |
| `experiments/run_experiment.py` | Orkestrasi matriks 72 run + arsip hasil | Metodologi |
| `targets.json`, `priority_map.json`, `framework_status.json` | Shared state antar proses (UI → engine) | Infrastruktur |
| `discovered_containers.json` | Snapshot discovery (engine → UI, fallback) | Infrastruktur |
| `metrics.csv` | Data bridge engine → dashboard / eksperimen | Infrastruktur |

---

## Alur Logika Konseptual

```mermaid
flowchart LR
    subgraph OS["Linux Kernel & Hardware APIs"]
        direction TB
        DOCKER_API["Docker Daemon<br/>(Container Runtime API)"]
        PENGATUR["cgroupfs Interface<br/>(CPU & RAM Quota I/O, Freeze)"]
        INFO["sysfs & procfs<br/>(Topologi Hardware)"]
        LISTRIK["RAPL/Hwmon<br/>(Sensor Energi Silikon)"]
    end

    subgraph APPS["Docker Container Services"]
        direction TB
        MESIN["<b>HECF Engine</b><br/>Otak utama pengontrol"]
        LAYAR["<b>HECF Dashboard</b><br/>Web Interface"]
        BENCHMARK["<b>HttpArena Target</b><br/>Aplikasi beban uji coba"]
    end

    subgraph FILE["Inter-Process Communication (Shared Volumes)"]
        direction TB
        LAPORAN["Metrics Report<br/>(metrics.csv)"]
        DAFTAR["Target Configuration<br/>(targets.json)"]
        PRIORITAS["Priority Map<br/>(priority_map.json)"]
        STATUS["Engine Toggle<br/>(framework_status.json)"]
        TEMUAN["Discovery Snapshot<br/>(discovered_containers.json)"]
    end

    subgraph PENGUJI["Load Generation"]
        LOCUST["Locust Test Suite<br/>(Simulasi HTTP Traffic)"]
    end

    DOCKER_API <-->|"Query"| MESIN
    PENGATUR <-->|"R/W Quota"| MESIN
    INFO -->|"Read Profile"| MESIN
    LISTRIK -->|"Read Energy"| MESIN

    MESIN -->|"W"| LAPORAN
    MESIN -->|"R"| DAFTAR
    MESIN -->|"R"| PRIORITAS
    MESIN -->|"R"| STATUS
    MESIN -->|"W"| TEMUAN

    DOCKER_API -->|"Live list (ro)"| LAYAR
    LAYAR -->|"R"| LAPORAN
    LAYAR <-->|"R/W"| DAFTAR
    LAYAR <-->|"R/W"| PRIORITAS
    LAYAR <-->|"R/W"| STATUS
    LAYAR -->|"R"| TEMUAN

    LOCUST -->|"Inject HTTP Requests"| BENCHMARK
```

---

## 🔌 Hubungan Infrastruktur dengan Algoritma (HECF Engine)

Jika `big_picture.md` dan `main_control_loop.md` membahas otak dari algoritma (isi dari folder `framework/`), maka diagram infrastruktur di atas menunjukkan **rumah dan lingkungan** di mana algoritma tersebut hidup.

1. **HECF Engine (`framework/main.py`)**: Ini adalah blok utama yang menjalankan seluruh *codingan* algoritma yang dijelaskan di file sebelumnya. Diinjeksi dalam bentuk _container_ mandiri lewat `docker-compose.yml` dengan `privileged: true` dan `pid: host` agar bisa menulis cgroups host dan membaca `/proc` host.
2. **Dashboard (`dashboard.py`)**: Algoritma HECF Engine tidak memiliki tampilan grafis. Oleh karena itu, *engine* menulis hasil hitungannya ke file `metrics.csv`. Dashboard membaca ~200 baris terakhir file tersebut dan menampilkannya di browser. Dashboard juga menulis `targets.json` (whitelist), `priority_map.json` (prioritas), dan `framework_status.json` (pause/resume engine). Daftar container di panel *Managed Containers* diambil langsung dari Docker socket (read-only), dengan `discovered_containers.json` sebagai fallback.
3. **Pemberi Beban (`locustfile.py`)**: Untuk membuktikan apakah algoritma di Layer 3 dan Layer 4 berfungsi dengan baik menahan beban, sistem membutuhkan simulasi _traffic_. Locust yang mengambil peran ini, dijalankan oleh `run_experiment.py` lewat `docker exec locust-master`.
4. **Target (`http-arena/main.py`)**: Kontainer aplikasi FastAPI (dummy) yang berperan sebagai server web dengan 3 endpoint (JSON, Static, Async DB). Algoritma HECF Engine (*Layer 2*) memonitor kontainer ini, sementara Locust menembaknya dengan _traffic_.
