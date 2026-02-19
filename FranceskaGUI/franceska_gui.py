"""
HARDPOINT: FRANCESKA
NukeTown, Malle – Airsoft Adventure

Reads Arduino serial output and displays live scores for Red vs Blue.

Usage:
    pip install -r requirements.txt
    python franceska_gui.py [COM_PORT]     # e.g. python franceska_gui.py COM3

If no port is given the script auto-detects the first Arduino it finds.
"""

import sys
import re
import threading
import urllib.request
import io
import tkinter as tk
from tkinter import font as tkfont

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# ── Airsoft Adventure / Nuketown logo (from airsoftadventure.be) ─────────────
LOGO_URL  = "https://pagemaker.b-cdn.net/media/71928/400x50.png"
LOGO_SIZE = (280, 35)   # display size in the header

# ── Serial ────────────────────────────────────────────────────────────────────
BAUD_RATE = 9600

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#0f0f0f"
PANEL_BG    = "#1a1a1a"
DIVIDER     = "#2a2a2a"
RED_COL     = "#e63946"
BLUE_COL    = "#4895ef"
NEUTRAL_COL = "#888888"
FG          = "#f1faee"
BAR_BG      = "#0a0a0a"

# Line patterns from Arduino
RE_SCORE = re.compile(
    r"RED:\s*(\d+)s\s*\|\s*BLUE:\s*(\d+)s\s*\|\s*Holding:\s*(\w+)",
    re.IGNORECASE,
)


# ── Serial reader (background thread) ────────────────────────────────────────
class SerialReader(threading.Thread):
    def __init__(self, port, on_line):
        super().__init__(daemon=True)
        self.port    = port
        self.on_line = on_line
        self.ser     = None

    def run(self):
        if not HAS_SERIAL:
            self.on_line("__ERROR__pyserial not installed. Run: pip install pyserial")
            return
        try:
            self.ser = serial.Serial(self.port, BAUD_RATE, timeout=1)
            while True:
                raw = self.ser.readline()
                if raw:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if line:
                        self.on_line(line)
        except Exception as exc:
            self.on_line(f"__ERROR__{exc}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_time(seconds: int) -> str:
    """Format seconds as M:SS for readability once past 60 s."""
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60:02d}s"


