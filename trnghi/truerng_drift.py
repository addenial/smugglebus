#!/usr/bin/env python3
"""
TrueRNG v3 — Drift Detector
Device: /dev/ttyACM0

Normal randomness = calm dark display.
Sustained HIGH or LOW streaks = panel shifts colour + streak counter shown.
Close the window or press Ctrl+C to stop.
"""

import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from collections import deque

# ── Config ────────────────────────────────────────────────────────────────────
DEVICE       = "/dev/ttyACM0"
BAUD         = 115200
WINDOW_SECS  = 30
INTERVAL_MS  = 60        # ~16 samples/sec

HIGH_THRESH  = 52000     # above this = "high zone"
LOW_THRESH   = 13000     # below this = "low zone"
STREAK_LIMIT = 8         # consecutive samples needed to trigger drift alert

# ── Serial ────────────────────────────────────────────────────────────────────
ser = serial.Serial(DEVICE, BAUD, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()

def read_uint16():
    raw = ser.read(2)
    return int.from_bytes(raw, byteorder='big')

# ── Data ──────────────────────────────────────────────────────────────────────
max_pts  = int(WINDOW_SECS * (1000 / INTERVAL_MS))
times    = deque(maxlen=max_pts)
values   = deque(maxlen=max_pts)
t_start  = time.time()

streak_count    = 0      # consecutive samples in same zone
streak_zone     = None   # "high", "low", or None
drift_triggered = False  # True once streak >= STREAK_LIMIT

# ── Palette ───────────────────────────────────────────────────────────────────
# Calm state
C_BG        = "#0a0a12"
C_PANEL     = "#10101e"
C_LINE      = "#4fc3f7"   # soft ice blue — readable, not aggressive
C_DOT_NORM  = "#4fc3f7"
C_TEXT      = "#8899aa"
C_AXIS      = "#1e2030"

# Drift HIGH — warm amber glow
C_HIGH_BG   = "#1a1000"
C_HIGH_PAN  = "#1f1500"
C_HIGH_LINE = "#ffb300"
C_HIGH_DOT  = "#ffca28"
C_HIGH_ALT  = "#ff8f00"
C_HIGH_TXT  = "#ffe082"

# Drift LOW — cool violet glow
C_LOW_BG    = "#08001a"
C_LOW_PAN   = "#0d0020"
C_LOW_LINE  = "#b39ddb"
C_LOW_DOT   = "#ce93d8"
C_LOW_ALT   = "#7e57c2"
C_LOW_TXT   = "#d1c4e9"

# ── Figure ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(13, 7), facecolor=C_BG, constrained_layout=True)
fig.canvas.manager.set_window_title("TrueRNG v3 — Drift Detector")

gs = gridspec.GridSpec(
    3, 1,
    height_ratios=[0.18, 4.5, 0.7],
    hspace=0.08,
    figure=fig
)

ax_header = fig.add_subplot(gs[0])
ax_main   = fig.add_subplot(gs[1])
ax_gauge  = fig.add_subplot(gs[2])

for ax in (ax_header, ax_main, ax_gauge):
    ax.set_facecolor(C_PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)

# Header panel
ax_header.set_xlim(0, 1)
ax_header.set_ylim(0, 1)
ax_header.set_xticks([])
ax_header.set_yticks([])

title_txt = ax_header.text(
    0.5, 0.62, "TrueRNG v3  ·  Drift Detector",
    transform=ax_header.transAxes,
    ha="center", va="center",
    color=C_TEXT, fontsize=13, fontweight="bold",
    fontfamily="monospace"
)
sub_txt = ax_header.text(
    0.5, 0.18, "/dev/ttyACM0  ·  115200 baud  ·  watching for drift",
    transform=ax_header.transAxes,
    ha="center", va="center",
    color="#445566", fontsize=8,
    fontfamily="monospace"
)

# Status badge (top right of header)
status_txt = ax_header.text(
    0.97, 0.5, "● RANDOM",
    transform=ax_header.transAxes,
    ha="right", va="center",
    color="#26c6da", fontsize=10, fontweight="bold",
    fontfamily="monospace"
)

# Main plot
ax_main.set_facecolor(C_PANEL)
ax_main.set_ylim(-500, 66035)
ax_main.set_xlim(0, WINDOW_SECS)
ax_main.set_ylabel("Value  (0 – 65 535)", color=C_TEXT, fontsize=9,
                    fontfamily="monospace")
ax_main.set_xlabel("seconds", color=C_TEXT, fontsize=8,
                    fontfamily="monospace")
ax_main.tick_params(colors=C_TEXT, labelsize=8)
for sp in ax_main.spines.values():
    sp.set_edgecolor(C_AXIS)
ax_main.set_facecolor(C_PANEL)

# Threshold bands (subtle)
high_band = ax_main.axhspan(HIGH_THRESH, 65535, color="#ffb30010", zorder=0)
low_band  = ax_main.axhspan(0, LOW_THRESH,      color="#7e57c210", zorder=0)

ax_main.axhline(HIGH_THRESH, color="#ffb30040", linewidth=0.7,
                linestyle=":", zorder=1)
ax_main.axhline(LOW_THRESH,  color="#7e57c240", linewidth=0.7,
                linestyle=":", zorder=1)

# Threshold labels (right margin)
ax_main.text(WINDOW_SECS * 0.99, HIGH_THRESH + 800, f"▲ {HIGH_THRESH:,}",
             color="#ffb30060", fontsize=7, ha="right", fontfamily="monospace")
ax_main.text(WINDOW_SECS * 0.99, LOW_THRESH  - 2500, f"▼ {LOW_THRESH:,}",
             color="#7e57c260", fontsize=7, ha="right", fontfamily="monospace")

# The live line + scatter
line,   = ax_main.plot([], [], color=C_LINE, linewidth=1.0,
                        alpha=0.85, zorder=3)
scatter = ax_main.scatter([], [], s=5, zorder=4, color=C_DOT_NORM)

# Drift overlay text (centre of plot, hidden until drift)
drift_label = ax_main.text(
    0.5, 0.5, "",
    transform=ax_main.transAxes,
    ha="center", va="center",
    fontsize=28, fontweight="bold", fontfamily="monospace",
    color="#ffb300", alpha=0.0   # starts invisible
)

# Streak info (bottom left of main plot)
streak_txt = ax_main.text(
    0.012, 0.045, "",
    transform=ax_main.transAxes,
    ha="left", va="bottom",
    fontsize=9, fontfamily="monospace",
    color=C_TEXT
)

# Live value readout (top left of main plot)
val_txt = ax_main.text(
    0.012, 0.965, "",
    transform=ax_main.transAxes,
    ha="left", va="top",
    fontsize=11, fontweight="bold", fontfamily="monospace",
    color=C_LINE
)

# Gauge
ax_gauge.set_facecolor(C_PANEL)
ax_gauge.set_xlim(0, 65535)
ax_gauge.set_ylim(0, 1)
ax_gauge.set_yticks([])
ax_gauge.tick_params(axis="x", colors=C_TEXT, labelsize=7)
for sp in ax_gauge.spines.values():
    sp.set_edgecolor(C_AXIS)

# Gauge zones
ax_gauge.axvspan(0,           LOW_THRESH,  color="#7e57c218", zorder=0)
ax_gauge.axvspan(HIGH_THRESH, 65535,       color="#ffb30018", zorder=0)

ax_gauge.barh(0.5, 65535, height=0.55, color="#1a1a2e", left=0, zorder=1)
gauge_bar = ax_gauge.barh(0.5, 0, height=0.55, color=C_LINE, left=0, zorder=2)

gauge_txt = ax_gauge.text(
    0.5, 0.5, "",
    transform=ax_gauge.transAxes,
    ha="center", va="center",
    fontsize=8, fontfamily="monospace", color=C_TEXT
)

# ── State ─────────────────────────────────────────────────────────────────────
_blink_state = [True]

def classify_zone(v):
    if v > HIGH_THRESH:
        return "high"
    elif v < LOW_THRESH:
        return "low"
    return None

def apply_calm_theme():
    fig.set_facecolor(C_BG)
    for ax in (ax_header, ax_main, ax_gauge):
        ax.set_facecolor(C_PANEL)
    line.set_color(C_LINE)
    title_txt.set_color(C_TEXT)
    status_txt.set_text("● RANDOM")
    status_txt.set_color("#26c6da")
    drift_label.set_alpha(0.0)
    drift_label.set_text("")
    streak_txt.set_text("")
    val_txt.set_color(C_LINE)
    gauge_bar[0].set_color(C_LINE)

def apply_drift_theme(zone, streak):
    if zone == "high":
        bg, pan, lc, ac, tc = C_HIGH_BG, C_HIGH_PAN, C_HIGH_LINE, C_HIGH_ALT, C_HIGH_TXT
        label = "▲ DRIFT HIGH"
        s_col = "#ffb300"
    else:
        bg, pan, lc, ac, tc = C_LOW_BG, C_LOW_PAN, C_LOW_LINE, C_LOW_ALT, C_LOW_TXT
        label = "▼ DRIFT LOW"
        s_col = "#b39ddb"

    fig.set_facecolor(bg)
    for ax in (ax_header, ax_main, ax_gauge):
        ax.set_facecolor(pan)

    line.set_color(lc)
    title_txt.set_color(tc)
    gauge_bar[0].set_color(lc)
    val_txt.set_color(lc)

    # Blink the drift label
    _blink_state[0] = not _blink_state[0]
    drift_label.set_text(label)
    drift_label.set_color(ac)
    drift_label.set_alpha(0.18 if _blink_state[0] else 0.08)

    status_txt.set_text(f"⚠  {label}")
    status_txt.set_color(s_col)

    streak_txt.set_text(
        f"streak  {streak} samples  ·  "
        f"{'above' if zone == 'high' else 'below'} "
        f"{'52,000' if zone == 'high' else '13,000'} "
        f"for {streak * INTERVAL_MS / 1000:.1f}s"
    )
    streak_txt.set_color(tc)

# ── Animation ─────────────────────────────────────────────────────────────────
def update(frame):
    global streak_count, streak_zone, drift_triggered

    t = time.time() - t_start
    v = read_uint16()
    times.append(t)
    values.append(v)

    zone = classify_zone(v)

    # Streak logic
    if zone is not None and zone == streak_zone:
        streak_count += 1
    elif zone is not None:
        streak_zone  = zone
        streak_count = 1
    else:
        streak_zone  = None
        streak_count = 0

    drift_triggered = (streak_count >= STREAK_LIMIT)

    # Build colour list for scatter dots
    t_list = list(times)
    v_list = list(values)

    dot_colours = []
    for val in v_list:
        z = classify_zone(val)
        if z == "high":
            dot_colours.append(C_HIGH_DOT)
        elif z == "low":
            dot_colours.append(C_LOW_DOT)
        else:
            dot_colours.append(C_DOT_NORM)

    # Update line + scatter
    line.set_data(t_list, v_list)
    scatter.set_offsets(list(zip(t_list, v_list)))
    scatter.set_color(dot_colours)

    # Scroll x
    x_lo = max(0, t - WINDOW_SECS)
    x_hi = max(WINDOW_SECS, t)
    ax_main.set_xlim(x_lo, x_hi)

    # Theme
    if drift_triggered:
        apply_drift_theme(streak_zone, streak_count)
    else:
        apply_calm_theme()

    # Live value readout
    val_txt.set_text(f"  {v:>5}  ")

    # Gauge
    gauge_bar[0].set_width(v)
    gauge_txt.set_text(f"{v:>5}  /  65535")

    return (line, scatter, drift_label, streak_txt,
            val_txt, status_txt, title_txt, gauge_bar[0], gauge_txt)

ani = animation.FuncAnimation(
    fig, update,
    interval=INTERVAL_MS,
    blit=False,          # full redraw needed for facecolor changes
    cache_frame_data=False
)

try:
    plt.show()
finally:
    ser.close()
    print("Serial port closed.")
