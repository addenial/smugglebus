
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
    
    
    
