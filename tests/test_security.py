# tests/test_security.py
# Unit tests for HECF Security & Micro-Freezing extension (§10/§12)
# Run: python -m pytest tests/ -v

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framework.security.image_signer import ImageSigner
from framework.security.privilege_guard import PrivilegeGuard
from framework.security.ddos_filter import DDoSFilter
from framework.security.edos_guard import EDoSGuard
from framework.security.encryption_calc import EncryptionCostCalculator
from framework.security.coresident_placement import CoResidentPlacement
from framework.security.micro_freezer import MicroFreezer
from framework.security.tcp_backlog_manager import TCPBacklogManager
from framework.security.sandbox_isolator import SandboxIsolator


# ===== Image Signer Tests =====

def test_image_signer_open_gate():
    """No trusted digests → all images allowed."""
    signer = ImageSigner(trusted_digests=[], required=False)
    result = signer.verify_container("test", "abc123", "sha256:deadbeef")
    assert result["trusted"] == True

def test_image_signer_trusted_match():
    signer = ImageSigner(trusted_digests=["sha256:deadbeef"], required=True)
    result = signer.verify_container("test", "abc123", "sha256:deadbeef000111")
    assert result["trusted"] == True

def test_image_signer_untrusted():
    signer = ImageSigner(trusted_digests=["sha256:trusted"], required=True)
    result = signer.verify_container("test", "abc123", "sha256:unknown")
    assert result["trusted"] == False
    assert signer.required == True

def test_image_signer_cache():
    """Subsequent calls for same container return cached result."""
    signer = ImageSigner(trusted_digests=["sha256:ok"], required=False)
    r1 = signer.verify_container("test", "id1", "sha256:ok")
    r2 = signer.verify_container("test", "id1", "sha256:different")
    assert r1 is r2  # Same object from cache


# ===== Privilege Guard Tests =====

def test_privilege_guard_priority_exempt():
    guard = PrivilegeGuard(enforce=True)
    result = guard.check_container("db", "id1", priority=True, privileged=True)
    assert result["safe"] == True
    assert result["reason"] == "priority_exempt"

def test_privilege_guard_non_priority_privileged():
    guard = PrivilegeGuard(enforce=True)
    result = guard.check_container("web", "id2", priority=False, privileged=True)
    assert result["safe"] == False
    assert len(result["warnings"]) > 0

def test_privilege_guard_clean():
    guard = PrivilegeGuard(enforce=True)
    result = guard.check_container("web", "id3", priority=False, privileged=False)
    assert result["safe"] == True

def test_privilege_guard_dangerous_caps():
    guard = PrivilegeGuard(enforce=True)
    result = guard.check_container("web", "id4", priority=False,
                                   privileged=False, cap_add=["SYS_ADMIN"])
    assert result["safe"] == False


# ===== DDoS Filter Tests =====

def test_ddos_no_attack():
    f = DDoSFilter(rate_threshold=100.0, window_seconds=1.0)
    result = f.analyze("test")
    assert result["is_ddos"] == False
    assert result["rate"] == 0.0

def test_ddos_attack_detected():
    f = DDoSFilter(rate_threshold=10.0, window_seconds=1.0)
    for _ in range(20):
        f.record_request("test", request_count=1)
    result = f.analyze("test")
    assert result["is_ddos"] == True
    assert result["rate"] > 10.0

def test_ddos_cleanup():
    f = DDoSFilter()
    f.record_request("alive")
    f.record_request("dead")
    f.cleanup({"alive"})
    assert "dead" not in f._request_log


# ===== EDoS Guard Tests =====

def test_edos_no_attack():
    guard = EDoSGuard(ddos_filter=None)
    result = guard.evaluate("test", "id1", priority=False)
    assert result["action"] == "normal"

def test_edos_priority_exempt():
    # Even if DDoS detected, priority containers are exempt
    ddos = DDoSFilter(rate_threshold=1.0)
    for _ in range(10):
        ddos.record_request("db")
    ddos.analyze("db")

    guard = EDoSGuard(ddos_filter=ddos)
    result = guard.evaluate("db", "id1", priority=True)
    assert result["action"] == "normal"

