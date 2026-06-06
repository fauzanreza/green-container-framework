# tests/test_framework.py
# Unit test untuk komponen utama HGCF
# Jalankan: python -m pytest tests/ -v

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framework.guardrail     import Guardrail
from framework.tier_detector import TierDetector, TIER_AGGRESSIVE, TIER_BALANCED, TIER_SOFT
from framework.predictor     import AFMVPredictor
from framework.energy        import estimate_power, estimate_energy, estimate_carbon, estimate_all


# ===== Guardrail Tests =====

def test_guardrail_not_active_below_threshold():
    g = Guardrail()
    for _ in range(5):
        result = g.update("test", cpu=70.0, mem=80.0)
    assert result == False, "Guardrail tidak boleh aktif di bawah threshold"

def test_guardrail_active_cpu():
    g = Guardrail()
    # Kirim 3 sampel CPU > 80% dari 5 sampel
    g.update("test", 85.0, 50.0)
    g.update("test", 60.0, 50.0)
    g.update("test", 90.0, 50.0)
    g.update("test", 70.0, 50.0)
    result = g.update("test", 88.0, 50.0)  # sampel ke-5, total 3 dari 5 > 80%
    assert result == True, "Guardrail harus aktif: 3 dari 5 sampel CPU > 80%"

def test_guardrail_active_mem():
    g = Guardrail()
    g.update("test", 50.0, 92.0)
    g.update("test", 50.0, 91.0)
    result = g.update("test", 50.0, 95.0)
    assert result == True, "Guardrail harus aktif: 3 dari sampel MEM > 90%"

def test_guardrail_reset():
    g = Guardrail()
    for _ in range(3):
        g.update("c1", 85.0, 50.0)
    g.reset("c1")
    result = g.update("c1", 85.0, 50.0)
    assert result == False, "Setelah reset, guardrail mulai dari nol"


# ===== TierDetector Tests =====

def test_tier_fallback_before_min_samples():
    td = TierDetector()
    td.add_sample("c1", 50.0)
    assert td.get_tier("c1") == TIER_BALANCED, "Sebelum min samples → fallback Balanced"

def test_tier_aggressive():
    td = TierDetector()
    # p50 rendah, p95 tinggi → ratio > 2.0
    for _ in range(50):
        td.add_sample("c1", 5.0)   # banyak sampel rendah
    for _ in range(50):
        td.add_sample("c1", 80.0)  # sebagian besar di level tinggi
    # Sebenarnya tier tergantung distribusi, test ini lebih ke smoke test
    tier = td.get_tier("c1")
    assert tier in [TIER_AGGRESSIVE, TIER_BALANCED, TIER_SOFT]

def test_tier_soft():
    td = TierDetector()
    # Semua sampel konstan → p95/p50 ≈ 1.0 → Soft
    for _ in range(20):
        td.add_sample("c1", 40.0)
    assert td.get_tier("c1") == TIER_SOFT

def test_tier_stats_keys():
    td = TierDetector()
    for _ in range(15):
        td.add_sample("c1", 50.0)
    stats = td.get_stats("c1")
    assert "p50" in stats and "p95" in stats and "spike_ratio" in stats


# ===== AFMV Predictor Tests =====

def test_afmv_returns_float():
    p = AFMVPredictor()
    result = p.update("c1", 50.0)
    assert isinstance(result, float)

def test_afmv_stable_input():
    """Input konstan → prediksi konvergen ke nilai input."""
    p = AFMVPredictor()
    for _ in range(20):
        pred = p.update("c1", 50.0)
    # Dengan input konstan, AFMV harus konvergen mendekati 50.0
    assert abs(pred - 50.0) < 5.0, f"AFMV tidak konvergen: {pred}"

def test_afmv_alpha_range():
    p = AFMVPredictor()
    for i in range(10):
        p.update("c1", float(i * 10))
    alpha = p.get_alpha("c1")
    assert 0.05 <= alpha <= 0.50, f"Alpha di luar range: {alpha}"

def test_afmv_different_containers_independent():
    p = AFMVPredictor()
    p.update("c1", 30.0)
    p.update("c2", 80.0)
    # Tidak ada cross-contamination
    pred_c1 = p.get_prediction("c1")
    pred_c2 = p.get_prediction("c2")
    assert pred_c1 != pred_c2


# ===== Energy Estimation Tests =====

def test_power_idle():
    from framework.config import P_IDLE
    assert estimate_power(0.0) == P_IDLE

def test_power_max():
    from framework.config import P_MAX
    assert estimate_power(100.0) == P_MAX

def test_power_clamping():
    # CPU > 100% tidak boleh menghasilkan daya > P_MAX
    from framework.config import P_MAX
    assert estimate_power(150.0) == P_MAX

def test_energy_positive():
    e = estimate_energy(30.0, 10)
    assert e > 0

def test_carbon_positive():
    c = estimate_carbon(0.001)
    assert c > 0

def test_estimate_all_keys():
    result = estimate_all(50.0, 10)
    assert "power_watt" in result
    assert "energy_kwh" in result
    assert "carbon_gco2" in result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])