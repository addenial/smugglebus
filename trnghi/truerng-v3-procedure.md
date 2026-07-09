# TrueRNG v3 — Setup & Demo Procedure
## Platform: Raspberry Pi 4 | Kali Linux

---

## PHASE 1 — Pre-Connection: Snapshot /dev Before Plugging In

Before inserting the USB, capture the current device list so you can diff it after insertion.

```bash
# List all /dev entries and save to a reference file
ls /dev > /tmp/dev_before.txt

# Also list USB-serial devices specifically (will be empty if none connected)
ls /dev/ttyUSB* 2>/dev/null || echo "No ttyUSB devices found yet"
ls /dev/ttyACM* 2>/dev/null || echo "No ttyACM devices found yet"
```

---

## PHASE 2 — Plug In the TrueRNG v3

Insert the TrueRNG v3 into a USB port on the Raspberry Pi 4.

Wait 2–3 seconds, then confirm the OS detected it:

```bash
# List /dev again and compare
ls /dev > /tmp/dev_after.txt
diff /tmp/dev_before.txt /tmp/dev_after.txt
```

You should see a new entry `/dev/ttyACM0` appear in the diff output.

```bash
# Confirm the device node directly
ls -l /dev/ttyACM0

# Check kernel messages to confirm driver loaded
dmesg | tail -20
```

Expected dmesg output will include lines similar to:
```
usb X-X: new full-speed USB device
cdc_acm X-X: ttyACM0: USB ACM device
```

The TrueRNG v3 appears as a **CDC ACM** USB device (`ttyACM0`), using the `cdc_acm` driver built into the Kali Linux kernel.

---

## PHASE 3 — Create Python Virtual Environment

Using a virtual environment keeps dependencies isolated from the system Python.

```bash
# Create the virtual environment in the current directory
python3 -m venv .

# Confirm the local Python binary is present
ls bin/python3
```

All subsequent Python and pip commands use the venv binaries directly — no need to activate.

---

## PHASE 4 — Install Dependencies

```bash
# Update package list
sudo apt update

# Install Python3 and pip if not already present
sudo apt install -y python3 python3-pip

# Install pyserial for serial communication
./bin/python3 -m pip install pyserial

# Install matplotlib for the GUI graph demo
./bin/python3 -m pip install matplotlib

# Add your user to the dialout group so you can access /dev/ttyACM0 without sudo
sudo usermod -aG dialout $USER

# Apply group change in current shell (or log out/in)
newgrp dialout
```


---

## PHASE 5 — Configure the Serial Port

The TrueRNG v3 communicates over serial at **115200 baud**.

```bash
# Set port parameters using stty
stty -F /dev/ttyACM0 115200 raw -echo

# Confirm settings
stty -F /dev/ttyACM0 -a
```

---

## PHASE 6 — Read Random Bytes: Print to Screen

Read raw random bytes from the device and display them on screen.

```bash
# Print 64 raw random bytes to the terminal as a hex dump
dd if=/dev/ttyACM0 bs=64 count=1 | xxd

# Or stream continuously and view as hex (press Ctrl+C to stop)
cat /dev/ttyACM0 | xxd | head -10
```

---

## PHASE 7 — Capture Random Data to a File

```bash
# Capture 1024 bytes of random data into a binary file
dd if=/dev/ttyACM0 of=/tmp/random_output.bin bs=1024 count=1

# View as hex dump
xxd /tmp/random_output.bin | head -20

# View as unsigned integers (one byte each, decimal)
od -An -tu1 /tmp/random_output.bin | head -10

# Check entropy quality with ent (install if needed)
sudo apt install -y ent
ent /tmp/random_output.bin
```

A healthy TrueRNG output will show entropy near **8.0 bits per byte**.

---

## PHASE 8 — Terminal Demo: Live Random Numbers

Save the following as `truerng_terminal.py`:

```python
#!/usr/bin/env python3
"""
TrueRNG v3 — Terminal Real-Time Demo
Device: /dev/ttyACM0

Shows a live scrolling bar in the terminal with HIGH/LOW indicators.
Press Ctrl+C to stop.
"""

import serial
import time
import sys

DEVICE    = "/dev/ttyACM0"
BAUD      = 115200
BAR_WIDTH = 50

def read_uint16(ser):
    raw = ser.read(2)
    return int.from_bytes(raw, byteorder='big')

def render_bar(value, max_val=65535, width=BAR_WIDTH):
    filled = int((value / max_val) * width)
    return "█" * filled + "░" * (width - filled)

def classify(value):
    if value > 55000:
        return "\033[91m HIGH \033[0m"
    elif value < 10000:
        return "\033[94m LOW  \033[0m"
    else:
        return "\033[92m MID  \033[0m"

print("\n\033[1mTrueRNG v3 — Live Terminal Demo\033[0m")
print(f"Device : {DEVICE}  |  Baud : {BAUD}")
print("─" * 70)
print("Press Ctrl+C to stop\n")

try:
    ser = serial.Serial(DEVICE, BAUD, timeout=2)
    time.sleep(0.1)
    ser.reset_input_buffer()

    sample  = 0
    t_start = time.time()

    while True:
        value   = read_uint16(ser)
        elapsed = time.time() - t_start
        sample += 1

        line = (
            f"  t={elapsed:6.2f}s  "
            f"#{sample:>5}  "
            f"|{render_bar(value)}|  "
            f"{value:>5}  "
            f"{classify(value)}"
        )

        sys.stdout.write("\r\033[K" + line)
        sys.stdout.flush()
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n\nStopped.")
    ser.close()
except serial.SerialException as e:
    print(f"\nSerial error: {e}")
```

Run it:

```bash
./bin/python3 truerng_terminal.py
```

---

## PHASE 9 — GUI Demo: Real-Time Random Number Graph

Save the following as `truerng_gui.py`:

```python
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
```

Run it:

```bash
./bin/python3 truerng_gui.py
```

A dark-themed window opens with a scrolling line graph (20-second window) and a live gauge bar at the bottom. Close the window to stop.

---

## Quick Troubleshooting

| Symptom | Fix |
|---|---|
| `/dev/ttyACM0` does not appear | Try a different USB port; run `dmesg \| tail -30` for errors |
| Permission denied on `/dev/ttyACM0` | Run `sudo usermod -aG dialout $USER` then `newgrp dialout` |
| `cdc_acm` driver missing | `sudo modprobe cdc_acm` |
| `ModuleNotFoundError: serial` | `./bin/python3 -m pip install pyserial` |
| `ModuleNotFoundError: matplotlib` | `./bin/python3 -m pip install matplotlib` |
| Graph window does not open | Ensure a display is connected; if SSH, set `export DISPLAY=:0` |
| No data / serial timeout | Run `stty -F /dev/ttyACM0 115200 raw -echo` first |
| Wrong Python used | Always use `./bin/python3`, never bare `python3` outside the venv |
