#!/bin/bash
# USBridge Raspberry Pi Update Script

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (e.g., sudo /opt/usbridge/deploy/update.sh)"
  exit
fi

echo "Updating USBridge..."

cd /opt/usbridge || exit

echo "Fetching latest tags and branches..."
git fetch --all --tags

# Get the latest tag
LATEST_TAG=$(git describe --tags $(git rev-list --tags --max-count=1) 2>/dev/null)

if [ -z "$LATEST_TAG" ]; then
    LATEST_TAG="None Found"
fi

echo "Please choose the version to update to:"
echo "1) Latest Official Release ($LATEST_TAG)"
echo "2) Development Branch (main)"
read -p "Enter choice [1/2]: " choice

if [ "$choice" == "1" ] && [ "$LATEST_TAG" != "None Found" ]; then
    echo "Checking out Official Release $LATEST_TAG..."
    git checkout tags/$LATEST_TAG
else
    echo "Checking out main branch..."
    git checkout main
    git pull origin main
fi

# Update Python environment
echo "Updating Python dependencies..."
./venv/bin/pip install -r requirements.txt

# Restart service
echo "Restarting USBridge service..."
systemctl restart usbridge

echo "USBridge updated successfully!"
echo "The service should be running. You can check its status with: sudo systemctl status usbridge"
