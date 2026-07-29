# Diagram Tools — Infrastruktur Teknologi HECF

> **Kategori:** Tools / Engineering Support (S1)
> **Sumber:** `docker-compose.yml`, `Dockerfile`, `requirements.txt`

Diagram ini menunjukkan **tumpukan teknologi (technology stack)** yang digunakan HECF — Docker, Linux Kernel, Locust, HttpArena — dan bagaimana mereka terhubung secara infrastruktur. Ini BUKAN algoritma, melainkan *tools* yang menjadi wadah eksekusi algoritma.

```mermaid
flowchart TB
    subgraph INFRA["Infrastruktur & Tools (Kategori: Engineering Support)"]
        direction TB

        subgraph DOCKER_COMPOSE["docker-compose.yml — Orchestrasi Container"]
            HECF_SVC["<b>Service: hecf</b><br/>privileged: true<br/>pid: host<br/><i>HECF Engine</i>"]
            DASH_SVC["<b>Service: hecf-dashboard</b><br/>Gunicorn 1 worker × 2 threads<br/>Port 8092<br/><i>dashboard.py</i>"]
            BENCH_SVC["<b>Service: bench-json</b><br/>HttpArena<br/>Port 8000<br/><i>http-arena/main.py</i>"]
        end

        subgraph VOLUMES["Shared Volumes (File-based IPC)"]
            CSV["metrics.csv<br/><i>HECF → Dashboard</i>"]
            TARGETS["targets.json<br/><i>Dashboard ↔ HECF</i>"]
            PRIO["priority_map.json<br/><i>Dashboard ↔ HECF</i>"]
            DISC["discovered_containers.json<br/><i>HECF → Dashboard</i>"]
            STATUS["framework_status.json<br/><i>Dashboard → HECF</i>"]
        end

        subgraph KERNEL_API["Linux Kernel API (Read/Write)"]
            CGROUP["/sys/fs/cgroup/<br/>cpu.stat, memory.stat,<br/>cpu.max, memory.max,<br/>cgroup.freeze"]
            PROC["/proc/cpuinfo<br/>/proc/meminfo<br/>/proc/stat<br/>/proc/loadavg"]
            RAPL["/sys/class/powercap/<br/>intel-rapl energy_uj"]
            SOCK["/var/run/docker.sock<br/>Docker Daemon API"]
        end

        subgraph LOAD_GEN["Load Generation Tools"]
            LOCUST["🔧 Locust<br/><i>locustfiles/locustfile.py</i><br/>4 profil: Low/Med/High/Spike"]
        end

        HECF_SVC -->|"Write"| CSV
        HECF_SVC -->|"Read"| TARGETS
        HECF_SVC -->|"Read"| PRIO
        HECF_SVC -->|"Write"| DISC
        HECF_SVC -->|"Read"| STATUS

        DASH_SVC -->|"Read"| CSV
        DASH_SVC -->|"Read/Write"| TARGETS
        DASH_SVC -->|"Read/Write"| PRIO
        DASH_SVC -->|"Read"| DISC
        DASH_SVC -->|"Write"| STATUS

        HECF_SVC <-->|"docker.from_env()"| SOCK
        HECF_SVC <-->|"Direct Read/Write"| CGROUP
        HECF_SVC -->|"Read"| PROC
        HECF_SVC -->|"Read"| RAPL
        DASH_SVC -->|"Read (ro)"| PROC
        DASH_SVC -->|"Read (ro)"| SOCK

        LOCUST -->|"HTTP Requests"| BENCH_SVC
    end
```

## Pemetaan File → Infrastruktur

| File | Peran | Kategori |
|---|---|---|
| `docker-compose.yml` | Konfigurasi deployment 3 service | Infrastruktur |
| `Dockerfile` | Build image Python + dependencies | Infrastruktur |
| `requirements.txt` | numpy, docker, flask, gunicorn, locust | Infrastruktur |
| `dashboard.py` | Web UI visualisasi 5 metrik | Tools (S1) |
| `http-arena/main.py` | Benchmark workload (JSON/Static/DB) | Tools (S1) |
| `locustfiles/locustfile.py` | Generator beban lalu lintas | Tools (S1) |
| `targets.json`, `priority_map.json` | Shared state antar proses | Infrastruktur |
| `metrics.csv` | Data bridge engine → dashboard | Infrastruktur |

---

## Alur Logika Konseptual

```mermaid
flowchart TB
    subgraph INFRA["Technology Stack & Infrastructure Tools"]
        direction TB

        subgraph APPS["Docker Container Services"]
            MESIN["<b>HECF Engine</b><br/>Otak utama pengontrol (Privileged)"]
            LAYAR["<b>HECF Dashboard</b><br/>Web Interface (Gunicorn/Flask)"]
            BENCHMARK["<b>HttpArena Target</b><br/>Aplikasi beban uji coba"]
        end

        subgraph FILE["Inter-Process Communication (Shared Volumes)"]
            LAPORAN["Metrics Report (metrics.csv)"]
            DAFTAR["Target Configuration (targets.json)"]
            PRIORITAS["Priority Map (priority_map.json)"]
        end

        subgraph OS["Linux Kernel & Hardware APIs"]
            PENGATUR["cgroupfs Interface<br/>(CPU & RAM Quota I/O)"]
            INFO["sysfs & procfs<br/>(Topologi Hardware)"]
            LISTRIK["RAPL/Hwmon<br/>(Sensor Daya Silikon)"]
            DOCKER_API["Docker Daemon<br/>(Container Runtime API)"]
        end

        subgraph PENGUJI["Load Generation"]
            LOCUST["Locust Test Suite<br/>(Simulasi HTTP Traffic)"]
        end

        MESIN -->|"Write"| LAPORAN
        MESIN -->|"Read"| DAFTAR
        MESIN -->|"Read"| PRIORITAS

        LAYAR -->|"Read"| LAPORAN
        LAYAR -->|"Read/Write"| DAFTAR
        LAYAR -->|"Read/Write"| PRIORITAS

        MESIN <-->|"Query Container List"| DOCKER_API
        MESIN <-->|"Read/Write Quota"| PENGATUR
        MESIN -->|"Read Host Profile"| INFO
        MESIN -->|"Read Power Metrics"| LISTRIK

        LOCUST -->|"Inject HTTP Requests"| BENCHMARK
    end
```
