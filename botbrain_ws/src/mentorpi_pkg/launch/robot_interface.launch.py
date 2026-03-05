#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
robot_interface.launch.py for HiWonder MentorPi

Launches three lifecycle nodes:
  mentorpi_read.py          — bridges MentorPi topics → BotBrain namespace
  mentorpi_write.py         — bridges BotBrain cmd_vel → MentorPi
  mentorpi_controller_commands.py — joystick button handling
"""
import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import LifecycleNode
from launch.actions import RegisterEventHandler, EmitEvent
from launch_ros.event_handlers import OnStateTransition
from launch.event_handlers import OnProcessStart
from launch_ros.events.lifecycle import ChangeState
from launch.events import matches_action
from lifecycle_msgs.msg import Transition


def generate_launch_description():

    launch_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(launch_dir))))
    )
    config_file = os.path.join(workspace_dir, 'robot_config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)['robot_configuration']

    robot_name = config['robot_name']
    prefix = robot_name + '/' if robot_name else ''

    # ------------------------------------------------------------------ #
    #  Lifecycle nodes                                                     #
    # ------------------------------------------------------------------ #

    read_node = LifecycleNode(
        package='mentorpi_pkg',
        executable='mentorpi_read.py',
        name='robot_read_node',
        namespace=robot_name,
        parameters=[{'prefix': prefix}],
        output='screen',
    )

    write_node = LifecycleNode(
        package='mentorpi_pkg',
        executable='mentorpi_write.py',
        name='robot_write_node',
        namespace=robot_name,
        parameters=[{'prefix': prefix}],
        output='screen',
    )

    controller_node = LifecycleNode(
        package='mentorpi_pkg',
        executable='mentorpi_controller_commands.py',
        name='controller_commands_node',
        namespace=robot_name,
        output='screen',
    )

    # ------------------------------------------------------------------ #
    #  Auto-configure + activate helpers                                   #
    # ------------------------------------------------------------------ #

    def _make_auto_lifecycle(node):
        configure = RegisterEventHandler(
            OnProcessStart(
                target_action=node,
                on_start=[EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(node),
                    transition_id=Transition.TRANSITION_CONFIGURE,
                ))]
            )
        )
        activate = RegisterEventHandler(
            OnStateTransition(
                target_lifecycle_node=node,
                goal_state='inactive',
                entities=[EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(node),
                    transition_id=Transition.TRANSITION_ACTIVATE,
                ))]
            )
        )
        return configure, activate

    read_cfg,  read_act  = _make_auto_lifecycle(read_node)
    write_cfg, write_act = _make_auto_lifecycle(write_node)
    ctrl_cfg,  ctrl_act  = _make_auto_lifecycle(controller_node)

    return LaunchDescription([
        read_node,
        write_node,
        controller_node,
        read_cfg,
        read_act,
        write_cfg,
        write_act,
        ctrl_cfg,
        ctrl_act,
    ])
