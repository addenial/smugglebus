# WireGuard VPN — Remote PS4 Access via Raspberry Pi Router

**Goal:** Connect to your PS4 from anywhere via iPhone/iPad using WireGuard,
so Remote Play works exactly as if you were on your home LAN.

**Tested on:**
- OS: Raspbian GNU/Linux 9 (Stretch) — armv7l
- Hardware: Raspberry Pi 3 Model B Rev 1.2 (BCM2835)
- Router: Netgear R8000 (Tomato firmware) — concepts apply to any router

**Your values to substitute throughout this guide:**

| Placeholder | What to replace with |
|---|---|
| `<YOUR_PUBLIC_IP>` | Your WAN/public IP (`curl ifconfig.me`) |
| `<YOUR_PI_ROUTER_IP>` | Pi's IP on your router's subnet (e.g. `192.168.1.x`) |
| `<YOUR_ROUTER_IP>` | Your router's LAN IP (e.g. `192.168.1.1`) |
| `<YOUR_SERVER_PUBLIC_KEY>` | Generated in Step 5 |
| `<YOUR_IPHONE_PUBLIC_KEY>` | Generated in Step 6 |
| `10.0.0.69` | Your Pi's bridge IP |
| `10.0.0.117` | Your PS4's LAN IP |

---

## How this works

```
iPhone (anywhere, cellular/any WiFi)
   │
   │  WireGuard tunnel — UDP 51820 (your one forwarded port)
   ▼
Your router (forwards UDP 51820 → Pi 10.0.0.69)
   ▼
Pi — WireGuard server (wg0 interface, routed mode)
   ▼
br0 (10.0.0.0/24) — PS4 lives here, eth0 + wlan1
   ▼
Remote Play connects to PS4 at 10.0.0.117 as if local
```

WireGuard uses **routed mode** (not a true L2 bridge) — your iPhone gets an
IP in a new VPN subnet (`10.8.0.0/24`) and the Pi routes traffic between that
subnet and `10.0.0.0/24`. Remote Play works fine over routed IP; it does not
strictly require L2 broadcast once a console is manually added by IP.

---

## Part 1 — Router configuration

You mentioned port forwarding and a static public IP are already easy on
your end. Configure exactly **one rule**:

