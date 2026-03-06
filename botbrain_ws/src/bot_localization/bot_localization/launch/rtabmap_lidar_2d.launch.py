"""
RTABMap SLAM / localization using a 2-D LiDAR (LaserScan).
Used when lidar_model is set to 'ld06' or 'ld19' in robot_config.yaml.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os
import yaml


def generate_launch_description():
    launch_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(launch_dir))))
    )
    config_file = os.path.join(workspace_dir, 'robot_config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['robot_configuration']

    robot_name = config['robot_name']
    prefix     = robot_name + '/' if robot_name != '' else ''
    frame_id   = f'{prefix}base_link'
    odom_frame = f'{prefix}odom'
    scan_topic = f'/{prefix}scan'
    # ICP odom uses a separate topic to avoid conflict with wheel-encoder odom
    icp_odom_topic = f'/{prefix}odom_icp'

    database_path_arg = DeclareLaunchArgument(
        'database_path',
        description='Path to the RTAB-Map database file'
    )
    database_path = LaunchConfiguration('database_path')

    # ICP odometry node — computes odometry from LiDAR scan matching.
    # This is needed when wheel-encoder odometry is unavailable (e.g. MentorPi
    # without the HiWonder hardware container running).
    icp_odom_node = Node(
        package='rtabmap_odom',
        executable='icp_odometry',
        name='icp_odometry',
        namespace=robot_name,
        output='screen',
        parameters=[{
            'frame_id': frame_id,
            'odom_frame_id': odom_frame,
            'use_sim_time': False,
            'approx_sync': True,
            'qos': 1,
            # ICP settings matching RTABMap
            'Icp/VoxelSize': '0.05',
            'Icp/PointToPlane': 'false',
            'Icp/Iterations': '30',
            'Icp/MaxCorrespondenceDistance': '1.0',
            'Icp/CorrespondenceRatio': '0.2',
            'Odom/ScanKeyFrameThr': '0.9',
            # Auto-reset the ICP reference after 1 consecutive failure so the
            # node recovers immediately after a fast turn or sudden motion,
            # instead of staying permanently stuck in the lost-odometry state.
            'Odom/ResetCountdown': '1',
            # Use TF from wheel odometry as the initial transformation guess.
            # This dramatically improves tracking during fast motion.
            'guess_frame_id': odom_frame,
        }],
        remappings=[
            ('scan', scan_topic),
            ('odom', icp_odom_topic),
        ],
    )

    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        namespace=robot_name,
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'frame_id': frame_id,
            'map_frame_id': 'map',
            'qos': 1,
            'approx_sync': True,
            'wait_for_transform': 0.5,

            # 2-D LaserScan subscription
            'subscribe_depth': False,
            'subscribe_rgb': False,
            'subscribe_scan': True,
            'subscribe_scan_cloud': False,
            'subscribe_odom_info': False,

            'database_path': database_path,

            # Occupancy grid for Nav2
            'Grid/FromDepth': 'false',
            'Grid/RayTracing': 'true',
            'Grid/3D': 'false',
            'RGBD/CreateOccupancyGrid': 'true',

            # Always publish the occupancy grid, even if no new nodes were added.
            # Without this, the map is only published when the robot moves.
            'map_always_update': True,

            # Odometry / update thresholds
            'RGBD/AngularUpdate': '0.05',
            'RGBD/LinearUpdate': '0.05',
            'RGBD/ProximityMaxGraphDepth': '0',
            'RGBD/ProximityPathMaxNeighbors': '1',

            # Memory / SLAM settings
            # IncrementalMemory=True  → full SLAM: builds and updates the map while driving
            # IncrementalMemory=False → localization only (requires an existing rtabmap.db)
            'Mem/NotLinkedNodesKept': 'false',
            'Mem/STMSize': '30',
            'Mem/IncrementalMemory': 'True',
            'Mem/InitWMWithAllNodes': 'True',

            # ICP (scan-matching)
            'Reg/Strategy': '1',
            'Icp/VoxelSize': '0.05',
            'Icp/PointToPlane': 'false',
            'Icp/Iterations': '10',
            'Icp/MaxCorrespondenceDistance': '0.5',
            'Icp/CorrespondenceRatio': '0.2',
        }],
        remappings=[
            ('odom', icp_odom_topic),
            ('scan', scan_topic),
        ],
    )

    return LaunchDescription([database_path_arg, icp_odom_node, rtabmap_node])
