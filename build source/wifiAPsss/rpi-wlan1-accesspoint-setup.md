# Raspberry Pi 4 — wlan1 Access Point (Bridged to eth0)

**OS:** Raspbian GNU/Linux 9 (Stretch) — armv7l  
**Goal:** wlan1 as WPA2 AP (ssid: `wifi1`, pass: `monkeyrobot`), bridged into
existing `10.0.0.0/24` LAN so eth0 and wlan1 clients share the same subnet and
broadcast domain (PS4 Remote Play, mDNS, etc.)

---

## Network Layout

```
Internet
   │
 wlan0  ← DHCP from your upstream router (wpa_supplicant@wlan0)
   │
  Pi  ← iptables MASQUERADE (your existing script)
   │
  br0  (10.0.0.69 static — dnsmasq serves DHCP here)
 ┌──┴──┐
eth0  wlan1
 │       └── AP: wifi1 / monkeyrobot
PS4   Laptops/Phones
```

---

## Interface roles

| Interface | Role | IP |
|-----------|------|----|
| `wlan0` | Internet uplink | DHCP from upstream router |
| `eth0` | Bridge port | None (owned by br0) |
| `wlan1` | Bridge port / AP | None (owned by br0) |
| `br0` | LAN bridge | `10.0.0.69` (static) |

---

## Step 1 — Install packages

```bash
sudo apt-get update
sudo apt-get install -y hostapd bridge-utils
```

> **⚠️ Raspbian Stretch (EOL) — bridge-utils 404 error:**  
> The main mirror has dropped packages for Stretch. Install bridge-utils manually:
> ```bash
> wget http://archive.debian.org/debian/pool/main/b/bridge-utils/bridge-utils_1.5-13+deb9u1_armhf.deb
> sudo dpkg -i bridge-utils_1.5-13+deb9u1_armhf.deb
> ```
> Verify:
> ```bash
> dpkg -l bridge-utils   # should show:  ii  bridge-utils  1.5-13+deb9u1
> which brctl            # should return: /sbin/brctl
> ```

---

## Step 2 — Configure hostapd

Create the config file:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Paste exactly:

```
interface=wlan1
driver=nl80211
ssid=wifi1
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
wpa=2
wpa_passphrase=monkeyrobot
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Point hostapd at that config:

```bash
sudo nano /etc/default/hostapd
```

Find `#DAEMON_CONF=""` and change it to:

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

---

## Step 3 — Fix wpa_supplicant (wlan0 only)

By default Raspbian runs a global wpa_supplicant that attaches to **all**
wireless interfaces including wlan1. This fights hostapd for wlan1 and causes
`nl80211: Could not configure driver mode`. Switch to a wlan0-only instance:

```bash
sudo cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
sudo systemctl disable wpa_supplicant
sudo systemctl enable wpa_supplicant@wlan0
```

---

## Step 4 — Update dhcpcd.conf

```bash
sudo nano /etc/dhcpcd.conf
```

At the **bottom of the file**, remove your existing `interface eth0` static
block and replace everything from it downward with:

```
interface br0
static ip_address=10.0.0.69/24
nolink

denyinterfaces eth0 wlan1

interface eth0
noipv4ll
nohook wpa_supplicant

interface wlan1
noipv4ll
nohook wpa_supplicant
```

Verify the bottom looks exactly right:

```bash
tail -20 /etc/dhcpcd.conf
```

Also verify no conflicts — there should be no other uncommented `interface eth0`
or `interface wlan1` blocks anywhere in the file:

```bash
grep -n "^interface\|^denyinterfaces\|^nohook\|^noipv4ll" /etc/dhcpcd.conf
```

> **Why `noipv4ll`:** Even with `denyinterfaces`, dhcpcd on Stretch sees eth0
> and wlan1 come up as bridge members and falls back to assigning `169.254.x.x`
> link-local addresses. `noipv4ll` suppresses that fallback entirely.
>
> **Why `nohook wpa_supplicant`:** Prevents dhcpcd from spawning its own
> wpa_supplicant on those interfaces, which would fight hostapd.

---

## Step 5 — Create the bridge

```bash
sudo nano /etc/network/interfaces
```

Add at the bottom:

```
auto br0
iface br0 inet manual
    bridge_ports eth0 wlan1
    bridge_stp off
    bridge_fd 0
```

> `inet manual` — dhcpcd handles the IP on br0; this file just defines the
> bridge structure.

---

## Step 6 — Add wlan1 to bridge automatically after hostapd starts

On Raspbian Stretch, hostapd does not automatically add wlan1 to the bridge
after claiming it in AP mode. Without this step, wlan1 clients connect to the
AP but get no DHCP and cannot reach the Pi or other LAN devices.

