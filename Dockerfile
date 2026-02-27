FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for usbip
RUN apt-get update && \
    apt-get install -y usbip hwdata kmod && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure Python outputs directly to terminal for Docker logs
ENV PYTHONUNBUFFERED=1

# Application port
EXPOSE 8000

CMD ["python", "main.py"]
