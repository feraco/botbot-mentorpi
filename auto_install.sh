#!/bin/bash
# Non-interactive BotBrain installer with pre-configured values
set -e

cd ~/BotBrain-main

# Configuration values
ROBOT_MODEL="go2"
DESCRIPTION_TYPE="xacro"
ROBOT_NAME="robotdog"
NETWORK_INTERFACE="eth0"
WIFI_INTERFACE="wlan0"
WIFI_SSID="WW 414"
WIFI_PASSWORD='~^410turR!NG^~'
OPENAI_API_KEY=""
SUPABASE_URL="https://placeholder.supabase.co"
SUPABASE_ANON_KEY="placeholder-anon-key-replace-with-real-credentials"
FRONT_CAMERA="d435i"
REAR_CAMERA="d435i"
FRONT_SERIAL=""
REAR_SERIAL=""

echo "=========================================="
echo "BotBrain Non-Interactive Installer"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Robot Model: $ROBOT_MODEL"
echo "  Description: $DESCRIPTION_TYPE"
echo "  Robot Name:  $ROBOT_NAME"
echo "  Network IF:  $NETWORK_INTERFACE"
echo "  WiFi IF:     $WIFI_INTERFACE"
echo "  WiFi SSID:   $WIFI_SSID"
echo "  Front Cam:   $FRONT_CAMERA"
echo "  Rear Cam:    $REAR_CAMERA"
echo ""

# Step 0: Install prerequisites
echo "=========================================="
echo "Step 0: Installing prerequisites..."
echo "=========================================="

if ! command -v pip3 &> /dev/null; then
    echo "Installing pip3..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
fi
echo "✓ pip3 OK"

if ! command -v dialog &> /dev/null; then
    echo "Installing dialog..."
    sudo apt-get update
    sudo apt-get install -y dialog
fi
echo "✓ dialog OK"

# Step 1: Update camera_config.yaml
echo "=========================================="
echo "Step 1: Updating camera configuration..."
echo "=========================================="

CAMERA_CONFIG_FILE="botbrain_ws/src/${ROBOT_MODEL}_pkg/config/camera_config.yaml"
if [ -f "$CAMERA_CONFIG_FILE" ]; then
    if [ "$FRONT_CAMERA" != "none" ]; then
        sed -i "/front:/,/type:/ s/type: \".*\"/type: \"$FRONT_CAMERA\"/" "$CAMERA_CONFIG_FILE"
        sed -i "/front:/,/serial_number:/ s/serial_number: \".*\"/serial_number: \"$FRONT_SERIAL\"/" "$CAMERA_CONFIG_FILE"
        echo "✓ Front camera: $FRONT_CAMERA"
    fi
    if [ "$REAR_CAMERA" != "none" ]; then
        sed -i "/back:/,/type:/ s/type: \".*\"/type: \"$REAR_CAMERA\"/" "$CAMERA_CONFIG_FILE"
        sed -i "/back:/,/serial_number:/ s/serial_number: \".*\"/serial_number: \"$REAR_SERIAL\"/" "$CAMERA_CONFIG_FILE"
        echo "✓ Rear camera: $REAR_CAMERA"
    fi
else
    echo "⚠ $CAMERA_CONFIG_FILE not found, skipping"
fi

# Step 2: Update cyclonedds_config.xml
echo "=========================================="
echo "Step 2: Updating CycloneDDS config..."
echo "=========================================="

CYCLONEDDS_CONFIG="botbrain_ws/cyclonedds_config.xml"
if [ -f "$CYCLONEDDS_CONFIG" ]; then
    sed -i "/<NetworkInterface name=\"lo\"/! s/<NetworkInterface name=\"[^\"]*\" priority=\"10\"/<NetworkInterface name=\"$NETWORK_INTERFACE\" priority=\"10\"/" "$CYCLONEDDS_CONFIG"
    echo "✓ CycloneDDS network interface: $NETWORK_INTERFACE"
else
    echo "⚠ $CYCLONEDDS_CONFIG not found, skipping"
fi

# Step 3: Update robot_config.yaml
echo "=========================================="
echo "Step 3: Updating robot configuration..."
echo "=========================================="

CONFIG_FILE="botbrain_ws/robot_config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    sed -i "s/robot_model: \".*\"/robot_model: \"$ROBOT_MODEL\"/" "$CONFIG_FILE"
    sed -i "s/description_file_type: \".*\"/description_file_type: \"$DESCRIPTION_TYPE\"/" "$CONFIG_FILE"
    sed -i "s/robot_name: \".*\"/robot_name: \"$ROBOT_NAME\"/" "$CONFIG_FILE"
    sed -i "s/network_interface: \".*\"/network_interface: \"$NETWORK_INTERFACE\"/" "$CONFIG_FILE"
    sed -i "s/wifi_interface: \".*\"/wifi_interface: \"$WIFI_INTERFACE\"/" "$CONFIG_FILE"
    sed -i "s/wifi_ssid: \".*\"/wifi_ssid: \"$WIFI_SSID\"/" "$CONFIG_FILE"
    sed -i "s/wifi_password: \".*\"/wifi_password: \"$WIFI_PASSWORD\"/" "$CONFIG_FILE"
    sed -i "s|openai_api_key: \".*\"|openai_api_key: \"$OPENAI_API_KEY\"|" "$CONFIG_FILE"
    echo "✓ robot_config.yaml updated"
    echo "  Contents:"
    cat "$CONFIG_FILE"
