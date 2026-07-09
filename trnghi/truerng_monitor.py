#!/usr/bin/env python3
"""
TrueRNG v3 — Long-Run Drift Monitor
Device: /dev/ttyACM0

Designed for multi-day unattended operation.
Logs all drift events to CSV and human-readable log.
Displays dual time windows, severity tiers, and live event panel.

Logs written to:  ./truerng_logs/
Press Ctrl+C or close the window to stop cleanly.
"""

import serial
import time
import sys
import os
import csv
import math
import datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from collections import deque

# ── Config ────────────────────────────────────────────────────────────────────
DEVICE       = "/dev/ttyACM0"
BAUD         = 115200
INTERVAL_MS  = 80          # ~12.5 samples/sec

HIGH_THRESH  = 52000
LOW_THRESH   = 13000

# Streak tiers (consecutive samples in same zone)
TIER_WATCH   = 8           # ~0.6s  — yellow
TIER_DRIFT   = 15          # ~1.2s  — amber
TIER_ANOMALY = 60          # ~4.8s  — red

# Time windows
WINDOW_SHORT = 10 * 60     # 10 minutes  — main graph
WINDOW_LONG  = 24 * 60 * 60  # 24 hours  — history graph (downsampled)

# Heartbeat to log every N seconds
HEARTBEAT_INTERVAL = 600   # 10 minutes

# Log directory
LOG_DIR = "./truerng_logs"

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG        = "#08080f"
C_PANEL     = "#0e0e1a"
C_PANEL2    = "#0b0b15"
C_AXIS      = "#1a1a2e"
C_TEXT      = "#7788aa"
C_TEXT_DIM  = "#3a4a5a"
C_BLUE      = "#4fc3f7"

# Tier colours
C_WATCH     = "#fff176"    # pale yellow
C_DRIFT     = "#ffb300"    # amber
C_ANOMALY   = "#ff1744"    # red

# Zone dot colours
C_DOT_HI    = "#ffca28"
C_DOT_LO    = "#ce93d8"
C_DOT_MID   = "#4fc3f7"

# Drift background fills
C_BG_WATCH  = "#0f0f00"
C_BG_DRIFT  = "#140a00"
C_BG_ANOM   = "#1a0005"

# ── Logging setup ─────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
session_ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_PATH    = os.path.join(LOG_DIR, f"drift_events_{session_ts}.csv")
LOG_PATH    = os.path.join(LOG_DIR, f"truerng_monitor_{session_ts}.log")

def init_logs():
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp", "elapsed_sec", "zone", "tier",
            "streak_samples", "duration_sec", "value_min", "value_max",
            "value_mean"
        ])
    with open(LOG_PATH, "w") as f:
        f.write(f"TrueRNG v3 Monitor — Session started {session_ts}\n")
        f.write(f"Device: {DEVICE}  Baud: {BAUD}\n")
        f.write(f"Thresholds: HIGH>{HIGH_THRESH}  LOW<{LOW_THRESH}\n")
        f.write(f"Tiers: WATCH>={TIER_WATCH}  DRIFT>={TIER_DRIFT}  ANOMALY>={TIER_ANOMALY}\n")
        f.write("─" * 70 + "\n\n")

def log_event(elapsed, zone, tier, streak, duration, vals):
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mn  = min(vals)
    mx  = max(vals)
    avg = sum(vals) / len(vals)
    with open(CSV_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            ts, f"{elapsed:.1f}", zone.upper(), tier,
            streak, f"{duration:.2f}", mn, mx, f"{avg:.0f}"
        ])
    with open(LOG_PATH, "a") as f:
        f.write(
            f"[{ts}]  {tier:<7}  {zone.upper():<4}  "
            f"streak={streak:>4}  dur={duration:.2f}s  "
            f"min={mn}  max={mx}  mean={avg:.0f}\n"
        )

def log_heartbeat(elapsed, total_samples, event_count):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(
            f"[{ts}]  ♥ HEARTBEAT  "
            f"uptime={fmt_duration(elapsed)}  "
            f"samples={total_samples}  events={event_count}\n"
        )

def fmt_duration(secs):
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"

# ── Serial ────────────────────────────────────────────────────────────────────
ser = serial.Serial(DEVICE, BAUD, timeout=2)
time.sleep(0.15)
ser.reset_input_buffer()

