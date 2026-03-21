#!/usr/bin/env python3
"""
WiFi Network Analyzer - iwlist ESSID/BSSID Monitor
A desktop GUI application for scanning and monitoring WiFi networks on Debian Linux.
Requires: python3-tk, wireless-tools (iwlist)
Run with: sudo python3 wifi_analyzer.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import subprocess
import threading
import re
import time
import os
import sys
from datetime import datetime
from collections import defaultdict


# ── Color palette ──────────────────────────────────────────────────────────────
BG_DARK       = "#0d1117"
BG_PANEL      = "#161b22"
BG_CARD       = "#1c2128"
BG_HOVER      = "#21262d"
ACCENT_BLUE   = "#58a6ff"
ACCENT_GREEN  = "#3fb950"
ACCENT_YELLOW = "#d29922"
ACCENT_RED    = "#f85149"
ACCENT_PURPLE = "#bc8cff"
ACCENT_CYAN   = "#79c0ff"
TEXT_PRIMARY  = "#e6edf3"
TEXT_MUTED    = "#8b949e"
TEXT_DIM      = "#484f58"
BORDER        = "#30363d"


def get_interfaces():
    """Return a list of wireless interface names."""
    try:
        result = subprocess.run(
            ["iwconfig"],
            capture_output=True, text=True, timeout=5
        )
        ifaces = re.findall(r'^(\w+)\s+IEEE', result.stdout, re.MULTILINE)
        if ifaces:
            return ifaces
    except Exception:
        pass
    # fallback: read /proc/net/wireless
    try:
        with open("/proc/net/wireless") as f:
            lines = f.readlines()[2:]
        return [l.split(":")[0].strip() for l in lines if ":" in l]
    except Exception:
        pass
    return ["wlan0"]


def parse_iwlist(output: str) -> list[dict]:
    """Parse raw iwlist scan output into a list of network dicts."""
    networks = []
    cells = re.split(r'(?=Cell \d+ - Address:)', output)
    for cell in cells:
        if "Address:" not in cell:
            continue
        net = {}

        m = re.search(r'Address:\s*([0-9A-Fa-f:]{17})', cell)
        net["bssid"] = m.group(1).upper() if m else "Unknown"

        m = re.search(r'ESSID:"([^"]*)"', cell)
        net["essid"] = m.group(1) if m else "<hidden>"

        m = re.search(r'Frequency:([\d.]+)\s*GHz', cell)
        net["frequency"] = m.group(1) + " GHz" if m else "?"

        m = re.search(r'Channel:(\d+)', cell)
        if not m:
            m = re.search(r'\(Channel (\d+)\)', cell)
        net["channel"] = m.group(1) if m else "?"

        m = re.search(r'Signal level=(-?\d+)\s*dBm', cell)
        if m:
            net["signal_dbm"] = int(m.group(1))
        else:
            m = re.search(r'Signal level=(\d+)/100', cell)
            if m:
                net["signal_dbm"] = int(m.group(1)) - 100
            else:
                net["signal_dbm"] = -100

        m = re.search(r'Noise level=(-?\d+)\s*dBm', cell)
        net["noise_dbm"] = int(m.group(1)) if m else None

        m = re.search(r'Quality=(\d+)/(\d+)', cell)
        if m:
            net["quality"] = round(int(m.group(1)) / int(m.group(2)) * 100)
        else:
            dbm = net["signal_dbm"]
            net["quality"] = max(0, min(100, 2 * (dbm + 100)))

        encryption_lines = re.findall(r'Encryption key:(on|off)', cell)
        ie_wpa = re.findall(r'IE:.*WPA', cell)
        ie_wpa2 = re.findall(r'IE:.*WPA2|IE:.*RSN', cell)
        if ie_wpa2:
            net["encryption"] = "WPA2"
        elif ie_wpa:
            net["encryption"] = "WPA"
        elif encryption_lines and encryption_lines[0] == "on":
            net["encryption"] = "WEP"
        else:
            net["encryption"] = "Open"

        rates = re.findall(r'(\d+\.?\d*) Mb/s', cell)
        net["max_rate"] = max((float(r) for r in rates), default=0)
        net["max_rate_str"] = f"{int(net['max_rate'])} Mbps" if net["max_rate"] else "?"

        net["mode"] = "Master"
        m = re.search(r'Mode:(\w+)', cell)
        if m:
            net["mode"] = m.group(1)

        net["vendor"] = bssid_to_vendor(net["bssid"])
        net["band"] = "5 GHz" if net["frequency"].startswith("5") else "2.4 GHz"
        net["last_seen"] = datetime.now().strftime("%H:%M:%S")

        networks.append(net)
    return networks


_VENDOR_OUI = {
    "00:50:F2": "Microsoft",
    "00:1A:2B": "Intel",
    "00:23:14": "Belkin",
    "18:D6:C7": "TP-Link",
    "A4:2B:B0": "TP-Link",
    "EC:08:6B": "TP-Link",
    "00:90:4C": "Epigram",
    "8C:59:C3": "Netgear",
    "A0:04:60": "Netgear",
    "28:80:88": "Netgear",
    "20:E5:2A": "Linksys",
    "00:14:BF": "Linksys",
    "00:1E:E5": "Cisco",
    "00:17:94": "Cisco",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "00:11:22": "Cimsys",
    "FC:EC:DA": "Ubiquiti",
    "44:D9:E7": "Ubiquiti",
    "04:18:D6": "Apple",
    "AC:BC:32": "Apple",
    "F0:18:98": "Apple",
}

def bssid_to_vendor(bssid: str) -> str:
    oui = bssid[:8].upper()
    return _VENDOR_OUI.get(oui, "Unknown")


def signal_color(dbm: int) -> str:
    if dbm >= -50:
        return ACCENT_GREEN
    elif dbm >= -65:
        return ACCENT_CYAN
    elif dbm >= -75:
        return ACCENT_YELLOW
    else:
        return ACCENT_RED


def signal_label(dbm: int) -> str:
    if dbm >= -50:
        return "Excellent"
    elif dbm >= -65:
        return "Good"
    elif dbm >= -75:
        return "Fair"
    else:
        return "Poor"


def draw_signal_bars(canvas, x, y, dbm, bar_w=4, bar_gap=2, max_h=16):
    """Draw 4 signal strength bars on a canvas."""
    canvas.delete("all")
    quality = max(0, min(100, 2 * (dbm + 100)))
    levels = [25, 50, 75, 100]
    color = signal_color(dbm)
    for i, threshold in enumerate(levels):
        h = int(max_h * (i + 1) / 4)
        bx = x + i * (bar_w + bar_gap)
        by_top = y + max_h - h
        fill = color if quality >= threshold else TEXT_DIM
        canvas.create_rectangle(bx, by_top, bx + bar_w, y + max_h, fill=fill, outline="")


# ── Main Application ───────────────────────────────────────────────────────────

class WiFiAnalyzer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WiFi Network Analyzer")
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # State
        self.interfaces      = get_interfaces()
        self.selected_iface  = tk.StringVar(value=self.interfaces[0] if self.interfaces else "wlan0")
        self.auto_scan       = tk.BooleanVar(value=False)
        self.scan_interval   = tk.IntVar(value=5)
        self.networks        = {}          # bssid → dict
        self.history         = defaultdict(list)  # bssid → [dbm, ...]
        self.sort_col        = "signal_dbm"
        self.sort_reverse    = True
        self.filter_text     = tk.StringVar()
        self.filter_band     = tk.StringVar(value="All")
        self.filter_enc      = tk.StringVar(value="All")
        self._scan_thread    = None
        self._auto_job       = None
        self._scanning       = False
        self.selected_bssid  = None

        self._build_ui()
        self._check_privileges()

    # ── Privilege check ────────────────────────────────────────────────────────

    def _check_privileges(self):
        if os.geteuid() != 0:
            self._status("Warning: not running as root — scan may fail. Try: sudo python3 wifi_analyzer.py", ACCENT_YELLOW)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_titlebar()
        self._build_toolbar()
        self._build_main()
        self._build_statusbar()

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=48)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        icon = tk.Label(bar, text="⬡", font=("Segoe UI", 20), fg=ACCENT_BLUE, bg=BG_PANEL)
        icon.pack(side="left", padx=(14, 4), pady=6)

        title = tk.Label(bar, text="WiFi Network Analyzer", font=("Segoe UI", 13, "bold"),
                         fg=TEXT_PRIMARY, bg=BG_PANEL)
        title.pack(side="left", pady=6)

        subtitle = tk.Label(bar, text="  iwlist monitor", font=("Segoe UI", 9),
                            fg=TEXT_MUTED, bg=BG_PANEL)
        subtitle.pack(side="left", pady=6)

        # Clock
        self._clock_var = tk.StringVar()
        clock = tk.Label(bar, textvariable=self._clock_var, font=("Courier", 10),
                         fg=TEXT_MUTED, bg=BG_PANEL)
        clock.pack(side="right", padx=16)
        self._tick_clock()

    def _tick_clock(self):
        self._clock_var.set(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG_CARD, height=48)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        def sep():
            tk.Frame(bar, bg=BORDER, width=1).pack(side="left", fill="y", padx=8, pady=8)

        # Interface selector
        tk.Label(bar, text="Interface:", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        iface_cb = ttk.Combobox(bar, textvariable=self.selected_iface,
                                values=self.interfaces, width=10,
                                state="readonly", font=("Segoe UI", 9))
        iface_cb.pack(side="left")
        self._style_combobox()

        sep()

        # Scan button
        self._scan_btn = self._toolbar_btn(bar, "  Scan", ACCENT_BLUE, self._start_scan)
        self._scan_btn.pack(side="left", padx=4)

        # Auto-scan toggle
        self._auto_btn = self._toolbar_btn(bar, "  Auto OFF", TEXT_MUTED, self._toggle_auto)
        self._auto_btn.pack(side="left", padx=4)

        # Interval
        tk.Label(bar, text="every", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        spin = tk.Spinbox(bar, from_=2, to=60, textvariable=self.scan_interval,
                          width=3, font=("Segoe UI", 9),
                          bg=BG_HOVER, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                          relief="flat", buttonbackground=BG_HOVER)
        spin.pack(side="left")
        tk.Label(bar, text="s", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))

        sep()

        # Clear button
        self._toolbar_btn(bar, "  Clear", ACCENT_RED, self._clear).pack(side="left", padx=4)

        sep()

        # Filters
        tk.Label(bar, text="Band:", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        band_cb = ttk.Combobox(bar, textvariable=self.filter_band,
                               values=["All", "2.4 GHz", "5 GHz"], width=8,
                               state="readonly", font=("Segoe UI", 9))
        band_cb.pack(side="left")
        band_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        tk.Label(bar, text="  Enc:", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        enc_cb = ttk.Combobox(bar, textvariable=self.filter_enc,
                              values=["All", "Open", "WEP", "WPA", "WPA2"], width=7,
                              state="readonly", font=("Segoe UI", 9))
        enc_cb.pack(side="left")
        enc_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        sep()

        # Search
        tk.Label(bar, text="Search:", fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        search = tk.Entry(bar, textvariable=self.filter_text, width=18,
                          font=("Segoe UI", 9), bg=BG_HOVER, fg=TEXT_PRIMARY,
                          insertbackground=TEXT_PRIMARY, relief="flat",
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=ACCENT_BLUE)
        search.pack(side="left")
        self.filter_text.trace_add("write", lambda *_: self._refresh_table())

        # Network count badge
        self._count_var = tk.StringVar(value="0 networks")
        tk.Label(bar, textvariable=self._count_var, fg=ACCENT_CYAN, bg=BG_CARD,
                 font=("Segoe UI", 9, "bold")).pack(side="right", padx=12)

    def _toolbar_btn(self, parent, text, color, cmd):
        btn = tk.Label(parent, text=text, fg=color, bg=BG_HOVER,
                       font=("Segoe UI", 9, "bold"), padx=10, pady=5,
                       cursor="hand2", relief="flat")
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_CARD))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_HOVER))
        return btn

    def _style_combobox(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=BG_HOVER, background=BG_HOVER,
                        foreground=TEXT_PRIMARY, selectbackground=ACCENT_BLUE,
                        selectforeground=TEXT_PRIMARY, arrowcolor=TEXT_MUTED,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", BG_HOVER)])

    def _build_main(self):
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG_DARK,
                              sashwidth=4, sashrelief="flat", opaqueresize=True)
        pane.pack(fill="both", expand=True, padx=0, pady=0)

        left = tk.Frame(pane, bg=BG_DARK)
        pane.add(left, minsize=550)

        right = tk.Frame(pane, bg=BG_DARK, width=340)
        pane.add(right, minsize=280)

        self._build_table(left)
        self._build_detail_panel(right)

    def _build_table(self, parent):
        hdr = tk.Frame(parent, bg=BG_DARK)
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(hdr, text="Networks", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_PRIMARY, bg=BG_DARK).pack(side="left")

        # Treeview
        cols = ("signal", "essid", "bssid", "band", "channel",
                "encryption", "quality", "rate", "vendor", "last_seen")
        col_labels = {
            "signal":     "Signal",
            "essid":      "ESSID / Network Name",
            "bssid":      "BSSID / MAC",
            "band":       "Band",
            "channel":    "CH",
            "encryption": "Security",
            "quality":    "Quality",
            "rate":       "Max Rate",
            "vendor":     "Vendor",
            "last_seen":  "Last Seen",
        }
        col_widths = {
            "signal": 70, "essid": 180, "bssid": 140, "band": 65,
            "channel": 40, "encryption": 70, "quality": 65, "rate": 75,
            "vendor": 100, "last_seen": 75,
        }

        frame = tk.Frame(parent, bg=BG_DARK)
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        style = ttk.Style()
        style.configure("Dark.Treeview",
                        background=BG_PANEL, foreground=TEXT_PRIMARY,
                        fieldbackground=BG_PANEL, rowheight=28,
                        font=("Courier", 9), borderwidth=0)
        style.configure("Dark.Treeview.Heading",
                        background=BG_CARD, foreground=TEXT_MUTED,
                        relief="flat", font=("Segoe UI", 9, "bold"),
                        borderwidth=0)
        style.map("Dark.Treeview",
                  background=[("selected", ACCENT_BLUE)],
                  foreground=[("selected", "#fff")])
        style.map("Dark.Treeview.Heading",
                  background=[("active", BG_HOVER)])

        vsb = ttk.Scrollbar(frame, orient="vertical")
        hsb = ttk.Scrollbar(frame, orient="horizontal")

        self.tree = ttk.Treeview(
            frame, columns=cols, show="headings",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set,
            style="Dark.Treeview", selectmode="browse"
        )
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        for col in cols:
            self.tree.heading(col, text=col_labels[col],
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=col_widths[col], anchor="w", stretch=False)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("excellent", foreground=ACCENT_GREEN)
        self.tree.tag_configure("good",      foreground=ACCENT_CYAN)
        self.tree.tag_configure("fair",      foreground=ACCENT_YELLOW)
        self.tree.tag_configure("poor",      foreground=ACCENT_RED)
        self.tree.tag_configure("alt",       background=BG_CARD)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_detail_panel(self, parent):
        tk.Label(parent, text="Network Details", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_PRIMARY, bg=BG_DARK).pack(anchor="w", padx=10, pady=(8, 4))

        self._detail_frame = tk.Frame(parent, bg=BG_PANEL, relief="flat",
                                      highlightthickness=1,
                                      highlightbackground=BORDER)
        self._detail_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_detail_placeholder()

    def _build_detail_placeholder(self):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        tk.Label(self._detail_frame,
                 text="\n\n\nSelect a network\nto view details",
                 font=("Segoe UI", 10), fg=TEXT_DIM, bg=BG_PANEL,
                 justify="center").pack(expand=True)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_CARD, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._progress = tk.Canvas(bar, bg=BG_CARD, highlightthickness=0,
                                   width=120, height=6)
        self._progress.pack(side="left", padx=(12, 6), pady=10)

        self._status_var = tk.StringVar(value="Ready. Press Scan to start.")
        tk.Label(bar, textvariable=self._status_var, fg=TEXT_MUTED, bg=BG_CARD,
                 font=("Segoe UI", 8)).pack(side="left")

        # iface info
        self._iface_info_var = tk.StringVar()
        tk.Label(bar, textvariable=self._iface_info_var, fg=TEXT_DIM, bg=BG_CARD,
                 font=("Courier", 8)).pack(side="right", padx=12)

    # ── Scanning logic ─────────────────────────────────────────────────────────

    def _start_scan(self):
        if self._scanning:
            return
        iface = self.selected_iface.get()
        self._scanning = True
        self._scan_btn.configure(text="  Scanning…", fg=ACCENT_YELLOW)
        self._status(f"Scanning {iface}…", ACCENT_YELLOW)
        self._animate_progress()
        self._scan_thread = threading.Thread(
            target=self._do_scan, args=(iface,), daemon=True
        )
        self._scan_thread.start()

    def _do_scan(self, iface: str):
        try:
            result = subprocess.run(
                ["iwlist", iface, "scan"],
                capture_output=True, text=True, timeout=20
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._scan_done([], error="Scan timed out."))
            return
        except FileNotFoundError:
            self.after(0, lambda: self._scan_done([], error="iwlist not found. Install wireless-tools."))
            return
        except Exception as ex:
            self.after(0, lambda: self._scan_done([], error=str(ex)))
            return

        if "Interface doesn't support scanning" in output:
            self.after(0, lambda: self._scan_done([], error=f"{iface} doesn't support scanning."))
            return
        if "No scan results" in output or output.strip() == "":
            nets = []
        else:
            nets = parse_iwlist(output)

        self.after(0, lambda: self._scan_done(nets))

    def _scan_done(self, nets: list[dict], error: str = None):
        self._scanning = False
        self._stop_progress()
        self._scan_btn.configure(text="  Scan", fg=ACCENT_BLUE)

        if error:
            self._status(f"Error: {error}", ACCENT_RED)
            messagebox.showerror("Scan Error", error)
            return

        # Merge into network dict
        for n in nets:
            bssid = n["bssid"]
            self.networks[bssid] = n
            self.history[bssid].append(n["signal_dbm"])
            if len(self.history[bssid]) > 60:
                self.history[bssid].pop(0)

        self._refresh_table()
        self._status(f"Found {len(nets)} networks  |  Total tracked: {len(self.networks)}", ACCENT_GREEN)
        self._count_var.set(f"{len(self._visible_networks())} networks")

        # Refresh detail panel if selection is still valid
        if self.selected_bssid and self.selected_bssid in self.networks:
            self._show_detail(self.networks[self.selected_bssid])

    def _toggle_auto(self):
        self.auto_scan.set(not self.auto_scan.get())
        if self.auto_scan.get():
            self._auto_btn.configure(text="  Auto ON", fg=ACCENT_GREEN)
            self._schedule_auto()
        else:
            self._auto_btn.configure(text="  Auto OFF", fg=TEXT_MUTED)
            if self._auto_job:
                self.after_cancel(self._auto_job)
                self._auto_job = None

    def _schedule_auto(self):
        if not self.auto_scan.get():
            return
        self._start_scan()
        interval_ms = max(2, self.scan_interval.get()) * 1000
        self._auto_job = self.after(interval_ms, self._schedule_auto)

    def _clear(self):
        self.networks.clear()
        self.history.clear()
        self.selected_bssid = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._build_detail_placeholder()
        self._count_var.set("0 networks")
        self._status("Cleared.", TEXT_MUTED)

    # ── Progress animation ─────────────────────────────────────────────────────

    def _animate_progress(self, pos=0):
        if not self._scanning:
            return
        self._progress.delete("all")
        w = 120
        seg = 40
        x1 = (pos % (w + seg)) - seg
        x2 = x1 + seg
        x1 = max(0, x1)
        x2 = min(w, x2)
        if x2 > x1:
            self._progress.create_rectangle(x1, 1, x2, 5, fill=ACCENT_BLUE, outline="")
        self._progress.create_rectangle(0, 0, w, 6,
                                         outline=BORDER, fill="", width=1)
        self.after(30, lambda: self._animate_progress(pos + 4))

    def _stop_progress(self):
        self._progress.delete("all")
        self._progress.create_rectangle(0, 1, 120, 5, fill=ACCENT_GREEN, outline="")

    # ── Table ──────────────────────────────────────────────────────────────────

    def _visible_networks(self) -> list[dict]:
        nets = list(self.networks.values())
        band = self.filter_band.get()
        enc  = self.filter_enc.get()
        txt  = self.filter_text.get().lower()
        if band != "All":
            nets = [n for n in nets if n.get("band") == band]
        if enc != "All":
            nets = [n for n in nets if n.get("encryption") == enc]
        if txt:
            nets = [n for n in nets
                    if txt in n.get("essid", "").lower()
                    or txt in n.get("bssid", "").lower()
                    or txt in n.get("vendor", "").lower()]
        nets.sort(key=lambda n: n.get(self.sort_col, 0) or 0,
                  reverse=self.sort_reverse)
        return nets

    def _refresh_table(self):
        selected = self.selected_bssid
        for item in self.tree.get_children():
            self.tree.delete(item)

        nets = self._visible_networks()
        self._count_var.set(f"{len(nets)} networks")

        for i, n in enumerate(nets):
            dbm = n["signal_dbm"]
            qlabel = signal_label(dbm)
            tag = qlabel.lower()
            if i % 2 == 1:
                tag = (tag, "alt")

            bars = "▂▄▆█"
            q = n["quality"]
            if q >= 75:
                bars_str = "▂▄▆█"
            elif q >= 50:
                bars_str = "▂▄▆·"
            elif q >= 25:
                bars_str = "▂▄··"
            else:
                bars_str = "▂···"

            enc_icon = {"Open": "  Open", "WEP": "  WEP",
                        "WPA": "  WPA", "WPA2": "  WPA2"}.get(n["encryption"], n["encryption"])

            values = (
                f"{bars_str} {dbm} dBm",
                n["essid"] or "<hidden>",
                n["bssid"],
                n["band"],
                n["channel"],
                enc_icon,
                f"{n['quality']}%",
                n["max_rate_str"],
                n["vendor"],
                n["last_seen"],
            )
            iid = self.tree.insert("", "end", iid=n["bssid"],
                                   values=values, tags=tag)
            if n["bssid"] == selected:
                self.tree.selection_set(iid)
                self.tree.focus(iid)

    def _sort_by(self, col):
        key_map = {
            "signal":     "signal_dbm",
            "essid":      "essid",
            "bssid":      "bssid",
            "band":       "band",
            "channel":    "channel",
            "encryption": "encryption",
            "quality":    "quality",
            "rate":       "max_rate",
            "vendor":     "vendor",
            "last_seen":  "last_seen",
        }
        real = key_map.get(col, col)
        if self.sort_col == real:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = real
            self.sort_reverse = real == "signal_dbm"
        self._refresh_table()

    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        bssid = sel[0]
        self.selected_bssid = bssid
        if bssid in self.networks:
            self._show_detail(self.networks[bssid])

    # ── Detail panel ───────────────────────────────────────────────────────────

    def _show_detail(self, n: dict):
        for w in self._detail_frame.winfo_children():
            w.destroy()

        dbm   = n["signal_dbm"]
        color = signal_color(dbm)

        # Header bar
        hdr = tk.Frame(self._detail_frame, bg=color, height=4)
        hdr.pack(fill="x")

        # SSID big display
        ssid_fr = tk.Frame(self._detail_frame, bg=BG_PANEL, pady=12)
        ssid_fr.pack(fill="x", padx=14)

        tk.Label(ssid_fr, text=n["essid"] or "<hidden>",
                 font=("Segoe UI", 14, "bold"), fg=TEXT_PRIMARY,
                 bg=BG_PANEL, wraplength=260, justify="left").pack(anchor="w")
        tk.Label(ssid_fr, text=n["bssid"],
                 font=("Courier", 10), fg=TEXT_MUTED, bg=BG_PANEL).pack(anchor="w")

        # Signal meter
        sig_fr = tk.Frame(self._detail_frame, bg=BG_CARD, pady=10)
        sig_fr.pack(fill="x")

        tk.Label(sig_fr, text="Signal Strength", font=("Segoe UI", 8),
                 fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w", padx=14)

        meter_fr = tk.Frame(sig_fr, bg=BG_CARD)
        meter_fr.pack(fill="x", padx=14, pady=(2, 0))

        tk.Label(meter_fr, text=f"{dbm} dBm",
                 font=("Courier", 22, "bold"), fg=color, bg=BG_CARD).pack(side="left")
        tk.Label(meter_fr, text=f"  {signal_label(dbm)}",
                 font=("Segoe UI", 10), fg=color, bg=BG_CARD).pack(side="left", pady=8)

        # Quality bar
        q = n["quality"]
        bar_outer = tk.Frame(self._detail_frame, bg=BG_DARK, height=8)
        bar_outer.pack(fill="x", padx=14, pady=(4, 8))
        bar_outer.pack_propagate(False)

        def draw_quality_bar(evt=None):
            w = bar_outer.winfo_width() or 200
            filled = int(w * q / 100)
            for child in bar_outer.winfo_children():
                child.destroy()
            tk.Frame(bar_outer, bg=color, width=filled, height=8).place(x=0, y=0)
            tk.Frame(bar_outer, bg=TEXT_DIM, width=w - filled, height=8).place(x=filled, y=0)

        bar_outer.bind("<Configure>", draw_quality_bar)
        self.after(50, draw_quality_bar)

        tk.Label(self._detail_frame, text=f"Quality: {q}%",
                 font=("Segoe UI", 8), fg=TEXT_MUTED,
                 bg=BG_PANEL).pack(anchor="e", padx=14)

        # Details grid
        tk.Frame(self._detail_frame, bg=BORDER, height=1).pack(fill="x", pady=6)

        fields = [
            ("Band",       n["band"]),
            ("Channel",    n["channel"]),
            ("Frequency",  n["frequency"]),
            ("Security",   n["encryption"]),
            ("Max Rate",   n["max_rate_str"]),
            ("Mode",       n["mode"]),
            ("Vendor",     n["vendor"]),
            ("Last Seen",  n["last_seen"]),
        ]
        if n["noise_dbm"] is not None:
            fields.insert(4, ("Noise", f"{n['noise_dbm']} dBm"))

        grid = tk.Frame(self._detail_frame, bg=BG_PANEL)
        grid.pack(fill="x", padx=14, pady=4)

        for r, (label, value) in enumerate(fields):
            tk.Label(grid, text=label, font=("Segoe UI", 8),
                     fg=TEXT_MUTED, bg=BG_PANEL,
                     width=10, anchor="w").grid(row=r, column=0, sticky="w", pady=1)
            tk.Label(grid, text=str(value), font=("Courier", 9),
                     fg=TEXT_PRIMARY, bg=BG_PANEL,
                     anchor="w").grid(row=r, column=1, sticky="w", padx=6, pady=1)

        # Signal history sparkline
        if len(self.history[n["bssid"]]) > 1:
            tk.Frame(self._detail_frame, bg=BORDER, height=1).pack(fill="x", pady=6)
            tk.Label(self._detail_frame, text="Signal History",
                     font=("Segoe UI", 8), fg=TEXT_MUTED,
                     bg=BG_PANEL).pack(anchor="w", padx=14)

            spark = tk.Canvas(self._detail_frame, bg=BG_CARD,
                              height=50, highlightthickness=0)
            spark.pack(fill="x", padx=14, pady=4)

            def draw_spark(evt=None):
                spark.delete("all")
                hist = self.history[n["bssid"]]
                cw = spark.winfo_width() or 260
                ch = spark.winfo_height() or 50
                if len(hist) < 2:
                    return
                mn, mx = min(hist) - 5, max(hist) + 5
                rng = mx - mn or 1
                pts = []
                for i, v in enumerate(hist):
                    px = int(i / (len(hist) - 1) * (cw - 4)) + 2
                    py = int((1 - (v - mn) / rng) * (ch - 4)) + 2
                    pts.append((px, py))
                color_s = signal_color(hist[-1])
                # Draw area fill
                poly = [2, ch - 2] + [c for p in pts for c in p] + [cw - 2, ch - 2]
                spark.create_polygon(poly, fill=color_s + "33", outline="")
                # Draw line
                for i in range(len(pts) - 1):
                    spark.create_line(pts[i][0], pts[i][1],
                                      pts[i+1][0], pts[i+1][1],
                                      fill=color_s, width=1)
                # Latest value dot
                spark.create_oval(pts[-1][0]-3, pts[-1][1]-3,
                                  pts[-1][0]+3, pts[-1][1]+3,
                                  fill=color_s, outline="")

            spark.bind("<Configure>", draw_spark)
            self.after(50, draw_spark)

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _status(self, msg: str, color: str = TEXT_MUTED):
        self._status_var.set(msg)
        # Update status label color by finding it
        for w in self.winfo_children():
            if isinstance(w, tk.Frame):
                for child in w.winfo_children():
                    if isinstance(child, tk.Label) and \
                       child.cget("textvariable") == str(self._status_var):
                        child.configure(fg=color)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app = WiFiAnalyzer()
    app.mainloop()


if __name__ == "__main__":
    main()
