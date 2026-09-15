# Panduan Pengujian A sampai Z (HECF Testing Guide)

Dokumen ini adalah panduan lengkap khusus untuk mengeksekusi pengujian (testing) pada sistem HECF. Pengujian terbagi menjadi jalur Antarmuka Web (UI) dan Terminal Server/Docker.

> **⚠️ Catatan Penting:** Semua perintah terminal di bawah ini dijalankan dari folder `~/portfolio-app` di server (`srv-laptop`). Akses server via SSH: `ssh srv-laptop`, lalu `cd ~/portfolio-app`.

---

## 📋 Referensi Cepat: Daftar Service & Port

| Service | Container Name | Port Eksternal | Port Internal | Keterangan |
|---|---|---|---|---|
| **HECF Engine** | `hecf` | — (tanpa port) | — | Framework utama (privileged) |
| **HECF Dashboard** | `hecf-dashboard` | `8092` | `8092` | Dashboard monitoring |
| **Bench-JSON** | `bench-json` | `8000` | `8000` | Target percobaan beban |
| **Locust Master** | `locust-master` | `8089` | `8089` | Penembak beban (Load Tester) |
| Portfolio Web | `portfolio-web` | `80` | `80` | Landing page portfolio |
| Signature App | `nginx-signature` | `8081` | `80` | Aplikasi tanda tangan |
| Siperah App | `nginx-siperah` | `8082` | `80` | Aplikasi Siperah |
| MusicaHub | `musicahub-app` | `3000` | `3000` | Aplikasi MusicaHub (Next.js) |
| MusicaHub (Nginx) | `nginx-musicahub` | `8083` | `80` | Reverse proxy MusicaHub |
| Quran Horizon | `nginx-quran-horizon` | `8084` | `80` | Reverse proxy Quran Horizon |
| Wedding Invite | `nginx-wedding-invite` | `8085` | `80` | Reverse proxy Wedding Invite |
| Time Saver | `nginx-time-saver` | `8086` | `80` | Reverse proxy Time Saver |
| ShopyVibe | `shopyvibe-app` | `3002` | `3000` | Aplikasi ShopyVibe (Next.js) |
| ShopyVibe (Nginx) | `nginx-shopyvibe` | `8091` | `80` | Reverse proxy ShopyVibe |
| Beszel Hub | `beszel-hub` | `8090` | `8090` | Server monitoring |
| MySQL | `mysql-db` | `3306` | `3306` | Database |

**Akses dari browser:** `http://[IP-Server]:[Port Eksternal]`

---

## 🎯 Skenario Khusus: Demo untuk Dosen Pembimbing
Jika kamu sedang bimbingan atau sidang dan diminta membuktikan bahwa HECF benar-benar berfungsi, gunakan skenario presentasi ini:

### Skenario 1: Demo "Full Terminal" (Membuktikan Validitas Teknis & Kernel)
Skenario ini disukai dosen teknis karena membuktikan kamu tidak sekadar membuat UI, melainkan benar-benar berinteraksi dengan kernel Linux dan Docker daemon.

> **⚡ PENTING:** Ketiga tab SSH **harus berjalan bersamaan (simultan)!** Jalankan Tab 2 & 3 **TERLEBIH DAHULU**, baru tembak di Tab 1. Jika kamu menjalankan Tab 3 (`docker stats`) setelah Locust selesai, CPU sudah kembali idle (0%) dan demo tidak terlihat efeknya.

1. Buka **3 tab Terminal (SSH)** secara berdampingan, masing-masing `ssh srv-laptop` lalu `cd ~/portfolio-app`.
2. **Tab 2 (Pantau cgroups & HECF logs) — JALANKAN DULUAN:**
   ```bash
   tail -f ../green-container-framework/metrics.csv
   ```
3. **Tab 3 (Pantau Real-time Docker Stats) — JALANKAN DULUAN:**
   ```bash
   docker stats bench-json hecf
   ```
4. **Tab 1 (Jalankan Beban) — TEMBAK SETELAH Tab 2 & 3 siap:**
   ```bash
   docker exec locust-master locust -f /mnt/locust/locustfile.py --headless -u 100 -r 10 --run-time 60s --host http://bench-json:8000
   ```
   *(Selama 60 detik, Tab 2 akan menunjukkan metrik HECF berubah & Tab 3 akan menunjukkan CPU `bench-json` melonjak)*

### Skenario 2: Demo "Dashboard Visual" (Membuktikan MAPE-K Loop & Metrik)
Skenario ini sangat bagus untuk presentasi awal agar dosen langsung paham konsep *closed-loop* dari HECF.
1. Buka **Dashboard HECF** di browser: `http://[IP-Server]:8092`
2. Buka **Locust Web UI** di tab browser sebelahnya: `http://[IP-Server]:8089`
3. Di Locust, isi:
   - **Number of users:** `100`
   - **Spawn rate:** `10`
   - **Host:** `http://bench-json:8000`
