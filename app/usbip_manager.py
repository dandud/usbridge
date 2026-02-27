import platform
import subprocess
import os
from typing import List, Dict, Any
from app.config_store import config_store
from app.logger import app_logger


class UsbIpManager:
    """
    Manages interactions with the local usbip daemon and sysfs for discovering, 
    binding, and unbinding USB devices for network sharing.
    """
    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        # Mock state for Windows testing
        self.mock_devices = [
            {"busid": "1-1", "name": "Logitech USB Mouse (Mock)", "bound": False},
            {"busid": "1-2", "name": "Realtek USB Audio (Mock)", "bound": True},
            {
                "busid": "2-1",
                "name": "SanDisk Cruzer Flash Drive (Mock)",
                "bound": False,
            },
        ]

    def list_devices(self) -> List[Dict[str, Any]]:
        """List local USB devices using sysfs and usbip."""
        if self.is_windows:
            config = config_store.load()
            auto_binds = config.get("auto_bind_devices", [])
            for d in self.mock_devices:
                if d["busid"] in auto_binds:
                    d["bound"] = True
            return self.mock_devices

        # Real Linux implementation using sysfs
        return self._get_sysfs_devices()

    def bind_device(self, busid: str) -> bool:
        """Bind a USB device and save to persistent config."""
        success = False
        if self.is_windows:
            for d in self.mock_devices:
                if d["busid"] == busid:
                    d["bound"] = True
                    success = True
                    break
        else:
            try:
                subprocess.run(
                    ["usbip", "bind", "-b", busid], check=True, capture_output=True
                )
                success = True
            except subprocess.CalledProcessError as e:
                app_logger.error(f"Error binding device {busid}: {e.stderr}")
                return False

        if success:
            config = config_store.load()
            auto_binds = config.get("auto_bind_devices", [])
            if busid not in auto_binds:
                auto_binds.append(busid)
                config["auto_bind_devices"] = auto_binds
                config_store.save(config)
            return True
        return False

    def unbind_device(self, busid: str) -> bool:
        """Unbind a USB device and remove from persistent config."""
        success = False
        if self.is_windows:
            for d in self.mock_devices:
                if d["busid"] == busid:
                    d["bound"] = False
                    success = True
                    break
        else:
            try:
                subprocess.run(
                    ["usbip", "unbind", "-b", busid], check=True, capture_output=True
                )
                success = True
            except subprocess.CalledProcessError as e:
                app_logger.error(f"Error unbinding device {busid}: {e.stderr}")
                return False

        if success:
            config = config_store.load()
            auto_binds = config.get("auto_bind_devices", [])
            if busid in auto_binds:
                auto_binds.remove(busid)
                config["auto_bind_devices"] = auto_binds
                config_store.save(config)
            return True
        return False

    def apply_auto_binds(self):
        """Called on startup to re-bind configured devices."""
        config = config_store.load()
        auto_binds = config.get("auto_bind_devices", [])
        for busid in auto_binds:
            app_logger.info(f"Applying persistent binding for {busid}")
            self.bind_device(busid)

    def _get_sysfs_devices(self) -> List[Dict[str, Any]]:
        """Reads detailed info directly from /sys/bus/usb/devices."""
        devices = []
        base_dir = "/sys/bus/usb/devices"

        if not os.path.exists(base_dir):
            app_logger.warning(
                "sysfs usb directory not found. Returning empty list."
            )
            return devices

        # Get bound items from `usbip list -l` for accurate bound status
        bound_busids = set()
        # Instead of parsing usbip list -l, we check the driver symlink in sysfs
        for entry in os.listdir(base_dir):
            # USB devices usually look like "1-1", "2-1.4", not "usb1"
            if "-" not in entry or entry.startswith("usb"):
                continue

            dev_path = os.path.join(base_dir, entry)

            # Read properties
            def read_prop(name):
                try:
                    with open(os.path.join(dev_path, name), "r") as f:
                        return f.read().strip()
                except Exception:
                    return ""

            manufacturer = read_prop("manufacturer")
            product = read_prop("product")

            # Skip root hubs or items with no meaningful product name
            if not product:
                continue

            name = product
            if manufacturer:
                name = f"{manufacturer} {product}"

            # Check if bound to usbip-host by looking at interface drivers
            is_bound = False
            try:
                # Interfaces are subdirectories like "1-1:1.0"
                for sub_entry in os.listdir(dev_path):
                    if sub_entry.startswith(f"{entry}:"):
                        driver_link = os.path.join(dev_path, sub_entry, "driver")
                        if os.path.islink(driver_link):
                            driver_target = os.readlink(driver_link)
                            if "usbip-host" in driver_target:
                                is_bound = True
                                break
            except Exception:
                pass

            devices.append({"busid": entry, "name": name, "bound": is_bound})

        return devices


usbip_manager = UsbIpManager()
