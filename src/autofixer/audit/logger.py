import structlog
import logging
from typing import Any, Dict

def setup_logging(log_level: str = "INFO"):
    """Configures structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=level)

def get_audit_logger():
    """Returns a logger specifically for audit events."""
    return structlog.get_logger("audit")

class AuditLog:
    """Helper for logging security-relevant actions."""
    
    def __init__(self):
        self.logger = get_audit_logger()

    def log_action(self, action: str, data: Dict[str, Any]):
        """Logs an action with associated data."""
        self.logger.info(action, **data)
