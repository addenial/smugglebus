#!/usr/bin/env python3
"""
TrueRNG v3 — Generative Art Demo Launcher
Device: /dev/ttyACM0

Pick a visualisation from the menu. Each one uses live hardware
randomness as its only input. Close the plot window to return to
the menu and choose another demo.
"""

import serial
import time
import sys
import textwrap
from collections import deque

DEVICE = "/dev/ttyACM0"
BAUD   = 115200

HIGH_THRESH = 52000
LOW_THRESH  = 13000

# ── Colour palette shared across demos ───────────────────────────────────────
C_BG      = "#0a0a12"
C_PANEL   = "#10101e"
C_TEXT    = "#8899aa"
C_AXIS    = "#1e2030"
C_BLUE    = "#4fc3f7"
C_AMBER   = "#ffb300"
C_VIOLET  = "#b39ddb"
C_GREEN   = "#69f0ae"

# ── Serial helpers ────────────────────────────────────────────────────────────
def open_serial():
    ser = serial.Serial(DEVICE, BAUD, timeout=2)
    time.sleep(0.1)
    ser.reset_input_buffer()
    return ser

def read_u16(ser):
    return int.from_bytes(ser.read(2), byteorder="big")

def norm(v, lo=0, hi=65535):
    """Normalise a u16 to 0.0–1.0."""
    return (v - lo) / (hi - lo)

# ── Demo registry ─────────────────────────────────────────────────────────────
DEMOS = []