def read_u16():
    return int.from_bytes(ser.read(2), byteorder="big")

# ── State ─────────────────────────────────────────────────────────────────────
t_start       = time.time()
total_samples = 0
total_events  = 0
longest_streak = 0
longest_zone   = "—"

streak_count  = 0
streak_zone   = None
streak_vals   = []
streak_start  = 0.0
active_tier   = None   # current tier if in drift, else None

last_heartbeat = t_start

# Short window buffers (~12.5 sps × 600s)
max_short = int(WINDOW_SHORT * (1000 / INTERVAL_MS))
t_short   = deque(maxlen=max_short)
v_short   = deque(maxlen=max_short)

# Long window buffer — store one point every 5 seconds (downsampled)
LONG_BUCKET  = 5.0
long_bucket_vals = []
long_bucket_t    = 0.0
t_long   = deque(maxlen=int(WINDOW_LONG / LONG_BUCKET))
v_long   = deque(maxlen=int(WINDOW_LONG / LONG_BUCKET))

# Event panel (last 8 events for on-screen display)
event_panel = deque(maxlen=8)

# ── Figure ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(15, 9), facecolor=C_BG, constrained_layout=False)
fig.canvas.manager.set_window_title("TrueRNG v3 — Long-Run Monitor")

# Grid: header | main graph | history graph | event panel
# Columns: graph (wide) | stats sidebar
outer = gridspec.GridSpec(
    4, 2,
    figure=fig,
    height_ratios=[0.12, 2.8, 0.9, 1.6],
    width_ratios=[3.2, 1.0],
    hspace=0.32,
    wspace=0.18,
    left=0.06, right=0.97,
    top=0.97,  bottom=0.04
)

ax_hdr    = fig.add_subplot(outer[0, :])   # full-width header
ax_main   = fig.add_subplot(outer[1, 0])   # 10-min graph
ax_hist   = fig.add_subplot(outer[2, 0])   # 24-hr history
ax_events = fig.add_subplot(outer[3, 0])   # event panel
ax_stats  = fig.add_subplot(outer[1:, 1])  # stats sidebar

for ax in (ax_hdr, ax_main, ax_hist, ax_events, ax_stats):
    ax.set_facecolor(C_PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)

# ── Header ────────────────────────────────────────────────────────────────────
ax_hdr.set_xlim(0, 1)
ax_hdr.set_ylim(0, 1)
ax_hdr.set_xticks([])
ax_hdr.set_yticks([])

hdr_title = ax_hdr.text(
    0.5, 0.65, "TrueRNG v3  ·  Long-Run Drift Monitor",
    transform=ax_hdr.transAxes, ha="center", va="center",
    color=C_TEXT, fontsize=13, fontweight="bold", fontfamily="monospace"
)
hdr_sub = ax_hdr.text(
    0.5, 0.12,
    f"/dev/ttyACM0  ·  115200 baud  ·  logging to {LOG_DIR}",
    transform=ax_hdr.transAxes, ha="center", va="center",
    color=C_TEXT_DIM, fontsize=8, fontfamily="monospace"
)
hdr_status = ax_hdr.text(
    0.99, 0.55, "● RANDOM",
    transform=ax_hdr.transAxes, ha="right", va="center",
    color=C_BLUE, fontsize=11, fontweight="bold", fontfamily="monospace"
)
hdr_uptime = ax_hdr.text(
    0.01, 0.55, "uptime  0s",
    transform=ax_hdr.transAxes, ha="left", va="center",
    color=C_TEXT_DIM, fontsize=8, fontfamily="monospace"
)

# ── Main graph (10-min window) ────────────────────────────────────────────────
ax_main.set_facecolor(C_PANEL)
ax_main.set_xlim(0, WINDOW_SHORT)
ax_main.set_ylim(-500, 66035)
ax_main.set_ylabel("Value  (0–65535)", color=C_TEXT, fontsize=8,
                    fontfamily="monospace")
ax_main.tick_params(colors=C_TEXT, labelsize=7)
for sp in ax_main.spines.values():
    sp.set_edgecolor(C_AXIS)