def test_edos_freeze_on_attack():
    ddos = DDoSFilter(rate_threshold=1.0, window_seconds=1.0)
    for _ in range(10):
        ddos.record_request("web")
    ddos.analyze("web")

    guard = EDoSGuard(ddos_filter=ddos)
    result = guard.evaluate("web", "id1", priority=False)
    assert result["action"] == "freeze"


# ===== Encryption Calculator Tests =====

def test_encryption_none_zero_cost():
    calc = EncryptionCostCalculator(mode="none")
    result = calc.estimate_cost(100.0)
    assert result["cpu_cost_percent"] == 0.0
    assert result["affordable"] == True

def test_encryption_aes_rsa_cost():
    calc = EncryptionCostCalculator(mode="aes_rsa", host_cpu_count=2)
    result = calc.estimate_cost(10.0)
    assert result["cpu_cost_percent"] > 0
    assert result["mode"] == "aes_rsa"

def test_encryption_transfer_safe():
    calc = EncryptionCostCalculator(mode="none")
    assert calc.is_transfer_safe(1000.0) == True


# ===== Co-resident Placement Tests =====

def test_coresident_single_tenant_noop():
    cp = CoResidentPlacement(multi_tenant=False)
    result = cp.check_placement("test")
    assert result["safe"] == True
    assert result["recommendation"] == "single_tenant_mode"

def test_coresident_multi_tenant_safe():
    cp = CoResidentPlacement(multi_tenant=True)
    cp.register_container("web", tenant="a", risk="low")
    result = cp.check_placement("web")
    assert result["safe"] == True

def test_coresident_high_risk_near_sensitive():
    cp = CoResidentPlacement(multi_tenant=True)
    cp.register_container("attacker", tenant="bad", risk="high")
    cp.register_container("secrets", tenant="good", risk="low", sensitive=True)
    result = cp.check_placement("attacker")
    assert result["safe"] == False
    assert len(result["warnings"]) > 0


# ===== Micro-Freezer Tests =====

def test_micro_freezer_priority_exempt():
    mf = MicroFreezer(dry_run=True)
    result = mf.evaluate("db", "id1", priority=True, cpu_percent=0.0)
    assert result["action"] == "none"
    assert result["reason"] == "priority_exempt"

def test_micro_freezer_not_idle_enough():
    mf = MicroFreezer(idle_trigger_seconds=5.0, dry_run=True)
    mf.record_activity("id1")
    result = mf.evaluate("web", "id1", priority=False, cpu_percent=1.0)
    assert result["action"] == "none"
    assert "not_idle_enough" in result["reason"]

def test_micro_freezer_freeze_idle():
    mf = MicroFreezer(idle_trigger_seconds=0.01, dry_run=True)
    mf._state["id1"] = {"frozen": False, "frozen_at": 0.0, "last_activity": time.time() - 1.0}
    result = mf.evaluate("web", "id1", priority=False, cpu_percent=0.0)
    assert result["action"] == "freeze"

def test_micro_freezer_max_duration_thaw():
    mf = MicroFreezer(max_freeze_duration_ms=1, dry_run=True)
    mf._state["id1"] = {"frozen": True, "frozen_at": time.time() - 1.0, "last_activity": 0}
    result = mf.evaluate("web", "id1", priority=False, cpu_percent=0.0)
    assert result["action"] == "thaw"

def test_micro_freezer_thaw_on_activity():
    mf = MicroFreezer(dry_run=True)
    mf._state["id1"] = {"frozen": True, "frozen_at": time.time(), "last_activity": 0}
    assert mf.is_frozen("id1") == True
    mf.record_activity("id1")
    assert mf.is_frozen("id1") == False


# ===== TCP Backlog Manager Tests =====

def test_tcp_backlog_reads_somaxconn():
    mgr = TCPBacklogManager()
    assert mgr.somaxconn > 0

def test_tcp_backlog_verify():
    mgr = TCPBacklogManager(min_headroom=1, expected_rps=1.0)
    result = mgr.verify()
    assert "safe" in result
    assert "somaxconn" in result


# ===== Sandbox Isolator Tests =====

def test_sandbox_no_threat():
    sb = SandboxIsolator(dry_run=True)
    result = sb.evaluate("web", "id1")
    assert result["action"] == "none"

def test_sandbox_get_incidents_empty():
    sb = SandboxIsolator(dry_run=True)
    assert sb.get_incidents() == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
