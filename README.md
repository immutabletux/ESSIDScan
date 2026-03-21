# ESSIDScan — WiFi Network Analyzer

A **desktop GUI application** for scanning and monitoring WiFi networks on **Debian/Ubuntu Linux** using `iwlist`.

Built with **PyQt5** — a proper native desktop GUI with real buttons, progress bars, sortable table, and signal history charts.

![Python 3](https://img.shields.io/badge/Python-3.x-blue)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green)
![Platform](https://img.shields.io/badge/Platform-Debian%20%7C%20Ubuntu-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Live WiFi scanning** via `iwlist` — discovers all nearby networks
- **Auto-scan** mode with configurable interval (2–60 seconds)
- **Network table** with sortable columns:
  - Signal strength (dBm + bars), ESSID, BSSID/MAC
  - Band (2.4 / 5 GHz), Channel, Frequency
  - Security (Open / WEP / WPA / WPA2)
  - Quality %, Max bitrate, Vendor OUI lookup, Last seen
- **Detail panel** — click any network to see:
  - Color-coded signal strength meter
  - Animated quality bar
  - Signal history sparkline chart
  - Full field breakdown (noise, mode, vendor, etc.)
- **Filters** — search by ESSID/BSSID/vendor, filter by band and encryption
- **Dark theme** UI with color-coded signal quality

---

## Requirements

- Debian / Ubuntu Linux
- Python 3
- `python3-pyqt5`
- `wireless-tools` (`iwlist`)

## Install Dependencies

```bash
chmod +x install_deps.sh
./install_deps.sh
```

Or manually:

```bash
sudo apt-get install -y wireless-tools python3 python3-pyqt5
```

## Run

```bash
# Root is required for iwlist to perform active scans
sudo python3 wifi_analyzer.py
```

---

## Screenshot

```
┌─────────────────────────────────────────────────────────────────────┐
│ ⬡ WiFi Network Analyzer   iwlist monitor            2026-03-21      │
├──────────────────────────────────────────────────────────────────────┤
│ Interface: wlan0 │ [Scan] [Auto OFF] every 5s │ [Clear] │ Search…   │
├────────────┬────────────────────┬───────────────────┬───────────────┤
│ Signal     │ ESSID              │ BSSID             │ Security …   │
│ ▂▄▆█ -45  │ HomeNetwork        │ AA:BB:CC:DD:EE:FF │ WPA2         │
│ ▂▄▆· -67  │ CoffeeShop_WiFi    │ 11:22:33:44:55:66 │ WPA2         │
│ ▂▄·· -78  │ <hidden>           │ 77:88:99:AA:BB:CC │ WEP          │
└────────────┴────────────────────┴───────────────────┴───────────────┘
```

---

## Files

| File | Description |
|------|-------------|
| `wifi_analyzer.py` | Main application (GUI + scan logic) |
| `install_deps.sh` | Dependency installer script |
| `wifi_analyzer.desktop` | Desktop launcher entry |

---

## Notes

- Root (`sudo`) is required because `iwlist scan` needs to activate the wireless interface's scanning mode.
- OUI vendor lookup covers common manufacturers; unrecognized OUIs show "Unknown".
- Signal history is tracked per-session (up to 60 readings per network).

## License

MIT
