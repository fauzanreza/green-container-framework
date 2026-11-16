#!/usr/bin/env python3
"""
scripts/analyze_24runs.py
Evaluasi Statistik Eksperimen 24 Run (6 Blok x 4 Mode) — Stdlib + NumPy ONLY!
Menghitung:
- Mean, SD, 95% Confidence Interval per mode
- Paired Wilcoxon Signed-Rank Test (exact distribution untuk N=6 pasang blok)
- Cohen's d effect size
- Holm-Bonferroni p-value adjustment untuk multiple comparisons
- Evaluasi klaim H1 & H2
"""

import sys
import csv
import math
from collections import defaultdict
import numpy as np


def wilcoxon_signed_rank_exact(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """
    Exact two-sided Paired Wilcoxon Signed-Rank Test using stdlib + NumPy only.
    Ideal for small paired block designs (e.g. N=6 blocks).
    """
    d = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    d = d[d != 0.0]
    n = len(d)
    if n == 0:
        return 0.0, 1.0

    abs_d = np.abs(d)
    # Compute ranks with average tie-breaking
    order = np.argsort(abs_d)
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_d[order[j + 1]] == abs_d[order[i]]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    w_pos = float(np.sum(ranks[d > 0]))
    w_neg = float(np.sum(ranks[d < 0]))
    w_stat = min(w_pos, w_neg)

    # Exact enumeration over 2^n sign assignments
    total_configs = 1 << n
    extreme_count = 0
    for mask in range(total_configs):
        s = 0.0
        for bit in range(n):
            if (mask >> bit) & 1:
                s += ranks[bit]
        s_min = min(s, float(np.sum(ranks)) - s)
        if s_min <= w_stat + 1e-9:
            extreme_count += 1

    p_val = min(1.0, extreme_count / float(total_configs))
    return w_stat, p_val


def cohens_d_paired(x: np.ndarray, y: np.ndarray) -> float:
    """Paired Cohen's d_z = mean(diff) / sd(diff)."""
    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    if len(diff) < 2:
        return 0.0
    sd = float(np.std(diff, ddof=1))
    if sd <= 1e-12:
        return 0.0
    return float(np.mean(diff)) / sd


def ci95(arr: np.ndarray) -> tuple[float, float, float]:
    """Return (mean, sd, half_width_95ci) using t-critical for df=len-1."""
    a = np.asarray(arr, dtype=float)
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = float(np.mean(a))
    if n < 2:
        return mean, 0.0, 0.0
    sd = float(np.std(a, ddof=1))
    # t_0.975 lookup table for small N (df = 1..10), fallback 1.96
    t_table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
               6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t_crit = t_table.get(n - 1, 1.96)
    hw = t_crit * (sd / math.sqrt(n))
    return mean, sd, hw


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down multiple testing correction."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = min(1.0, p * (m - rank))
        running_max = max(running_max, adj)
        adjusted[orig_idx] = running_max
    return adjusted


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/analyze_24runs.py <summary_24runs.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    data = defaultdict(lambda: defaultdict(dict))
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            b = int(row["block"])
            m = row["mode"]
            data[m][b] = {
                "kwh": float(row["rapl_kwh"]),
                "mean_rt": float(row["mean_rt_ms"]),
                "p95_rt": float(row["p95_rt_ms"]),
                "fails": int(row["fail_count"]),
                "oh": float(row["overhead_cpu_pct"]),
            }

    modes = ["default_docker", "static_cap", "reactive_only", "full_hecf"]
    print("\n=== 1. DESCRIPTIVE STATISTICS (MEAN ± SD [95% CI]) ===")
    print(f"{'Mode':<16} | {'Energy (kWh)':<24} | {'Mean RT (ms)':<18} | {'P95 RT (ms)':<18} | {'Overhead (%)':<14}")
    print("-" * 100)
    for m in modes:
        blocks = sorted(data[m].keys())
        if not blocks:
            continue
        kwh_m, kwh_s, kwh_ci = ci95([data[m][b]["kwh"] for b in blocks])
        rt_m, rt_s, rt_ci = ci95([data[m][b]["mean_rt"] for b in blocks])
        p95_m, p95_s, p95_ci = ci95([data[m][b]["p95_rt"] for b in blocks])
        oh_m, oh_s, oh_ci = ci95([data[m][b]["oh"] for b in blocks])
        print(f"{m:<16} | {kwh_m:.6f} ± {kwh_s:.6f} (±{kwh_ci:.6f}) | {rt_m:6.1f} ± {rt_s:5.1f}   | {p95_m:6.1f} ± {p95_s:5.1f}   | {oh_m:5.2f} ± {oh_s:4.2f}%")

    # Pairwise comparisons against full_hecf
    baselines = ["default_docker", "static_cap", "reactive_only"]
    common_blocks = sorted(set.intersection(*(set(data[m].keys()) for m in modes))) if all(data[m] for m in modes) else []

    if len(common_blocks) >= 2:
        print("\n=== 2. PAIRED WILCOXON + COHEN'S D + HOLM ADJUSTMENT (Energy kWh) ===")
        raw_ps = []
        results = []
        hecf_kwh = np.array([data["full_hecf"][b]["kwh"] for b in common_blocks])
        for base in baselines:
            base_kwh = np.array([data[base][b]["kwh"] for b in common_blocks])
            w, p = wilcoxon_signed_rank_exact(hecf_kwh, base_kwh)
            d = cohens_d_paired(hecf_kwh, base_kwh)
            pct_diff = ((np.mean(hecf_kwh) - np.mean(base_kwh)) / np.mean(base_kwh) * 100.0) if np.mean(base_kwh) > 0 else 0.0
            raw_ps.append(p)
            results.append((base, pct_diff, w, p, d))

        adj_ps = holm_adjust(raw_ps)
        for (base, pct_diff, w, p, d), p_holm in zip(results, adj_ps):
            print(f"full_hecf vs {base:<14}: ΔEnergy={pct_diff:+6.2f}% | W={w:4.1f} | p_raw={p:.4f} | p_Holm={p_holm:.4f} | Cohen's d={d:+.3f}")


if __name__ == "__main__":
    main()