4. Klik **Start Swarming** di Locust.
5. Buka kembali Dashboard HECF. Tunjukkan kepada dosen bagaimana grafik CPU melonjak, status Tier berubah menjadi "Aggressive", indikator energi (Watt) berubah, dan bagaimana sistem HECF secara otomatis melindungi server dari *crash* (OOM/CPU Lockup).

### Skenario 3: Demo "Whitelist Dinamis" (Manajemen Target On-the-Fly)
Untuk membuktikan bahwa sistem ini fleksibel dan aman untuk *production*, tunjukkan fitur isolasi target:
1. Buka **Dashboard HECF**: `http://[IP-Server]:8092`
2. Arahkan dosen ke panel **"Managed Containers"**.
3. Perlihatkan bahwa kamu bisa mengeluarkan (exclude) suatu container dari pantauan HECF hanya dengan mengekliknya (kartu berubah abu-abu), dan menambahkannya kembali (kartu hijau) tanpa me-*restart* HECF ataupun container tersebut.
4. Ini membuktikan fitur *Dynamic Shared State* (`targets.json`) bekerja sempurna.

### Skenario 4: Menjawab Pertanyaan Jebakan Keamanan (Safenet / Appendix A)
Jika penguji bertanya: *"Bagaimana jika sistemmu malah dimanfaatkan peretas untuk melumpuhkan server (EDoS)?"* atau *"Bagaimana kalau micro-freeze nge-hang?"*
1. Jangan panik. Buka terminal atau VSCode.
2. Tunjukkan folder `framework/security/`.
3. Jelaskan bahwa kamu sudah mengimplementasikan **11 Fitur Safenet (Safety-Net)** di latar belakang (seperti *Watchdog Auto-Thaw*, *Anti-EDoS Logic*, *Zombie Healer*, dll) yang akan meng-*override* MAPE-K jika terdeteksi anomali. Fitur ini sengaja di-*hidden* dari metrik utama agar fokus tesis pada efisiensi energi tetap terjaga.

---

## 1. Persiapan Infrastruktur Server
File `docker-compose.yml` berada di dalam folder `/home/arzafri3/portfolio-app`. Semua path relatif (seperti `../green-container-framework/`) sudah sesuai dari folder tersebut.

* **Masuk ke folder project dan jalankan layanan pengujian:**
  ```bash
  cd ~/portfolio-app
  docker compose up -d hecf hecf-dashboard bench-json locust-master
  ```
  *(Perintah ini akan menyalakan mesin HECF, Dashboard, target percobaan `bench-json`, dan penembak beban `locust-master` tanpa merestart aplikasi portofoliomu yang lain)*

* **Menyalakan SEMUA layanan (termasuk portofolio):**
  ```bash
  docker compose up -d
  ```

* **Melihat status container yang berjalan:**
  ```bash
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  ```

---

## 2. Cara Menguji 5 Metrik Utama (Sesuai PRD)
Dalam penelitian HECF, ada 5 metrik utama yang harus diukur. Berikut cara mengujinya baik lewat terminal maupun Dashboard:

### Metrik 1 & 2: CPU Utilization & Memory/RAM
* **Via Dashboard:** Buka `http://[IP-Server]:8092`, lihat grafik CPU dan RAM secara visual.
* **Via Terminal (Native Docker):** 
  ```bash
  docker stats bench-json
  ```
  *(Atau ganti `bench-json` dengan container portfoliomu seperti `musicahub-app`, `shopyvibe-app`, `time-saver-app`, dll)*

### Metrik 3: Konsumsi Energi (Joule / kWh)
* **Via Dashboard:** Lihat indikator "Estimated Power" dalam Watt di `http://[IP-Server]:8092`.
* **Via Terminal (Melihat raw data CSV):**
  ```bash
  tail -f ../green-container-framework/metrics.csv
  ```
* **Via Terminal (Cek Sensor Hardware Asli Laptop/Server):**
  ```bash
  cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
  ```

### Metrik 4: Latensi Web / SLA (P95 Response Time)
* **Via Locust Web UI:** Buka `http://[IP-Server]:8089` dan lihat tab "Charts" bagian "Response Times (ms)". Garis persentil 95th (P95) tidak boleh melebihi 500ms.
* **Via Terminal Locust:** Hasil akhir dari perintah `docker exec locust-master ...` akan memunculkan tabel persentil latensi.

### Metrik 5: Overhead Framework (Beban HECF itu sendiri)
Syarat HECF adalah bebannya harus <5% dari kapasitas server. HECF dibatasi maks **128 MB RAM**, Dashboard maks **256 MB RAM**.
* **Via Terminal (Cek seberapa berat HECF berjalan di background):**
  ```bash
  docker stats hecf hecf-dashboard
  ```

