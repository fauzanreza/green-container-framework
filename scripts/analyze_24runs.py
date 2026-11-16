#!/usr/bin/env python3
"""
scripts/analyze_24runs.py
Evaluasi Statistik Eksperimen 24 Run (6 Blok x 4 Mode) — 100% Python Standard Library!
Tidak membutuhkan numpy/scipy/pandas di host OS sehingga dijamin berjalan di server mana pun.
Menghitung:
- Mean, SD, 95% Confidence Interval per mode
- Paired Wilcoxon Signed-Rank Test (exact distribution untuk N=6 pasang blok)
- Cohen's d effect size (paired d_z)
- Holm-Bonferroni p-value adjustment untuk multiple comparisons
- Evaluasi klaim H1 & H2
"""

import sys
import csv
import math
from collections import defaultdict


def mean(arr: list[float]) -> float:
    return sum(arr) / len(arr) if arr else 0.0


def std_sample(arr: list[float]) -> float:
    n = len(arr)
    if n < 2:
        return 0.0
    m = mean(arr)
    var = sum((x - m) ** 2 for x in arr) / (n - 1)
    return math.sqrt(var)


def wilcoxon_signed_rank_exact(x: list[float], y: list[float]) -> tuple[float, float]:
    """
    Exact two-sided Paired Wilcoxon Signed-Rank Test using 100% Python stdlib.
    Ideal for small paired block designs (e.g. N=6 blocks).
    """
    d = [ float(xi) - float(yi) for xi, yi in zip(x, y) if (float(xi) - float(yi)) != 0.0 ]
    n = len(d)
    if n == 0:
        return 0.0, 1.0

    abs_d = [abs(val) for val in d]
    order = sorted(range(n), key=lambda idx: abs_d[idx])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_d[order[j + 1]] == abs_d[order[i]]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1

    w_pos = sum(ranks[idx] for idx in range(n) if d[idx] > 0)
    w_neg = sum(ranks[idx] for idx in range(n) if d[idx] < 0)
    w_stat = min(w_pos, w_neg)
    total_rank_sum = sum(ranks)

    # Exact enumeration over 2^n sign assignments
    total_configs = 1 << n
    extreme_count = 0
    for mask in range(total_configs):
        s = 0.0
        for bit in range(n):
            if (mask >> bit) & 1:
                s += ranks[bit]
        s_min = min(s, total_rank_sum - s)
        if s_min <= w_stat + 1e-9:
            extreme_count += 1

    p_val = min(1.0, extreme_count / float(total_configs))
    return w_stat, p_val


def cohens_d_paired(x: list[float], y: list[float]) -> float:
    """Paired Cohen's d_z = mean(diff) / sd(diff)."""
    diff = [float(xi) - float(yi) for xi, yi in zip(x, y)]
    if len(diff) < 2:
        return 0.0
    sd = std_sample(diff)
    if sd <= 1e-12:
        return 0.0
    return mean(diff) / sd


def ci95(arr: list[float]) -> tuple[float, float, float]:
    """Return (mean, sd, half_width_95ci) using t-critical for df=len-1."""
    a = [float(v) for v in arr]
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0.0
    m = mean(a)
    if n < 2:
        return m, 0.0, 0.0
    sd = std_sample(a)
    t_table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
               6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t_crit = t_table.get(n - 1, 1.96)
    hw = t_crit * (sd / math.sqrt(n))
    return m, sd, hw


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
    data = defaultdict(lambda: defaultdict(list))
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            b = int(row["block"])
            m = row["mode"]
            data[m][b].append({
                "kwh": float(row["rapl_kwh"]),
                "mean_rt": float(row["mean_rt_ms"]),
                "p95_rt": float(row["p95_rt_ms"]),
                "fails": int(row["fail_count"]),
                "oh": float(row["overhead_cpu_pct"]),
            })

    # Average across replications within each (mode, block) pair
    agg_data = defaultdict(dict)
    for m, blocks_dict in data.items():
        for b, rep_list in blocks_dict.items():
            agg_data[m][b] = {
                "kwh": mean([r["kwh"] for r in rep_list]),
                "mean_rt": mean([r["mean_rt"] for r in rep_list]),
                "p95_rt": mean([r["p95_rt"] for r in rep_list]),
                "fails": sum(r["fails"] for r in rep_list),
                "oh": mean([r["oh"] for r in rep_list]),
            }
    data = agg_data

    modes = ["default_docker", "static_cap", "reactive_only", "full_hecf"]
    print("\n=== 1. DESCRIPTIVE STATISTICS (MEAN ± SD [95% CI]) ===")
    print(f"{'Mode':<16} | {'Energy (kWh)':<28} | {'Mean RT (ms)':<18} | {'P95 RT (ms)':<18} | {'Overhead (%)':<14}")
    print("-" * 104)
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
        hecf_kwh = [data["full_hecf"][b]["kwh"] for b in common_blocks]
        for base in baselines:
            base_kwh = [data[base][b]["kwh"] for b in common_blocks]
            w, p = wilcoxon_signed_rank_exact(hecf_kwh, base_kwh)
            d = cohens_d_paired(hecf_kwh, base_kwh)
            mean_base = mean(base_kwh)
            pct_diff = ((mean(hecf_kwh) - mean_base) / mean_base * 100.0) if mean_base > 0 else 0.0
            raw_ps.append(p)
            results.append((base, pct_diff, w, p, d))

        adj_ps = holm_adjust(raw_ps)
        for (base, pct_diff, w, p, d), p_holm in zip(results, adj_ps):
            print(f"full_hecf vs {base:<14}: ΔEnergy={pct_diff:+6.2f}% | W={w:4.1f} | p_raw={p:.4f} | p_Holm={p_holm:.4f} | Cohen's d={d:+.3f}")


if __name__ == "__main__":
    main()
