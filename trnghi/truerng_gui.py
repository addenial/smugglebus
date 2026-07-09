
#!/usr/bin/env python3
"""
TrueRNG v3 — Real-Time GUI Graph
Device: /dev/ttyACM0

Scrolling live plot of random values (0-65535) over time.
HIGH (>55000) marked red, LOW (<10000) marked blue.
Close the window or press Ctrl+C to stop.
"""

import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
from collections import deque

DEVICE      = "/dev/ttyACM0"
BAUD        = 115200
WINDOW_SECS = 20
INTERVAL_MS = 50
HIGH_THRESH = 55000
LOW_THRESH  = 10000

ser = serial.Serial(DEVICE, BAUD, timeout=1)
time.sleep(0.1)
ser.reset_input_buffer()

def read_uint16():
    raw = ser.read(2)
    return int.from_bytes(raw, byteorder='big')

max_pts = int(WINDOW_SECS * (1000 / INTERVAL_MS))
times   = deque(maxlen=max_pts)
values  = deque(maxlen=max_pts)
t_start = time.time()

BG       = "#0e0e1a"
PANEL    = "#14142b"
COL_LINE = "#00e5ff"
COL_HIGH = "#ff4444"
COL_LOW  = "#4488ff"
COL_MID  = "#00e5ff"
COL_TEXT = "#ccccdd"

fig, (ax_main, ax_bar) = plt.subplots(
    2, 1,
    figsize=(12, 7),
    gridspec_kw={"height_ratios": [5, 1]},
    facecolor=BG
)
fig.suptitle("TrueRNG v3 — Live Random Output  (/dev/ttyACM0)",
             color=COL_TEXT, fontsize=13, fontweight="bold", y=0.98)

ax_main.set_facecolor(PANEL)
ax_main.set_ylim(-1000, 66535)
ax_main.set_xlim(0, WINDOW_SECS)
ax_main.set_ylabel("Value  (0 - 65535)", color=COL_TEXT, fontsize=10)
ax_main.set_xlabel("Time (seconds)", color=COL_TEXT, fontsize=10)
ax_main.tick_params(colors=COL_TEXT)
for sp in ax_main.spines.values():
    sp.set_edgecolor("#333355")

ax_main.axhspan(HIGH_THRESH, 65535, color="#ff444422", zorder=0)
ax_main.axhspan(0, LOW_THRESH,      color="#4488ff22", zorder=0)
ax_main.axhline(HIGH_THRESH, color=COL_HIGH, linewidth=0.8, linestyle="--", alpha=0.7)
ax_main.axhline(LOW_THRESH,  color=COL_LOW,  linewidth=0.8, linestyle="--", alpha=0.7)

patches = [
    mpatches.Patch(color=COL_HIGH, label=f"HIGH  > {HIGH_THRESH}"),
    mpatches.Patch(color=COL_LOW,  label=f"LOW   < {LOW_THRESH}"),
    mpatches.Patch(color=COL_MID,  label="MID"),
]
ax_main.legend(handles=patches, loc="upper right",
               facecolor="#1a1a3a", edgecolor="#444466",
               labelcolor=COL_TEXT, fontsize=9)

line,    = ax_main.plot([], [], color=COL_LINE, linewidth=0.9, alpha=0.9)
scatter  = ax_main.scatter([], [], s=6, zorder=5)
val_text = ax_main.text(0.01, 0.95, "", transform=ax_main.transAxes,
                        color=COL_TEXT, fontsize=12, fontfamily="monospace",
                        verticalalignment="top")

ax_bar.set_facecolor(PANEL)
ax_bar.set_xlim(0, 65535)
ax_bar.set_ylim(0, 1)
ax_bar.set_yticks([])
ax_bar.set_xlabel("Current value gauge", color=COL_TEXT, fontsize=9)
ax_bar.tick_params(axis="x", colors=COL_TEXT, labelsize=8)
for sp in ax_bar.spines.values():
    sp.set_edgecolor("#333355")

ax_bar.barh(0.5, 65535, height=0.6, color="#222244", left=0)
bar_val = ax_bar.barh(0.5, 0, height=0.6, color=COL_MID, left=0)

plt.tight_layout(rect=[0, 0, 1, 0.97])

def update(frame):
    t = time.time() - t_start
    v = read_uint16()
    times.append(t)
    values.append(v)

    t_list = list(times)
    v_list = list(values)

    colours = []
    for val in v_list:
        if val > HIGH_THRESH:   colours.append(COL_HIGH)
        elif val < LOW_THRESH:  colours.append(COL_LOW)
        else:                   colours.append(COL_MID)

    line.set_data(t_list, v_list)
    scatter.set_offsets(list(zip(t_list, v_list)))
    scatter.set_color(colours)
    ax_main.set_xlim(max(0, t - WINDOW_SECS), max(WINDOW_SECS, t))

    if v > HIGH_THRESH:     zone, col = "HIGH", COL_HIGH
    elif v < LOW_THRESH:    zone, col = "LOW ", COL_LOW
    else:                   zone, col = "MID ", COL_MID

    val_text.set_text(f"  {v:>5}   {zone}   t={t:.1f}s")
    val_text.set_color(col)
    bar_val[0].set_width(v)
    bar_val[0].set_color(col)

    return line, scatter, val_text, bar_val[0]

ani = animation.FuncAnimation(fig, update,
                               interval=INTERVAL_MS,
                               blit=True,
                               cache_frame_data=False)
plt.tight_layout(rect=[0, 0, 1, 0.97])

try:
    plt.show()
finally:
    ser.close()
    print("Serial port closed.")



