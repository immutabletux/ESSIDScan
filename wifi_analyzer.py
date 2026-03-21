#!/usr/bin/env python3
"""
ESSIDscan
Desktop GUI application for Debian Linux using PyQt5 + iwlist.
Run with: sudo python3 wifi_analyzer.py
"""

import sys
import os
import re
import random
import subprocess
from datetime import datetime
from collections import defaultdict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QFrame, QProgressBar, QScrollArea, QSizePolicy,
    QAbstractItemView, QToolBar, QStatusBar, QMessageBox,
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QRect, QPoint,
)
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QPolygon,
)


# ── OUI vendor table ───────────────────────────────────────────────────────────
OUI_VENDORS = {
    "18:D6:C7": "TP-Link",   "A4:2B:B0": "TP-Link",   "EC:08:6B": "TP-Link",
    "8C:59:C3": "Netgear",   "A0:04:60": "Netgear",   "28:80:88": "Netgear",
    "20:E5:2A": "Linksys",   "00:14:BF": "Linksys",
    "00:1E:E5": "Cisco",     "00:17:94": "Cisco",
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi",
    "FC:EC:DA": "Ubiquiti",  "44:D9:E7": "Ubiquiti",
    "04:18:D6": "Apple",     "AC:BC:32": "Apple",     "F0:18:98": "Apple",
    "00:1A:2B": "Intel",     "00:23:14": "Belkin",
}

def oui_vendor(bssid: str) -> str:
    return OUI_VENDORS.get(bssid[:8].upper(), "Unknown")


# ── Signal helpers ─────────────────────────────────────────────────────────────
def dbm_to_quality(dbm: int) -> int:
    return max(0, min(100, 2 * (dbm + 100)))

def signal_label(dbm: int) -> str:
    if dbm >= -50: return "Excellent"
    if dbm >= -65: return "Good"
    if dbm >= -75: return "Fair"
    return "Poor"

def signal_color(dbm: int) -> QColor:
    if dbm >= -50: return QColor("#3fb950")
    if dbm >= -65: return QColor("#79c0ff")
    if dbm >= -75: return QColor("#d29922")
    return QColor("#f85149")


# ── VM / VirtualBox detection ──────────────────────────────────────────────────
def is_virtual_machine() -> bool:
    """Return True when running inside a VM (VirtualBox, VMware, QEMU, etc.)."""
    dmi_paths = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/board_vendor",
    ]
    vm_strings = {"virtualbox", "vmware", "qemu", "kvm", "xen", "hyper-v", "bochs", "innotek"}
    for path in dmi_paths:
        try:
            with open(path) as f:
                val = f.read().strip().lower()
                if any(v in val for v in vm_strings):
                    return True
        except Exception:
            pass
    # Check systemd-detect-virt
    try:
        r = subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip() not in ("none", ""):
            return True
    except Exception:
        pass
    return False


# ── Demo / simulation data ──────────────────────────────────────────────────────
_DEMO_NETS = [
    {"essid": "HomeNetwork_5G",   "bssid": "A4:2B:B0:11:22:33", "channel": 36, "frequency": "5.180 GHz", "encryption": "WPA2", "max_rate": 867.0,  "base_dbm": -48},
    {"essid": "HomeNetwork_2G",   "bssid": "A4:2B:B0:11:22:34", "channel":  6, "frequency": "2.437 GHz", "encryption": "WPA2", "max_rate": 300.0,  "base_dbm": -52},
    {"essid": "CoffeeShop_WiFi",  "bssid": "8C:59:C3:AA:BB:CC", "channel": 11, "frequency": "2.462 GHz", "encryption": "WPA2", "max_rate": 130.0,  "base_dbm": -67},
    {"essid": "DIRECT-Samsung-TV","bssid": "FC:EC:DA:33:44:55", "channel":  1, "frequency": "2.412 GHz", "encryption": "WPA2", "max_rate": 54.0,   "base_dbm": -71},
    {"essid": "Neighbor_Net",     "bssid": "EC:08:6B:66:77:88", "channel": 40, "frequency": "5.200 GHz", "encryption": "WPA",  "max_rate": 300.0,  "base_dbm": -74},
    {"essid": "",                 "bssid": "20:E5:2A:99:AA:BB", "channel":  6, "frequency": "2.437 GHz", "encryption": "WPA2", "max_rate": 54.0,   "base_dbm": -79},
    {"essid": "OldRouter",        "bssid": "00:23:14:CC:DD:EE", "channel":  6, "frequency": "2.437 GHz", "encryption": "WEP",  "max_rate": 54.0,   "base_dbm": -82},
    {"essid": "GuestNetwork",     "bssid": "28:80:88:FF:00:11", "channel": 11, "frequency": "2.462 GHz", "encryption": "Open", "max_rate": 130.0,  "base_dbm": -85},
]