else
    echo "✗ $CONFIG_FILE not found!"
    exit 1
fi

# Step 4: Create .env file for Supabase
echo "=========================================="
echo "Step 4: Creating .env file..."
echo "=========================================="

cat > .env << EOF
NEXT_PUBLIC_SUPABASE_URL=$SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
EOF
echo "✓ .env file created"

# Step 5: Pull Docker images
echo "=========================================="
echo "Step 5: Pulling Docker images..."
echo "=========================================="

docker compose pull 2>&1
PULL_RESULT=$?
if [ $PULL_RESULT -ne 0 ]; then
    echo "✗ Failed to pull Docker images (exit code: $PULL_RESULT)"
    exit 1
fi
echo "✓ Docker images pulled"

# Step 6: Setup botbrain.service
echo "=========================================="
echo "Step 6: Setting up botbrain.service..."
echo "=========================================="

WORKSPACE_PATH="$(pwd)"
if [ -f "botbrain.service" ]; then
    sed "s|BOTBRAIN_WORKSPACE_PATH|$WORKSPACE_PATH|g" botbrain.service > /tmp/botbrain.service.tmp
    sudo cp /tmp/botbrain.service.tmp /etc/systemd/system/botbrain.service
    sudo systemctl daemon-reload
    sudo systemctl enable botbrain.service
    rm -f /tmp/botbrain.service.tmp
    echo "✓ botbrain.service enabled"
else
    echo "✗ botbrain.service not found!"
    exit 1
fi

# Step 7: Setup web_server.service
echo "=========================================="
echo "Step 7: Setting up web_server.service..."
echo "=========================================="

if [ -f "web_server.service" ]; then
    sed "s|BOTBRAIN_WORKSPACE_PATH|$WORKSPACE_PATH|g" web_server.service > /tmp/web_server.service.tmp
    sudo cp /tmp/web_server.service.tmp /etc/systemd/system/web_server.service
    sudo systemctl daemon-reload
    sudo systemctl enable web_server.service
    rm -f /tmp/web_server.service.tmp
    echo "✓ web_server.service enabled"
else
    echo "✗ web_server.service not found!"
    exit 1
fi

# Step 8: Run builder services
echo "=========================================="
echo "Step 8: Starting builder services..."
echo "=========================================="

docker compose up -d builder_base builder_yolo web_server_builder 2>&1
BUILD_RESULT=$?
if [ $BUILD_RESULT -ne 0 ]; then
    echo "✗ Failed to start builder services (exit code: $BUILD_RESULT)"
    exit 1
fi

# Wait for builder services to complete
echo "Waiting for builder services to complete..."
BUILDER_BASE_ID=$(docker compose ps -q builder_base 2>/dev/null)
BUILDER_YOLO_ID=$(docker compose ps -q builder_yolo 2>/dev/null)
WEB_SERVER_BUILDER_ID=$(docker compose ps -q web_server_builder 2>/dev/null)

if [ -n "$BUILDER_BASE_ID" ]; then
    echo "  Waiting for builder_base..."
    docker wait "$BUILDER_BASE_ID" 2>/dev/null || true
fi
if [ -n "$BUILDER_YOLO_ID" ]; then
    echo "  Waiting for builder_yolo..."
    docker wait "$BUILDER_YOLO_ID" 2>/dev/null || true
fi
if [ -n "$WEB_SERVER_BUILDER_ID" ]; then
    echo "  Waiting for web_server_builder..."
    docker wait "$WEB_SERVER_BUILDER_ID" 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "✓ Installation Complete!"
echo "=========================================="
echo ""
echo "Configuration summary:"
echo "  - Robot model: $ROBOT_MODEL"
echo "  - Description type: $DESCRIPTION_TYPE"
echo "  - Robot name: $ROBOT_NAME"
echo "  - Network interface: $NETWORK_INTERFACE"
echo "  - Wi-Fi interface: $WIFI_INTERFACE"
echo "  - Wi-Fi SSID: $WIFI_SSID"
echo "  - Front camera: $FRONT_CAMERA"
echo "  - Rear camera: $REAR_CAMERA"
echo ""
echo "Services status:"
echo "  - botbrain.service: enabled"
echo "  - web_server.service: enabled"
echo ""
