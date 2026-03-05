# Auto-Boot & Autostart Guide

BotBrain uses two systemd services to automatically start all components on boot:

| Service | Description |
|---------|-------------|
| `botbrain.service` | Starts all ROS2 Docker containers (bringup, localization, navigation, etc.) |
| `web_server.service` | Starts the Next.js web UI container (`web_server_prod`) |

---

## How It Works

Both services are installed and enabled by `install.sh`. They use `After=network-online.target` and an `ExecStartPre` wait loop to ensure a default network route exists before starting Docker containers. This prevents ROS2 nodes from initializing without network connectivity (which would cause DDS discovery to fail).

```
Boot → systemd → network-online.target → botbrain.service → docker compose up ...
                                        → web_server.service → docker compose up web_server_prod
```

### Service File Template

The `.service` files in the repo use the placeholder `BOTBRAIN_WORKSPACE_PATH`. `install.sh` replaces this with the actual installation directory using `sed` before copying to `/etc/systemd/system/`.

---

## Installation

Run the installer as root from the BotBrain directory:

```bash
cd /home/pi/BotBrain-main
sudo bash install.sh
```

The installer will:
1. Pull all required Docker images
2. Install and enable `botbrain.service`
3. Install and enable `web_server.service`
4. Run the builder containers to compile ROS2 packages and build the Next.js frontend

---

## Manual Service Management

```bash
# Check status
sudo systemctl status botbrain.service
sudo systemctl status web_server.service

# Start / Stop / Restart
sudo systemctl start botbrain.service
sudo systemctl stop botbrain.service
sudo systemctl restart web_server.service

# View logs
journalctl -u botbrain.service -f
journalctl -u web_server.service -f

# Disable auto-start (troubleshooting)
sudo systemctl disable botbrain.service
sudo systemctl disable web_server.service
```

---

## Docker Container Management

All ROS2 containers are started by `botbrain.service` via `docker compose up`. You can manage them directly:

```bash
cd /home/pi/BotBrain-main

# See all container statuses
docker compose ps

# Restart a specific container
docker compose restart localization

# View container logs
docker logs localization --tail 50 -f
docker logs web_server_prod --tail 20

# Stop everything
docker compose stop

# Start everything (excluding builder/dev containers)
source botbrain_ws/robot_select.sh
docker compose up dev bringup localization navigation rosa yolo jetson_stats state_machine -d
docker compose up web_server_prod -d
```

---

## Troubleshooting Boot Issues

### Containers not starting

```bash
journalctl -u botbrain.service --no-pager | tail -30
```

Common causes:
- No default network route at boot (increases wait time)
- `docker.service` not running: `sudo systemctl start docker`
- Wrong workspace path: check `WorkingDirectory=` in `/etc/systemd/system/botbrain.service`

### Web UI not accessible after boot

```bash
docker logs web_server_prod --tail 20
sudo systemctl status web_server.service
```

If the `.next/` build directory is missing or empty, you need to rebuild the frontend. See `CHANGELOG.md` for the local build + rsync procedure.

### Map not updating on WiFi

See [docs/NETWORK_SETUP.md](NETWORK_SETUP.md) — the most common cause is CycloneDDS using eth0 over wlan0.

---

## Verifying Everything is Running

```bash
# Check all containers
docker compose ps

# Check ICP odometry health (should show ratio > 0.5)
docker logs localization --tail 10

# Check web server
docker logs web_server_prod --tail 5
# Expected: ✓ Ready in XXXms
```
