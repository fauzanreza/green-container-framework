#!/usr/bin/env python3
# experiments/run_experiment.py
# Orchestrates the 72-run experimental design matrix for HECF thesis.
# 2 Conditions x 3 Workloads x 4 Intensities x 3 Replications = 72 runs

import os
import time
import shutil
import logging
import itertools
import subprocess

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

WARMUP_SEC = 5 * 60
EVALUATION_SEC = 30 * 60
TOTAL_DURATION_SEC = WARMUP_SEC + EVALUATION_SEC
COOLDOWN_SEC = 60 # Cooldown to let system settle before next run

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "experiment_results")
SESSION_TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")
LOCUST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locustfiles", "locustfile.py")

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
    
    # Restart HECF container using docker-compose
    compose_dir = os.path.dirname(os.path.dirname(__file__))
    
    # Create or clear metrics.csv
    metrics_file = os.path.join(compose_dir, "metrics.csv")
    if os.path.exists(metrics_file):
        os.remove(metrics_file)
        
    subprocess.run(["docker", "compose", "restart", "hecf"], cwd=compose_dir, env=env, check=False)
    time.sleep(5)

def run_locust(workload: str, intensity_name: str, duration: int, is_warmup: bool, run_name: str):
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
                bar_len = 40
                filled = int(bar_len * progress)
                bar = '█' * filled + '-' * (bar_len - filled)
                remaining = int(max(0, duration - elapsed))
                
                # Print dynamic progress bar
                print(f"\r  \033[36mProgress:\033[0m [{bar}] {progress*100:.1f}% ({remaining}s remaining)", end="", flush=True)
                time.sleep(1)
                
            print(f"\r  \033[32mProgress:\033[0m [{'█'*40}] 100.0% (0s remaining)\n", flush=True)
        if not is_warmup:
            for suffix in ["_stats.csv", "_stats_history.csv", "_failures.csv", "_exceptions.csv"]:
                src = f"locust-master:{container_csv_path}{suffix}"
                dst = os.path.join(RESULTS_DIR, f"{run_name}_locust{suffix}")
                subprocess.run(["docker", "cp", src, dst], check=False)
    except subprocess.CalledProcessError as e:
        logger.error("Locust failed: %s", e)

def run_matrix():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        
    matrix = list(itertools.product(CONDITIONS, WORKLOADS, list(INTENSITIES.keys()), REPLICATIONS))
    total_runs = len(matrix)
    
    logger.info("Starting experiment matrix: %d total runs", total_runs)
    
    for idx, (condition, workload, intensity, rep) in enumerate(matrix, 1):
        run_name = f"{condition}_{workload}_{intensity}_rep{rep}"
        logger.info("=" * 60)
        logger.info("RUN %d/%d: %s", idx, total_runs, run_name)
        logger.info("=" * 60)
        
        # 1. Setup Docker Environment
        setup_environment(condition)
        
        logger.info("Waiting for cooldown (%ds)...", COOLDOWN_SEC)
        time.sleep(COOLDOWN_SEC)
        
        # 2. Warmup Phase
        run_locust(workload, intensity, WARMUP_SEC, is_warmup=True, run_name=run_name)
        
        # 3. Clear metrics before main evaluation
        compose_dir = os.path.dirname(os.path.dirname(__file__))
        metrics_file = os.path.join(compose_dir, "metrics.csv")
        if os.path.exists(metrics_file):
            open(metrics_file, 'w').close()
            
        # 4. Evaluation Phase
        run_locust(workload, intensity, EVALUATION_SEC, is_warmup=False, run_name=run_name)
        
        # 5. Archive Server Metrics
        dest_file = os.path.join(RESULTS_DIR, f"{run_name}_server_metrics.csv")
        if os.path.exists(metrics_file):
            shutil.copy2(metrics_file, dest_file)
            logger.info("Saved server metrics to %s", dest_file)
        else:
            logger.error("metrics.csv not found for run %s", run_name)

if __name__ == "__main__":
    run_matrix()