def demo(title, description):
    def decorator(fn):
        DEMOS.append({"title": title, "description": description, "fn": fn})
        return fn
    return decorator

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 1 — Random Walk
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="Random Walk",
    description=(
        "A single dot wanders a 2-D canvas. Each TRNG value nudges it up, "
        "down, left, or right. True randomness fills the space evenly over "
        "time. Drift pulls the dot toward one edge and pins it there — "
        "you'll see a clear diagonal bias appear in the trail."
    )
)
def demo_random_walk():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np

    TRAIL = 600
    ser   = open_serial()

    x, y      = [0.0], [0.0]
    trail_x   = deque([0.0], maxlen=TRAIL)
    trail_y   = deque([0.0], maxlen=TRAIL)
    streak     = 0
    streak_dir = None

    fig, ax = plt.subplots(figsize=(8, 8), facecolor=C_BG)
    fig.canvas.manager.set_window_title("Random Walk")
    ax.set_facecolor(C_PANEL)
    ax.set_xlim(-60, 60)
    ax.set_ylim(-60, 60)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)

    ax.axhline(0, color=C_AXIS, linewidth=0.5)
    ax.axvline(0, color=C_AXIS, linewidth=0.5)

    title_t = ax.set_title("Random Walk  ·  TrueRNG v3",
                            color=C_TEXT, fontsize=11, fontfamily="monospace")

    n      = len(trail_x)
    alphas = [i / n for i in range(n)]
    trail_line, = ax.plot([], [], color=C_BLUE, linewidth=0.7, alpha=0.5)
    dot,         = ax.plot([], [], "o", color=C_GREEN, markersize=7, zorder=5)
    info_t = ax.text(0.02, 0.97, "", transform=ax.transAxes,
                     color=C_TEXT, fontsize=8, va="top",
                     fontfamily="monospace")

    def update(_):
        nonlocal streak, streak_dir
        v  = read_u16(ser)
        n2 = norm(v)

        # Map to 4 directions using value quartiles
        step = 1.5
        if   n2 < 0.25:  dx, dy, d = -step,  0,     "left"
        elif n2 < 0.50:  dx, dy, d =  step,  0,     "right"
        elif n2 < 0.75:  dx, dy, d =  0,    -step,  "down"
        else:            dx, dy, d =  0,     step,  "up"

        cx = max(-58, min(58, trail_x[-1] + dx))
        cy = max(-58, min(58, trail_y[-1] + dy))
        trail_x.append(cx)
        trail_y.append(cy)

        # Streak detection
        if d == streak_dir:
            streak += 1
        else:
            streak_dir = d
            streak = 1

        drift = streak >= 12
        colour = C_AMBER if drift else C_BLUE

        tl = list(trail_x)
        yl = list(trail_y)
        trail_line.set_data(tl, yl)
        trail_line.set_color(colour)
        dot.set_data([cx], [cy])
        dot.set_color(C_AMBER if drift else C_GREEN)

        status = f"⚠ DRIFT {streak_dir.upper()} ({streak})" if drift else "● RANDOM"
        info_t.set_text(f"val={v:>5}   {status}")
        info_t.set_color(C_AMBER if drift else C_TEXT)
        fig.patch.set_facecolor("#1a1000" if drift else C_BG)

        return trail_line, dot, info_t

    ani = animation.FuncAnimation(fig, update, interval=40,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 2 — Frequency Histogram
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="Frequency Histogram",
    description=(
        "Divides the 0–65535 range into 32 buckets and counts how many "
        "values land in each one. A healthy RNG keeps all bars roughly "
        "equal height — a flat, even distribution. Drift makes one end "
        "of the histogram pile up while the other stays empty."
    )
)
def demo_histogram():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np

    BUCKETS = 32
    counts  = [0] * BUCKETS
    bucket_w = 65536 // BUCKETS
    ser = open_serial()

    fig, ax = plt.subplots(figsize=(12, 5), facecolor=C_BG)
    fig.canvas.manager.set_window_title("Frequency Histogram")
    ax.set_facecolor(C_PANEL)
    ax.set_xlim(-0.5, BUCKETS - 0.5)
    ax.set_xlabel("Value bucket  (left = low,  right = high)", color=C_TEXT,
                  fontsize=9, fontfamily="monospace")
    ax.set_ylabel("Count", color=C_TEXT, fontsize=9, fontfamily="monospace")
    ax.tick_params(colors=C_TEXT, labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)
    ax.set_title("Frequency Histogram  ·  TrueRNG v3",
                 color=C_TEXT, fontsize=11, fontfamily="monospace")

    xs     = list(range(BUCKETS))
    bars   = ax.bar(xs, counts, color=C_BLUE, width=0.85, zorder=2)
    ideal  = ax.axhline(0, color=C_GREEN, linewidth=0.8, linestyle="--",
                        alpha=0.5, label="ideal equal")

    info_t = ax.text(0.5, 0.95, "", transform=ax.transAxes,
                     ha="center", va="top", color=C_TEXT,
                     fontsize=9, fontfamily="monospace")

    sample_n = [0]

    def update(_):
        v = read_u16(ser)
        bucket = min(v // bucket_w, BUCKETS - 1)
        counts[bucket] += 1
        sample_n[0]    += 1

        # Colour bars: high buckets amber, low buckets violet, mid blue
        high_start = (HIGH_THRESH // bucket_w)
        low_end    = (LOW_THRESH  // bucket_w)
        max_c      = max(counts) or 1

        for i, (bar, c) in enumerate(zip(bars, counts)):
            bar.set_height(c)
            if i >= high_start:
                bar.set_color(C_AMBER)
            elif i <= low_end:
                bar.set_color(C_VIOLET)
            else:
                bar.set_color(C_BLUE)

        ideal.set_ydata([sample_n[0] / BUCKETS] * 2)
        ax.set_ylim(0, max_c * 1.15)

        # Skew detection
        high_sum = sum(counts[high_start:])
        low_sum  = sum(counts[:low_end+1])
        mid_sum  = sample_n[0] - high_sum - low_sum
        skew = ""
        if high_sum > mid_sum * 1.5:
            skew = "  ⚠ HIGH SKEW"
        elif low_sum > mid_sum * 1.5:
            skew = "  ⚠ LOW SKEW"

        info_t.set_text(f"samples: {sample_n[0]}{skew}")
        info_t.set_color(C_AMBER if skew else C_TEXT)

        return bars.patches + [ideal, info_t]

    ani = animation.FuncAnimation(fig, update, interval=30,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 3 — Noise Canvas
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="Noise Canvas",
    description=(
        "Fills a pixel grid using TRNG values mapped to colour. Each new "
        "value paints the next cell. True randomness looks like TV static — "
        "rich, varied, no pattern. Drift produces visible patches or streaks "
        "of the same colour bleeding across the canvas."
    )
)
def demo_noise_canvas():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np

    COLS, ROWS = 80, 60
    canvas = np.zeros((ROWS, COLS, 3))
    pos    = [0]   # current cell index
    ser    = open_serial()

    fig, ax = plt.subplots(figsize=(10, 7), facecolor=C_BG)
    fig.canvas.manager.set_window_title("Noise Canvas")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Noise Canvas  ·  TrueRNG v3",
                 color=C_TEXT, fontsize=11, fontfamily="monospace")
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)

    img = ax.imshow(canvas, interpolation="nearest", vmin=0, vmax=1,
                    aspect="auto")

    info_t = ax.text(0.5, -0.04, "", transform=ax.transAxes,
                     ha="center", color=C_TEXT, fontsize=8,
                     fontfamily="monospace")

    # Map u16 → RGB using hue cycling for rich colour
    def val_to_rgb(v):
        n = v / 65535.0
        # hue-based: shift through blue→green→amber→violet
        if   n < 0.25:  r, g, b = 0.0,        n*4,       1.0
        elif n < 0.50:  r, g, b = 0.0,        1.0,       1-(n-0.25)*4
        elif n < 0.75:  r, g, b = (n-0.5)*4,  1.0,       0.0
        else:           r, g, b = 1.0,        1-(n-0.75)*4, 0.0
        return r, g, b

    TOTAL = ROWS * COLS
    BATCH = 8   # cells painted per frame

    def update(_):
        for _ in range(BATCH):
            v   = read_u16(ser)
            idx = pos[0] % TOTAL
            row = idx // COLS
            col = idx  % COLS
            canvas[row, col] = val_to_rgb(v)
            pos[0] += 1

        img.set_data(canvas)

        pct = min(100, int(pos[0] / TOTAL * 100))
        info_t.set_text(f"cells painted: {pos[0]}   canvas fills: {pos[0]//TOTAL}")
        return img, info_t

    ani = animation.FuncAnimation(fig, update, interval=30,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 4 — Colour Stream
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="Colour Stream  (Waterfall)",
    description=(
        "Each TRNG value becomes a colour stripe scrolling downward like a "
        "waterfall. True randomness produces a rich, varied cascade of "
        "colour — no two stripes the same. Drift creates long bands of "
        "near-identical colour, clearly visible as a solid block in the flow."
    )
)
def demo_colour_stream():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import numpy as np

    WIDTH  = 120   # stripes wide
    HEIGHT = 80    # rows visible
    canvas = np.zeros((HEIGHT, WIDTH, 3))
    ser    = open_serial()

    fig, ax = plt.subplots(figsize=(11, 6), facecolor=C_BG)
    fig.canvas.manager.set_window_title("Colour Stream — Waterfall")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Colour Stream  ·  TrueRNG v3",
                 color=C_TEXT, fontsize=11, fontfamily="monospace")

    img    = ax.imshow(canvas, interpolation="nearest", aspect="auto")
    info_t = ax.text(0.5, -0.04, "", transform=ax.transAxes,
                     ha="center", color=C_TEXT, fontsize=8,
                     fontfamily="monospace")

    sample_n = [0]

    def val_to_rgb(v):
        """Map u16 to a vivid HSV-like colour."""
        import colorsys
        hue = v / 65535.0
        sat = 0.75 + 0.25 * ((v % 8192) / 8192.0)
        val = 0.6  + 0.4  * ((v % 4096) / 4096.0)
        return colorsys.hsv_to_rgb(hue, sat, val)

    STRIPES_PER_FRAME = 2

    def update(_):
        nonlocal canvas
        sample_n[0] += STRIPES_PER_FRAME

        # Read one value → one full-width stripe
        for _ in range(STRIPES_PER_FRAME):
            v   = read_u16(ser)
            rgb = val_to_rgb(v)
            new_row = np.full((1, WIDTH, 3), rgb)
            # Scroll down: drop last row, prepend new stripe at top
            canvas = np.concatenate([new_row, canvas[:-1]], axis=0)

        img.set_data(canvas)
        info_t.set_text(f"stripes: {sample_n[0]}")
        return img, info_t

    ani = animation.FuncAnimation(fig, update, interval=40,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 5 — 2D Scatter Heatmap
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="2-D Scatter  (Dot Cloud)",
    description=(
        "Reads pairs of TRNG values and plots them as (x, y) coordinates. "
        "A perfect RNG fills the square evenly — a uniform dot cloud with "
        "no gaps or clusters. Drift pushes dots into a corner or band, "
        "leaving the rest of the canvas almost empty."
    )
)
def demo_scatter():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation

    MAX_DOTS = 2000
    xs = deque(maxlen=MAX_DOTS)
    ys = deque(maxlen=MAX_DOTS)
    ser = open_serial()

    fig, ax = plt.subplots(figsize=(7, 7), facecolor=C_BG)
    fig.canvas.manager.set_window_title("2-D Scatter")
    ax.set_facecolor(C_PANEL)
    ax.set_xlim(0, 65535)
    ax.set_ylim(0, 65535)
    ax.set_aspect("equal")
    ax.set_xlabel("value  (sample N)",   color=C_TEXT, fontsize=9,
                  fontfamily="monospace")
    ax.set_ylabel("value  (sample N+1)", color=C_TEXT, fontsize=9,
                  fontfamily="monospace")
    ax.tick_params(colors=C_TEXT, labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)
    ax.set_title("2-D Scatter  ·  TrueRNG v3",
                 color=C_TEXT, fontsize=11, fontfamily="monospace")

    # Quadrant guides
    ax.axhline(32767, color=C_AXIS, linewidth=0.5)
    ax.axvline(32767, color=C_AXIS, linewidth=0.5)

    sc     = ax.scatter([], [], s=2, color=C_BLUE, alpha=0.4, zorder=3)
    info_t = ax.text(0.02, 0.97, "", transform=ax.transAxes,
                     color=C_TEXT, fontsize=8, va="top",
                     fontfamily="monospace")

    prev = [read_u16(ser)]

    DOTS_PER_FRAME = 6

    def update(_):
        for _ in range(DOTS_PER_FRAME):
            v = read_u16(ser)
            xs.append(prev[0])
            ys.append(v)
            prev[0] = v

        xl = list(xs)
        yl = list(ys)
        sc.set_offsets(list(zip(xl, yl)))

        # Colour each dot by drift zone of y value
        colours = []
        for yv in yl:
            if yv > HIGH_THRESH:    colours.append(C_AMBER)
            elif yv < LOW_THRESH:   colours.append(C_VIOLET)
            else:                   colours.append(C_BLUE)
        sc.set_color(colours)

        info_t.set_text(f"dots: {len(xl)}")
        return sc, info_t

    ani = animation.FuncAnimation(fig, update, interval=40,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# DEMO 6 — Circle Burst
# ─────────────────────────────────────────────────────────────────────────────
@demo(
    title="Circle Burst",
    description=(
        "Each TRNG value spawns a translucent circle at a position and size "
        "determined by consecutive values. True randomness scatters circles "
        "evenly across the canvas in a range of sizes. Drift clusters them "
        "into one region — you'll see a glowing pile build up in a corner "
        "while the rest of the canvas stays dark."
    )
)
def demo_circle_burst():
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.patches import Circle

    ser  = open_serial()
    buf  = []   # rolling (x, y, r, colour) for up to N circles

    MAX_CIRCLES = 300

    fig, ax = plt.subplots(figsize=(8, 8), facecolor=C_BG)
    fig.canvas.manager.set_window_title("Circle Burst")
    ax.set_facecolor(C_PANEL)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor(C_AXIS)
    ax.set_title("Circle Burst  ·  TrueRNG v3",
                 color=C_TEXT, fontsize=11, fontfamily="monospace")

    info_t = ax.text(0.5, 0.01, "", transform=ax.transAxes,
                     ha="center", color=C_TEXT, fontsize=8,
                     fontfamily="monospace")

    patches = []
    sample_n = [0]
    v_buf    = []   # accumulate values to consume 3 per circle

    def pick_colour(x, y):
        # Colour by position: corners show drift bias
        if x > norm(HIGH_THRESH) or y > norm(HIGH_THRESH):
            return C_AMBER
        elif x < norm(LOW_THRESH) or y < norm(LOW_THRESH):
            return C_VIOLET
        return C_BLUE

    CIRCLES_PER_FRAME = 3

    def update(_):
        nonlocal patches

        for _ in range(CIRCLES_PER_FRAME):
            # Read 3 values: x position, y position, radius
            vx = read_u16(ser)
            vy = read_u16(ser)
            vr = read_u16(ser)
            sample_n[0] += 3

            x = norm(vx)
            y = norm(vy)
            r = 0.01 + norm(vr) * 0.07

            col = pick_colour(x, y)
            buf.append((x, y, r, col))

        # Trim to max
        while len(buf) > MAX_CIRCLES:
            buf.pop(0)

        # Redraw all circles
        for p in patches:
            p.remove()
        patches = []

        for i, (x, y, r, col) in enumerate(buf):
            alpha = 0.08 + 0.25 * (i / len(buf))
            c = Circle((x, y), r, color=col, alpha=alpha, linewidth=0)
            ax.add_patch(c)
            patches.append(c)

        info_t.set_text(f"circles: {len(buf)}   values read: {sample_n[0]}")
        return patches + [info_t]

    ani = animation.FuncAnimation(fig, update, interval=50,
                                  blit=False, cache_frame_data=False)
    plt.tight_layout()
    try:
        plt.show()
    finally:
        ser.close()

# ─────────────────────────────────────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────────────────────────────────────
BORDER = "─" * 62

def print_menu():
    print(f"\n\033[1m{'TrueRNG v3  ·  Generative Art Demos':^62}\033[0m")
    print(f"\033[90m{'Device: /dev/ttyACM0':^62}\033[0m")
    print(f"\033[90m{BORDER}\033[0m")
    for i, d in enumerate(DEMOS, 1):
        print(f"\n  \033[1;96m[{i}]\033[0m  \033[1m{d['title']}\033[0m")
        wrapped = textwrap.fill(d["description"], width=54,
                                initial_indent="       ",
                                subsequent_indent="       ")
        print(f"\033[90m{wrapped}\033[0m")
    print(f"\n\033[90m{BORDER}\033[0m")
    print(f"  \033[90m[Q]  Quit\033[0m")
    print()

def main():
    while True:
        print_menu()
        try:
            raw = input("  Select a demo: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\nBye!")
            sys.exit(0)

        if raw in ("q", "quit", "exit"):
            print("\nBye!")
            sys.exit(0)

        try:
            choice = int(raw)
        except ValueError:
            print("\n  \033[91mPlease enter a number or Q.\033[0m")
            continue

        if not 1 <= choice <= len(DEMOS):
            print(f"\n  \033[91mEnter a number between 1 and {len(DEMOS)}.\033[0m")
            continue

        demo_entry = DEMOS[choice - 1]
        print(f"\n  \033[92mLaunching: {demo_entry['title']}\033[0m")
        print("  \033[90mClose the plot window to return to this menu.\033[0m\n")

        try:
            demo_entry["fn"]()
        except serial.SerialException as e:
            print(f"\n  \033[91mSerial error: {e}\033[0m")
            print("  Check that /dev/ttyACM0 is connected and you are in the dialout group.\n")
        except Exception as e:
            print(f"\n  \033[91mError: {e}\033[0m\n")

if __name__ == "__main__":
    import serial
    main()
