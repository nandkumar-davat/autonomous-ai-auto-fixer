import json
import logging
import structlog
from autofixer.audit.logger import configure_audit_logging

def test_audit_log_structure(capsys):
    # Configure logging to use JSON and capture stdout
    configure_audit_logging(log_level="INFO", json_format=True)
    logger = structlog.get_logger("audit_test")
    
    logger.info("testing audit", user="admin", action="fix")
    
    captured = capsys.readouterr()
    log_lines = captured.out.strip().split("\n")
    
    last_log = json.loads(log_lines[-1])
    assert last_log["event"] == "testing audit"
    assert last_log["user"] == "admin"
    assert last_log["action"] == "fix"
    assert "timestamp" in last_log
    assert "audit_hash" in last_log
    assert "level" in last_log

def test_tamper_evident_hash():
    # We can check if the hash changes if the event changes
    from autofixer.audit.logger import _add_tamper_evident_hash
    
    event1 = {"event": "action", "timestamp": "2023-01-01T00:00:00Z"}
    event2 = {"event": "action", "timestamp": "2023-01-01T00:00:01Z"}
    
    res1 = _add_tamper_evident_hash(None, None, event1.copy())
    res2 = _add_tamper_evident_hash(None, None, event2.copy())
    
    assert res1["audit_hash"] != res2["audit_hash"]
    assert len(res1["audit_hash"]) == 64 # SHA-256 hex length