| Setting | Value |
|---|---|
| Protocol | **UDP only** |
| External port | `51820` |
| Internal IP | `<YOUR_PI_ROUTER_IP>` (Pi's wlan0 — what your router sees) |
| Internal port | `51820` |

> **Why `<YOUR_PI_ROUTER_IP>` and not `10.0.0.69`:** The Pi has two "faces".
> Your router only knows about `<YOUR_PI_ROUTER_IP>` (Pi's wlan0, on the router's
> own subnet). The `10.0.0.69` address is internal to the Pi's own bridge
> (br0) and is invisible to your router. WireGuard traffic arrives at
> `<YOUR_PI_ROUTER_IP>:51820` on wlan0, then the Pi routes it internally into br0
> to reach the PS4.
>
> **Why UDP only:** WireGuard runs entirely over UDP. No TCP forwarding
> needed. WireGuard also does not respond to port scans or probes —
> it stays completely silent unless a valid encrypted handshake is
> presented, so this single open port is very low risk.

No other ports need forwarding. All Remote Play traffic travels **inside**
the encrypted WireGuard tunnel — the router doesn't need to know anything
about Remote Play itself.

---

## Part 2 — Pi: Install and configure WireGuard

### Step 1 — Install kernel headers

```bash
# Confirm kernel version
uname -r
# Should show: 4.19.66-v7+

# Download matching headers
wget http://archive.raspberrypi.org/debian/pool/main/r/raspberrypi-firmware/raspberrypi-kernel-headers_1.20190819-1_armhf.deb
sudo dpkg -i raspberrypi-kernel-headers_1.20190819-1_armhf.deb

# Verify
ls /lib/modules/4.19.66-v7+/build
# Should list directories: arch, drivers, include, etc.
```

### Step 2 — Install dirmngr

```bash
wget http://archive.debian.org/debian/pool/main/g/gnupg2/dirmngr_2.1.18-8~deb9u4_armhf.deb
sudo dpkg -i dirmngr_2.1.18-8~deb9u4_armhf.deb
```

### Step 3 — Install wireguard-tools

```bash
wget http://archive.debian.org/debian/pool/main/w/wireguard/wireguard-tools_1.0.20210223-1_armhf.deb
sudo dpkg -i wireguard-tools_1.0.20210223-1_armhf.deb

# Verify
wg --version
# Should show: wireguard-tools v1.0.20210223
```

### Step 4 — Install Go and build wireguard-go from source

The Pi 3 kernel (4.19.66) does not have the WireGuard kernel module —
it was added to mainline Linux in 5.6. wireguard-go provides userspace
WireGuard with no kernel module required. No pre-built ARM binaries exist
so we build from source using Go.

```bash
# Download Go for ARM (armv6l works on Pi 3 and Pi 4 32-bit)
wget https://go.dev/dl/go1.21.6.linux-armv6l.tar.gz
sudo tar -C /usr/local -xzf go1.21.6.linux-armv6l.tar.gz

# Add to PATH for this session
export PATH=$PATH:/usr/local/go/bin

# Verify Go
go version
# Should show: go version go1.21.6 linux/arm
```

Clone and build wireguard-go:

```bash
git clone https://github.com/WireGuard/wireguard-go.git
cd wireguard-go
make
# Takes several minutes on Pi 3 — compiling Go source
```

Install the binary:

```bash
sudo cp wireguard-go /usr/local/bin/wireguard-go
sudo chmod 755 /usr/local/bin/wireguard-go
cd ~

# Verify
wireguard-go --version
# Should show: wireguard-go v0.0.20250522 Userspace WireGuard daemon for linux-arm
```

Make Go PATH and WireGuard userspace setting permanent:

```bash
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
echo 'export WG_QUICK_USERSPACE_IMPLEMENTATION=wireguard-go' >> ~/.bashrc
source ~/.bashrc
```

> **Why wireguard-go shows "kernel has first class support" warning:**
> This is a hardcoded generic message in wireguard-go source — it always
> shows regardless of whether the kernel module actually exists. It does
> NOT mean the kernel module is available. Confirm with:
> ```bash
> sudo modprobe wireguard
> # If returns: FATAL: Module wireguard not found → wireguard-go is needed
> ```

---

### Step 5 — Generate server keys

```bash
mkdir ~/wgkeys
cd ~/wgkeys
umask 077
wg genkey | tee server_private.key | wg pubkey > server_public.key
cat server_private.key
cat server_public.key
```

Keep both — you'll need `server_public.key` for the iPhone config in Part 3.

### Step 6 — Generate a client key pair (for your iPhone)

```bash
wg genkey | tee iphone_private.key | wg pubkey > iphone_public.key
cat iphone_private.key
cat iphone_public.key
```

You'll need `iphone_private.key` for the iPhone app config (Part 3) and
`iphone_public.key` for the server config below.

### Step 7 — Create the WireGuard server config

```bash
sudo nano /etc/wireguard/wg0.conf
```

Paste — replace `<SERVER_PRIVATE_KEY>` and `<IPHONE_PUBLIC_KEY>` with the
values from Steps 5 and 6:

```ini
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = <SERVER_PRIVATE_KEY>
PostUp   = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o br0 -j MASQUERADE; iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o br0 -j MASQUERADE; iptables -t nat -D POSTROUTING -o wlan0 -j MASQUERADE

[Peer]
# iPhone
PublicKey = <IPHONE_PUBLIC_KEY>
AllowedIPs = 10.8.0.2/32
```

> **What the PostUp/PostDown lines do:** They allow traffic to flow between
> the VPN tunnel and your `br0` LAN, and masquerade VPN client traffic so
> PS4 sees it as coming from the Pi (similar to your existing wlan0
> masquerade rule, just for the wg0 → br0 direction).

### Step 8 — Allow IP forwarding (likely already on from your AP setup)

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

Make it permanent if not already:

```bash
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
```

### Step 9 — Bring up the WireGuard interface

```bash
sudo WG_QUICK_USERSPACE_IMPLEMENTATION=wireguard-go wg-quick up wg0
```

Expected output:

```
[#] ip link add wg0 type wireguard
RTNETLINK answers: Operation not supported
[!] Missing WireGuard kernel module. Falling back to slow userspace implementation.
[#] wireguard-go wg0
[#] wg setconf wg0 /dev/fd/63
[#] ip -4 address add 10.8.0.1/24 dev wg0
[#] ip link set mtu 1420 up dev wg0
[#] iptables -A FORWARD -i wg0 -j ACCEPT ...
```

> The "Missing WireGuard kernel module. Falling back to slow userspace
> implementation" message is expected and fine — wireguard-go takes over
> and the interface comes up successfully. "Slow" is relative; it is
> perfectly adequate for PS4 Remote Play.

Verify interface is up:

```bash
sudo wg show
ip addr show wg0
```

Expected `wg show` output:

```
interface: wg0
  public key: <YOUR_SERVER_PUBLIC_KEY>
  private key: (hidden)
  listening port: 51820

peer: <YOUR_IPHONE_PUBLIC_KEY>
  allowed ips: 10.8.0.2/32
```

> **Why `ListenPort = 51820`:** Explicitly set in `wg0.conf`. If omitted,
> WireGuard picks a random port each restart which would break the router
> port forward rule. Always specify it.

Verify:

```bash
sudo wg show
ip addr show wg0
```

You should see `wg0` with IP `10.8.0.1` and your iPhone's public key listed
as a peer (handshake will show "(none)" until the iPhone connects).

### Step 10 — Enable NAT forwarding as a boot service

Your existing `nat-forward-rules-share-internet.sh` must run at boot
**before** WireGuard starts, otherwise the tunnel comes up without internet
forwarding in place. Create a systemd service for it:

```bash
sudo bash -c 'cat > /etc/systemd/system/nat-forward.service << EOF
[Unit]
Description=NAT forwarding rules for internet sharing
After=network.target
Before=wg-quick@wg0.service

[Service]
Type=oneshot
ExecStart=/bin/bash /home/pi/nat-forward-rules-share-internet.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF'
```

> **Why `here-doc` (`<< EOF`) instead of nano:** Copy-pasting a systemd
> unit file into nano can introduce hidden characters or encoding issues
> that cause `Bad message` errors. The `bash -c 'cat > file << EOF'`
> method writes the file directly from the shell, avoiding this entirely.

Verify the file looks clean:

```bash
cat /etc/systemd/system/nat-forward.service
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nat-forward
sudo systemctl start nat-forward
sudo systemctl status nat-forward
```

---

### Step 11 — Enable WireGuard to start on boot

Create a systemd override so the `wireguard-go` env var is always set:

```bash
sudo mkdir -p /etc/systemd/system/wg-quick@wg0.service.d
sudo bash -c 'cat > /etc/systemd/system/wg-quick@wg0.service.d/override.conf << EOF
[Service]
Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=wireguard-go
EOF'
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
sudo systemctl status wg-quick@wg0
```

> `Active: active (exited)` is normal — wg-quick runs once to bring up
> the interface then exits. The interface stays up.

---

### Step 12 — Reboot and verify everything comes up automatically

```bash
sudo reboot
```

After reboot confirm full stack:

```bash
# NAT rules applied
sudo iptables -t nat -L POSTROUTING -n
# Should show MASQUERADE on wlan0

# WireGuard interface up
sudo wg show
# Should show wg0, listening port 51820, iPhone peer

# Internet working
ping -c3 1.1.1.1

# Bridge intact
brctl show
# Should show eth0 and wlan1 under br0

# All services healthy
sudo systemctl status nat-forward wg-quick@wg0 hostapd dnsmasq
```

---

### Template — converting any bash script to a boot service

Use this pattern any time you need a script to run automatically at boot
on Raspbian/Debian systemd systems:

```bash
sudo bash -c 'cat > /etc/systemd/system/YOUR-SERVICE-NAME.service << EOF
[Unit]
Description=Human readable description of what this does
After=network.target
Before=some-other.service

[Service]
Type=oneshot
ExecStart=/bin/bash /path/to/your/script.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable YOUR-SERVICE-NAME
sudo systemctl start YOUR-SERVICE-NAME
sudo systemctl status YOUR-SERVICE-NAME
```

**Key fields explained:**

| Field | Purpose |
|---|---|
| `After=network.target` | Wait for network before running |
| `Before=x.service` | Run before another service |
| `Type=oneshot` | Script runs once and exits (not a daemon) |
| `RemainAfterExit=yes` | systemd considers service "active" after script exits |
| `WantedBy=multi-user.target` | Start at normal boot (not single-user/rescue) |

**Useful commands for any service:**

```bash
sudo systemctl enable SERVICE    # start on boot
sudo systemctl disable SERVICE   # remove from boot
sudo systemctl start SERVICE     # start now
sudo systemctl stop SERVICE      # stop now
sudo systemctl restart SERVICE   # restart now
sudo systemctl status SERVICE    # check status
sudo journalctl -u SERVICE -n 50 # last 50 log lines
```

---

## Part 3 — iPhone/iPad: WireGuard app setup

### Step 1 — Install the WireGuard app

Install **WireGuard** from the App Store (official app, by WireGuard
Development Team).

### Step 2 — Create a new tunnel manually

1. Open the WireGuard app
2. Tap **+** → **Create from scratch**
3. Fill in:

**Interface:**
| Field | Value |
|---|---|
| Name | `smugglebus` |
| Private Key | paste `iphone_private.key` from `~/wgkeys/` on the Pi |
| Addresses | `10.8.0.2/24` |
| DNS servers | `10.0.0.69` (optional — routes DNS through your dnsmasq) |

**Add Peer:**
| Field | Value |
|---|---|
| Public Key | your server public key from `~/wgkeys/server_public.key` |
| Endpoint | `<YOUR_PUBLIC_IP>:51820` |
| Allowed IPs | `10.0.0.0/24, 10.8.0.0/24` |
| Persistent keepalive | `25` |

> **Why `Allowed IPs = 10.0.0.0/24, 10.8.0.0/24`:** Split tunnel — only
> home LAN traffic routes through the VPN. Normal internet browsing stays
> on your cellular/WiFi connection untouched.

4. Save and toggle the tunnel **ON**

### Step 3 — Verify tunnel is live

On the Pi:

```bash
sudo wg show
```

You should see `latest handshake` timestamp updating and `transfer` bytes
increasing — confirms tunnel is live and passing traffic.

Test reachability from iPhone — while VPN is on, try reaching PS4 FTP:
```
ftp://10.0.0.117
```
If PS4 FTP responds, full routing through the tunnel is confirmed.

---

## Part 4 — PS4 Remote Play over VPN: use PXPlay

### Why the official PS Remote Play app does not work over VPN

The official **PS Remote Play** iOS app performs a pre-flight check
requiring a WiFi network connection before attempting to connect. When on
cellular with WireGuard active, the app detects a non-WiFi interface and
throws:

```
"Can't find the wifi network. Check your internet connection."
```

This is a **Sony app restriction**, not a network or VPN problem. The
tunnel itself works perfectly — PS4 FTP and SSH through the VPN both
confirmed working, proving full layer 3 reachability to `10.0.0.117`.

Workarounds attempted and why they fall short:

| Approach | Result |
|---|---|
| Enable "Use Mobile Data" in official app | Routes through Sony relay servers, not direct to PS4 — defeats self-hosted VPN purpose |
| Manual PIN registration on PS4 | Registration goes through Sony cloud — does not enable direct IP connection |
| Connect to WiFi + WireGuard simultaneously | Passes WiFi pre-flight check but requires WiFi — defeats the anywhere use case |

### Solution — PXPlay by Florian Grill

**PXPlay** is a third-party PS4/PS5 Remote Play client for iOS that
supports manual direct IP connection, bypassing Sony's WiFi requirement
and broadcast discovery entirely.

**Install:** Search **PXPlay** on the App Store (developer: Florian Grill)

**Connection steps:**

1. Ensure WireGuard tunnel is active on iPhone
2. Ensure PS4 is powered on
3. Open PXPlay
4. Select **Remote Connection** → **Manual Connection**
5. Enter PS4 IP: `10.0.0.117`
6. Tap **Connect**

> **Note:** Initial connection test takes a few minutes over public
> internet while PXPlay negotiates the stream. Once established, streaming
> is responsive and playable over cellular.

> **Why this works:** PXPlay allows direct IP specification — it connects
> straight to `10.0.0.117` through the WireGuard tunnel with no broadcast
> discovery or Sony relay involved. The VPN handles all routing
> transparently.

### Confirmed working end-to-end

```
iPhone (anywhere, cellular)
   │
   │  WireGuard tunnel UDP 51820
   ▼
<YOUR_PUBLIC_IP> → router → <YOUR_PI_ROUTER_IP> (Pi wlan0)
   ▼
Pi wg0 (10.8.0.1) → br0 → 10.0.0.117 (PS4 eth0)
   ▼
PXPlay streams PS4 gameplay — direct, no Sony relay
```

---

## Verification checklist

On the Pi, while iPhone has the tunnel active:

```bash
# Confirm handshake succeeded
sudo wg show

# Confirm iPhone got an IP and can reach the Pi
ping -c3 10.8.0.2

# Confirm iPhone can reach the PS4 across the bridge
# (run from Pi, simulating the route)
ping -c3 10.0.0.117
```

`sudo wg show` should show a `latest handshake` timestamp updating
periodically and `transfer` bytes increasing — that confirms the tunnel is
live and passing traffic.

---

## Troubleshooting

### `wg-quick up wg0` fails with module not found

wireguard-go may not be in PATH or didn't install correctly. Check:

```bash
which wireguard-go
wireguard-go --version
```

If missing, re-download:
```bash
wget https://github.com/WireGuard/wireguard-go/releases/download/0.0.20230223/wireguard-go-linux-arm
chmod +x wireguard-go-linux-arm
sudo mv wireguard-go-linux-arm /usr/local/bin/wireguard-go
```

### iPhone connects (handshake shows) but PS4 not visible

Most likely `AllowedIPs` is missing `10.0.0.0/24` on the iPhone peer config,
or `iptables FORWARD` rules aren't applied. Check:

```bash
sudo iptables -L FORWARD -v
```

You should see `ACCEPT` rules referencing `wg0`. If missing, the PostUp
lines in `wg0.conf` didn't run — restart the interface:

```bash
sudo wg-quick down wg0
sudo wg-quick up wg0
```

### Remote Play app doesn't auto-discover PS4 over VPN

This is expected — VPN routed mode doesn't carry the LAN broadcast/mDNS
discovery packets. Manually add the console by IP in the Remote Play app:
**Settings → Add Device → enter PS4's IP** (e.g. `10.0.0.117`). After the
first manual add, the app remembers it for future connections.

### Connection works at home but not remotely

Confirm your router's UDP 51820 forward rule is active and your public IP
hasn't changed (you mentioned it's static, but worth double-checking):

