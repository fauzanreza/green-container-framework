# Flowchart — discover_containers()

> **Kode Sumber:** `framework/profiler.py` → fungsi `discover_containers()` (baris 94–260)
> **Posisi di Diagram:** Layer 1 — Environment Profiler → Container Discovery & Tagging
> **Kategori:** Tools / Data Acquisition (S1)

Fungsi ini berjalan **setiap polling cycle**. Menemukan semua container running, melakukan filtering dan tagging prioritas, kemudian menerapkan whitelist.

```mermaid
flowchart TD
    START(["discover_containers()<br/>Dipanggil setiap polling cycle"])

    DOCKER_LIST["docker.from_env()<br/>client.containers.list()"]
    DOCKER_FAIL{"Gagal connect<br/>Docker daemon?"}
    DOCKER_ERR["Return {} (kosong)"]

    READ_STATE["Baca shared state files:<br/>• priority_map.json<br/>• targets.json"]

    LOOP_START["FOR EACH container yang running"]

    IS_SELF{"container.id<br/>mengandung<br/>self hostname?"}
    SKIP_SELF["Skip (container HECF sendiri)"]

    IS_EXCLUDED{"Nama container ada<br/>di EXCLUDED_CONTAINERS?<br/>(hecf, cloudflared, dll)"}
    SKIP_EXCLUDED["Skip (hardcoded exclusion)"]

    CHECK_PORTS["Parse bound ports<br/>dari Docker API"]
    PORT_EXCLUDE{"Port ada di<br/>CRITICAL_PORTS_EXCLUDE?<br/>(3306, 5432, 6379, dll)"}
    AUTO_EXCLUDE["[AUTO-EXCLUDE]<br/>Skip — risiko korupsi data"]

    PORT_PRIORITY{"Port ada di<br/>CRITICAL_PORTS_PRIORITY?<br/>(80, 443, 8080, dll)"}
    AUTO_PRIO["auto_priority = True"]

    CHECK_PRIO_MAP{"Nama ada di<br/>priority_map.json?"}
    USE_MAP["priority = mapped value"]
    CHECK_LABEL{"Docker label<br/>hecf.priority == high?"}
    USE_LABEL["priority = from label"]

    CHECK_PATTERN{"Nama/image cocok<br/>NETWORK_INFRA_PATTERNS?<br/>(nginx, caddy, traefik, dll)"}
    FORCE_PRIO["[AUTO-PRIORITY]<br/>priority = True"]

    ADD_DISCOVERED["Tambahkan ke all_discovered dict<br/>meta = id, priority, pid, image,<br/>status, ports, auto_reason"]

    LOOP_END["NEXT container"]

    WRITE_JSON["Tulis discovered_containers.json<br/>(snapshot untuk dashboard UI)"]

    CHECK_WHITELIST{"targets.json<br/>ada isi?"}
    WHITELIST_MODE["WHITELIST MODE:<br/>Filter: hanya container<br/>yang ada di targets.json"]
    OPEN_MODE["OPEN MODE:<br/>Kelola semua container<br/>yang ditemukan"]

    RETURN(["Return targets dict"])

    START --> DOCKER_LIST
    DOCKER_LIST --> DOCKER_FAIL
    DOCKER_FAIL -->|Ya| DOCKER_ERR
    DOCKER_FAIL -->|Tidak| READ_STATE
    READ_STATE --> LOOP_START

    LOOP_START --> IS_SELF
    IS_SELF -->|Ya| SKIP_SELF
    IS_SELF -->|Tidak| IS_EXCLUDED
    SKIP_SELF --> LOOP_END

    IS_EXCLUDED -->|Ya| SKIP_EXCLUDED
    IS_EXCLUDED -->|Tidak| CHECK_PORTS
    SKIP_EXCLUDED --> LOOP_END

    CHECK_PORTS --> PORT_EXCLUDE
    PORT_EXCLUDE -->|Ya| AUTO_EXCLUDE
    PORT_EXCLUDE -->|Tidak| PORT_PRIORITY
    AUTO_EXCLUDE --> LOOP_END

    PORT_PRIORITY -->|Ya| AUTO_PRIO
    PORT_PRIORITY -->|Tidak| CHECK_PRIO_MAP
    AUTO_PRIO --> CHECK_PRIO_MAP

    CHECK_PRIO_MAP -->|Ya| USE_MAP
    CHECK_PRIO_MAP -->|Tidak| CHECK_LABEL
    USE_MAP --> CHECK_PATTERN
    CHECK_LABEL --> USE_LABEL
    USE_LABEL --> CHECK_PATTERN

    CHECK_PATTERN -->|Ya| FORCE_PRIO
    CHECK_PATTERN -->|Tidak| ADD_DISCOVERED
    FORCE_PRIO --> ADD_DISCOVERED

    ADD_DISCOVERED --> LOOP_END
    LOOP_END -->|Masih ada container| LOOP_START
    LOOP_END -->|Selesai| WRITE_JSON

    WRITE_JSON --> CHECK_WHITELIST
    CHECK_WHITELIST -->|Ya, ada isi| WHITELIST_MODE
    CHECK_WHITELIST -->|Tidak, kosong| OPEN_MODE
    WHITELIST_MODE --> RETURN
    OPEN_MODE --> RETURN
```

