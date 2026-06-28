#!/usr/bin/env python3
"""
smugglebus-monitor.py
Live terminal dashboard for the smugglebus Pi router.
Zero dependencies — pure Python stdlib only.

Usage:
    PYTHONIOENCODING=utf-8 ./python3.9/bin/python3 smugglebus-monitor.py
    PYTHONIOENCODING=utf-8 ./python3.9/bin/python3 smugglebus-monitor.py --interval 5
    Ctrl-C to quit
"""

import time
import argparse
import subprocess
import re
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

LEASES_FILE    = "/var/lib/misc/dnsmasq.leases"
MAC_CACHE_FILE = Path("/tmp/smugglebus_mac_cache.json")
MAX_DNS        = 40
MAX_DOMAINS    = 8
MAX_CONNS      = 20
PI_OUI         = "b8:27:eb"
PI_IPS         = {"10.0.0.69", "192.168.1.33"}

ACTIVE_MIN = 5
RECENT_MIN = 30

# ── ANSI ──────────────────────────────────────────────────────────────────────
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"
BLUE="\033[34m"; MGNT="\033[35m"; CYAN="\033[36m"; WHITE="\033[37m"

def c(text, *codes): return "".join(codes) + str(text) + R
def visible_len(s): return len(re.sub(r'\033\[[0-9;]*m', '', s))
def pad(s, width, align="left"):
    diff = width - visible_len(s)
    if diff <= 0: return s
    return (" "*diff + s) if align == "right" else (s + " "*diff)
def hr(width, col=DIM): return c("─"*width, col)
def term_width():
    try: return min(os.get_terminal_size().columns, 140)
    except: return 120
def clear(): sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()

IFACE_COLOR = {"eth0": CYAN, "wlan1": YELLOW, "wlan0": GREEN, "br0": BLUE}
def iface_col(i): return IFACE_COLOR.get(i.rstrip("~*"), WHITE)
def qtype_col(q): return {"A": GREEN,"AAAA": BLUE,"PTR": YELLOW,
                           "MX": MGNT,"CNAME": CYAN}.get(q, WHITE)
def activity_col(mins):
    if mins is None:        return DIM,    "idle"
    if mins < ACTIVE_MIN:   return GREEN,  "active"
    if mins < RECENT_MIN:   return YELLOW, "recent"
    return DIM, "idle"
def dot(mins):
    col, _ = activity_col(mins)
    return c("●", col)

# ── persistent MAC cache ──────────────────────────────────────────────────────
def load_mac_cache():
    try:    return json.loads(MAC_CACHE_FILE.read_text())
    except: return {}
def save_mac_cache(cache):
    try:    MAC_CACHE_FILE.write_text(json.dumps(cache))
    except: pass

