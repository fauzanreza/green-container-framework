# Panduan Pengujian A sampai Z (HECF Testing Guide)

Dokumen ini adalah panduan lengkap khusus untuk mengeksekusi pengujian (testing) pada sistem HECF. Pengujian terbagi menjadi jalur Antarmuka Web (UI) dan Terminal Server/Docker.

> **⚠️ Catatan Penting:** Semua perintah terminal di bawah ini dijalankan dari folder `~/portfolio-app` di server (`srv-laptop`). Akses server via SSH: `ssh srv-laptop`, lalu `cd ~/portfolio-app`.

---

## 📑 Daftar Isi
1. [Cara Membaca Panduan Ini (Alur Pengujian)](#1-cara-membaca-panduan-ini-alur-pengujian)
2. [Langkah 0: Persiapan Infrastruktur Server](#2-langkah-0-persiapan-infrastruktur-server)
3. [Jalur A: Mengambil Data Tesis (72 Skenario Otomatis)](#3-jalur-a-mengambil-data-tesis-72-skenario-otomatis)
4. [Jalur B: Demo Sidang (Pembuktian Visual)](#4-jalur-b-demo-sidang-pembuktian-visual)
5. [Eksperimen Manual & Cheat Sheet](#5-eksperimen-manual--cheat-sheet)
6. [Referensi Cepat: Daftar Service & Port](#6-referensi-cepat-daftar-service--port)
7. [Utilitas Tambahan & Troubleshooting](#7-utilitas-tambahan--troubleshooting)

---

## 1. Cara Membaca Panduan Ini (Alur Pengujian)

Pilih jalur pengujian sesuai dengan tujuan kamu saat ini. Jangan mencampuradukkan antara pengambilan data dengan demo sidang, karena tujuannya berbeda.

- **Ingin Mengambil Data untuk Laporan Tesis?**
  Maka kamu akan menjalankan skrip otomatis yang memakan waktu berjam-jam (72 skenario).
  **Alur:** Lakukan **[Langkah 0](#2-langkah-0-persiapan-infrastruktur-server)** $\rightarrow$ Langsung ke **[Jalur A](#3-jalur-a-mengambil-data-tesis-72-skenario-otomatis)**.

- **Sedang Bimbingan / Sidang dengan Dosen?**
  Gunakan demo *live* berdurasi pendek (1-2 menit) untuk membuktikan sistem berfungsi.
  **Alur:** Lakukan **[Langkah 0](#2-langkah-0-persiapan-infrastruktur-server)** $\rightarrow$ Langsung ke **[Jalur B](#4-jalur-b-demo-sidang-pembuktian-visual)**.

- **Ingin Menguji Sendiri / Eksplorasi Manual?**
  Kamu bisa mengecek resource, membatasi CPU/RAM secara manual, atau menembak beban sendiri.
  **Alur:** Lakukan **[Langkah 0](#2-langkah-0-persiapan-infrastruktur-server)** $\rightarrow$ Langsung ke **[Bagian 5](#5-eksperimen-manual--cheat-sheet)**.

---

## 2. Langkah 0: Persiapan Infrastruktur Server
*Langkah ini WAJIB dilakukan sebelum memulai pengujian apa pun.*

File `docker-compose.yml` berada di dalam folder `/home/arzafri3/portfolio-app`.
1. **Login ke Server via SSH:**
   ```bash
   ssh srv-laptop
   cd ~/portfolio-app
   ```
2. **Jalankan Layanan Pengujian (HECF, Dashboard, Target, Locust):**
   ```bash
   docker compose up -d hecf hecf-dashboard bench-json locust-master
   ```
   *(Bila ingin menyalakan SEMUA portfolio, gunakan `docker compose up -d`)*
3. **Pastikan Container Berjalan:**
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   ```

---

## 3. Jalur A: Mengambil Data Tesis (72 Skenario Otomatis)
Gunakan skrip otomatis ini untuk mengeksekusi 72 kombinasi (HECF On/Off, jenis beban, intensitas, repetisi). Output terminal Locust sudah disembunyikan ke dalam log di folder `results/` agar tidak memenuhi layar.

### 🎯 Kriteria Kesuksesan Data (Sesuai PRD)
1. **SLA (Metrik 4):** Latensi Web Persentil 95 (P95) tetap **di bawah 500ms**.
2. **Hemat Energi (Metrik 3):** Total energi berkurang **10% - 20%** dari baseline.
3. **Overhead (Metrik 5):** CPU & RAM HECF **<5%** kapasitas server.
4. **Stabilitas:** Server tidak *hang/OOM*.

### Cara Eksekusi
1. **Jalankan Eksperimen (Tinggalkan hingga selesai):**
   ```bash
   python3 ../green-container-framework/experiments/run_experiment.py
   ```
2. **Analisa & Rekap Hasil ke CSV Akhir:**
   ```bash
   python3 ../green-container-framework/experiments/analyze_results.py
   ```

---

## 4. Jalur B: Demo Sidang (Pembuktian Visual)
Jangan jalankan 72 skenario saat presentasi! Gunakan skenario cepat ini untuk pembuktian ke dosen.

### Skenario 1: Demo "Full Terminal" (Membuktikan Validitas Kernel)
> **⚡ PENTING:** Buka 3 terminal berdampingan. Jalankan Tab 2 & 3 **DULUAN**, baru eksekusi Locust di Tab 1.

* **Tab 2 (Pantau log & energi):** `tail -f ../green-container-framework/metrics.csv`
* **Tab 3 (Pantau CPU Docker):** `docker stats bench-json hecf`
* **Tab 1 (Tembak Beban selama 60s):**
  ```bash
  docker exec locust-master locust -f /mnt/locust/locustfile.py --headless -u 100 -r 10 --run-time 60s --host http://bench-json:8000
  ```

### Skenario 2: Demo "Dashboard Visual" (Membuktikan MAPE-K Loop)
1. Buka HECF Dashboard: `http://[IP-Server]:8092`
2. Buka Locust Web UI: `http://[IP-Server]:8089`
3. Di Locust, atur Users: `100`, Spawn: `10`, Host: `http://bench-json:8000`, lalu klik **Start Swarming**.
4. Pindah ke HECF Dashboard, perlihatkan ke dosen bagaimana Tier berubah (Normal $\rightarrow$ Aggressive) dan perlindungan server bekerja secara otomatis saat diserang beban.

### Skenario 3: Demo "Whitelist Dinamis" (Fleksibilitas)
1. Buka HECF Dashboard: `http://[IP-Server]:8092` $\rightarrow$ panel **"Managed Containers"**.
2. Klik *card* container (misal hijau berubah abu-abu) untuk mengeluarkan (*exclude*) container tersebut secara *real-time* tanpa me-restart server.

### Skenario 4: Menjawab Pertanyaan Jebakan Keamanan (Safenet)
Jika ditanya: *"Bagaimana jika di-hack atau nge-hang?"*
1. Buka folder `framework/security/` di VSCode.
2. Jelaskan adanya **11 Fitur Safenet (Safety-Net)** (seperti *Watchdog Auto-Thaw*, *Anti-EDoS*) yang berjalan di *background* untuk meng-*override* MAPE-K jika terjadi anomali ekstrem.

---

## 5. Eksperimen Manual & Cheat Sheet

### A. Cara Mengukur 5 Metrik Secara Manual
* **CPU & RAM:** `docker stats bench-json` atau pantau via Dashboard (`8092`).
* **Konsumsi Energi:** `tail -f ../green-container-framework/metrics.csv` atau Dashboard. Sensor native hardware: `cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`
* **SLA (Latensi):** Hasil akhir Locust (Persentil 95th).
* **Overhead HECF:** `docker stats hecf hecf-dashboard` (Syarat: Maks 128MB/256MB RAM).

### B. Cheat Sheet Cekikan Resource & Micro-Freeze (cgroups manual)
Gunakan ini untuk membajak resource secara manual (seperti yang dilakukan HECF).
* **Limit 1 GB RAM & 0.5 CPU:** 
  `docker update --memory="1g" --memory-swap="1g" --cpus="0.5" bench-json`
* **Lepas Semua Limit (Unlimited):**
  `docker update --cpus="0.0" --memory="0" --memory-swap="0" bench-json`
* **Micro-Freeze / Pembekuan (CPU 0%):**
  - Bekukan: `docker pause bench-json`
  - Cairkan: `docker unpause bench-json`

---

## 6. Referensi Cepat: Daftar Service & Port

| Service | Container Name | Port Eksternal | Port Internal |
|---|---|---|---|
| **HECF Engine** | `hecf` | — | — |
| **HECF Dashboard** | `hecf-dashboard` | `8092` | `8092` |
| **Bench-JSON** | `bench-json` | `8000` | `8000` |
| **Locust Master** | `locust-master` | `8089` | `8089` |
| Portfolio Web | `portfolio-web` | `80` | `80` |
| MusicaHub | `musicahub-app` / `nginx-musicahub` | `8083` | `3000` / `80` |
| ShopyVibe | `shopyvibe-app` / `nginx-shopyvibe` | `8091` | `3000` / `80` |
| ... *(Aplikasi web lainnya)* | *beragam* | `8081` - `8086` | `80` |

---

## 7. Utilitas Tambahan & Troubleshooting
* **Lihat log HECF Engine/Dashboard secara live:**
  ```bash
  docker compose logs -f hecf
  ```
* **Restart hanya service HECF (tanpa merusak container portofolio):**
  ```bash
  docker compose restart hecf hecf-dashboard
  ```
* **Menyalakan / Mematikan HECF secara *On-the-Fly*:**
  ```bash
  echo '{"is_active": true}' > ../green-container-framework/framework_status.json
  ```
* **Cek Kapasitas Total Server:**
  `lscpu` (Cek CPU core) dan `free -m` (Cek RAM)
