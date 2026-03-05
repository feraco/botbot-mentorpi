#!/usr/bin/env python3
"""
RGB camera launch file.
Launches bot_camera.camera_node for a USB/UVC camera (V4L2).
Configure in robot_config.yaml:
  camera_device: 0         # /dev/video<n> index
  camera_topic:  "front_camera/color/image_raw"   # topic to publish
  camera_width:  640
  camera_height: 480
  camera_fps:    30
"""
import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    launch_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(launch_dir))))
    )
    config_file = os.path.join(workspace_dir, 'robot_config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['robot_configuration']

    # Only launch if camera_device is configured (not None/empty)
    camera_device = config.get('camera_device')
    if camera_device is None or str(camera_device).strip() == '':
        return LaunchDescription([])

    device_id     = int(camera_device)
    topic_name    = config.get('camera_topic',  'front_camera/color/image_raw')
    width         = int(config.get('camera_width',  640))
    height        = int(config.get('camera_height', 480))
    fps           = int(config.get('camera_fps',     30))

    camera_node = Node(
        package='bot_camera',
        executable='camera_node',
        name='front_camera',
        namespace='',
        output='screen',
        parameters=[{
            'device_id':  device_id,
            'topic_name': topic_name,
            'width':      width,
            'height':     height,
            'fps':        fps,
            'frame_id':   'front_camera_link',
        }],
    )

    return LaunchDescription([camera_node])
