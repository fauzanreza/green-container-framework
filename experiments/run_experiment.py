#!/usr/bin/env python3
# experiments/run_experiment.py
# Orchestrates the 72-run experimental design matrix for HECF thesis.
# 2 Conditions x 3 Workloads x 4 Intensities x 3 Replications = 72 runs
# 20 minutes per run (5 min warmup + 15 min evaluation) = 24 hours total

import os
import time
import shutil
import logging
import itertools
import subprocess
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("hecf.experiment")

# Factorial Design Variables
CONDITIONS = ["default_docker", "hecf_active"]
WORKLOADS = ["json", "static", "db"]
INTENSITIES = {
    "Low": {"users": 10, "spawn_rate": 1},
    "Medium": {"users": 50, "spawn_rate": 5},
    "High": {"users": 150, "spawn_rate": 10},
    "Spike": {"users": 300, "spawn_rate": 50},
}
REPLICATIONS = [1, 2, 3]

WARMUP_SEC = 300 # 5 minutes
EVALUATION_SEC = 900 # 15 minutes
TOTAL_DURATION_SEC = WARMUP_SEC + EVALUATION_SEC
COOLDOWN_SEC = 0 # No cooldown to keep exactly 20 mins per run

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # green-container-framework/
COMPOSE_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "portfolio-app")  # ../portfolio-app/ (main docker-compose.yml)
RESULTS_DIR = os.path.join(PROJECT_DIR, "experiment_results")
SESSION_TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")
LOCUST_FILE = os.path.join(PROJECT_DIR, "locustfiles", "locustfile.py")

def setup_environment(condition: str):
    """Set environment variables for HECF and restart container."""
    env = os.environ.copy()
    
    if condition == "default_docker":
        env["HECF_MODE"] = "default_docker"
    else:
        env["HECF_MODE"] = "full_hecf"
        env["GUARDRAIL_CPU_THRESHOLD"] = "80"
        env["GUARDRAIL_RAM_THRESHOLD"] = "90"
        
    logger.info("Setting HECF Condition=%s", condition)
    
    # Create or clear metrics.csv without breaking Docker bind mount (preserve inode)
    metrics_file = os.path.join(PROJECT_DIR, "metrics.csv")
    open(metrics_file, 'w').close()
        
    # Restart HECF container using docker-compose from portfolio-app directory
    subprocess.run(["docker", "compose", "up", "-d", "hecf"], cwd=COMPOSE_DIR, env=env, check=False)
    time.sleep(5)

def run_locust(condition: str, workload: str, intensity_name: str, duration: int, is_warmup: bool, run_name: str, global_ctx: dict = None):
    """Run Locust load generator using subprocess."""
    intensity = INTENSITIES[intensity_name]
    logger.info("Running Locust (Warmup=%s) for %ds: Workload=%s, Intensity=%s", is_warmup, duration, workload, intensity_name)
    
    env = os.environ.copy()
    env["WORKLOAD_TYPE"] = workload
    
    # Generate CSV results only for the main evaluation phase
    csv_prefix_arg = []
    container_csv_path = f"/tmp/{run_name}_locust"
    if not is_warmup:
        csv_prefix_arg = ["--csv", container_csv_path]
    
    # Map workload to host
    hosts = {
        "json": "http://bench-json:8000",
        "static": "http://portfolio-web:80",
        "db": "http://shopyvibe-app:3000"
    }
    target_host = hosts.get(workload, "http://bench-json:8000")

    cmd = [
        "docker", "exec", "locust-master",
        "locust", "-f", "/mnt/locust/locustfile.py",
        "--host", target_host,
        "--headless",
        "-u", str(intensity["users"]),
        "-r", str(intensity["spawn_rate"]),
        "--run-time", f"{duration}s"
    ] + csv_prefix_arg

    log_file_path = os.path.join(RESULTS_DIR, f"{run_name}_locust_{'warmup' if is_warmup else 'eval'}_{SESSION_TIMESTAMP}.log")
    
    try:
        with open(log_file_path, "a") as log_file:
            # Write a clear header so the user knows what iteration and parameters they are looking at
            log_file.write(f"============================================================\n")
            log_file.write(f"HECF EXPERIMENT LOG\n")
            log_file.write(f"Timestamp    : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Run Name     : {run_name}\n")
            log_file.write(f"Workload     : {workload}\n")
            log_file.write(f"Intensity    : {intensity_name} (Users: {intensity['users']}, Spawn Rate: {intensity['spawn_rate']})\n")
            log_file.write(f"Phase        : {'Warmup' if is_warmup else 'Evaluation'}\n")
            log_file.write(f"Duration     : {duration} seconds\n")
            log_file.write(f"============================================================\n\n")
            
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT)
            start_time = time.time()
            while True:
                ret = process.poll()
                if ret is not None:
                    if ret != 0:
                        print() # Prevent overwriting error message
                        raise subprocess.CalledProcessError(ret, cmd)
                    break
                    
                elapsed = time.time() - start_time
                progress = min(1.0, elapsed / duration)
                bar_len = 20
                filled = int(bar_len * progress)
                bar = '█' * filled + '-' * (bar_len - filled)
                remaining = int(max(0, duration - elapsed))
                
                info_text = f"[{condition} | {workload} | {intensity_name}]"
                
                # Global ETA calculation
                global_text = ""
                if global_ctx:
                    g_elapsed = time.time() - global_ctx["start_time"]
                    g_rem = max(0, global_ctx["total_duration"] - g_elapsed)
                    h, rem_sec = divmod(g_rem, 3600)
                    m, s = divmod(rem_sec, 60)
                    g_prog = min(100.0, (g_elapsed / global_ctx["total_duration"]) * 100)
                    global_text = f" | Global ETA: {int(h)}h{int(m)}m{int(s)}s ({g_prog:.1f}%)"

                # Print dynamic progress bar with short info
                print(f"\r  \033[36mProgress:\033[0m [{bar}] {progress*100:.1f}% ({remaining}s) {info_text}{global_text}", end="", flush=True)
                time.sleep(1)
                
            print(f"\r  \033[32mProgress:\033[0m [{'█'*20}] 100.0% (0s remaining) [{condition} | {workload} | {intensity_name}]\n", flush=True)
        if not is_warmup:
            for suffix in ["_stats.csv", "_stats_history.csv", "_failures.csv", "_exceptions.csv"]:
                src = f"locust-master:{container_csv_path}{suffix}"
                dst = os.path.join(RESULTS_DIR, f"{run_name}_locust{suffix}")
                subprocess.run(["docker", "cp", src, dst], check=False)
    except subprocess.CalledProcessError as e:
        logger.error("Locust failed: %s", e)

