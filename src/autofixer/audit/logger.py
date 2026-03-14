import logging
import sys
import structlog
from structlog.types import EventDict

def _add_tamper_evident_hash(logger: logging.Logger, log_method: str, event_dict: EventDict) -> EventDict:
    """A simplistic tamper-evident hash (HMAC) for audit logs."""
    import hashlib
    import json
    
    # In a real environment, you'd use a secret key from Azure Key Vault
    secret_key = b"super-secret-audit-key" 
    
    # Create a deterministic string to hash
    event_str = json.dumps(event_dict, sort_keys=True)
    
    h = hashlib.sha256()
    h.update(secret_key)
    h.update(event_str.encode('utf-8'))
    
    event_dict["audit_hash"] = h.hexdigest()
    return event_dict

def configure_audit_logging(log_level: str = "INFO", json_format: bool = True):
    """Configures structured, tamper-aware logging for the agent."""
    
    # Map string level to logging module level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_tamper_evident_hash,  # Ensure integrity
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
