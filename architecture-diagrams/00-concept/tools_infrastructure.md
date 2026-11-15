# Infrastruktur dan Alat Pendukung HECF

> **Kategori:** Tools & Engineering Support (S1)
> **Sumber kode:** `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `http-arena/`, `locustfiles/`, `experiments/run_experiment.py`

Jika `big_picture.md` dan `main_control_loop.md` membahas cara HECF berpikir dan mengambil keputusan, dokumen ini membahas **ekosistem tempat algoritma tersebut dijalankan, dipantau, dan diuji**. Komponen-komponen yang digambarkan di sini bukanlah bagian dari logika kontrol cerdasnya, melainkan pondasi infrastruktur—mulai dari sistem operasi Linux, pengelola container Docker, mekanisme pertukaran berkas, antarmuka web, hingga simulator lalu lintas pengguna—yang memungkinkan HECF bekerja di lingkungan nyata sekaligus diuji secara ilmiah dan berulang.

---

## 1. Alur Logika Konseptual Infrastruktur

Diagram di bawah memetakan empat kelompok komponen infrastruktur dari atas ke bawah: perangkat keras, alat pengujian, layanan utama, dan ruang pertukaran laporan serta pengaturan.

```mermaid
%%{init: {'flowchart': {'wrappingWidth': 250, 'padding': 18, 'nodeSpacing': 36, 'rankSpacing': 48, 'curve': 'linear'}}}%%
flowchart TB
    subgraph OS["Sistem Operasi &amp; Perangkat Keras Server"]
        direction TB
        DOCKER_API["<b>Docker Runtime</b><br/>Pengelola container &amp;<br/>daftar layanan aktif"]:::sys
        KERNEL_API["<b>Linux Kernel Interface</b><br/>Pembaca pemakaian &amp;<br/>pengatur jatah CPU/RAM"]:::sys
        HW_API["<b>System Info &amp; Power Sensors</b><br/>Informasi spesifikasi server<br/>&amp; sensor listrik prosesor"]:::sys
    end

    subgraph PENGUJI["Pengujian Beban (Load Generation)"]
        direction TB
        RUNNER["<b>Experiment Runner</b><br/>Otomasi skenario uji &amp;<br/>pengarsipan data hasil"]:::test
        LOCUST["<b>Locust Load Simulator</b><br/>Simulasi trafik web: rendah,<br/>sedang, tinggi, lonjakan"]:::test
    end

    subgraph APPS["Layanan Utama dalam Docker"]
        direction TB
        MESIN["<b>HECF Engine</b><br/>Otak pengatur otomatis<br/>siklus kontrol tertutup"]:::app
        LAYAR["<b>HECF Dashboard</b><br/>Antarmuka web pemantau<br/>grafik &amp; pengaturan"]:::app
        BENCHMARK["<b>Benchmark Target App</b><br/>Aplikasi web uji coba<br/>penerima beban trafik"]:::target
    end

    subgraph FILE["Pertukaran Data (Shared Volumes)"]
        direction TB
        LAPORAN["<b>Telemetry &amp; Discovery</b><br/>Tabel catatan energi &amp;<br/>daftar container aktif"]:::vol
        ATURAN["<b>Control &amp; Policy Config</b><br/>Daftar target, prioritas,<br/>&amp; tombol aktif/jeda"]:::vol
    end

    DOCKER_API <-->|Daftar container| MESIN
    KERNEL_API <-->|Baca &amp; atur jatah| MESIN
    HW_API -->|Profil &amp; daya listrik| MESIN
    DOCKER_API -.->|Pantau daftar aktif| LAYAR

    MESIN -->|Tulis laporan| LAPORAN
    MESIN -->|Baca aturan| ATURAN
    LAYAR -->|Tampilkan data| LAPORAN
    LAYAR <-->|Baca &amp; ubah| ATURAN

    RUNNER -->|Jalankan skenario| LOCUST
    RUNNER -->|Pilih mode uji| MESIN
    LOCUST -->|Permintaan web| BENCHMARK

    style OS fill:#f8fafc,stroke:#475569,stroke-width:2px,color:#1e293b
    style PENGUJI fill:#fffaf0,stroke:#b7791f,stroke-width:2px,color:#744210
    style APPS fill:#eff6ff,stroke:#2b6cb0,stroke-width:2px,color:#1a365d
    style FILE fill:#faf5ff,stroke:#6b46c1,stroke-width:2px,color:#44337a

    classDef sys fill:#edf2f7,stroke:#4a5568,stroke-width:1.5px,color:#1a202c;
    classDef test fill:#fefcbf,stroke:#b7791f,stroke-width:1.5px,color:#1a202c;
    classDef app fill:#dbeafe,stroke:#2b6cb0,stroke-width:1.5px,color:#1a202c;
    classDef target fill:#c6f6d5,stroke:#2f855a,stroke-width:1.5px,color:#1a202c;
    classDef vol fill:#e9d8fd,stroke:#6b46c1,stroke-width:1.5px,color:#1a202c;
