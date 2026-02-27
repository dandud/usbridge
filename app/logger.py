import logging
from logging.handlers import RotatingFileHandler
import os
import asyncio

LOG_FILE = "usbridge.log"

# Ensure log format covers timestamp, level, and message clearly
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Create rotating file handler (max 5MB, keep 3 backups)
try:
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
    )
except PermissionError:
    # Fallback to local dir if running from restricted location
    file_handler = RotatingFileHandler(
        "usbridge_fallback.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )

file_handler.setFormatter(log_formatter)


class WebSocketLogHandler(logging.Handler):
    """Custom handler to broadcast logs to connected websocket clients"""

    def emit(self, record):
        try:
            from app.api import ws_manager

            msg = self.format(record)
            # Create a task to run the async broadcast without blocking the sync logger
            # Need to get or create event loop because logger can be called from sync endpoints
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    ws_manager.broadcast({"type": "log_change", "log": msg})
                )
            except RuntimeError:
                pass  # No running event loop
        except Exception:
            pass


ws_handler = WebSocketLogHandler()
ws_handler.setFormatter(log_formatter)

# Set up the logger
app_logger = logging.getLogger("usbridge")
app_logger.setLevel(logging.INFO)
app_logger.addHandler(file_handler)
app_logger.addHandler(ws_handler)


def get_recent_logs(num_lines: int = 100) -> list[str]:
    """Reads the last N lines from the log file efficiently."""
    if not os.path.exists(LOG_FILE):
        return []

    # Read last lines using a simple approach.
    # For very large files, a tail -n implementation is better, but a 5MB log is small enough to read lines in memory
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-num_lines:]]
    except Exception as e:
        app_logger.error(f"Failed to read logs: {e}")
        return []


def set_log_level(level_str: str):
    """Update active log level dynamically based on config"""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    level = level_map.get(level_str.upper(), logging.INFO)
    app_logger.setLevel(level)
