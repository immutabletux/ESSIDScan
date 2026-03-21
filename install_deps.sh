#!/usr/bin/env bash
# Install dependencies for ESSIDscan on Debian/Ubuntu Linux
set -e

echo "==> Updating package list..."
sudo apt-get update -y

echo "==> Installing wireless-tools (iwlist)..."
sudo apt-get install -y wireless-tools

echo "==> Installing Python3 and PyQt5..."
sudo apt-get install -y python3 python3-pyqt5

echo ""
echo "==> All dependencies installed."
echo ""
echo "Run the analyzer with:"
echo "    sudo python3 wifi_analyzer.py"
echo ""
echo "Note: Root (sudo) is required for iwlist to perform active scans."