Create a systemd drop-in that runs `brctl addif` every time hostapd starts:

```bash
sudo mkdir -p /etc/systemd/system/hostapd.service.d
sudo nano /etc/systemd/system/hostapd.service.d/override.conf
```

Paste:

```
[Service]
ExecStartPost=/sbin/brctl addif br0 wlan1
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

---

## Step 7 — Update dnsmasq to use the bridge

```bash
sudo nano /etc/dnsmasq.conf
```

Change:

```
# REMOVE:
interface=eth0

# ADD:
interface=br0
```

---

## Step 8 — Enable hostapd and reboot

```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo reboot
```

> **What `unmask` does:** Raspbian ships hostapd masked (hard-disabled via
> symlink to /dev/null) to prevent accidental AP startup. `unmask` removes
> that block. `enable` sets it to start at boot.

---

## Step 9 — Verify after reboot

```bash
# wpa_supplicant should only show -iwlan0, NOT -iwlan1
ps aux | grep wpa_supplicant

# Both eth0 AND wlan1 should be listed under br0
brctl show

# hostapd should be active (running) and show AP-ENABLED
sudo systemctl status hostapd

# br0 should have 10.0.0.69
ifconfig br0

# eth0 and wlan1 should have NO inet address — only a MAC
ifconfig eth0
ifconfig wlan1

# wlan0 should have your upstream router IP
ifconfig wlan0

# dnsmasq should be running and bound to br0
sudo systemctl status dnsmasq

# Check active DHCP leases
sudo cat /var/lib/misc/dnsmasq.leases
```

Expected results:

```
# ps aux | grep wpa_supplicant
wpa_supplicant -iwlan0 ...      ← only wlan0, no wlan1

# brctl show
bridge name   bridge id           STP  interfaces
br0           8000.b827ebc57b0e   no   eth0
                                       wlan1

# ifconfig eth0 / wlan1 — no inet line, only ether (MAC)

# ifconfig br0
br0: inet 10.0.0.69  netmask 255.255.255.0
```

---

## Troubleshooting

### hostapd config file not found

```
Could not open configuration file '/etc/hostapd/hostapd.conf'
```

The file was never saved. Recreate it:

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Paste the config from Step 2. Also confirm `/etc/default/hostapd` has
`DAEMON_CONF="/etc/hostapd/hostapd.conf"` uncommented.

---

### hostapd fails: `nl80211: Could not configure driver mode`

wpa_supplicant is running on wlan1 and fighting hostapd. Check:

```bash
ps aux | grep wpa_supplicant
```

If you see `-iwlan1` in the output, Step 3 hasn't taken effect. Confirm:

```bash
sudo systemctl status wpa_supplicant        # should be disabled/inactive
sudo systemctl status wpa_supplicant@wlan0  # should be enabled/active
```

Repeat Step 3 and reboot. You can also kill it and test hostapd immediately:

```bash
sudo pkill -f "wpa_supplicant.*wlan1"
sudo iw dev wlan1 set type __ap
sudo hostapd /etc/hostapd/hostapd.conf
```

---

### eth0 or wlan1 gets a 169.254.x.x address

dhcpcd sees the interface come up as a bridge member and falls back to a
link-local IP. Check for two causes:

**Cause A — missing `noipv4ll`:** Confirm your dhcpcd.conf has the `interface
eth0` and `interface wlan1` blocks with `noipv4ll` from Step 4.

**Cause B — stray interface block overriding `denyinterfaces`:** Check:

```bash
grep -n "^interface\|^denyinterfaces" /etc/dhcpcd.conf
```

Remove any extra uncommented `interface eth0` or `interface wlan1` blocks.
Then flush and reboot:

```bash
sudo ip addr flush dev eth0
sudo ip addr flush dev wlan1
sudo reboot
```

---

### wlan1 clients connect to wifi1 but get no IP / can't reach the Pi

wlan1 is not in the bridge. Verify:

```bash
brctl show
```

If wlan1 is missing, add it manually to test immediately:

```bash
sudo brctl addif br0 wlan1
```

If that fixes it but it doesn't survive reboot, confirm the systemd drop-in
from Step 6 is in place:

```bash
cat /etc/systemd/system/hostapd.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart hostapd
brctl show
```

---

### wlan1 not in bridge after reboot (hostapd silent failure)

If hostapd is failing silently, wlan1 never enters AP mode and the bridge
can't claim it. Check:

```bash
sudo journalctl -b | grep -i hostapd
```

Fix hostapd first (see above), then the bridge will populate automatically
via the ExecStartPost hook.

---

## Your existing NAT script

`nat-forward-rules-share-internet.sh` runs unchanged — it masquerades `br0`
traffic out through `wlan0` and does not need to know about the bridge
internals.
