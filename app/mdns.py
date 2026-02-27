import socket
from zeroconf import ServiceInfo, Zeroconf
from app.logger import app_logger


class MDNSAdvertiser:
    def __init__(self):
        self.zeroconf = None
        self.service_info = None

    def _get_ip_address(self):
        try:
            # Create a dummy socket to get the local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self, port: int = 8000):
        try:
            ip_addr = self._get_ip_address()
            hostname = socket.gethostname()

            # Zeroconf requires the hostname to end with .local.
            if not hostname.endswith(".local"):
                local_hostname = f"{hostname}.local."
            else:
                local_hostname = f"{hostname}."

            self.zeroconf = Zeroconf()

            # Broadcast as an HTTP service
            self.service_info = ServiceInfo(
                "_http._tcp.local.",
                "USBridge Manager._http._tcp.local.",
                addresses=[socket.inet_aton(ip_addr)],
                port=port,
                server=local_hostname,
                properties={"description": "USB over IP Manager"},
            )

            self.zeroconf.register_service(self.service_info)
            app_logger.info(
                f"mDNS active: broadcasting as {local_hostname} on {ip_addr}:{port}"
            )
        except Exception as e:
            app_logger.error(f"Failed to start mDNS advertiser: {e}")

    def stop(self):
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                app_logger.info("mDNS advertiser stopped.")
            except Exception as e:
                app_logger.error(f"Error stopping mDNS advertiser: {e}")


mdns_advertiser = MDNSAdvertiser()