```bash
curl ifconfig.me
```

Should return `<YOUR_PUBLIC_IP>` — compare against the `Endpoint` in your iPhone's WireGuard config. If it changed, update the iPhone config with the new IP.

---

## Security notes

- Each additional device (iPad, laptop, etc.) needs its own key pair and
  its own `[Peer]` block in `wg0.conf` with a unique `10.8.0.x` address —
  never reuse keys across devices.
- To revoke a device, simply delete its `[Peer]` block from `wg0.conf` and
  run `sudo wg-quick down wg0 && sudo wg-quick up wg0`.
- WireGuard's silence-by-default behavior (no response to invalid packets)
  means port scanners won't even detect the open port is in use, which is
  a meaningful security advantage over typical VPN protocols.

---

## Adding a new VPN peer (e.g. iPad)

Each device needs its own unique key pair and a unique VPN IP address.
Never reuse keys between devices — if one device is lost or compromised
you can revoke just that peer without affecting others.

### Step 1 — Generate iPad key pair on the Pi

```bash
cd ~/wgkeys
umask 077
wg genkey | tee ipad_private.key | wg pubkey > ipad_public.key
cat ipad_private.key
cat ipad_public.key
```

### Step 2 — Add iPad as a peer in wg0.conf

```bash
sudo nano /etc/wireguard/wg0.conf
```

