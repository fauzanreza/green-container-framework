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

from locust import HttpUser, task, between, constant_pacing
import random


class BenchUser(HttpUser):
    """
    Simulasi user yang mengakses tiga tipe endpoint HttpArena:
    - JSON Processing (API response ringan)
    - Static Files (throughput murni)
    - Async DB (operasi database asinkron)
    """
    wait_time = between(0.1, 1.0)

    @task(3)
    def json_endpoint(self):
        """JSON Processing — workload API modern."""
        with self.client.get("/", name="JSON-Processing", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def static_endpoint(self):
        """Static Files — throughput murni."""
        with self.client.get("/static/dummy.txt", name="Static-Files", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def db_endpoint(self):
        """Async DB — operasi database asinkron."""
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