def demo_scan() -> list:
    """Return simulated network list with slightly randomised signal levels."""
    now = datetime.now().strftime("%H:%M:%S")
    nets = []
    for template in _DEMO_NETS:
        dbm = template["base_dbm"] + random.randint(-4, 4)
        freq = template["frequency"]
        band = "5 GHz" if freq.startswith("5") else "2.4 GHz"
        nets.append({
            "essid":      template["essid"],
            "bssid":      template["bssid"],
            "channel":    template["channel"],
            "frequency":  freq + " GHz" if not freq.endswith("GHz") else freq,
            "signal_dbm": dbm,
            "noise_dbm":  None,
            "quality":    dbm_to_quality(dbm),
            "encryption": template["encryption"],
            "max_rate":   template["max_rate"],
            "band":       band,
            "vendor":     oui_vendor(template["bssid"]),
            "last_seen":  now,
        })
    return nets


# ── Interface detection ────────────────────────────────────────────────────────
def get_interfaces() -> list:
    # Most reliable: check /sys/class/net/<iface>/wireless directory existence
    try:
        import os as _os
        sys_ifaces = [
            iface for iface in _os.listdir("/sys/class/net")
            if _os.path.isdir(f"/sys/class/net/{iface}/wireless")
        ]
        if sys_ifaces:
            return sorted(sys_ifaces)
    except Exception:
        pass
    # Fallback: parse iwconfig output
    try:
        r = subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5)
        ifaces = re.findall(r'^(\w+)\s+IEEE', r.stdout, re.MULTILINE)
        if ifaces:
            return ifaces
    except Exception:
        pass
    # Fallback: /proc/net/wireless
    try:
        with open("/proc/net/wireless") as f:
            ifaces = [l.split(":")[0].strip() for l in f.readlines()[2:] if ":" in l]
            if ifaces:
                return ifaces
    except Exception:
        pass
    # Fallback: iw dev
    try:
        r = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=5)
        ifaces = re.findall(r'Interface\s+(\S+)', r.stdout)
        if ifaces:
            return ifaces
    except Exception:
        pass
    return []


# ── iwlist parser ──────────────────────────────────────────────────────────────
def parse_iwlist(output: str) -> list:
    networks = []
    for cell in re.split(r'(?=Cell \d+ - Address:)', output):
        if "Address:" not in cell:
            continue
        n = {}

        m = re.search(r'Address:\s*([0-9A-Fa-f:]{17})', cell)
        n["bssid"] = m.group(1).upper() if m else "Unknown"

        m = re.search(r'ESSID:"([^"]*)"', cell)
        n["essid"] = m.group(1) if m else ""

        m = re.search(r'Frequency:([\d.]+)\s*GHz', cell)
        n["frequency"] = m.group(1) + " GHz" if m else "?"

        m = re.search(r'Channel:(\d+)', cell) or re.search(r'\(Channel (\d+)\)', cell)
        n["channel"] = int(m.group(1)) if m else 0

        m = re.search(r'Signal level=(-?\d+)\s*dBm', cell)
        if m:
            n["signal_dbm"] = int(m.group(1))
        else:
            m = re.search(r'Signal level=(\d+)/100', cell)
            n["signal_dbm"] = int(m.group(1)) - 100 if m else -100

        m = re.search(r'Noise level=(-?\d+)\s*dBm', cell)
        n["noise_dbm"] = int(m.group(1)) if m else None

        n["quality"] = dbm_to_quality(n["signal_dbm"])

        wpa2 = re.search(r'IE:.*WPA2|IE:.*RSN', cell)
        wpa  = re.search(r'IE:.*WPA', cell)
        enc  = re.search(r'Encryption key:(on|off)', cell)
        if wpa2:              n["encryption"] = "WPA2"
        elif wpa:             n["encryption"] = "WPA"
        elif enc and enc.group(1) == "on": n["encryption"] = "WEP"
        else:                 n["encryption"] = "Open"

        rates = re.findall(r'(\d+\.?\d*) Mb/s', cell)
        n["max_rate"] = max((float(r) for r in rates), default=0)

        n["band"]      = "5 GHz" if n["frequency"].startswith("5") else "2.4 GHz"
        n["vendor"]    = oui_vendor(n["bssid"])
        n["last_seen"] = datetime.now().strftime("%H:%M:%S")
        networks.append(n)
    return networks


