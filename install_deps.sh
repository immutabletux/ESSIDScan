#!/usr/bin/env bash
# Install dependencies for WiFi Analyzer on Debian/Ubuntu Linux
set -e

echo "==> Updating package list..."
sudo apt-get update -y

echo "==> Installing wireless-tools (iwlist) and Python3 tkinter..."
sudo apt-get install -y wireless-tools python3-tk python3

echo ""
echo "==> Done! Run the analyzer with:"
echo "    sudo python3 wifi_analyzer.py"
echo ""
echo "Note: Root (sudo) is required for iwlist to perform active scans."