def load_logo(url: str, size: tuple) -> "ImageTk.PhotoImage | None":
    if not HAS_PIL:
        return None
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ── GUI ───────────────────────────────────────────────────────────────────────
class HardpointGUI:
    def __init__(self, root: tk.Tk, port: str | None = None):
        self.root       = root
        self.red_score  = 0
        self.blue_score = 0
        self.holding    = "NEUTRAL"
        self.reader: SerialReader | None = None

        root.title("HARDPOINT: FRANCESKA – NukeTown Malle")
        root.configure(bg=BG)
        root.geometry("920x540")
        root.resizable(False, False)

        self._build_menu()
        self._build_ui()
        self._connect(port)

    # ── Menu bar ──────────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self.root, bg="#1a1a1a", fg=FG, tearoff=False,
                          activebackground="#2a2a2a", activeforeground=FG,
                          borderwidth=0)

        serial_menu = tk.Menu(menubar, bg="#1a1a1a", fg=FG, tearoff=False,
                              activebackground="#2a2a2a", activeforeground=FG)
        serial_menu.add_command(label="Select Port…", command=self._open_port_dialog)
        serial_menu.add_command(label="Disconnect",   command=self._disconnect)
        serial_menu.add_separator()
        serial_menu.add_command(label="Refresh Port List",
                                command=self._open_port_dialog)

        menubar.add_cascade(label="Serial", menu=serial_menu)
        self.root.config(menu=menubar)

    # ── Port selector dialog ──────────────────────────────────────────────────
    def _open_port_dialog(self):
        if not HAS_SERIAL:
            return

        ports = list(serial.tools.list_ports.comports())

        dlg = tk.Toplevel(self.root)
        dlg.title("Select COM Port")
        dlg.configure(bg=PANEL_BG)
        dlg.resizable(False, False)
        dlg.grab_set()          # modal
        dlg.transient(self.root)

        # ── Header ────────────────────────────────────────────────────────────
        tk.Label(dlg, text="Select COM Port", fg=FG, bg=PANEL_BG,
                 font=("Helvetica Neue", 14, "bold")).pack(padx=24, pady=(16, 4))
        tk.Label(dlg, text="Available serial ports:", fg=NEUTRAL_COL, bg=PANEL_BG,
                 font=("Helvetica Neue", 10)).pack(padx=24)

        tk.Frame(dlg, bg=DIVIDER, height=1).pack(fill="x", padx=16, pady=8)

        # ── Port list ─────────────────────────────────────────────────────────
        list_frame = tk.Frame(dlg, bg=PANEL_BG)
        list_frame.pack(padx=16, fill="both")

        selected_port = tk.StringVar(value="")

        if not ports:
            tk.Label(list_frame, text="No ports found.", fg=NEUTRAL_COL,
                     bg=PANEL_BG, font=("Courier New", 10)).pack(pady=8)
        else:
            for p in ports:
                desc  = p.description or p.device
                label = f"{p.device}  —  {desc}"
                rb = tk.Radiobutton(
                    list_frame, text=label,
                    variable=selected_port, value=p.device,
                    fg=FG, bg=PANEL_BG, selectcolor="#2a2a2a",
                    activebackground=PANEL_BG, activeforeground=FG,
                    font=("Courier New", 10), anchor="w",
                )
                rb.pack(fill="x", pady=2)

            # Pre-select currently connected port or best guess
            current = self.reader.port if self.reader else self._auto_detect()
            if current and any(p.device == current for p in ports):
                selected_port.set(current)
            elif ports:
                selected_port.set(ports[0].device)

        tk.Frame(dlg, bg=DIVIDER, height=1).pack(fill="x", padx=16, pady=8)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(dlg, bg=PANEL_BG)
        btn_frame.pack(padx=16, pady=(0, 16), fill="x")

        def on_connect():
            port = selected_port.get()
            if port:
                dlg.destroy()
                self._disconnect()
                self._connect(port)

        tk.Button(
            btn_frame, text="Connect", command=on_connect,
            bg=RED_COL, fg=FG, font=("Helvetica Neue", 11, "bold"),
            relief="flat", padx=16, pady=6, cursor="hand2",
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="Cancel", command=dlg.destroy,
            bg="#2a2a2a", fg=FG, font=("Helvetica Neue", 11),
            relief="flat", padx=16, pady=6, cursor="hand2",
        ).pack(side="left")

        # Centre the dialog over the main window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  - dlg.winfo_reqwidth())  // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dlg.winfo_reqheight()) // 2
        dlg.geometry(f"+{x}+{y}")

    # ── Disconnect helper ─────────────────────────────────────────────────────
    def _disconnect(self):
        if self.reader:
            self.reader.close()
            self.reader = None
        self.status_bar.config(text="Disconnected.", fg=NEUTRAL_COL)

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 0))

        # Logo (loaded async so the window opens immediately)
        self._logo_ref = None
        self.logo_lbl  = tk.Label(header, bg=BG)
        self.logo_lbl.pack()
        threading.Thread(target=self._fetch_logo, daemon=True).start()

        tk.Label(
            header, text="HARDPOINT: FRANCESKA",
            fg=FG, bg=BG, font=("Helvetica Neue", 34, "bold"),
        ).pack()
        tk.Label(
            header, text="NukeTown · Malle",
            fg=NEUTRAL_COL, bg=BG, font=("Helvetica Neue", 13),
        ).pack()

        tk.Frame(self.root, bg=DIVIDER, height=1).pack(fill="x", padx=24, pady=14)

        # ── Score row ─────────────────────────────────────────────────────────
        row = tk.Frame(self.root, bg=BG)
        row.pack(fill="both", expand=True, padx=24)
        row.columnconfigure(0, weight=3, minsize=280)
        row.columnconfigure(1, weight=2, minsize=180)
        row.columnconfigure(2, weight=3, minsize=280)

        self.red_score_lbl  = self._score_panel(row, col=0, team="RED",  color=RED_COL)
        self._status_panel(row, col=1)
        self.blue_score_lbl = self._score_panel(row, col=2, team="BLUE", color=BLUE_COL)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root, text="Searching for Arduino…",
            fg=NEUTRAL_COL, bg=BAR_BG,
            font=("Courier New", 10), anchor="w", padx=12, pady=4,
        )
        self.status_bar.pack(fill="x", side="bottom")

    def _score_panel(self, parent, col: int, team: str, color: str) -> tk.Label:
        """Red or Blue panel. Returns the big score Label."""
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")

        tk.Label(
            frame, text=team, fg=color, bg=PANEL_BG,
            font=("Helvetica Neue", 18, "bold"),
        ).pack(pady=(22, 2))

        score_lbl = tk.Label(
            frame, text="0s", fg=color, bg=PANEL_BG,
            font=("Helvetica Neue", 68, "bold"),
            width=8, anchor="center",   # fixed width prevents layout shifting
        )
        score_lbl.pack(pady=(0, 22))
        return score_lbl

    def _status_panel(self, parent, col: int):
        """Centre panel – who holds the hardpoint."""
        frame = tk.Frame(parent, bg=PANEL_BG)
        frame.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")
        frame.grid_propagate(False)   # lock to grid-given size; children can't resize it

        tk.Label(
            frame, text="HOLDING", fg=NEUTRAL_COL, bg=PANEL_BG,
            font=("Helvetica Neue", 12),
        ).pack(pady=(22, 4))

        self.holding_lbl = tk.Label(
            frame, text="—", fg=NEUTRAL_COL, bg=PANEL_BG,
            font=("Helvetica Neue", 26, "bold"),
            width=7, anchor="center",   # fixed width; "NEUTRAL" → "—" keeps it short
        )
        self.holding_lbl.pack()

        tk.Frame(frame, bg=DIVIDER, height=1).pack(fill="x", padx=16, pady=8)

        self.event_lbl = tk.Label(
            frame, text="", fg=NEUTRAL_COL, bg=PANEL_BG,
            font=("Helvetica Neue", 10), wraplength=160,
            height=2, anchor="n", justify="center",
        )
        self.event_lbl.pack(pady=(0, 8))

        tk.Button(
            frame, text="RESET", command=self._reset,
            bg="#2a2a2a", fg=NEUTRAL_COL,
            font=("Helvetica Neue", 10, "bold"),
            relief="flat", padx=14, pady=4, cursor="hand2",
            activebackground="#3a3a3a", activeforeground=FG,
        ).pack(pady=(0, 18))

    # ── Logo fetch (background thread → main thread update) ──────────────────
    def _fetch_logo(self):
        photo = load_logo(LOGO_URL, LOGO_SIZE)
        if photo:
            self._logo_ref = photo   # prevent GC
            self.root.after(0, lambda: self.logo_lbl.config(image=photo))

    # ── Serial connection ─────────────────────────────────────────────────────
    def _connect(self, port: str | None):
        if not HAS_SERIAL:
            self.status_bar.config(
                text="pyserial not installed – run: pip install pyserial"
            )
            return

        if port is None:
            port = self._auto_detect()

        if port is None:
            self.status_bar.config(
                text="No Arduino found. Plug it in and restart, or pass port as argument."
            )
            return

        self.status_bar.config(text=f"Connecting to {port} @ {BAUD_RATE} baud…")
        self.reader = SerialReader(port, self._on_line)
        self.reader.start()
        self.status_bar.config(text=f"Connected  –  {port}  @  {BAUD_RATE} baud")

    @staticmethod
    def _auto_detect() -> str | None:
        keywords = ("ARDUINO", "CH340", "CP210", "USB SERIAL", "USB-SERIAL")
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            if any(k in (p.description or "").upper() for k in keywords):
                return p.device
        return ports[0].device if ports else None

    # ── Serial line handler (called from reader thread) ───────────────────────
    def _on_line(self, line: str):
        m = RE_SCORE.match(line)
        if m:
            self.red_score  = int(m.group(1))
            self.blue_score = int(m.group(2))
            self.holding    = m.group(3).upper()
            self.root.after(0, self._refresh_scores)
            return

        if "SCORES RESET" in line:
            self.root.after(0, self._reset)
            return

        if ">>" in line:
            self.root.after(0, lambda l=line: self.event_lbl.config(
                text=l.replace(">>", "").strip()
            ))

        if line.startswith("__ERROR__"):
            msg = line.replace("__ERROR__", "")
            self.root.after(0, lambda m=msg: self.status_bar.config(
                text=f"Serial error: {m}", fg="#e63946"
            ))

    # ── Reset (called when Arduino sends >> SCORES RESET) ─────────────────────
    def _reset(self):
        self.red_score  = 0
        self.blue_score = 0
        self._refresh_scores()
        self.event_lbl.config(text="Scores reset.")

    # ── Score refresh (main thread) ───────────────────────────────────────────
    def _refresh_scores(self):
        self.red_score_lbl.config(text=fmt_time(self.red_score))
        self.blue_score_lbl.config(text=fmt_time(self.blue_score))

        if self.holding == "RED":
            self.holding_lbl.config(text="RED", fg=RED_COL)
        elif self.holding == "BLUE":
            self.holding_lbl.config(text="BLUE", fg=BLUE_COL)
        else:
            self.holding_lbl.config(text="—", fg=NEUTRAL_COL)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    def on_close(self):
        if self.reader:
            self.reader.close()
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port_arg = sys.argv[1] if len(sys.argv) > 1 else None

    root = tk.Tk()
    app  = HardpointGUI(root, port=port_arg)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
