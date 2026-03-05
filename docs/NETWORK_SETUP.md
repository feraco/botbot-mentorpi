# Network Setup Guide

This document covers the network configuration required for BotBrain to work correctly over WiFi.

---

## 1. CycloneDDS Interface Priority

### Why It Matters

CycloneDDS is the DDS middleware used by ROS2. It uses multicast to discover and communicate between ROS nodes. When multiple network interfaces exist (e.g. `wlan0` and `eth0`), CycloneDDS picks the highest-priority interface for multicast traffic.

**The Problem:** If `eth0` has higher priority than `wlan0`, plugging in an Ethernet cable causes all ROS2 traffic (LiDAR scans, odometry, map data) to flow over `eth0`. When the browser connects over WiFi, the web UI cannot receive this data — the map never updates and ICP odometry shows `ratio=0.000000`.

**The Fix:** Set `wlan0` priority higher than `eth0` in `botbrain_ws/cyclonedds_config.xml`:

```xml
<NetworkInterface name="lo"    priority="100" multicast="true" />
<NetworkInterface name="wlan0" priority="50"  multicast="true" presence_required="false" />
<NetworkInterface name="eth0"  priority="10"  multicast="true" presence_required="false" />
```

`presence_required="false"` means CycloneDDS won't fail to start if the interface isn't present (e.g. no cable for eth0).

### Verifying the Fix

After restarting the ROS containers:

```bash
docker logs localization --tail 20
```

Healthy output looks like:
```
[icp_odometry-6]: Odom: ratio=0.804469, std dev=0.009168m|0.002899rad
[icp_odometry-6]: Odom: ratio=0.817680, std dev=0.009309m|0.002944rad
```

`ratio` should be > 0.5. If it shows `0.000000`, DDS is not routing traffic correctly.

---

## 2. WiFi Auto-Connect on Boot (Raspberry Pi / HiWonder boards)

### Background

HiWonder robotics boards (e.g. "ArmPi" series) ship with a custom `wifi.service` (`/home/pi/hiwonder-toolbox/wifi.py`) that creates a WiFi **hotspot** (`192.168.149.1`) on every boot. This conflicts with connecting to an existing WiFi network.

### Disabling the HiWonder Hotspot

```bash
# SSH into the Pi (use Ethernet or the hotspot IP 192.168.149.1)
ssh pi@192.168.149.1

# Disable the HiWonder wifi service permanently
sudo systemctl disable wifi.service
sudo systemctl stop wifi.service

# Remove the hotspot connection profile
sudo rm -f /etc/NetworkManager/system-connections/HW-*.nmconnection
sudo nmcli connection reload
```

### Creating a Persistent WiFi Client Profile

Write a NetworkManager connection file directly (replace `YourSSID` and `YourPassword`):

```bash
sudo tee /etc/NetworkManager/system-connections/wifi-client.nmconnection << 'EOF'
[connection]
id=wifi-client
uuid=$(uuidgen)
type=wifi
autoconnect=true
autoconnect-priority=100

[wifi]
mode=infrastructure
ssid=YourSSID

[wifi-security]
auth-alg=open
key-mgmt=wpa-psk
psk=YourPassword
psk-flags=0

[ipv4]
method=auto

[ipv6]
addr-gen-mode=default
method=auto
EOF

sudo chmod 600 /etc/NetworkManager/system-connections/wifi-client.nmconnection
sudo nmcli connection reload
sudo nmcli connection up wifi-client
```

### Verifying WiFi on Boot

```bash
# After reboot, check which interface is connected
ip addr show wlan0
nmcli connection show --active
```

The Pi should connect to your WiFi network automatically. The IP is assigned by DHCP — check your router's DHCP leases or use:

```bash
# From another machine on the same network
nmap -sn 192.168.1.0/24 | grep -A1 Raspberry
```

---

## 3. Ethernet Recovery Access

If WiFi is not working, you can still access the Pi via Ethernet by connecting directly to the robot and adding a static IP on the same subnet used by the Pi's Ethernet interface (typically `192.168.123.x` on Go2-based setups or `192.168.149.x` on HiWonder boards).

```bash
# On your computer (Linux), add a static IP on the Ethernet interface
sudo ip addr add 192.168.123.99/24 dev <your-eth-interface>

# Then SSH to the Pi
ssh pi@192.168.123.170
```

The Pi's Ethernet IP may change on DHCP networks — check via `arp -n` or `nmap` if needed.
