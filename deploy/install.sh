#!/bin/bash
# USBridge Raspberry Pi Installation Script

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (e.g., sudo ./deploy/install.sh)"
  exit
fi

echo "Installing USBridge..."
cd "$(dirname "$0")/.." || exit

# Load usbip kernel modules
echo "Configuring kernel modules..."
modprobe usbip-core
modprobe usbip-host
echo "usbip-host" > /etc/modules-load.d/usbip.conf

# Install dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y usbip hwdata python3-venv

# Setup directory
echo "Copying application files..."
mkdir -p /opt/usbridge
cp -R ./* /opt/usbridge/
cd /opt/usbridge

# Setup Python environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
cp deploy/usbridge.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable usbridge
systemctl restart usbridge

echo "USBridge installed successfully!"
echo "The service should be running. You can check its status with: sudo systemctl status usbridge"
echo "Access the web interface at: http://$(hostname -I | awk '{print $1}'):8000"
echo "If this is your first time, check your desktop or mDNS at http://usbridge.local:8000"
