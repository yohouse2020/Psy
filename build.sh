#!/bin/bash

# Install system dependencies
apt-get update
apt-get install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt

# Check installed packages
echo "=== Installed Python packages ==="
pip list

# Check Python version
echo "=== Python version ==="
python --version