# X axis — show as MM:SS relative
def fmt_xaxis_short(ax, x_lo, x_hi):
    ticks = ax.get_xticks()
    labels = []
    for t in ticks:
        if x_lo <= t <= x_hi:
            m = int(t // 60)
            s = int(t % 60)
            labels.append(f"{m}:{s:02d}")
        else:
            labels.append("")
    ax.set_xticklabels(labels, fontsize=7, color=C_TEXT,
                        fontfamily="monospace")

ax_main.set_title("Last 10 minutes", color=C_TEXT_DIM, fontsize=8,
                   fontfamily="monospace", loc="left", pad=4)

# Threshold bands
ax_main.axhspan(HIGH_THRESH, 65535, color="#ffb30010", zorder=0)
ax_main.axhspan(0, LOW_THRESH,       color="#b39ddb10", zorder=0)
ax_main.axhline(HIGH_THRESH, color="#ffb30035", linewidth=0.6,
                linestyle=":", zorder=1)
ax_main.axhline(LOW_THRESH,  color="#b39ddb35", linewidth=0.6,
                linestyle=":", zorder=1)
ax_main.text(0.995, HIGH_THRESH / 65535 + 0.01,
             f"▲{HIGH_THRESH//1000}k", transform=ax_main.get_yaxis_transform(),
             ha="right", fontsize=6, color="#ffb30060", fontfamily="monospace")
ax_main.text(0.995, LOW_THRESH / 65535 - 0.03,
             f"▼{LOW_THRESH//1000}k", transform=ax_main.get_yaxis_transform(),
             ha="right", fontsize=6, color="#b39ddb60", fontfamily="monospace")

main_line,    = ax_main.plot([], [], color=C_BLUE, linewidth=0.7,
                              alpha=0.8, zorder=3)
main_scatter  = ax_main.scatter([], [], s=3, zorder=4, color=C_DOT_MID)

# Drift tier label (large, centre of main graph)
tier_label = ax_main.text(
    0.5, 0.5, "",
    transform=ax_main.transAxes, ha="center", va="center",
    fontsize=22, fontweight="bold", fontfamily="monospace",
    color=C_ANOMALY, alpha=0.0
)
streak_label = ax_main.text(
    0.5, 0.36, "",
    transform=ax_main.transAxes, ha="center", va="center",
    fontsize=9, fontfamily="monospace", color=C_TEXT_DIM
)

# ── History graph (24-hr, downsampled mean) ───────────────────────────────────
ax_hist.set_facecolor(C_PANEL2)
ax_hist.set_xlim(0, 300)   # starts at 5 min, grows
ax_hist.set_ylim(0, 65535)
ax_hist.set_ylabel("Mean / 5s", color=C_TEXT, fontsize=7,
                    fontfamily="monospace")
ax_hist.tick_params(colors=C_TEXT, labelsize=6)
ax_hist.set_title("Full session history  (5-second mean)",
                   color=C_TEXT_DIM, fontsize=8,
                   fontfamily="monospace", loc="left", pad=4)
for sp in ax_hist.spines.values():
    sp.set_edgecolor(C_AXIS)
ax_hist.axhline(HIGH_THRESH, color="#ffb30030", linewidth=0.5, linestyle=":")
ax_hist.axhline(LOW_THRESH,  color="#b39ddb30", linewidth=0.5, linestyle=":")
ax_hist.axhline(32767,       color="#ffffff15", linewidth=0.5, linestyle="-")

hist_line, = ax_hist.plot([], [], color="#4fc3f790", linewidth=0.8, zorder=3)
hist_fill  = ax_hist.fill_between([], [], 32767, color="#4fc3f710", zorder=2)

# ── Event panel ───────────────────────────────────────────────────────────────
ax_events.set_facecolor(C_PANEL2)
ax_events.set_xlim(0, 1)
ax_events.set_ylim(0, 1)
ax_events.set_xticks([])
ax_events.set_yticks([])
ax_events.set_title("Recent drift events",
                     color=C_TEXT_DIM, fontsize=8,
                     fontfamily="monospace", loc="left", pad=4)

EVENT_ROWS = 8
event_texts = []
for i in range(EVENT_ROWS):
    y = 0.92 - i * (0.92 / EVENT_ROWS)
    t = ax_events.text(
        0.01, y, "",
        transform=ax_events.transAxes, ha="left", va="top",
        fontsize=7.5, fontfamily="monospace", color=C_TEXT_DIM
    )
    event_texts.append(t)

# Column headers
ax_events.text(0.01, 0.98, "  TIME           ZONE  TIER     STREAK  DURATION  RANGE",
               transform=ax_events.transAxes, ha="left", va="top",
               fontsize=6.5, fontfamily="monospace", color=C_TEXT_DIM)

# ── Stats sidebar ─────────────────────────────────────────────────────────────
ax_stats.set_facecolor(C_PANEL2)
ax_stats.set_xlim(0, 1)
ax_stats.set_ylim(0, 1)
ax_stats.set_xticks([])
ax_stats.set_yticks([])
ax_stats.set_title("Session stats",
                    color=C_TEXT_DIM, fontsize=8,
                    fontfamily="monospace", loc="left", pad=4)

STAT_LABELS = [
    "Uptime",
    "Samples",
    "Rate",
    "",
    "Total events",
    "  Watch",
    "  Drift",
    "  Anomaly",
    "",
    "Longest streak",
    "  Zone",
    "  Duration",
    "",
    "Current value",
    "Current zone",
    "",
    "Log file",
]
stat_texts = []
for i, lbl in enumerate(STAT_LABELS):
    y = 0.97 - i * (0.94 / len(STAT_LABELS))
    lbl_t = ax_stats.text(
        0.05, y, lbl,
        transform=ax_stats.transAxes, ha="left", va="top",
        fontsize=7, fontfamily="monospace", color=C_TEXT_DIM
    )
    val_t = ax_stats.text(
        0.97, y, "",
        transform=ax_stats.transAxes, ha="right", va="top",
        fontsize=7, fontfamily="monospace", color=C_TEXT
    )
    stat_texts.append(val_t)

# Log filenames (static)
stat_texts[16].set_text(os.path.basename(CSV_PATH))
stat_texts[16].set_color(C_TEXT_DIM)

# ── Tier helpers ──────────────────────────────────────────────────────────────
tier_counts = {"WATCH": 0, "DRIFT": 0, "ANOMALY": 0}

def get_tier(streak):
    if streak >= TIER_ANOMALY:  return "ANOMALY"
    if streak >= TIER_DRIFT:    return "DRIFT"
    if streak >= TIER_WATCH:    return "WATCH"
    return None

def tier_colour(tier):
    return {
        "WATCH":   C_WATCH,
        "DRIFT":   C_DRIFT,
        "ANOMALY": C_ANOMALY,
    }.get(tier, C_BLUE)

def tier_bg(tier):
    return {
        "WATCH":   C_BG_WATCH,
        "DRIFT":   C_BG_DRIFT,
        "ANOMALY": C_BG_ANOM,
    }.get(tier, C_BG)

def dot_colour(v):
    if v > HIGH_THRESH:  return C_DOT_HI
    if v < LOW_THRESH:   return C_DOT_LO
    return C_DOT_MID

# ── Blink state ───────────────────────────────────────────────────────────────
_blink = [True]

# ── Animation ─────────────────────────────────────────────────────────────────
def update(_):
    global streak_count, streak_zone, streak_vals, streak_start
    global total_samples, total_events, longest_streak, longest_zone
    global active_tier, last_heartbeat, hist_fill
    global long_bucket_vals, long_bucket_t

    now     = time.time()
    elapsed = now - t_start
    v       = read_u16()
    total_samples += 1

    t_short.append(elapsed)
    v_short.append(v)

    # ── Downsampled long-history bucket ──────────────────────────────────────
    long_bucket_vals.append(v)
    if elapsed - long_bucket_t >= LONG_BUCKET:
        bucket_mean = sum(long_bucket_vals) / len(long_bucket_vals)
        t_long.append(elapsed)
        v_long.append(bucket_mean)
        long_bucket_vals.clear()
        long_bucket_t = elapsed  # Note: treated as module-level via closure

    # ── Streak tracking ───────────────────────────────────────────────────────
    zone = None
    if v > HIGH_THRESH:  zone = "high"
    elif v < LOW_THRESH: zone = "low"

    prev_streak = streak_count
    if zone and zone == streak_zone:
        streak_count += 1
        streak_vals.append(v)
    elif zone:
        # New zone started — close previous event if it qualified
        if streak_zone and streak_count >= TIER_WATCH:
            _close_event(elapsed)
        streak_zone  = zone
        streak_count = 1
        streak_vals  = [v]
        streak_start = elapsed
    else:
        # Back to mid — close event if qualified
        if streak_zone and streak_count >= TIER_WATCH:
            _close_event(elapsed)
        streak_zone  = None
        streak_count = 0
        streak_vals  = []

    tier = get_tier(streak_count) if streak_zone else None
    active_tier = tier

    # Longest streak update
    if streak_count > longest_streak:
        longest_streak = streak_count
        longest_zone   = streak_zone or "—"

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
        log_heartbeat(elapsed, total_samples, total_events)
        last_heartbeat = now

    # ── Theme ────────────────────────────────────────────────────────────────
    bg = tier_bg(tier) if tier else C_BG
    fig.set_facecolor(bg)
    ax_main.set_facecolor(tier_bg(tier) if tier else C_PANEL)
    line_col = tier_colour(tier) if tier else C_BLUE
    main_line.set_color(line_col)

    # ── Main graph ────────────────────────────────────────────────────────────
    tl = list(t_short)
    vl = list(v_short)
    main_line.set_data(tl, vl)
    main_scatter.set_offsets(list(zip(tl, vl)))
    main_scatter.set_color([dot_colour(x) for x in vl])

    x_hi = max(WINDOW_SHORT, elapsed)
    x_lo = x_hi - WINDOW_SHORT
    ax_main.set_xlim(x_lo, x_hi)

    # X tick labels as MM:SS
    ticks = [x_lo + i * 60 for i in range(11)]
    ax_main.set_xticks(ticks)
    labels = []
    for tk in ticks:
        m = int(tk // 60)
        s = int(tk % 60)
        labels.append(f"{m}:{s:02d}")
    ax_main.set_xticklabels(labels, fontsize=6, color=C_TEXT,
                             fontfamily="monospace")

    # ── Tier overlay label ────────────────────────────────────────────────────
    if tier:
        _blink[0] = not _blink[0]
        zone_str  = "HIGH" if streak_zone == "high" else "LOW"
        col       = tier_colour(tier)
        dur       = elapsed - streak_start
        tier_label.set_text(f"▲ {tier}  {zone_str}" if streak_zone == "high"
                             else f"▼ {tier}  {zone_str}")
        tier_label.set_color(col)
        tier_label.set_alpha(0.22 if _blink[0] else 0.10)
        streak_label.set_text(
            f"streak  {streak_count} samples  ·  {dur:.1f}s"
        )
        streak_label.set_color(col)
        hdr_status.set_text(f"⚠  {tier}  {zone_str}")
        hdr_status.set_color(col)
    else:
        tier_label.set_alpha(0.0)
        streak_label.set_text("")
        hdr_status.set_text("● RANDOM")
        hdr_status.set_color(C_BLUE)

    hdr_uptime.set_text(f"uptime  {fmt_duration(elapsed)}")

    # ── History graph ─────────────────────────────────────────────────────────
    if len(t_long) >= 2:
        tlong_l = list(t_long)
        vlong_l = list(v_long)
        hist_line.set_data(tlong_l, vlong_l)
        ax_hist.set_xlim(tlong_l[0], max(tlong_l[-1], tlong_l[0] + 300))

        # Recolour fill
        try:
            hist_fill.remove()
        except Exception:
            pass
        hist_fill = ax_hist.fill_between(
            tlong_l, vlong_l, 32767,
            where=[x >= 32767 for x in vlong_l],
            color="#ffb30018", zorder=2
        )
        ax_hist.fill_between(
            tlong_l, vlong_l, 32767,
            where=[x < 32767 for x in vlong_l],
            color="#b39ddb18", zorder=2
        )

        # X axis as HH:MM
        ax_hist.set_xticks([tlong_l[0] + i * 3600
                            for i in range(int(elapsed / 3600) + 2)])
        hl = []
        for tk in ax_hist.get_xticks():
            h = int((tk - t_start) // 3600)
            m = int(((tk - t_start) % 3600) // 60)
            hl.append(f"{h}:{m:02d}")
        ax_hist.set_xticklabels(hl, fontsize=6, color=C_TEXT,
                                  fontfamily="monospace")

    # ── Event panel ───────────────────────────────────────────────────────────
    events_list = list(event_panel)
    for i, et in enumerate(event_texts):
        if i < len(events_list):
            ev  = events_list[-(i+1)]   # newest first
            col = tier_colour(ev["tier"])
            et.set_text(
                f"  {ev['ts']}   "
                f"{ev['zone'].upper():<5}  "
                f"{ev['tier']:<7}  "
                f"{ev['streak']:>5}   "
                f"{ev['dur']:.1f}s      "
                f"{ev['vmin']}–{ev['vmax']}"
            )
            et.set_color(col)
        else:
            et.set_text("")

    # ── Stats sidebar ─────────────────────────────────────────────────────────
    rate = total_samples / elapsed if elapsed > 0 else 0
    ls_dur = longest_streak * INTERVAL_MS / 1000

    vals_out = [
        fmt_duration(elapsed),
        f"{total_samples:,}",
        f"{rate:.1f} /s",
        "",
        str(total_events),
        str(tier_counts["WATCH"]),
        str(tier_counts["DRIFT"]),
        str(tier_counts["ANOMALY"]),
        "",
        str(longest_streak),
        longest_zone.upper() if longest_zone != "—" else "—",
        f"{ls_dur:.1f}s",
        "",
        str(v),
        ("HIGH" if v > HIGH_THRESH
         else "LOW" if v < LOW_THRESH
         else "mid"),
        "",
        os.path.basename(CSV_PATH),
    ]

    for i, (st, val) in enumerate(zip(stat_texts, vals_out)):
        st.set_text(val)
        # Colour the current zone value
        if i == 14:   # "Current zone"
            if val == "HIGH":   st.set_color(C_DOT_HI)
            elif val == "LOW":  st.set_color(C_DOT_LO)
            else:               st.set_color(C_TEXT_DIM)
        elif i in (5, 6, 7):   # event tier counts
            st.set_color([C_WATCH, C_DRIFT, C_ANOMALY][i - 5]
                         if int(val or 0) > 0 else C_TEXT_DIM)

    return (main_line, main_scatter, tier_label, streak_label,
            hdr_status, hdr_uptime, hist_line) + tuple(event_texts) + tuple(stat_texts)


def _close_event(elapsed):
    """Called when a qualifying streak ends. Logs and adds to event panel."""
    global total_events
    if not streak_zone or not streak_vals:
        return
    tier = get_tier(streak_count)
    if not tier:
        return
    total_events += 1
    tier_counts[tier] += 1
    dur = elapsed - streak_start
    ts  = datetime.datetime.now().strftime("%H:%M:%S")
    log_event(elapsed, streak_zone, tier, streak_count, dur, streak_vals)
    event_panel.append({
        "ts":     ts,
        "zone":   streak_zone,
        "tier":   tier,
        "streak": streak_count,
        "dur":    dur,
        "vmin":   min(streak_vals),
        "vmax":   max(streak_vals),
    })


# ── Init & run ────────────────────────────────────────────────────────────────
init_logs()

print(f"\n\033[1mTrueRNG v3 — Long-Run Drift Monitor\033[0m")
print(f"Device  : {DEVICE}")
print(f"Logs    : {os.path.abspath(LOG_DIR)}/")
print(f"CSV     : {os.path.basename(CSV_PATH)}")
print(f"Log     : {os.path.basename(LOG_PATH)}")
print(f"\nClose the window or press Ctrl+C to stop cleanly.\n")

ani = animation.FuncAnimation(
    fig, update,
    interval=INTERVAL_MS,
    blit=False,
    cache_frame_data=False
)

try:
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    elapsed = time.time() - t_start
    # Final log entry
    with open(LOG_PATH, "a") as f:
        f.write("\n" + "─" * 70 + "\n")
        f.write(
            f"Session ended.  Uptime: {fmt_duration(elapsed)}  "
            f"Samples: {total_samples}  Events: {total_events}\n"
        )
    print(f"\nStopped cleanly.")
    print(f"Uptime  : {fmt_duration(elapsed)}")
    print(f"Samples : {total_samples:,}")
    print(f"Events  : {total_events}  "
          f"(Watch:{tier_counts['WATCH']}  "
          f"Drift:{tier_counts['DRIFT']}  "
          f"Anomaly:{tier_counts['ANOMALY']})")
    print(f"Logs saved to {os.path.abspath(LOG_DIR)}/")