Add a new `[Peer]` block at the bottom — assign the next available IP
(`10.8.0.3` since iPhone is `10.8.0.2`):

```ini
[Peer]
# iPad
PublicKey = <IPAD_PUBLIC_KEY>
AllowedIPs = 10.8.0.3/32
```

### Step 3 — Reload WireGuard without dropping existing connections

No need to bring the tunnel down — add the peer live:

```bash
sudo wg addconf wg0 <(wg-quick strip wg0)
```

Or reload cleanly:

```bash
sudo wg syncconf wg0 <(wg-quick strip wg0)
```

Verify the new peer appears:

```bash
sudo wg show
# Should now list both iPhone (10.8.0.2) and iPad (10.8.0.3) peers
```

### Step 4 — Configure WireGuard app on iPad

Same process as iPhone (Part 3) with these differences:

**Interface:**
| Field | Value |
|---|---|
| Name | `smugglebus` |
| Private Key | paste `ipad_private.key` |
| Addresses | `10.8.0.3/24` |
| DNS servers | `10.0.0.69` |

**Peer:**
| Field | Value |
|---|---|
| Public Key | your server public key from `~/wgkeys/server_public.key` |
| Endpoint | `<YOUR_PUBLIC_IP>:51820` |
| Allowed IPs | `10.0.0.0/24, 10.8.0.0/24` |
| Persistent keepalive | `25` |

