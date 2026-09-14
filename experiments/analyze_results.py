#!/usr/bin/env python3
# experiments/analyze_results.py
# Analisis Statistik Hasil Eksperimen HECF (Design Science Research)

import os
import glob
import pandas as pd
import numpy as np
from scipy import stats
import argparse

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "experiment_results")

def calc_cohens_d(group1, group2):
    """Menghitung Cohen's d effect size."""
    diff = group1 - group2
    return np.mean(diff) / np.std(diff, ddof=1)

def run_statistical_test(baseline_data, hecf_data, metric_name):
    """
    Melakukan uji normalitas (Shapiro-Wilk) lalu
    Paired t-test atau Wilcoxon signed-rank.
    """
    if len(baseline_data) < 3 or len(hecf_data) < 3:
        return {"metric": metric_name, "error": "Not enough data"}
        
    # Uji Normalitas (Selisih)
    diff = baseline_data - hecf_data
    stat_shapiro, p_shapiro = stats.shapiro(diff)
    is_normal = p_shapiro > 0.05
    
    # Pilih Uji Komparatif
    if is_normal:
        stat_test, p_val = stats.ttest_rel(baseline_data, hecf_data)
        test_used = "Paired t-test"
    else:
        stat_test, p_val = stats.wilcoxon(baseline_data, hecf_data)
        test_used = "Wilcoxon signed-rank"
        
    cohens_d = calc_cohens_d(baseline_data, hecf_data)
    
    return {
        "Metric": metric_name,
        "Normal (Shapiro p>0.05)": is_normal,
        "Test Used": test_used,
        "P-Value": p_val,
        "Significant (p<0.05)": p_val < 0.05,
        "Cohen's d": cohens_d,
        "Baseline Mean": np.mean(baseline_data),
        "HECF Mean": np.mean(hecf_data)
    }

def analyze():
    print("="*60)
    print("HECF Statistical Analysis Engine")
    print("="*60)
    
    if not os.path.exists(RESULTS_DIR):
        print(f"Error: Directory {RESULTS_DIR} not found.")
        return
        
    # Implementasi dummy untuk membaca dan mengagregasi metrics CSV.
    # Dalam skenario asli, script ini akan mem-parsing `_server_metrics.csv` dan `_locust_stats.csv`.
    print(f"Mencari data CSV di {RESULTS_DIR}...")
    server_csvs = glob.glob(os.path.join(RESULTS_DIR, "*_server_metrics.csv"))
    locust_csvs = glob.glob(os.path.join(RESULTS_DIR, "*_locust_stats.csv"))
    
    print(f"Ditemukan {len(server_csvs)} file metrik server dan {len(locust_csvs)} file metrik Locust.")
    print("\n[NOTE] Harap pastikan data eksperimen (72 eksekusi) sudah lengkap.")
    
    # Contoh struktur DataFrame final (simulasi):
    # df = pd.DataFrame({
    #     "cpu_default": [...], "cpu_hecf": [...],
    #     "ram_default": [...], "ram_hecf": [...],
    #     "energy_default": [...], "energy_hecf": [...],
    #     "p95_default": [...], "p95_hecf": [...]
    # })
    #
    # Kemudian memanggil run_statistical_test()
    # 
    # print("Hasil Uji H1 (Resource & Energy):")
    # print(pd.DataFrame([
    #    run_statistical_test(df['cpu_default'], df['cpu_hecf'], 'CPU Utilization (%)'),
    #    run_statistical_test(df['ram_default'], df['ram_hecf'], 'RAM Usage (MB)'),
    #    run_statistical_test(df['energy_default'], df['energy_hecf'], 'Energy Consumption (Joule)')
    # ]).to_string(index=False))
    #
    # print("\nHasil Uji H2 (Quality of Service & Overhead):")
    # print(pd.DataFrame([
    #    run_statistical_test(df['p95_default'], df['p95_hecf'], 'P95 Latency (ms)')
    # ]).to_string(index=False))
    
    print("\nSkrip analisis telah siap. Uncomment agregasi DataFrame pandas di skrip")
    print("setelah eksperimen `run_experiment.py` selesai dieksekusi 100%.")

if __name__ == "__main__":
    analyze()
