FROM python:3.11-slim

# Install required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    openvpn \
    iproute2 \
    dnsutils \
    curl \
    iputils-ping \
    procps \
    && rm -rf /var/lib/apt/lists/*


# Create app directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Run worker
CMD ["python3", "main.py"]