# ── bridge FDB ────────────────────────────────────────────────────────────────
def read_bridge_fdb():
    port_to_iface = {}
    mac_to_iface  = {}
    try:
        brif_path = Path("/sys/class/net/br0/brif")
        if brif_path.exists():
            for d in sorted(brif_path.iterdir()):
                pf = d / "port_no"
                if pf.exists():
                    port_to_iface[int(pf.read_text().strip(), 16)] = d.name
        r = subprocess.run(["brctl", "showmacs", "br0"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        for line in r.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
            parts = line.split()
            if len(parts) < 3: continue
            try:
                port = int(parts[0]); mac = parts[1].lower()
                if parts[2] == "yes": continue
                mac_to_iface[mac] = port_to_iface.get(port, "port"+str(port))
            except: continue
    except: pass
    return mac_to_iface

def read_arp_cache():
    cache = {}
    try:
        for line in Path("/proc/net/arp").read_text().splitlines()[1:]:
            p = line.split()
            if len(p) >= 6: cache[p[3].lower()] = p[5]
    except: pass
    return cache

def resolve_iface(mac, fdb, arp, mac_cache):
    m = mac.lower()
    if m in fdb:        return fdb[m], "live"
    if m in arp:        return arp[m],  "arp"
    if m in mac_cache:  return mac_cache[m], "cached"
    return "?", "unknown"

# ── leases ────────────────────────────────────────────────────────────────────
def read_leases():
    clients = []
    try: text = Path(LEASES_FILE).read_text()
    except FileNotFoundError: return clients
    for line in text.strip().splitlines():
        p = line.split()
        if len(p) < 4: continue
        expiry, mac, ip, hostname = p[0], p[1], p[2], p[3]
        if mac.lower().startswith(PI_OUI): continue
        try:    exp = datetime.fromtimestamp(int(expiry)).strftime("%H:%M:%S")
        except: exp = expiry
        clients.append({"mac": mac, "ip": ip,
                         "hostname": hostname if hostname != "*" else "(unknown)",
                         "expires": exp})
    return clients

# ── DNS log ───────────────────────────────────────────────────────────────────
def fetch_dns(n=MAX_DNS*8):
    queries = []
    try:
        r = subprocess.run(
            ["journalctl", "-u", "dnsmasq", "-n", str(n),
             "--no-pager", "--output=short"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        for line in r.stdout.decode("utf-8", errors="replace").splitlines():
            m = re.search(
                r'(\d{2}:\d{2}:\d{2}).*query\[(\w+)\]\s+(\S+)\s+from\s+([\d.]+)', line)
            if m:
                queries.append({"time": m.group(1), "qtype": m.group(2),
                                 "query": m.group(3), "client": m.group(4)})
    except: pass
    return queries

# ── conntrack ─────────────────────────────────────────────────────────────────
def is_lan(ip):
    return ip.startswith("10.0.0.") or ip.startswith("192.168.")

def fetch_conntrack(lan_ips):
    """
    Parse /proc/net/nf_conntrack.
    Format on this kernel:
      ipv4  2  tcp  6  TTL  [STATE]  src=x dst=y sport=a dport=b  src=y dst=x ...
      ipv4  2  udp  17 TTL          src=x dst=y sport=a dport=b  src=y dst=x ...

    Column 3 = protocol name (tcp/udp/unknown)
    First src/dst pair = originating direction
    Second src/dst pair = reply direction (reply dst is Pi's wlan0 IP due to NAT)

    Note: bridged LAN-to-LAN traffic (PS4↔iPhone) does NOT appear in conntrack
    unless br_netfilter is loaded. Only routed traffic (LAN→WAN) shows up.
    """
    lan_conns = []
    wan_conns = []
    seen      = set()
    try:
        lines = Path("/proc/net/nf_conntrack").read_text().splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) < 4: continue
            # col index 2 = protocol string
            proto = parts[2].upper()
            if proto == "UNKNOWN": continue

            # first src/dst/sport/dport in the line = originating direction
            m = re.search(
                r'src=([\d.]+)\s+dst=([\d.]+)\s+sport=(\d+)\s+dport=(\d+)',
                line)
            if not m: continue
            src   = m.group(1)
            dst   = m.group(2)
            sport = m.group(3)
            dport = m.group(4)

            # skip Pi itself, DNS, multicast, broadcast, unroutable
            if src in PI_IPS or dst in PI_IPS:           continue
            if dport in ("53","67","68") or sport in ("53","67","68"): continue
            if dst.startswith("224.") or dst.startswith("255."): continue
            if src == "0.0.0.0" or dst == "0.0.0.0":    continue

            key = (src, dst, dport)
            if key in seen: continue
            seen.add(key)

            state = ""
            if "ESTABLISHED" in line: state = "ESTABLISHED"
            elif "ASSURED"   in line: state = "ASSURED"

            if is_lan(src) and is_lan(dst):
                # true LAN-to-LAN (only visible if br_netfilter loaded)
                lan_conns.append({
                    "src": src, "dst": dst,
                    "src_h": lan_ips.get(src, src),
                    "dst_h": lan_ips.get(dst, dst),
                    "proto": proto, "dport": dport, "state": state,
                })
            elif is_lan(src):
                # LAN → WAN (NAT masqueraded)
                wan_conns.append({
                    "src": src, "dst": dst,
                    "src_h": lan_ips.get(src, src),
                    "proto": proto, "dport": dport, "state": state,
                })
    except: pass
    return lan_conns, wan_conns

# ── last seen ─────────────────────────────────────────────────────────────────
def last_seen_map(dns_all):
    now  = datetime.now()
    last = {}
    for e in dns_all:
        if e["client"] not in last:
            last[e["client"]] = e["time"]
    result = {}
    for ip, t in last.items():
        try:
            hh, mm, ss = map(int, t.split(":"))
            then = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
            result[ip] = max(0, (now - then).total_seconds() / 60)
        except: result[ip] = None
    return result

def ip_map(clients):
    return {cl["ip"]: cl["hostname"] for cl in clients}

# ── render ────────────────────────────────────────────────────────────────────
def render(clients, fdb, arp_cache, mac_cache, dns_all):
    W         = term_width()
    now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip2host   = ip_map(clients)
    q_count   = Counter(e["client"] for e in dns_all)
    last_seen = last_seen_map(dns_all)
    lan_ips   = {**ip2host}
    lan_conns, wan_conns = fetch_conntrack(lan_ips)
    lines     = []

    # header
    title = " smugglebus monitor "
    pl = (W - len(title)) // 2
    pr = W - pl - len(title)
    lines.append(c("─"*pl, DIM, GREEN) + c(title, BOLD, GREEN) + c("─"*pr, DIM, GREEN))
    lines.append(c("  " + now +
        "    Ctrl-C to quit    " +
        c("●", GREEN) + c("<5m  ", DIM) +
        c("●", YELLOW) + c("<30m  ", DIM) +
        c("●", DIM) + c(" idle", DIM), DIM))
    lines.append(hr(W))

    # ── section 1: DHCP clients ───────────────────────────────────────────────
    lines.append(c("  DHCP CLIENTS", BOLD, MGNT))
    lines.append(hr(W))
    lines.append("  " +
        pad("", 3) +
        pad(c("HOSTNAME",  BOLD, WHITE), 22) + "  " +
        pad(c("IP",        BOLD, WHITE), 15) + "  " +
        pad(c("MAC",       BOLD, WHITE), 19) + "  " +
        pad(c("IFACE",     BOLD, WHITE), 10) + "  " +
        pad(c("LAST SEEN", BOLD, WHITE), 12) + "  " +
        pad(c("QUERIES",   BOLD, WHITE), 8)  + "  " +
        c("LEASE EXP", BOLD, WHITE))
    lines.append(hr(W))

    if not clients:
        lines.append(c("  (no leases yet)", DIM))
    else:
        for cl in sorted(clients,
                         key=lambda x: last_seen.get(x["ip"]) if last_seen.get(x["ip"]) is not None else 9999):
            mac             = cl["mac"].lower()
            iface, src      = resolve_iface(mac, fdb, arp_cache, mac_cache)
            mins            = last_seen.get(cl["ip"])
            col, _          = activity_col(mins)
            ic              = iface_col(iface)
            qc              = str(q_count.get(cl["ip"], 0))
            if src == "arp":     iface_disp = c(iface, ic, BOLD) + c("~", DIM)
            elif src == "cached":iface_disp = c(iface, ic, BOLD) + c("*", DIM)
            elif src == "unknown":iface_disp= c("?", DIM)
            else:                iface_disp = c(iface, ic, BOLD)
            if mins is None:     ls = c("idle", DIM)
            elif mins < 1:       ls = c("just now", GREEN)
            elif mins < 60:      ls = c(str(int(mins)) + "m ago", col)
            else:                ls = c(str(int(mins//60)) + "h ago", DIM)
            lines.append("  " + dot(mins) + " " +
                pad(c(cl["hostname"], col, BOLD), 22) + "  " +
                pad(c(cl["ip"], GREEN), 15) + "  " +
                pad(c(cl["mac"], DIM), 19) + "  " +
                pad(iface_disp, 10) + "  " +
                pad(ls, 12) + "  " +
                pad(c(qc, CYAN), 8) + "  " +
                c(cl["expires"], DIM))

    lines.append(c("  ~ ARP fallback  * remembered (sleeping)", DIM))
    lines.append(hr(W))

    # ── section 2: LAN connections ────────────────────────────────────────────
    lines.append(c("  LAN CONNECTIONS  (device ↔ device)", BOLD, MGNT))
    lines.append(c("  note: bridged traffic only visible if br_netfilter is loaded", DIM))
    lines.append(hr(W))
    if not lan_conns:
        lines.append(c("  (no direct LAN connections active)", DIM))
    else:
        lines.append("  " +
            pad(c("FROM", BOLD, WHITE), 24) + "  " +
            pad(c("TO", BOLD, WHITE), 24) + "  " +
            pad(c("PROTO", BOLD, WHITE), 7) + "  " +
            c("PORT", BOLD, WHITE))
        lines.append(hr(W))
        for conn in lan_conns[:10]:
            # highlight known service ports
            port_name = {
                "9295": "PS Remote Play",
                "9296": "PS Remote Play",
                "9297": "PS Remote Play",
                "1900": "SSDP/UPnP",
                "5353": "mDNS",
                "137":  "NetBIOS",
                "445":  "SMB",
                "80":   "HTTP",
                "443":  "HTTPS",
            }.get(conn["dport"], "port " + conn["dport"])
            highlight = GREEN if "Remote Play" in port_name else WHITE
            lines.append("  " +
                pad(c(conn["src_h"], CYAN, BOLD) + c(" ("+conn["src"]+")", DIM), 32) + "  " +
                pad(c(conn["dst_h"], YELLOW, BOLD) + c(" ("+conn["dst"]+")", DIM), 32) + "  " +
                pad(c(conn["proto"], DIM), 7) + "  " +
                c(port_name, highlight, BOLD))
    lines.append(hr(W))

    # ── section 3: internet connections ───────────────────────────────────────
    lines.append(c("  INTERNET CONNECTIONS  (LAN → WAN)", BOLD, MGNT))
    lines.append(hr(W))
    if not wan_conns:
        lines.append(c("  (no active internet connections)", DIM))
    else:
        lines.append("  " +
            pad(c("CLIENT",  BOLD, WHITE), 22) + "  " +
            pad(c("DEST IP", BOLD, WHITE), 18) + "  " +
            pad(c("PROTO",   BOLD, WHITE), 7)  + "  " +
            pad(c("PORT",    BOLD, WHITE), 7)  + "  " +
            c("STATUS", BOLD, WHITE))
        lines.append(hr(W))
        # deduplicate by client+dest showing most recent
        seen = {}
        for conn in wan_conns:
            key = (conn["src"], conn["dst"])
            if key not in seen:
                seen[key] = conn
        for conn in list(seen.values())[:MAX_CONNS]:
            status = c("assured", GREEN) if conn["state"] == "ASSURED" else c("new", YELLOW)
            lines.append("  " +
                pad(c(conn["src_h"], CYAN, BOLD), 22) + "  " +
                pad(c(conn["dst"], WHITE), 18) + "  " +
                pad(c(conn["proto"], DIM), 7)  + "  " +
                pad(c(conn["dport"], DIM), 7)  + "  " +
                status)
    lines.append(hr(W))

    # ── section 4: top domains ────────────────────────────────────────────────
    lines.append(c("  TOP QUERIED DOMAINS", BOLD, MGNT))
    lines.append(hr(W))
    domain_counts = Counter(e["query"] for e in dns_all
                            if e["qtype"] in ("A", "AAAA", "CNAME"))
    top = domain_counts.most_common(MAX_DOMAINS)
    if not top:
        lines.append(c("  (no data yet)", DIM))
    else:
        mx = top[0][1]; bw = 25
        for domain, count in top:
            filled = int(bw * count / mx)
            bar = c("█"*filled, CYAN) + c("░"*(bw-filled), DIM)
            lines.append("  " + pad(domain, 48) + "  " + bar +
                         "  " + c(str(count), BOLD, CYAN))
    lines.append(hr(W))

    # ── section 5: live DNS feed grouped by client ───────────────────────────
    lines.append(c("  LIVE DNS QUERIES  (newest first, grouped by client)", BOLD, MGNT))
    lines.append(hr(W))

    recent = [e for e in dns_all if e["qtype"] in ("A","AAAA","PTR","MX","CNAME")]

    if not recent:
        lines.append(c("  (no queries yet)", DIM))
    else:
        # build per-client ordered list preserving newest-first within each client
        # order clients by their most recent query (newest client first)
        client_order = []
        seen_clients = set()
        for e in reversed(recent):
            if e["client"] not in seen_clients:
                client_order.append(e["client"])
                seen_clients.add(e["client"])

        per_client = defaultdict(list)
        for e in reversed(recent):
            per_client[e["client"]].append(e)

        PER_CLIENT_ROWS = max(4, MAX_DNS // max(len(client_order), 1))

        for idx, client_ip in enumerate(client_order):
            hostname  = ip2host.get(client_ip, client_ip)
            mins      = last_seen.get(client_ip)
            col, _    = activity_col(mins)
            entries   = per_client[client_ip][:PER_CLIENT_ROWS]

            # client header row
            if idx > 0:
                lines.append("")
            lines.append("  " + dot(mins) + " " +
                c(hostname, col, BOLD) +
                c("  " + client_ip, DIM) +
                c("  (" + str(len(per_client[client_ip])) + " queries)", DIM))
            lines.append("  " + c("  " + "─"*(W-4), DIM))

            for e in entries:
                lines.append("    " +
                    pad(c(e["time"], DIM), 10) + "  " +
                    pad(c(e["qtype"], qtype_col(e["qtype"])), 7) + "  " +
                    c(e["query"], WHITE))

            remaining = len(per_client[client_ip]) - PER_CLIENT_ROWS
            if remaining > 0:
                lines.append(c("    ... and " + str(remaining) + " more", DIM))

    lines.append(hr(W))
    return "\n".join(lines)

# ── main ──────────────────────────────────────────────────────────────────────
INTERVAL = 2.0

def main():
    global INTERVAL
    parser = argparse.ArgumentParser(description="smugglebus monitor")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    INTERVAL = args.interval
    mac_cache = load_mac_cache()

    try:
        while True:
            clients   = read_leases()
            fdb       = read_bridge_fdb()
            arp_cache = read_arp_cache()
            dns_all   = fetch_dns()

            updated = False
            for mac, iface in fdb.items():
                if mac_cache.get(mac) != iface:
                    mac_cache[mac] = iface
                    updated = True
            if updated:
                save_mac_cache(mac_cache)

            clear()
            print(render(clients, fdb, arp_cache, mac_cache, dns_all))
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        clear()
        print(c("\nmonitor stopped.\n", DIM))

if __name__ == "__main__":
    main()
