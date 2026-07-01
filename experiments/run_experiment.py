#!/usr/bin/env python3
# experiments/run_experiment.py
# Orchestrates the 72-run experimental design matrix for HECF thesis.

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

# Factorial Design Variables (3 x 3 x 2 x 4 = 72 combinations)
WORKLOADS = ["web_tier", "api_tier", "db_tier"]
TRAFFIC_PATTERNS = ["steady", "spiky", "burst"]
SENSITIVITY_LEVELS = ["normal", "tight"] # tight = threshold -20%
MODES = ["default_docker", "static_cap", "reactive_only", "full_hecf"]

EXPERIMENT_DURATION_SEC = 15 * 60 # 15 minutes eval
COOLDOWN_DURATION_SEC = 5 * 60    # 5 minutes cooldown/cold-start

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "experiment_results")

def setup_environment(mode: str, sensitivity: str):
    """Set environment variables for HECF and restart container."""
    env = os.environ.copy()
    env["HECF_MODE"] = mode
    
    if sensitivity == "tight":
        # -20% thresholds for sensitivity analysis
        env["GUARDRAIL_CPU_THRESHOLD"] = "64" # 80 * 0.8
        env["GUARDRAIL_RAM_THRESHOLD"] = "72" # 90 * 0.8
    else:
        env["GUARDRAIL_CPU_THRESHOLD"] = "80"
        env["GUARDRAIL_RAM_THRESHOLD"] = "90"
        
    logger.info("Setting HECF Mode=%s, Sensitivity=%s", mode, sensitivity)
    
    # Restart HECF container using docker-compose
    compose_dir = os.path.dirname(os.path.dirname(__file__))
    
    # Create or clear metrics.csv
    metrics_file = os.path.join(compose_dir, "metrics.csv")
    if os.path.exists(metrics_file):
        os.remove(metrics_file)
        
    subprocess.run(["docker", "compose", "restart", "hecf"], cwd=compose_dir, env=env)
    # Wait for HECF to start
    time.sleep(5)

def run_load_generator(workload: str, traffic: str):
    """Start Locust load generator."""
    logger.info("Starting load generator: Workload=%s, Traffic=%s", workload, traffic)
    # Placeholder for starting locust process (e.g. via subprocess or docker API)
    # subprocess.Popen(["locust", "-f", f"locustfiles/{workload}_{traffic}.py", "--headless", "-t", f"{EXPERIMENT_DURATION_SEC}s"])
    
def stop_load_generator():
    """Stop Locust load generator."""
    logger.info("Stopping load generator.")
    # subprocess.run(["pkill", "-f", "locust"])

def run_matrix():
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        
    matrix = list(itertools.product(WORKLOADS, TRAFFIC_PATTERNS, SENSITIVITY_LEVELS, MODES))
    total_runs = len(matrix)
    
    logger.info("Starting experiment matrix: %d total runs", total_runs)
    
    for idx, (workload, traffic, sensitivity, mode) in enumerate(matrix, 1):
        run_name = f"{workload}_{traffic}_{sensitivity}_{mode}"
        logger.info("=" * 60)
        logger.info("RUN %d/%d: %s", idx, total_runs, run_name)
        logger.info("=" * 60)
        
        # 1. Setup HECF
        setup_environment(mode, sensitivity)
        
        # 2. Cooldown before starting (Wait for system to stabilize)
        logger.info("Waiting for cooldown/cold-start (%ds)...", COOLDOWN_DURATION_SEC)
        # time.sleep(COOLDOWN_DURATION_SEC)
        
        # 3. Start Load
        run_load_generator(workload, traffic)
        
        # 4. Wait for experiment duration
        logger.info("Experiment running for %ds...", EXPERIMENT_DURATION_SEC)
        # time.sleep(EXPERIMENT_DURATION_SEC)
        
        # 5. Stop Load
        stop_load_generator()
        
        # 6. Archive Results
        metrics_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "metrics.csv")
        dest_file = os.path.join(RESULTS_DIR, f"{run_name}_metrics.csv")
        if os.path.exists(metrics_file):
            shutil.copy2(metrics_file, dest_file)
            logger.info("Saved results to %s", dest_file)
        else:
            logger.error("metrics.csv not found for run %s", run_name)

if __name__ == "__main__":
    # run_matrix()
    logger.info("Experiment script initialized (Dry Run). Uncomment run_matrix() to execute.")
