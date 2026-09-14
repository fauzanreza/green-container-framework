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
    if not is_warmup:
        csv_path = os.path.join(RESULTS_DIR, f"{run_name}_locust")
        csv_prefix_arg = ["--csv", csv_path]
    
    cmd = [
        "locust", "-f", LOCUST_FILE,
        "--host", "http://localhost:8000", # adjust if needed based on docker host port
        "--headless",
        "-u", str(intensity["users"]),
        "-r", str(intensity["spawn_rate"]),
        "--run-time", f"{duration}s"
    ] + csv_prefix_arg

    try:
        subprocess.run(cmd, env=env, check=True)
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
    # Uncomment to actually run
    # run_matrix()
    logger.info("Experiment script initialized (Dry Run). Uncomment run_matrix() to execute.")
