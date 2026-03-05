#!/usr/bin/env python3
"""
LiDAR driver launch file.
Supports LDRobot LD06 and LD19 2D LiDARs via ldlidar_stl_ros2.
Configure via robot_config.yaml: lidar_model and lidar_port.
"""
import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node


_LIDAR_PRODUCT_MAP = {
    'ld06': 'LDLiDAR_LD06',
    'ld19': 'LDLiDAR_LD19',
    'stl27l': 'LDLiDAR_STL27L',
}

_LIDAR_BAUDRATE_MAP = {
    'ld06': 230400,
    'ld19': 230400,
    'stl27l': 921600,
}

# LiDAR mount offset relative to base_link (metres, radians)
# Adjust these to match the physical position of the LiDAR on the robot.
LIDAR_X   =  0.0
LIDAR_Y   =  0.0
LIDAR_Z   =  0.1   # 10 cm above base_link
LIDAR_YAW =  0.0   # 0 = facing forward


def generate_launch_description():
    launch_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(launch_dir))))
    )
    config_file = os.path.join(workspace_dir, 'robot_config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['robot_configuration']

    robot_name  = config.get('robot_name', '')
    lidar_model = (config.get('lidar_model') or '').strip().lower()
    lidar_port  = (config.get('lidar_port')  or '/dev/ldlidar').strip()

    nodes = []

    if not lidar_model:
        return LaunchDescription(nodes)

    prefix         = robot_name + '/' if robot_name else ''
    base_link_frame = f'{prefix}base_link'
    laser_frame     = f'{prefix}base_laser'

    product_name = _LIDAR_PRODUCT_MAP.get(lidar_model)
    baudrate     = _LIDAR_BAUDRATE_MAP.get(lidar_model, 230400)

    if product_name is None:
        print(f'[lidar.launch] WARNING: unknown lidar_model "{lidar_model}" — skipping LiDAR launch')
        return LaunchDescription(nodes)

    # ---- LiDAR driver node ------------------------------------------------
    ldlidar_node = Node(
        package='ldlidar_stl_ros2',
        executable='ldlidar_stl_ros2_node',
        name='ldlidar_node',
        namespace=robot_name,
        output='screen',
        parameters=[
            {'product_name': product_name},
            {'topic_name': 'scan'},
            {'frame_id': laser_frame},
            {'port_name': lidar_port},
            {'port_baudrate': baudrate},
            {'laser_scan_dir': True},
            {'enable_angle_crop_func': False},
            {'angle_crop_min': 135.0},
            {'angle_crop_max': 225.0},
        ],
    )
    nodes.append(ldlidar_node)

    # ---- Static TF: base_link → base_laser --------------------------------
    lidar_tf_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='lidar_tf_publisher',
        namespace=robot_name,
        arguments=[
            str(LIDAR_X), str(LIDAR_Y), str(LIDAR_Z),
            str(LIDAR_YAW), '0', '0',
            base_link_frame, laser_frame,
        ],
        output='screen',
    )
    nodes.append(lidar_tf_node)

    return LaunchDescription(nodes)
