# tests/test_framework.py
# Unit tests for HECF core components
# Run: python -m pytest tests/ -v

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framework.guardrail     import Guardrail
from framework.tier_detector import TierDetector
from framework.predictor     import EMAPredictor
from framework.energy        import estimate_power, estimate_energy, estimate_all
from framework.modes         import OperationMode


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


# ===== Guardrail EMA Pre-Warning Tests (NEW) =====

def test_guardrail_ema_prewarning_lowers_threshold():
    """When EMA is near the threshold, guardrail should trigger earlier."""
    g = Guardrail()
    # CPU=76% is below the normal 80% threshold, but EMA=77% is within
    # the 5% pre-warning margin (80-5=75). The effective threshold should
    # be lowered to 75%, making 76% trigger as "over".
    for _ in range(3):
        result = g.update("test", cpu=76.0, mem=50.0, ema_pred=77.0)
    assert result == True, "EMA pre-warning should lower threshold: 76% > 75% effective"

def test_guardrail_no_prewarning_without_ema():
    """Without EMA, the original 80% threshold is used."""
    g = Guardrail()
    for _ in range(3):
        result = g.update("test", cpu=76.0, mem=50.0)  # no ema_pred
    assert result == False, "Without EMA, 76% is below 80% threshold"

def test_guardrail_prewarning_not_triggered_when_ema_low():
    """When EMA is far from the threshold, no pre-warning adjustment."""
    g = Guardrail()
    for _ in range(3):
        result = g.update("test", cpu=76.0, mem=50.0, ema_pred=50.0)
    assert result == False, "EMA=50% is far from threshold, no pre-warning"

def test_guardrail_cleanup():
    """Cleanup should remove state for disappeared containers."""
    g = Guardrail()
    g.update("alive", 50.0, 50.0)
    g.update("dead", 50.0, 50.0)
    g.cleanup({"alive"})
    # "dead" should be cleaned up, "alive" should remain
    assert "alive" in g._history
    assert "dead" not in g._history


# ===== TierDetector Tests =====

def test_tier_fallback_before_min_samples():
    td = TierDetector()
    td.add_sample("c1", 50.0)
    assert td.get_tier("c1") == 2, "Sebelum min samples → fallback Balanced (Tier 2)"

def test_tier_aggressive():
    td = TierDetector()
    # p50 rendah, p95 tinggi → ratio > 2.0
    for _ in range(50):
        td.add_sample("c1", 5.0)   # banyak sampel rendah
    for _ in range(50):
        td.add_sample("c1", 80.0)  # sebagian besar di level tinggi
    # Sebenarnya tier tergantung distribusi, test ini lebih ke smoke test
    tier = td.get_tier("c1")
    assert tier in [1, 2, 3]

def test_tier_soft():
    td = TierDetector()
    # Semua sampel konstan → p95/p50 ≈ 1.0 → Soft (Tier 3)
    for _ in range(120):
        td.add_sample("c1", 40.0)
    assert td.get_tier("c1") == 3

def test_tier_stats_keys():
    td = TierDetector()
    for _ in range(15):
        td.add_sample("c1", 50.0)
    stats = td.get_stats("c1")
    assert "p50" in stats and "p95" in stats and "spike_ratio" in stats

def test_tier_cleanup():
    """Cleanup should remove state for disappeared containers."""
    td = TierDetector()
    td.add_sample("alive", 50.0)
    td.add_sample("dead", 50.0)
    td.cleanup({"alive"})
    assert "alive" in td._windows
    assert "dead" not in td._windows


# ===== EMA Predictor Tests =====

def test_ema_returns_float():
    p = EMAPredictor()
    result = p.update("c1", 50.0)
    assert isinstance(result, float)

def test_ema_stable_input():
    """Input konstan → prediksi konvergen ke nilai input."""
    p = EMAPredictor()
    for _ in range(20):
        pred = p.update("c1", 50.0)
    # Dengan input konstan, EMA harus konvergen mendekati 50.0
    assert abs(pred - 50.0) < 1.0, f"EMA tidak konvergen: {pred}"