### Step 5 — Verify iPad tunnel

On the Pi after iPad connects:

```bash
sudo wg show
# Should show latest handshake for 10.8.0.3
```

---

### Peer IP address assignments

Keep track of which IP belongs to which device:

| Device | VPN IP | Key file |
|---|---|---|
| Pi (server) | `10.8.0.1` | `server_private.key` |
| iPhone | `10.8.0.2` | `iphone_private.key` |
| iPad | `10.8.0.3` | `ipad_private.key` |
| Next device | `10.8.0.4` | `devicename_private.key` |

### Revoking a device

```bash
sudo nano /etc/wireguard/wg0.conf
# Delete the [Peer] block for the device

# Reload live
sudo wg syncconf wg0 <(wg-quick strip wg0)

# Confirm peer is gone
sudo wg show
```

The removed device's tunnel immediately stops working — no reboot needed.


---

## Appendix — Router WAN hardening (Netgear R8000 / Tomato firmware)

**Context:** During WireGuard setup we discovered TCP 22 (SSH) and TCP 23
(telnet) were open on the WAN interface `vlan2` (`<YOUR_PUBLIC_IP>`). Standard
`iptables -I INPUT` rules appeared to work but were being bypassed or
overwritten by Tomato firmware's own firewall rebuild cycle.

