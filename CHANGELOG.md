# Changelog

All notable changes to BotBrain are documented here.

---

## [Unreleased]

### Fixed

#### Cockpit Map Not Displaying (`frontend/src/components/map-view-nav2.tsx`)
- **Problem**: The cockpit map was blank because `MapViewNav2` subscribed to the hardcoded topic `/map` instead of the robot-profile-aware topic (e.g. `/robotdog/map`).
- **Fix**: Replaced the hardcoded topic string with `getRosTopic('map', currentProfile)` so the topic is resolved dynamically from the active robot profile. Added `enabled: !!currentProfile` guard to prevent subscribing before the profile is loaded.
- **Files changed**: `frontend/src/components/map-view-nav2.tsx`

  ```diff
  + import { useRobotProfile } from '@/contexts/RobotProfileContext';
  + import { getRosTopic } from '@/utils/ros/topics-and-services-v2';
  
    export default function MapViewNav2({ ... }) {
  +   const { currentProfile } = useRobotProfile();
  -   const mapTopic = '/map';
  -   const { occupancyGrid } = useOccupancyGrid({ topicName: mapTopic });
  +   const mapTopic = getRosTopic('map', currentProfile);
  +   const { occupancyGrid } = useOccupancyGrid({ topicName: mapTopic, enabled: !!currentProfile });
  ```

#### CycloneDDS Interface Priority — Map Only Updated on Ethernet (`botbrain_ws/cyclonedds_config.xml`)
- **Problem**: When an Ethernet cable was connected, CycloneDDS (the ROS2 DDS middleware) preferred `eth0` (priority 20) over `wlan0` (priority 10). All ROS2 traffic — including LiDAR scans and odometry — flowed over Ethernet. When the browser connected over WiFi, ICP odometry showed `ratio=0.000000` (scan matching failed) because data never arrived at the localization container over the correct interface. The map never updated.
- **Fix**: Raised `wlan0` priority to `50` and lowered `eth0` to `10` so WiFi is always the primary DDS interface. Ethernet becomes optional/fallback.
- **Files changed**: `botbrain_ws/cyclonedds_config.xml`

  ```diff
  - <NetworkInterface name="eth0" priority="20" multicast="true" />
  - <NetworkInterface name="wlan0" priority="10" multicast="true" />
  + <NetworkInterface name="wlan0" priority="50" multicast="true" presence_required="false" />
  + <NetworkInterface name="eth0" priority="10" multicast="true" presence_required="false" />
  ```
- **Verification**: After fix, `docker logs localization` shows `ratio=0.78–0.83` (healthy ICP scan matching on WiFi).

### Added

#### Network Setup Documentation (`docs/NETWORK_SETUP.md`)
- Documents the CycloneDDS interface priority fix.
- Documents the WiFi auto-connect setup (disabling HiWonder `wifi.service` hotspot, writing a persistent NetworkManager connection profile).
- Explains the `192.168.149.x` fallback Ethernet subnet for recovery access.

#### Auto-Boot Documentation (`docs/BOOT_AUTOSTART.md`)
- Documents how `botbrain.service` and `web_server.service` are installed and enabled via `install.sh`.
- Explains the network-wait logic that prevents containers from starting before a default route is available.
- Covers troubleshooting steps for when services fail on boot.

---

## Notes on Deploying Frontend Builds

The Pi (Raspberry Pi / Jetson) may not have internet access required for Next.js builds (Google Fonts CDN, npm registry). Build the frontend **locally** and rsync the output:

```bash
# 1. Build locally (substitute your Supabase values)
sudo docker run --rm \
  -v $(pwd)/frontend:/app \
  -w /app \
  -e NEXT_PUBLIC_SUPABASE_URL=<your-url> \
  -e NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-key> \
  node:22-bullseye bash -c "npm ci && npm run build"

# 2. Fix ownership (docker builds as root)
sudo chown -R $USER:$USER frontend/.next

# 3. Rsync to Pi (replace IP as needed)
rsync -az --delete --exclude='cache/' frontend/.next/ pi@<PI_IP>:/home/pi/BotBrain-main/frontend/.next/

# 4. Restart web server on Pi
ssh pi@<PI_IP> 'cd /home/pi/BotBrain-main && docker compose restart web_server_prod'
```
