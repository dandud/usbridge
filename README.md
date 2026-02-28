<div align="center">
  <img src="static/usbridge_logo.png" alt="USBridge Logo" height="120">
  <h1>USBridge</h1>
  <p><b>A web-based USB over IP (USB/IP) manager for Linux and Raspberry Pi.</b></p>
</div>

---

## Overview
USBridge is a Python application that provides a web interface for the Linux `usbip` utility. 

It allows you to bind local USB devices and expose them across your local network so they can be accessed natively by other computers.

## Features
* **Web Dashboard**: View, bind, and unbind USB devices from a browser window.
* **Hardware Auto-Discovery**: Direct indexing via `/sys/bus/usb/devices`.
* **Persistent Bindings**: Configurable auto-start bindings when the server reboots.
* **Network Discovery**: Advertises via mDNS (`usbridge.local`).
* **Real-time Updates**: WebSockets push device state changes and service logs to the dashboard.
* **Security**: Optional password authentication utilizing SHA256 hashed storage.
* **Connection Snippets**: The UI generates the necessary client connection commands for copy-pasting for both Linux (`usbip`) and Windows (`usbipd-win`).
* **Custom Device Nicknames**: Override clunky hardware strings with memorable aliases (e.g., "Home Assistant Zigbee") persistently.
* **Force-Disconnect**: Instantly sever stuck remote client socket connections right from the dashboard with a single click.

## Installation (Raspberry Pi / Linux)

For an automated setup that installs dependencies, prepares the virtual environment, and configures USBridge to run automatically on startup via `systemd`:

### Quick Install (One-Liner)
You can download and run the installer in a single command:
```bash
git clone https://github.com/dandud/usbridge.git && cd usbridge && sudo chmod +x deploy/install.sh && sudo ./deploy/install.sh
```

**What the install script does:**
1. Loads the `usbip-core` and `usbip-host` kernel modules.
2. Installs required system packages (`usbip`, `hwdata`, `python3-venv`).
3. Sets up a local Python virtual environment and installs PIP dependencies.
4. Registers and starts `usbridge.service` using `systemd`.

### Over-The-Air Updates
Because USBridge configuration runs entirely off of untracked files (`config.json` and persistent bindings), you can safely pull down the newest repo changes anytime without overriding your passwords or port configs.

To update an existing installation to the newest code on GitHub (or jump between Official Releases and the Main testing branch), run:
```bash
sudo chmod +x /opt/usbridge/deploy/update.sh
sudo /opt/usbridge/deploy/update.sh
```

## Docker Deployment (Alternative)

To run USBridge in an isolated container environment utilizing Docker Compose, you can utilize the provided configuration logic.

**Prerequisites:**
Docker requires your host Linux machine to load the `usbip` kernel modules beforehand since the container connects natively directly to them. Run:
```bash
sudo modprobe usbip-core
sudo modprobe usbip-host
```

**Starting the Container:**
Initialize the data files before launching so Docker mounts them natively as target files instead of new directories:
```bash
touch config.json usbridge.log
docker-compose up -d --build
```
*(Note: the container image requires `privileged` system mode and host networking to appropriately bridge `/sys/bus/usb` into the application network.)*

## Manual Setup & Development

To run the application manually or develop on a non-Linux system (where USBIP bindings are mocked for testing scenarios):

1. **Install Python Requirements:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# (Optional) For running the test suite:
pip install -r requirements-dev.txt
pytest
```

2. **Run the Server:**
```bash
python main.py
```

3. Navigate your browser to `http://localhost:8000` or `http://usbridge.local:8000` (if mDNS is supported on your network).

## Configuration
The server automatically generates a `config.json` upon its first startup. You can modify this file to change:
* The web server port (default: `8000`).
* Authentication requirements (enable/disable, and set initial passwords).
* A persistent list of auto-bind devices (stored as bus IDs).

## License
This application is licensed under the **GNU General Public License v3.0 (GPLv3)**. Please see the [LICENSE](LICENSE) file for full details.