```

*Gambar 1. Ekosistem infrastruktur, layanan container, pertukaran data, dan alat uji HECF.*

---

## 2. Penjelasan Analitis Hubungan Infrastruktur dengan Algoritma

Seluruh ekosistem pengujian HECF dijalankan di atas satu server Linux menggunakan orkestrasi Docker. Pemilihan pendekatan berbasis container ini memiliki alasan praktis sekaligus metodologis: setiap layanan terisolasi satu sama lain dengan batas memori masing-masing, sehingga seluruh sistem dapat dibongkar-pasang ulang dengan konfigurasi yang identik untuk menjamin eksperimen dapat direproduksi secara konsisten.

**Bagaimana HECF Engine berinteraksi langsung dengan mesin host.** Meskipun berjalan di dalam container terpisah agar rapi dan mudah disebarkan, **HECF Engine** harus mampu melihat dan mengendalikan container lain pada server yang sama. Oleh karena itu, container Engine diberi hak akses khusus terhadap sistem host sehingga ia dapat berkomunikasi dengan tiga fasilitas utama server: **Docker Runtime** untuk mengetahui daftar layanan yang sedang hidup, **Linux Kernel Interface** untuk membaca pemakaian sumber daya aktual sekaligus mengirimkan batas jatah baru atau perintah pembekuan, serta **sensor informasi sistem dan daya prosesor** agar kalkulasi energinya bertumpu pada spesifikasi fisik dan pembacaan daya nyata (bila tersedia).

**Mengapa Dashboard dan Engine berkomunikasi lewat berkas bersama (*Shared Volumes*).** Di sisi antarmuka pengguna, **HECF Dashboard** berperan sebagai panel kontrol web bagi peneliti maupun operator. Alih-alih menghubungkan Dashboard dan Engine melalui jalur jaringan API yang saling mengunci (*tight coupling*), arsitektur ini memilih pola pertukaran data melalui **berkas bersama**. Engine menuliskan catatan energi, metrik CPU/RAM, dan daftar container terdeteksi ke berkas laporan, sedangkan Dashboard membacanya untuk disajikan dalam bentuk grafik pemantauan. Sebaliknya, ketika operator memilih aplikasi target, mengubah tingkat prioritas layanan, atau menekan tombol jeda melalui Dashboard, perubahan tersebut disimpan ke berkas konfigurasi bersama untuk dibaca Engine pada siklus patroli berikutnya. Desain terpisah (*decoupled*) ini memberikan ketahanan operasional yang tinggi: seandainya tampilan Dashboard mengalami gangguan atau dimuat ulang, HECF Engine tetap berjalan menstabilkan server tanpa terhenti.

**Bagaimana efektivitas algoritma dibuktikan secara terukur.** Untuk membuktikan bahwa algoritma di balik HECF mampu menghemat konsumsi listrik tanpa merusak kecepatan respons aplikasi, sistem membutuhkan objek uji dan beban lalu lintas yang terkendali. Peran objek uji dijalankan oleh **Benchmark Target App**—sebuah server web ringan yang melayani beberapa jenis beban kerja—sementara **Locust Load Simulator** bertindak sebagai ribuan pengguna tiruan yang menembakkan permintaan web dalam berbagai pola intensitas (beban rendah, sedang, tinggi, hingga lonjakan tiba-tiba). Seluruh rangkaian eksperimen tersebut diorkestrasi oleh **Experiment Runner** yang mengganti-ganti mode operasi HECF (sebagai pembanding dengan kondisi standar) serta mengarsipkan hasil pengukuran secara otomatis untuk dianalisis dalam tesis.

---

## 3. Detail Teknis Infrastruktur

Diagram teknis berikut merinci jalur berkas sistem operasi, konfigurasi `docker-compose.yml`, port layanan, dan nama berkas IPC aktual di repositori.

```mermaid
%%{init: {'flowchart': {'wrappingWidth': 250, 'padding': 18, 'nodeSpacing': 36, 'rankSpacing': 48, 'curve': 'linear'}}}%%
flowchart TB
    subgraph KAPI["Linux Kernel &amp; Host Mounts"]
        direction TB
        SOCK["/var/run/docker.sock<br/>(Docker Daemon API)"]:::sys
        CG["/sys/fs/cgroup/<br/>cpu.stat, cpu.max, memory.*,<br/>cgroup.freeze, cgroup.events"]:::sys
        PROC["/proc/ (cpuinfo, meminfo,<br/>stat, loadavg, uptime)"]:::sys
        RAPL["/sys/class/powercap/ &amp; hwmon/<br/>(energy_uj / energy1_input)"]:::sys
    end

    subgraph DC["docker-compose.yml Services"]
        direction TB
        HECF["<b>hecf</b> (python -m framework.main)<br/>privileged: true, pid: host, 128M"]:::app
        DSH["<b>hecf-dashboard</b> (dashboard:app)<br/>Gunicorn 1w×2t, :8092, mem 256M"]:::app
        BENCH["<b>bench-json</b> (http-arena/main.py)<br/>FastAPI + Uvicorn :8000, low"]:::target
    end

    subgraph VOL["Shared Volumes (File-based IPC)"]
        direction TB
        CSV["metrics.csv &amp;<br/>discovered_containers.json"]:::vol
        CFG["targets.json, priority_map.json,<br/>framework_status.json"]:::vol
    end

    subgraph EXP["Experiment Harness"]
        direction TB
        RUN["experiments/run_experiment.py"]:::test
        LOC["Locust (locust-master)<br/>locustfiles/locustfile.py"]:::test
    end

    SOCK <-->|docker.from_env| HECF
    CG <-->|R/W| HECF
    PROC -->|R ro| HECF
    RAPL -->|R privileged| HECF
    SOCK -.->|R ro list| DSH
    PROC -.->|R ro htop| DSH

    HECF -->|W| CSV
    HECF -->|R| CFG
    DSH -->|R| CSV
    DSH <-->|R/W| CFG

    RUN -->|docker exec| LOC
    RUN -->|HECF_MODE + compose up| HECF
    LOC -->|HTTP| BENCH

    style KAPI fill:#f8fafc,stroke:#475569,stroke-width:2px,color:#1e293b
    style DC fill:#eff6ff,stroke:#2b6cb0,stroke-width:2px,color:#1a365d
    style VOL fill:#faf5ff,stroke:#6b46c1,stroke-width:2px,color:#44337a
    style EXP fill:#fffaf0,stroke:#b7791f,stroke-width:2px,color:#744210

    classDef sys fill:#edf2f7,stroke:#4a5568,stroke-width:1.5px,color:#1a202c;
    classDef test fill:#fefcbf,stroke:#b7791f,stroke-width:1.5px,color:#1a202c;
    classDef app fill:#dbeafe,stroke:#2b6cb0,stroke-width:1.5px,color:#1a202c;
    classDef target fill:#c6f6d5,stroke:#2f855a,stroke-width:1.5px,color:#1a202c;
    classDef vol fill:#e9d8fd,stroke:#6b46c1,stroke-width:1.5px,color:#1a202c;