def run_matrix(is_demo=False):
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        
    matrix = list(itertools.product(CONDITIONS, WORKLOADS, list(INTENSITIES.keys()), REPLICATIONS))
    total_runs = len(matrix)
    
    logger.info("Starting experiment matrix: %d total runs", total_runs)
    
    global_ctx = {
        "start_time": time.time(),
        "total_duration": total_runs * (WARMUP_SEC + EVALUATION_SEC + COOLDOWN_SEC)
    }
    
    for idx, (condition, workload, intensity, rep) in enumerate(matrix, 1):
        run_name = f"demo_{condition}_{workload}_{intensity}_rep{rep}" if is_demo else f"{condition}_{workload}_{intensity}_rep{rep}"
        logger.info("=" * 60)
        logger.info("RUN %d/%d: %s", idx, total_runs, run_name)
        logger.info("=" * 60)
        
        # 1. Setup Docker Environment
        setup_environment(condition)
        
        if COOLDOWN_SEC > 0:
            logger.info("Waiting for cooldown (%ds)...", COOLDOWN_SEC)
            time.sleep(COOLDOWN_SEC)
        
        # 2. Warmup Phase
        run_locust(condition, workload, intensity, WARMUP_SEC, is_warmup=True, run_name=run_name, global_ctx=global_ctx)
        
        # 3. Clear metrics before main evaluation
        metrics_file = os.path.join(PROJECT_DIR, "metrics.csv")
        if os.path.exists(metrics_file):
            open(metrics_file, 'w').close()
            
        # 4. Evaluation Phase
        run_locust(condition, workload, intensity, EVALUATION_SEC, is_warmup=False, run_name=run_name, global_ctx=global_ctx)
        
        # 5. Archive Server Metrics
        dest_file = os.path.join(RESULTS_DIR, f"{run_name}_server_metrics.csv")
        if os.path.exists(metrics_file):
            shutil.copy2(metrics_file, dest_file)
            logger.info("Saved server metrics to %s", dest_file)
        else:
            logger.error("metrics.csv not found for run %s", run_name)

    logger.info("=" * 60)
    logger.info("All experiments finished successfully!")
    logger.info("To view the full Locust report of the last run, use:")
    logger.info("  cat %s", os.path.join("experiment_results", f"{run_name}_locust_eval_{SESSION_TIMESTAMP}.log"))
    logger.info("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run HECF Experiments")
    parser.add_argument("--demo", action="store_true", help="Run a quick 30-second demo instead of the full 72 runs")
    args = parser.parse_args()

    if args.demo:
        logger.info("🏃 DEMO MODE ACTIVATED: Running a quick 30-second test for presentation...")
        CONDITIONS = ["default_docker", "hecf_active"]
        WORKLOADS = ["json"]
        INTENSITIES = {"Low": {"users": 10, "spawn_rate": 1}}
        REPLICATIONS = [1]
        WARMUP_SEC = 5
        EVALUATION_SEC = 25
        COOLDOWN_SEC = 0

    run_matrix(is_demo=args.demo)
