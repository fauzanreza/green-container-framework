# locustfiles/locustfile.py
# Load Generator untuk eksperimen HGCF
# Ref: Ahmad et al. (2025) — Locust untuk load testing microservice benchmark
# Ref: Proposal HGCF — 4 level beban: Low, Medium, High, Spike
#
# Cara pakai:
#   locust -f locustfile.py --host http://bench-json:8000 --headless \
#          -u 50 -r 5 --run-time 30m
#
# Atau buka UI: http://localhost:8089

import os
from locust import HttpUser, task, between

# Baca WORKLOAD_TYPE dari environment variable, default ke 'all' (gabungan)
WORKLOAD = os.environ.get("WORKLOAD_TYPE", "all").lower()

class BenchUser(HttpUser):
    """
    Simulasi user yang mengakses tiga tipe endpoint HttpArena secara terisolasi atau gabungan:
    - JSON Processing (API response ringan)
    - Static Files (throughput murni)
    - Async DB (operasi database asinkron)
    """
    wait_time = between(0.1, 1.0)

    @task(3 if WORKLOAD in ["json", "all"] else 0)
    def json_endpoint(self):
        """JSON Processing — workload API modern."""
        if WORKLOAD not in ["json", "all"]: return
        with self.client.get("/", name="JSON-Processing", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2 if WORKLOAD in ["static", "all"] else 0)
    def static_endpoint(self):
        """Static Files — throughput murni."""
        if WORKLOAD not in ["static", "all"]: return
        with self.client.get("/static/dummy.txt", name="Static-Files", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2 if WORKLOAD in ["db", "all"] else 0)
    def db_endpoint(self):
        """Async DB — operasi database asinkron."""
        if WORKLOAD not in ["db", "all"]: return
        with self.client.get("/db", name="Async-DB", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")


# ============================================================
# Profil beban sesuai Proposal HGCF (Section 3.4.2):
#
# Level      Users  Spawn Rate  Peak CPU  Tujuan
# Low        10     1/s         10-20%    Baseline idle
# Medium     50     5/s         40-60%    Normal operation
# High       150    10/s        70-85%    Peak load
# Spike      300    50/s        90-100%   Trigger guardrail/tier
#
# Contoh command per level:
# Low:    locust ... -u 10  -r 1  --run-time 30m
# Medium: locust ... -u 50  -r 5  --run-time 30m
# High:   locust ... -u 150 -r 10 --run-time 30m
# Spike:  locust ... -u 300 -r 50 --run-time 5m
# ============================================================