---

## Deskripsi Alur Berbasis Bisnis/Akademik

```mermaid
flowchart TD
    START(["Proses Penemuan Container (Service Discovery)"])

    HUBUNGI["Interogasi Docker Daemon API:<br/>Ambil meta-data seluruh container aktif"]
    GAGAL{"Koneksi<br/>API Gagal?"}
    KOSONG["Abort operasi:<br/>Kembalikan set kosong (empty list)"]

    BACA_PENGATURAN["Konfigurasi Eksternal:<br/>• Muat Peta Prioritas (Priority Map)<br/>• Muat Daftar Target (Target List)"]

    PERIKSA(["Iterasi Evaluasi per Container"])

    DIRI_SENDIRI{"Mendeteksi Self-Instance<br/>(HECF Engine)?"}
    LEWAT1["Bypass: Hindari rekursi kontrol (self-monitoring)"]

    DILARANG{"Terdaftar dalam<br/>Exclusion List (Hardcoded)?"}
    LEWAT2["Bypass: Container infrastruktur kritikal"]

    CEK_PORT["Inspeksi Binding Port Jaringan"]
    PORT_BAHAYA{"Terdeteksi Port Database?<br/>(MySQL, PostgreSQL, Redis)?"}
    LEWAT3["Bypass Otomatis:<br/>Mitigasi risiko korupsi I/O database"]

    PORT_WEB{"Terdeteksi Port Web Publik?<br/>(HTTP 80, HTTPS 443, 8080)?"}
    PENTING_WEB["Penandaan Prioritas: Web Service Kritikal"]

    CEK_SETTING{"Evaluasi Prioritas Konfigurasi Manual?"}
    PAKAI_MANUAL["Terapkan Bobot Prioritas Manual"]
    CEK_LABEL{"Evaluasi Metadata Label Docker?"}
    PAKAI_LABEL["Terapkan Bobot Berdasarkan Label"]

    CEK_NAMA{"Inspeksi RegEx Penamaan Node<br/>('nginx', 'traefik', proxy)?"}
    PENTING_INFRA["Penandaan Prioritas: Infrastruktur Jaringan"]

    MASUKKAN["Registrasi Container ke<br/>Daftar Inventaris Terpantau"]

    LANJUT["Lanjutkan ke iterasi container berikutnya"]

    TULIS["Ekspor Inventaris ke Persisten Storage<br/>(Sinkronisasi State dengan Dashboard)"]

    CEK_WHITELIST{"Mode Pembatasan Target<br/>(Whitelist) Aktif?"}
    WHITELIST["Filter Diterapkan:<br/>Isolasi pada container spesifik"]
    SEMUA["Mode Global (Promiscuous):<br/>Pantau seluruh container yang terdaftar"]

    SELESAI(["Kembalikan Objek Target Tersaring<br/>ke Engine Utama"])

    START --> HUBUNGI
    HUBUNGI --> GAGAL
    GAGAL -->|Ya| KOSONG
    GAGAL -->|Tidak| BACA_PENGATURAN
    BACA_PENGATURAN --> PERIKSA

    PERIKSA --> DIRI_SENDIRI
    DIRI_SENDIRI -->|Ya| LEWAT1
    DIRI_SENDIRI -->|Tidak| DILARANG
    LEWAT1 --> LANJUT

    DILARANG -->|Ya| LEWAT2
    DILARANG -->|Tidak| CEK_PORT
    LEWAT2 --> LANJUT

    CEK_PORT --> PORT_BAHAYA
    PORT_BAHAYA -->|Ya| LEWAT3
    PORT_BAHAYA -->|Tidak| PORT_WEB
    LEWAT3 --> LANJUT

    PORT_WEB -->|Ya| PENTING_WEB
    PORT_WEB -->|Tidak| CEK_SETTING
    PENTING_WEB --> CEK_SETTING

    CEK_SETTING -->|Ya| PAKAI_MANUAL
    CEK_SETTING -->|Tidak| CEK_LABEL
    PAKAI_MANUAL --> CEK_NAMA
    CEK_LABEL --> PAKAI_LABEL
    PAKAI_LABEL --> CEK_NAMA

    CEK_NAMA -->|Ya| PENTING_INFRA
    CEK_NAMA -->|Tidak| MASUKKAN
    PENTING_INFRA --> MASUKKAN
    MASUKKAN --> LANJUT

    LANJUT -->|Masih ada| PERIKSA
    LANJUT -->|Semua sudah| TULIS

    TULIS --> CEK_WHITELIST
    CEK_WHITELIST -->|Ya| WHITELIST
    CEK_WHITELIST -->|Tidak| SEMUA
    WHITELIST --> SELESAI
    SEMUA --> SELESAI
```