---

## 3. Simulasi Penembakan Beban (Locust)
Container `locust-master` sudah dikonfigurasi dengan volume mount ke folder `locustfiles/` dan terhubung ke jaringan `portfolio-network`. Kamu bisa menembak target manapun di jaringan internal Docker.

### A. Tembakan Beban via Web UI
1. Akses **`http://[IP-Server]:8089`** di browser.
2. Isi "Number of users" (misal: `100`) dan "Spawn rate" (misal: `10`).
3. Isi Host dengan salah satu target berikut (gunakan **nama container internal**, bukan IP):

   | Target | Host URL |
   |---|---|
   | Bench-JSON (dummy) | `http://bench-json:8000` |
   | MusicaHub | `http://musicahub-app:3000` |
   | Quran Horizon | `http://quran-horizon-app:3000` |
   | Wedding Invite | `http://wedding-2d-invite-app:3000` |
   | Time Saver | `http://time-saver-app:3001` |
   | ShopyVibe | `http://shopyvibe-app:3000` |

4. Klik **Start Swarming**.

### B. Tembakan Beban via Terminal (Otomatis / Headless)
Bila ingin _benchmark_ yang konsisten tanpa repot mengeklik web, perintahkan container `locust-master` untuk menembak:

* **Target: Bench-JSON (default):**
  ```bash
  docker exec locust-master locust -f /mnt/locust/locustfile.py --headless -u 100 -r 10 --run-time 60s --host http://bench-json:8000
  ```

* **Target: Aplikasi portofolio (contoh MusicaHub):**
  ```bash
  docker exec locust-master locust -f /mnt/locust/locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://musicahub-app:3000
  ```

* **Target: ShopyVibe:**
  ```bash
  docker exec locust-master locust -f /mnt/locust/locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://shopyvibe-app:3000
  ```

---

## 4. Cheat Sheet Cekikan Resource & Micro-Freeze
Bagian ini digunakan untuk menyimulasikan kejadian ekstrem atau membajak limit resource secara manual layaknya HECF.

### A. Simulasi Limit RAM (1 GB / 2 GB) & CPU
Membatasi target agar maksimal hanya menggunakan 1 GB atau 2 GB RAM, dan CPU 50% (0.5 core):
```bash
docker update --memory="1g" --memory-swap="1g" --cpus="0.5" bench-json
```
```bash
docker update --memory="2g" --memory-swap="2g" --cpus="1.0" musicahub-app
```
*(Bisa diaplikasikan ke container manapun seperti `siperah-app`, `shopyvibe-app`, `time-saver-app`, `quran-horizon-app`, `wedding-2d-invite-app`, dll)*

### B. Balikin ke Normal "Full Spec" Laptop
Jika kamu ingin **melepas semua batasan** agar container bisa memakan seluruh resource laptop/server secara bebas (unlimited):
```bash
docker update --cpus="0.0" --memory="0" --memory-swap="0" bench-json
```
*(Angka `0` pada Docker berarti unlimited/full spec hardware)*

### C. Simulasi "Micro-Freeze" (Pembekuan)
Menidurkan sementara container agar CPU 0% tanpa mematikan data RAM:
* **Membekukan (Pause):** `docker pause bench-json`
* **Mencairkan (Unpause):** `docker unpause bench-json`

---

## 5. Otomasi Pengujian 72 Skenario (Eksperimen Lengkap)
Untuk penelitian, skrip otomatis berikut akan mengeksekusi 72 skenario pengujian beruntun (kombinasi HECF On/Off, beban locust, repetisi).

* **Menjalankan Eksperimen:**
  ```bash
  python3 ../green-container-framework/experiments/run_experiment.py
  ```
* **Menganalisa & Merekap Hasil:**
  ```bash
  python3 ../green-container-framework/experiments/analyze_results.py
  ```

---

## 6. Utilitas Tambahan
* **Melihat log (Terminal Output) secara langsung dari HECF Engine dan Dashboard:**
  ```bash
  docker compose logs -f hecf
  docker compose logs -f hecf-dashboard
  ```
* **Menghidupkan/Mematikan HECF On-the-Fly (Tanpa Restart):**
  ```bash
  echo '{"is_active": true}' > ../green-container-framework/framework_status.json   # Menyalakan
  echo '{"is_active": false}' > ../green-container-framework/framework_status.json  # Mematikan
  ```
* **Cek Kapasitas Total Server/Laptop:**
  ```bash
  lscpu      # Cek total Core
  free -m    # Cek total RAM
  ```
* **Restart hanya service HECF (tanpa ganggu yang lain):**
  ```bash
  docker compose restart hecf hecf-dashboard
  ```
* **Lihat log terakhir HECF (50 baris terakhir):**
  ```bash
  docker compose logs --tail 50 hecf
  ```
