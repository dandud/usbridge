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
            nicknames = config.get("nicknames", {})
            for d in self.mock_devices:
                if d["busid"] in auto_binds:
                    d["bound"] = True
                if d["busid"] in nicknames and nicknames[d["busid"]]:
                    d["name"] = nicknames[d["busid"]]
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
                # Pre-emptively flush any kernel match_busid ghosts before binding
                subprocess.run(["usbip", "unbind", "-b", busid], capture_output=True)

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
                # We do not enforce check=True here because unbinding a ghost device 
                # might throw a minor CLI error but still successfully flush the kernel.
                subprocess.run(
                    ["usbip", "unbind", "-b", busid], capture_output=True
                )
                success = True
            except Exception as e:
                app_logger.error(f"Failed to execute unbind command for {busid}: {e}")
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

    def force_disconnect_device(self, busid: str) -> bool:
        """Forcefully disconnect a remote client by unbinding and immediately rebinding."""
        if self.is_windows:
            self.unbind_device(busid)
            self.bind_device(busid)
            return True
        else:
            try:
                subprocess.run(["usbip", "unbind", "-b", busid], capture_output=True)
                subprocess.run(
                    ["usbip", "bind", "-b", busid], check=True, capture_output=True
                )
                return True
            except subprocess.CalledProcessError as e:
                app_logger.error(f"Error force disconnecting device {busid}: {e.stderr}")
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

            config = config_store.load()
            nicknames = config.get("nicknames", {})
            if entry in nicknames and nicknames[entry]:
                name = nicknames[entry]

            # On Debian 12, the definitive way to check if a device is bound is to check 
            # if the fundamental device itself (not an intra-interface) is bound to usbip-host
            is_bound = False
            is_attached = False
            driver_link = os.path.join(dev_path, "driver")
            if os.path.islink(driver_link):
                try:
                    driver_target = os.readlink(driver_link)
                    if "usbip-host" in driver_target:
                        is_bound = True
                        
                        # Check if actively attached to a client over the network
                        status_file = os.path.join(dev_path, "usbip_status")
                        if os.path.exists(status_file):
                            try:
                                with open(status_file, "r") as sf:
                                    if sf.read().strip() == "2":
                                        is_attached = True
                            except Exception:
                                pass
                except Exception:
                    pass

            devices.append({"busid": entry, "name": name, "bound": is_bound, "attached": is_attached})

        return devices


usbip_manager = UsbIpManager()
