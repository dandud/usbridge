import json
import os
import hashlib
import secrets
from typing import Dict, Any

CONFIG_FILE = "config.json"


def _hash_default(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    )
    return f"{salt}:{key.hex()}"


DEFAULT_CONFIG = {
    "auth_enabled": False,
    "auth_username": "admin",
    "auth_password_hash": _hash_default("password"),
    "log_level": "INFO",
    "app_port": 8000,
    "auto_bind_devices": [],
    "nicknames": {},
}


class ConfigStore:
    """
    Manages the application's global configuration file (JSON), 
    handling loading, saving, and migrating core settings.
    """
    def __init__(self, filepath: str = CONFIG_FILE):
        self.filepath = filepath
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(self.filepath):
            self.save(DEFAULT_CONFIG)

    def load(self) -> Dict[str, Any]:
        """Loads the configuration from disk, applying defaults and migrations if necessary."""
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)

            needs_save = False
            # Migrate plain text password to hash if it exists
            if "auth_password" in data:
                data["auth_password_hash"] = _hash_default(data.pop("auth_password"))
                needs_save = True
            if "app_port" not in data:
                data["app_port"] = 8000
                needs_save = True
            if "auto_bind_devices" not in data:
                data["auto_bind_devices"] = []
                needs_save = True
            if "nicknames" not in data:
                data["nicknames"] = {}
                needs_save = True

            if needs_save:
                self.save(data)

            return data
        except Exception:
            return DEFAULT_CONFIG.copy()

    def save(self, data: Dict[str, Any]) -> bool:
        """Saves current configuration parameters to the persistent JSON file."""
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception:
            return False


config_store = ConfigStore()