---

### How we found it

```bash
# Port scan from LAN machine to public IP
nmap -Pn -sT -sV -n <YOUR_PUBLIC_IP> -p 21,22,23,25,80,443 --open

# Confirmed telnet was actually accepting connections
nc -v <YOUR_PUBLIC_IP> 23

# Checked what was listening
netstat -tln | grep :23

# Found telnetd process (BusyBox ps syntax)
ps w | grep telnet
# Result: 1271 root  telnetd -p 23

# Checked NAT table to understand traffic path
iptables -t nat -L -n --line-numbers
# Found: WANPREROUTING chain handles dst=<YOUR_PUBLIC_IP> before INPUT
```

---

### Why plain iptables INPUT rules didn't fully work

Tomato firmware periodically **rebuilds its own iptables chains** (on events
like WAN reconnect, service restart, or GUI save). Any rules inserted
manually with `iptables -I INPUT` survive until the next rebuild, then
disappear or get reordered.

Additionally, Tomato's INPUT chain has a blanket `ACCEPT all` rule near the
bottom that catches anything your DROP missed — including SSH connections
that pass through the `shlimit` rate-limit chain.

The correct fix is to use **Tomato's own firewall script** which is re-applied
automatically every time Tomato rebuilds its chains:

---

### Permanent fix — Tomato firewall script

In the Tomato web GUI:

**Administration → Scripts → Firewall tab**

Add these lines and click **Save**:

```bash
# Block WAN ingress SSH and telnet permanently
iptables -I INPUT -i vlan2 -p tcp --dport 22 -j DROP
iptables -I INPUT -i vlan2 -p tcp --dport 23 -j DROP
```