```

> **Catatan Deployment:** `experiments/run_experiment.py` menjalankan `docker compose` dari direktori kerja container `locust-master` (`../portfolio-app` pada lingkungan server uji), sedangkan `docker-compose.yml` di repositori ini mendefinisikan tiga service inti: `hecf`, `hecf-dashboard`, dan `bench-json`.

### Pemetaan File ke Infrastruktur

| File / Path | Peran Teknis | Kategori |
| --- | --- | --- |
| `docker-compose.yml` | Orkestrasi tiga service (`hecf` batas memori 128M, `hecf-dashboard` batas 256M pada port 8092, dan `bench-json` pada port 8000) beserta volume mount host. | Infrastruktur |
| `Dockerfile` | Image berbasis Python 3.10-slim beserta dependensi sistem dan perintah eksekusi utama `python -m framework.main`. | Infrastruktur |
| `requirements.txt` | Daftar pustaka Python (`docker`, `numpy`, `requests`, `pytest`, `locust`, `Flask`, `gunicorn`). | Infrastruktur |
| `dashboard.py` | Aplikasi web Flask (dijalankan dengan Gunicorn 1 worker × 2 threads) untuk visualisasi metrik, panel *Managed Containers*, dan pemantau host. | Tools (S1) |
| `http-arena/main.py` | Layanan web uji berbasis FastAPI + Uvicorn yang menyediakan endpoint JSON (`/`), berkas statis (`/static/dummy.txt`), dan endpoint basis data (`/db`). | Tools (S1) |
| `locustfiles/locustfile.py` | Skrip simulator beban lalu lintas HTTP dengan dukungan variasi profil beban dan jenis workload (`json`, `static`, `db`, `all`). | Tools (S1) |
| `experiments/run_experiment.py` | Pengendali skenario eksperimen yang memicu pengujian lintas mode, workload, intensitas, dan replikasi, lalu mengarsipkan hasilnya. | Metodologi |
| `targets.json`, `priority_map.json`, `framework_status.json` | Berkas konfigurasi bersama yang ditulis oleh Dashboard UI dan dibaca secara berkala oleh HECF Engine. | Infrastruktur (IPC) |
| `discovered_containers.json` | Snapshot daftar container non-excluded yang ditulis oleh Engine dan dibaca Dashboard dalam mode *read-only*. | Infrastruktur (IPC) |
| `metrics.csv` | Jembatan data telemetri 16 kolom yang ditulis atomik oleh Engine untuk dibaca Dashboard maupun analisis pasca-eksperimen. | Infrastruktur (IPC) |