# ── Sortable numeric table item ────────────────────────────────────────────────
class NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by a numeric UserRole value."""
    def __lt__(self, other):
        self_val  = self.data(Qt.UserRole)
        other_val = other.data(Qt.UserRole)
        if self_val is None or other_val is None:
            return super().__lt__(other)
        return self_val < other_val


# ── Signal bar widget ──────────────────────────────────────────────────────────
class SignalBarsWidget(QWidget):
    def __init__(self, dbm: int = -100, parent=None):
        super().__init__(parent)
        self.dbm = dbm
        self.setFixedSize(36, 22)

    def set_dbm(self, dbm: int):
        self.dbm = dbm
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        quality = dbm_to_quality(self.dbm)
        color   = signal_color(self.dbm)
        dim     = QColor("#3a3f47")
        bar_w, gap = 6, 3
        heights = [6, 10, 14, 20]
        thresholds = [25, 50, 75, 100]
        for i, (h, thresh) in enumerate(zip(heights, thresholds)):
            x = i * (bar_w + gap)
            y = self.height() - h
            c = color if quality >= thresh else dim
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, y, bar_w, h, 2, 2)


# ── Sparkline widget ───────────────────────────────────────────────────────────
class SparklineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        from PyQt5.QtCore import QSize
        return QSize(self.minimumWidth(), 60)

    def set_history(self, history: list):
        self.history = list(history)
        self.update()

    def paintEvent(self, event):
        if len(self.history) < 2:
            p = QPainter(self)
            p.setPen(QColor("#484f58"))
            p.drawText(self.rect(), Qt.AlignCenter, "No history yet")
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad = 6

        mn = min(self.history) - 3
        mx = max(self.history) + 3
        rng = mx - mn or 1

        def px(i):
            return pad + int(i / (len(self.history) - 1) * (w - 2 * pad))

        def py(v):
            return pad + int((1 - (v - mn) / rng) * (h - 2 * pad))

        pts = [QPoint(px(i), py(v)) for i, v in enumerate(self.history)]

        # Fill area
        last_dbm = self.history[-1]
        base_color = signal_color(last_dbm)
        fill = QColor(base_color)
        fill.setAlpha(40)

        poly_pts = [QPoint(pts[0].x(), h)] + pts + [QPoint(pts[-1].x(), h)]
        poly = QPolygon(poly_pts)
        p.setBrush(QBrush(fill))
        p.setPen(Qt.NoPen)
        p.drawPolygon(poly)

        # Line
        pen = QPen(base_color, 2)
        p.setPen(pen)
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])

        # End dot
        p.setBrush(QBrush(base_color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(pts[-1], 4, 4)

        # dBm labels
        p.setPen(QColor("#8b949e"))
        p.setFont(QFont("Monospace", 7))
        p.drawText(QRect(0, 0, w, 14), Qt.AlignRight, f"{mx:.0f} dBm")
        p.drawText(QRect(0, h - 14, w, 14), Qt.AlignRight, f"{mn:.0f} dBm")


# ── Scan worker thread ─────────────────────────────────────────────────────────
class ScanWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, iface: str):
        super().__init__()
        self.iface = iface

    def run(self):
        try:
            r = subprocess.run(
                ["iwlist", self.iface, "scan"],
                capture_output=True, text=True, timeout=20,
            )
            out = r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            self.error.emit("Scan timed out.")
            return
        except FileNotFoundError:
            self.error.emit("iwlist not found. Install: sudo apt install wireless-tools")
            return
        except Exception as ex:
            self.error.emit(str(ex))
            return

        if "Interface doesn't support scanning" in out:
            self.error.emit(f"{self.iface} does not support scanning.")
            return
        if "No such device" in out:
            self.error.emit(
                f"Interface '{self.iface}' not found.\n\n"
                "Select a valid wireless interface from the dropdown."
            )
            return
        if "Network is down" in out:
            self.error.emit(
                f"Interface '{self.iface}' is down.\n\n"
                f"Try: sudo ip link set {self.iface} up"
            )
            return

        nets = parse_iwlist(out)
        if not nets and r.returncode != 0:
            self.error.emit(
                f"iwlist returned no results.\n\nRaw output:\n{out[:300]}"
            )
            return
        self.finished.emit(nets)


# ── Demo scan worker ───────────────────────────────────────────────────────────
class DemoScanWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def run(self):
        import time
        time.sleep(0.8)          # simulate scan delay
        self.finished.emit(demo_scan())


# ── Detail panel ───────────────────────────────────────────────────────────────
class DetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = {}
        self._build()

    def _build(self):
        self.setMinimumWidth(300)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Color accent bar
        self.accent_bar = QFrame()
        self.accent_bar.setFixedHeight(4)
        self.accent_bar.setStyleSheet("background:#58a6ff;")
        root.addWidget(self.accent_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        self.layout_inner = QVBoxLayout(container)
        self.layout_inner.setContentsMargins(16, 16, 16, 16)
        self.layout_inner.setSpacing(12)

        # Placeholder
        self.placeholder = QLabel("Select a network\nto view details")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color:#484f58; font-size:13px;")
        self.layout_inner.addWidget(self.placeholder)
        self.layout_inner.addStretch()

    def clear(self):
        while self.layout_inner.count():
            item = self.layout_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.placeholder = QLabel("Select a network\nto view details")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color:#484f58; font-size:13px;")
        self.layout_inner.addWidget(self.placeholder)
        self.layout_inner.addStretch()

    def show_network(self, n: dict, history: list):
        # Clear old content
        while self.layout_inner.count():
            item = self.layout_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dbm   = n["signal_dbm"]
        color = signal_color(dbm)
        self.accent_bar.setStyleSheet(f"background:{color.name()};")

        # SSID
        essid = n["essid"] or "<hidden>"
        lbl_ssid = QLabel(essid)
        lbl_ssid.setStyleSheet("font-size:16px; font-weight:bold; color:#e6edf3;")
        lbl_ssid.setWordWrap(True)
        self.layout_inner.addWidget(lbl_ssid)

        lbl_bssid = QLabel(n["bssid"])
        lbl_bssid.setStyleSheet("font-family:monospace; font-size:11px; color:#8b949e;")
        self.layout_inner.addWidget(lbl_bssid)

        # Signal strength row
        sig_frame = QFrame()
        sig_frame.setStyleSheet("background:#1c2128; border-radius:8px;")
        sig_layout = QHBoxLayout(sig_frame)
        sig_layout.setContentsMargins(14, 10, 14, 10)

        bars = SignalBarsWidget(dbm)
        bars.setFixedSize(44, 30)
        sig_layout.addWidget(bars)

        dbm_lbl = QLabel(f"{dbm} dBm")
        dbm_lbl.setStyleSheet(f"font-size:24px; font-weight:bold; color:{color.name()};")
        sig_layout.addWidget(dbm_lbl)

        qlbl = QLabel(signal_label(dbm))
        qlbl.setStyleSheet(f"font-size:12px; color:{color.name()};")
        sig_layout.addWidget(qlbl)
        sig_layout.addStretch()
        self.layout_inner.addWidget(sig_frame)

        # Quality progress bar
        q_row = QVBoxLayout()
        q_row.setSpacing(3)
        q_lbl = QLabel(f"Signal Quality: {n['quality']}%")
        q_lbl.setStyleSheet("font-size:11px; color:#8b949e;")
        q_row.addWidget(q_lbl)

        qbar = QProgressBar()
        qbar.setValue(n["quality"])
        qbar.setTextVisible(False)
        qbar.setFixedHeight(8)
        qbar.setStyleSheet(f"""
            QProgressBar {{
                background:#21262d; border-radius:4px; border:none;
            }}
            QProgressBar::chunk {{
                background:{color.name()}; border-radius:4px;
            }}
        """)
        q_row.addWidget(qbar)
        q_widget = QWidget()
        q_widget.setLayout(q_row)
        self.layout_inner.addWidget(q_widget)

        # Divider
        self.layout_inner.addWidget(self._divider())

        # Details grid
        fields = [
            ("Band",      n["band"]),
            ("Channel",   str(n["channel"])),
            ("Frequency", n["frequency"]),
            ("Security",  n["encryption"]),
            ("Max Rate",  f"{int(n['max_rate'])} Mbps" if n["max_rate"] else "?"),
            ("Vendor",    n["vendor"]),
            ("Last Seen", n["last_seen"]),
        ]
        if n["noise_dbm"] is not None:
            fields.insert(3, ("Noise", f"{n['noise_dbm']} dBm"))

        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setSpacing(6)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        for label, value in fields:
            row = QHBoxLayout()
            l = QLabel(label)
            l.setFixedWidth(80)
            l.setStyleSheet("font-size:11px; color:#8b949e;")
            v = QLabel(value)
            v.setStyleSheet("font-size:11px; font-family:monospace; color:#e6edf3;")
            v.setWordWrap(True)
            row.addWidget(l)
            row.addWidget(v, 1)
            w = QWidget()
            w.setLayout(row)
            grid_layout.addWidget(w)

        self.layout_inner.addWidget(grid_widget)

        # Sparkline
        if len(history) >= 2:
            self.layout_inner.addWidget(self._divider())
            spark_lbl = QLabel("Signal History")
            spark_lbl.setStyleSheet("font-size:11px; color:#8b949e;")
            self.layout_inner.addWidget(spark_lbl)

            spark = SparklineWidget()
            spark.set_history(history)
            self.layout_inner.addWidget(spark)

        self.layout_inner.addStretch()

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color:#30363d;")
        return line


# ── Main window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    COLUMNS = [
        ("signal",     "Signal",      90),
        ("essid",      "ESSID",      180),
        ("bssid",      "BSSID",      150),
        ("band",       "Band",        70),
        ("channel",    "CH",          45),
        ("encryption", "Security",    80),
        ("quality",    "Quality",     80),
        ("max_rate",   "Max Rate",    80),
        ("vendor",     "Vendor",     110),
        ("last_seen",  "Last Seen",   75),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESSIDscan")
        self.resize(1280, 780)
        self.setMinimumSize(900, 600)

        self.networks  = {}
        self.history   = defaultdict(list)
        self._worker   = None
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._start_scan)

        self._no_iface_warning = False
        self._demo_mode = False
        self._apply_stylesheet()
        self._build_ui()
        self._check_root()

    # ── Stylesheet ─────────────────────────────────────────────────────────────
    def _apply_stylesheet(self):
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background: #0d1117;
            color: #e6edf3;
            font-family: 'Segoe UI', 'Ubuntu', sans-serif;
            font-size: 12px;
        }
        QToolBar {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            spacing: 4px;
            padding: 4px 8px;
        }
        QToolBar QLabel {
            color: #8b949e;
            font-size: 11px;
        }
        QPushButton {
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 5px 14px;
            font-size: 12px;
        }
        QPushButton:hover  { background: #30363d; border-color: #58a6ff; }
        QPushButton:pressed { background: #161b22; }
        QPushButton#btn_scan {
            background: #1f6feb;
            color: #ffffff;
            border: none;
            font-weight: bold;
        }
        QPushButton#btn_scan:hover  { background: #388bfd; }
        QPushButton#btn_scan:pressed { background: #1158c7; }
        QPushButton#btn_demo {
            background: #161b22;
            color: #8b949e;
            border: 1px solid #30363d;
            font-weight: bold;
        }
        QPushButton#btn_demo:hover   { background: #21262d; color: #79c0ff; border-color: #79c0ff; }
        QPushButton#btn_demo:checked {
            background: #0d2340;
            color: #79c0ff;
            border: 1px solid #79c0ff;
        }
        QPushButton#btn_auto_on {
            background: #1a3a1a;
            color: #3fb950;
            border: 1px solid #3fb950;
            font-weight: bold;
        }
        QPushButton#btn_auto_on:hover { background: #1f4a1f; }
        QPushButton#btn_clear {
            background: #2d1117;
            color: #f85149;
            border: 1px solid #f85149;
        }
        QPushButton#btn_clear:hover { background: #3d1a1a; }
        QComboBox {
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 4px 8px;
            min-width: 90px;
        }
        QComboBox:hover { border-color: #58a6ff; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox::down-arrow { image: none; border: none; }
        QComboBox QAbstractItemView {
            background: #161b22;
            color: #e6edf3;
            selection-background-color: #1f6feb;
            border: 1px solid #30363d;
        }
        QLineEdit {
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 4px 10px;
        }
        QLineEdit:focus { border-color: #58a6ff; }
        QSpinBox {
            background: #21262d;
            color: #e6edf3;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 4px 6px;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background: #30363d;
            border: none;
            width: 16px;
        }
        QTableWidget {
            background: #161b22;
            color: #e6edf3;
            gridline-color: #21262d;
            border: none;
            font-size: 12px;
            selection-background-color: #1f6feb;
        }
        QTableWidget::item { padding: 4px 8px; border: none; }
        QTableWidget::item:hover { background: #21262d; }
        QTableWidget::item:selected { background: #1f6feb; color: #ffffff; }
        QHeaderView::section {
            background: #1c2128;
            color: #8b949e;
            border: none;
            border-right: 1px solid #30363d;
            border-bottom: 1px solid #30363d;
            padding: 6px 8px;
            font-size: 11px;
            font-weight: bold;
        }
        QHeaderView::section:hover { background: #21262d; color: #e6edf3; }
        QScrollBar:vertical {
            background: #0d1117;
            width: 8px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background: #30363d;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background: #484f58; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal {
            background: #0d1117;
            height: 8px;
            border: none;
        }
        QScrollBar::handle:horizontal {
            background: #30363d;
            border-radius: 4px;
            min-width: 20px;
        }
        QScrollBar::handle:horizontal:hover { background: #484f58; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QStatusBar {
            background: #161b22;
            color: #8b949e;
            border-top: 1px solid #30363d;
            font-size: 11px;
            padding: 0 8px;
        }
        QSplitter::handle { background: #30363d; width: 1px; }
        QFrame#detail_panel {
            background: #161b22;
            border-left: 1px solid #30363d;
        }
        """)

    # ── UI construction ─────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        # Interface
        tb.addWidget(QLabel("  Interface:"))
        self.iface_combo = QComboBox()
        ifaces = get_interfaces()
        self._is_vm = is_virtual_machine()
        if ifaces:
            self.iface_combo.addItems(ifaces)
        else:
            self.iface_combo.addItem("demo")
            self._no_iface_warning = True
            self._demo_mode = True
        self.iface_combo.setFixedWidth(120)
        tb.addWidget(self.iface_combo)

        # Demo mode toggle button (visible always, active when no real iface)
        self.btn_demo = QPushButton("  Demo OFF")
        self.btn_demo.setObjectName("btn_demo")
        self.btn_demo.setFixedHeight(30)
        self.btn_demo.setCheckable(True)
        self.btn_demo.setChecked(self._demo_mode)
        self.btn_demo.setText("  Demo ON" if self._demo_mode else "  Demo OFF")
        self.btn_demo.toggled.connect(self._toggle_demo)
        tb.addWidget(self.btn_demo)

        tb.addSeparator()

        # Scan
        self.btn_scan = QPushButton("  Scan")
        self.btn_scan.setObjectName("btn_scan")
        self.btn_scan.setFixedHeight(30)
        self.btn_scan.clicked.connect(self._start_scan)
        tb.addWidget(self.btn_scan)

        # Auto
        self.btn_auto = QPushButton("  Auto Scan")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setFixedHeight(30)
        self.btn_auto.toggled.connect(self._toggle_auto)
        tb.addWidget(self.btn_auto)

        tb.addWidget(QLabel("  every"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(2, 120)
        self.spin_interval.setValue(10)
        self.spin_interval.setSuffix(" s")
        self.spin_interval.setFixedWidth(70)
        self.spin_interval.valueChanged.connect(self._update_auto_interval)
        tb.addWidget(self.spin_interval)

        tb.addSeparator()

        # Clear
        self.btn_clear = QPushButton("  Clear")
        self.btn_clear.setObjectName("btn_clear")
        self.btn_clear.setFixedHeight(30)
        self.btn_clear.clicked.connect(self._clear)
        tb.addWidget(self.btn_clear)

        tb.addSeparator()

        # Filters
        tb.addWidget(QLabel("  Band:"))
        self.combo_band = QComboBox()
        self.combo_band.addItems(["All", "2.4 GHz", "5 GHz"])
        self.combo_band.setFixedWidth(80)
        self.combo_band.currentIndexChanged.connect(self._refresh_table)
        tb.addWidget(self.combo_band)

        tb.addWidget(QLabel("  Security:"))
        self.combo_enc = QComboBox()
        self.combo_enc.addItems(["All", "Open", "WEP", "WPA", "WPA2"])
        self.combo_enc.setFixedWidth(75)
        self.combo_enc.currentIndexChanged.connect(self._refresh_table)
        tb.addWidget(self.combo_enc)

        tb.addWidget(QLabel("  Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("ESSID / BSSID / Vendor…")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._refresh_table)
        tb.addWidget(self.search_box)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.lbl_count = QLabel("0 networks")
        self.lbl_count.setStyleSheet("color:#79c0ff; font-weight:bold; margin-right:12px;")
        tb.addWidget(self.lbl_count)

    def _build_central(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: network table ──────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in self.COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            self.table.styleSheet() +
            "QTableWidget { alternate-background-color: #1c2128; }"
        )

        for i, (_, _, w) in enumerate(self.COLUMNS):
            self.table.setColumnWidth(i, w)

        self.table.horizontalHeader().setSectionResizeMode(
            self._col("essid"), QHeaderView.Stretch
        )

        self.table.itemSelectionChanged.connect(self._on_select)
        left_layout.addWidget(self.table)
        splitter.addWidget(left)

        # ── Right: detail panel ──────────────────────────────────────────────
        self.detail = DetailPanel()
        self.detail.setObjectName("detail_panel")
        self.detail.setMinimumWidth(300)
        splitter.addWidget(self.detail)

        splitter.setSizes([900, 360])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.setCentralWidget(splitter)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self.status_label = QLabel("Ready. Press Scan to start.")
        sb.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)       # indeterminate
        self.progress_bar.setFixedWidth(140)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #21262d;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background: #58a6ff;
                border-radius: 5px;
            }
        """)
        sb.addPermanentWidget(self.progress_bar)

        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("color:#484f58; font-family:monospace;")
        sb.addPermanentWidget(self.clock_label)

        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)
        self._tick_clock()

    def _tick_clock(self):
        self.clock_label.setText(datetime.now().strftime("  %Y-%m-%d  %H:%M:%S  "))

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def _col(self, key: str) -> int:
        return next(i for i, (k, _, _) in enumerate(self.COLUMNS) if k == key)

    def _check_root(self):
        if self._demo_mode:
            vm_note = " (VirtualBox detected — USB WiFi passthrough required for live scan)" if self._is_vm else ""
            self._set_status(
                f"DEMO MODE — simulated networks{vm_note}",
                "#79c0ff"
            )
            return
        if self._no_iface_warning:
            self._set_status(
                "No wireless interfaces found. "
                "Ensure your WiFi adapter is connected and drivers are loaded.",
                "#f85149"
            )
            return
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            self._set_status(
                "Not running as root — scan may fail. Try: sudo python3 wifi_analyzer.py",
                "#d29922"
            )

    def _set_status(self, msg: str, color: str = "#8b949e"):
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color:{color};")

    # ── Scanning ────────────────────────────────────────────────────────────────
    def _toggle_demo(self, checked: bool):
        self._demo_mode = checked
        self.btn_demo.setText("  Demo ON" if checked else "  Demo OFF")
        if checked:
            if not self.iface_combo.findText("demo") >= 0:
                self.iface_combo.insertItem(0, "demo")
            self.iface_combo.setCurrentText("demo")
            self._set_status("DEMO MODE — simulated networks", "#79c0ff")
        else:
            # Re-populate real interfaces
            ifaces = get_interfaces()
            self.iface_combo.clear()
            if ifaces:
                self.iface_combo.addItems(ifaces)
                self._no_iface_warning = False
                self._check_root()
            else:
                self.iface_combo.addItem("demo")
                self._demo_mode = True
                self.btn_demo.setChecked(True)
                self._set_status("No real interfaces found — staying in Demo mode.", "#f85149")

    def _start_scan(self):
        if self._worker and self._worker.isRunning():
            return
        iface = self.iface_combo.currentText()
        if self._demo_mode or iface == "demo":
            self.btn_scan.setEnabled(False)
            self.btn_scan.setText("  Scanning…")
            self.progress_bar.setVisible(True)
            self._set_status("Demo scan running…", "#79c0ff")
            self._worker = DemoScanWorker()
            self._worker.finished.connect(self._scan_done)
            self._worker.error.connect(self._scan_error)
            self._worker.start()
            return
        if not iface:
            QMessageBox.warning(
                self, "No Interface",
                "No wireless interface found.\n\n"
                "Enable Demo Mode or connect a WiFi adapter."
            )
            return
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("  Scanning…")
        self.progress_bar.setVisible(True)
        self._set_status(f"Scanning {iface}…", "#d29922")

        self._worker = ScanWorker(iface)
        self._worker.finished.connect(self._scan_done)
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, nets: list):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("  Scan")

        for n in nets:
            bssid = n["bssid"]
            self.networks[bssid] = n
            self.history[bssid].append(n["signal_dbm"])
            if len(self.history[bssid]) > 60:
                self.history[bssid].pop(0)

        self._refresh_table()
        visible = self._visible_networks()
        demo_tag = "  [DEMO]" if self._demo_mode else ""
        self._set_status(
            f"Scan complete{demo_tag} — {len(nets)} networks found  |  {len(self.networks)} total tracked",
            "#79c0ff" if self._demo_mode else "#3fb950"
        )
        self.lbl_count.setText(f"{len(visible)} networks")

        # Refresh detail if selected network was updated
        sel = self.table.selectedItems()
        if sel:
            row = self.table.row(sel[0])
            bssid_item = self.table.item(row, self._col("bssid"))
            if bssid_item:
                bssid = bssid_item.text()
                if bssid in self.networks:
                    self.detail.show_network(
                        self.networks[bssid], self.history[bssid]
                    )

    def _scan_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("  Scan")
        self._set_status(f"Error: {msg}", "#f85149")
        QMessageBox.critical(self, "Scan Error", msg)

    def _update_auto_interval(self, value: int):
        if self._auto_timer.isActive():
            self._auto_timer.setInterval(value * 1000)

    def _toggle_auto(self, checked: bool):
        if checked:
            self.btn_auto.setText("  Auto: ON")
            self.btn_auto.setObjectName("btn_auto_on")
            self.btn_auto.setStyleSheet("""
                QPushButton {
                    background:#1a3a1a; color:#3fb950;
                    border:1px solid #3fb950; border-radius:6px;
                    padding:5px 14px; font-weight:bold;
                }
                QPushButton:hover { background:#1f4a1f; }
            """)
            self._auto_timer.start(self.spin_interval.value() * 1000)
            self._start_scan()
        else:
            self.btn_auto.setText("  Auto Scan")
            self.btn_auto.setStyleSheet("")
            self._auto_timer.stop()

    def _clear(self):
        self.networks.clear()
        self.history.clear()
        self.table.setRowCount(0)
        self.detail.clear()
        self.lbl_count.setText("0 networks")
        self._set_status("Cleared.", "#8b949e")

    # ── Table ────────────────────────────────────────────────────────────────────
    def _visible_networks(self) -> list:
        nets = list(self.networks.values())
        band = self.combo_band.currentText()
        enc  = self.combo_enc.currentText()
        txt  = self.search_box.text().lower()
        if band != "All":
            nets = [n for n in nets if n["band"] == band]
        if enc != "All":
            nets = [n for n in nets if n["encryption"] == enc]
        if txt:
            nets = [n for n in nets
                    if txt in n["essid"].lower()
                    or txt in n["bssid"].lower()
                    or txt in n["vendor"].lower()]
        return nets

    def _refresh_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        nets = self._visible_networks()
        self.lbl_count.setText(f"{len(nets)} networks")

        for n in nets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 36)

            dbm   = n["signal_dbm"]
            color = signal_color(dbm)

            # Signal column: custom widget with bars + dBm text
            sig_widget = QWidget()
            sig_layout = QHBoxLayout(sig_widget)
            sig_layout.setContentsMargins(8, 2, 4, 2)
            sig_layout.setSpacing(6)
            bars = SignalBarsWidget(dbm)
            sig_layout.addWidget(bars)
            dbm_lbl = QLabel(f"{dbm} dBm")
            dbm_lbl.setStyleSheet(f"color:{color.name()}; font-size:11px; font-family:monospace;")
            sig_layout.addWidget(dbm_lbl)
            self.table.setCellWidget(row, self._col("signal"), sig_widget)

            # Quality column: progress bar
            qbar = QProgressBar()
            qbar.setValue(n["quality"])
            qbar.setTextVisible(True)
            qbar.setFormat(f"{n['quality']}%")
            qbar.setFixedHeight(16)
            qbar.setStyleSheet(f"""
                QProgressBar {{
                    background:#21262d; border-radius:3px; border:none;
                    color:#e6edf3; font-size:10px; text-align:center;
                    margin:8px 6px;
                }}
                QProgressBar::chunk {{
                    background:{color.name()}; border-radius:3px;
                }}
            """)
            self.table.setCellWidget(row, self._col("quality"), qbar)

            # Text columns
            text_cols = {
                "essid":      n["essid"] or "<hidden>",
                "bssid":      n["bssid"],
                "band":       n["band"],
                "encryption": n["encryption"],
                "max_rate":   f"{int(n['max_rate'])} Mbps" if n["max_rate"] else "?",
                "vendor":     n["vendor"],
                "last_seen":  n["last_seen"],
            }

            enc_colors = {
                "Open": "#f85149", "WEP": "#d29922",
                "WPA": "#79c0ff", "WPA2": "#3fb950",
            }

            for key, val in text_cols.items():
                item = QTableWidgetItem(val)
                if key == "encryption":
                    item.setForeground(QColor(enc_colors.get(val, "#e6edf3")))
                elif key == "essid":
                    item.setFont(QFont("", 12, QFont.Bold))
                elif key in ("bssid",):
                    item.setFont(QFont("Monospace", 10))
                self.table.setItem(row, self._col(key), item)

            # Sortable numeric item for signal column (NumericItem sorts by UserRole)
            sig_item = NumericItem()
            sig_item.setData(Qt.UserRole, dbm)
            self.table.setItem(row, self._col("signal"), sig_item)
            self.table.setCellWidget(row, self._col("signal"), sig_widget)

            # Sortable numeric item for channel column
            ch_item = NumericItem()
            ch_item.setData(Qt.UserRole, n["channel"])
            ch_item.setText(str(n["channel"]))
            self.table.setItem(row, self._col("channel"), ch_item)

        self.table.setSortingEnabled(True)

    def _on_select(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = self.table.row(sel[0])
        bssid_item = self.table.item(row, self._col("bssid"))
        if not bssid_item:
            return
        bssid = bssid_item.text()
        if bssid in self.networks:
            self.detail.show_network(self.networks[bssid], self.history[bssid])


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ESSIDscan")
    app.setOrganizationName("immutabletux")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
