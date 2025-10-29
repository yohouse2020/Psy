#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y ffmpeg

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check versions
echo "=== Python version ==="
python --version

echo "=== Installed packages ==="
pip list