> These run every time Tomato rebuilds iptables — on boot, WAN reconnect,
> and GUI saves. This is the correct persistent method for Tomato firmware.
> Manual `iptables` commands on the CLI are temporary and get wiped.

---

### Kill telnetd permanently — Tomato Init script

telnetd is compiled into the Tomato firmware and started at boot. You
cannot remove the binary, but you can kill it after every boot via the
Init script:

**Administration → Scripts → Init tab**

Add:

```bash
# Kill telnetd after boot
sleep 5 && kill $(ps w | grep telnetd | grep -v grep | awk '{print $1}') &
```

> The `sleep 5` gives Tomato time to finish its own init before the kill
> runs. The `&` backgrounds it so it doesn't block other init tasks.

---

### Verify after saving

From your Kali machine:

```bash
# Rescan — 22 and 23 should no longer appear
nmap -Pn -sT -sV -n <YOUR_PUBLIC_IP> -p 21,22,23,25,80,443 --open

# Attempt telnet — should time out
nc -v <YOUR_PUBLIC_IP> 23

# WireGuard UDP should still work (different protocol, not affected)
# (verify by connecting iPhone WireGuard tunnel)
```

---

### Confirm WireGuard forward survived

Tomato correctly placed the WireGuard forward in its own `wanin` chain
which persists across firewall rebuilds:

```bash
iptables -L wanin -n
# Should show:
# ACCEPT  udp  anywhere  smugglebus  udp dpt:51820
```

This rule was added by Tomato's port-forward GUI and is managed by
Tomato — do not manually delete or recreate it.

---

### Lesson learned — NAT hairpinning (testing from inside LAN)

**Symptom:** nmap scan of `<YOUR_PUBLIC_IP>` from a device on `smugglebus`
(10.0.0.x) showed SSH/telnet open even after DROP rules were confirmed in
place. Same scan from a mobile hotspot (truly external) showed ports closed.

**Root cause — NAT hairpinning (NAT loopback):**

When you scan your own public IP from inside your LAN, traffic takes this
path:

```
kali (10.0.0.x) → Pi wlan0 (<YOUR_PI_ROUTER_IP>) → router WAN (<YOUR_PUBLIC_IP>)
→ router recognises its own IP → loops traffic back internally via br0
→ arrives on br0 interface, NOT vlan2
→ your vlan2 DROP rules never fire → appears open
```

Versus a genuine external scan:
```
mobile hotspot → internet → <YOUR_PUBLIC_IP> → hits vlan2
→ DROP rules fire → port closed ✓
```

The traceroute from smugglebus confirmed this behaviour:
```
hop 1: 10.0.0.69     (Pi — smugglebus gateway)
hop 2: <YOUR_PUBLIC_IP> (router WAN — hairpin loop back)
```

**This is normal and intended router behaviour** — LAN devices can always
reach the router's own services internally regardless of WAN firewall rules.
It is NOT a security vulnerability.

**Correct way to test WAN firewall rules:**
```bash
# WRONG — scans from inside LAN, subject to NAT hairpin, not a real test
nmap -Pn -sT -n <YOUR_PUBLIC_IP> -p 22,23 --open

# CORRECT — disconnect from smugglebus, connect to mobile hotspot, then:
nmap -Pn -sT -n <YOUR_PUBLIC_IP> -p 22,23 --open
# or use an online port scanner like https://www.shodan.io or
# https://www.grc.com/x/ne.dll?bh0bkyd2
```

**Confirmed working** — scan from mobile hotspot showed ports 22 and 23
closed. WireGuard UDP 51820 remains open and functional as intended.

To scan your own public IP periodically from the Pi:

```bash
# Quick check of WAN-exposed ports
nmap -Pn -sT -n <YOUR_PUBLIC_IP> -p 21,22,23,25,80,443 --open
```

Save as a script for convenience:

```bash
nano ~/check-wan-ports.sh
```

```bash
#!/bin/bash
echo "=== WAN port scan $(date) ==="
nmap -Pn -sT -n <YOUR_PUBLIC_IP> -p 21,22,23,25,80,443,51820 --open
```

```bash
chmod +x ~/check-wan-ports.sh
bash ~/check-wan-ports.sh
```