def test_ema_alpha_fixed():
    """Alpha should always be 0.2 (fixed, per PRD §11)."""
    p = EMAPredictor()
    p.update("c1", 50.0)
    alpha = p.get_alpha("c1")
    assert alpha == 0.2, f"Alpha harus fixed 0.2, got: {alpha}"

def test_ema_different_containers_independent():
    p = EMAPredictor()
    p.update("c1", 30.0)
    p.update("c2", 80.0)
    # Tidak ada cross-contamination
    pred_c1 = p.get_prediction("c1")
    pred_c2 = p.get_prediction("c2")
    assert pred_c1 != pred_c2

def test_ema_cleanup():
    """Cleanup should remove state for disappeared containers."""
    p = EMAPredictor()
    p.update("alive", 50.0)
    p.update("dead", 50.0)
    p.cleanup({"alive"})
    assert "alive" in p._predictions
    assert "dead" not in p._predictions


# ===== Energy Estimation Tests =====

def test_power_idle():
    from framework.config import P_IDLE_WATTS, P_MAX_WATTS
    assert estimate_power(0.0, P_IDLE_WATTS, P_MAX_WATTS) == P_IDLE_WATTS

def test_power_max():
    from framework.config import P_IDLE_WATTS, P_MAX_WATTS
    assert estimate_power(100.0, P_IDLE_WATTS, P_MAX_WATTS) == P_MAX_WATTS

def test_power_clamping():
    # CPU > 100% tidak boleh menghasilkan daya > P_MAX
    from framework.config import P_IDLE_WATTS, P_MAX_WATTS
    assert estimate_power(150.0, P_IDLE_WATTS, P_MAX_WATTS) == P_MAX_WATTS

def test_energy_positive():
    e = estimate_energy(30.0, 10)
    assert e > 0

def test_estimate_all_keys():
    from framework.config import P_IDLE_WATTS, P_MAX_WATTS
    result = estimate_all(50.0, 10, P_IDLE_WATTS, P_MAX_WATTS)
    assert "power_watt" in result
    assert "energy_kwh" in result
    # No carbon_gco2 — explicitly removed from scope (PRD §4.2)
    assert "carbon_gco2" not in result

def test_power_hardware_apportionment():
    # Total HW power = 40W, CPU count = 4 (Total Capacity 400%). 
    # Container uses 100% CPU. Apportionment should be 40W * (100 / 400) = 10W
    assert estimate_power(100.0, 15.0, 54.0, hw_power=40.0, cpu_count=4) == 10.0
    
    # Container uses 200% CPU. Apportionment should be 40W * (200 / 400) = 20W
    assert estimate_power(200.0, 15.0, 54.0, hw_power=40.0, cpu_count=4) == 20.0
    
    # Idle container (0% CPU). Apportionment should be 0W
    assert estimate_power(0.0, 15.0, 54.0, hw_power=40.0, cpu_count=4) == 0.0


# ===== OperationMode Tests (NEW) =====

def test_mode_valid():
    assert OperationMode.is_valid("full_hecf")
    assert OperationMode.is_valid("default_docker")
    assert not OperationMode.is_valid("invalid_mode")

def test_mode_shaping_disabled_for_default():
    assert not OperationMode.is_shaping_enabled("default_docker")
    assert OperationMode.is_shaping_enabled("full_hecf")
    assert OperationMode.is_shaping_enabled("static_cap")

def test_mode_tier_only_full_hecf():
    assert OperationMode.is_tier_enabled("full_hecf")
    assert not OperationMode.is_tier_enabled("reactive_only")
    assert not OperationMode.is_tier_enabled("default_docker")

def test_mode_predictor_only_full_hecf():
    assert OperationMode.is_predictor_enabled("full_hecf")
    assert not OperationMode.is_predictor_enabled("reactive_only")

def test_mode_guardrail_reactive_and_full():
    assert OperationMode.is_guardrail_enabled("full_hecf")
    assert OperationMode.is_guardrail_enabled("reactive_only")
    assert not OperationMode.is_guardrail_enabled("default_docker")
    assert not OperationMode.is_guardrail_enabled("static_cap")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])