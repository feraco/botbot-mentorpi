#!/usr/bin/env python3
"""
mentorpi_read.py  —  BotBrain bridge node for HiWonder MentorPi

Subscribes to MentorPi's native ROS2 topics and republishes them
under the BotBrain robot namespace so the rest of the stack
(localization, navigation, state machine) can consume them.

MentorPi standard topics consumed:
  /odom                 → nav_msgs/Odometry
  /imu                  → sensor_msgs/Imu   (optional)
  /joint_states         → sensor_msgs/JointState (optional)

BotBrain topics published (all under robot_name namespace):
  odom                  → nav_msgs/Odometry
  imu/data              → sensor_msgs/Imu
  joint_states          → sensor_msgs/JointState
  battery               → sensor_msgs/BatteryState (simulated — MentorPi has no battery topic)

TF:
  Forwards odom → base_link transform published by MentorPi's ros2_control.
  BotBrain navigation expects this TF to be present.
"""

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.executors import MultiThreadedExecutor

from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, JointState, BatteryState
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster


class MentorPiRead(LifecycleNode):
    def __init__(self):
        super().__init__('robot_read_node')

        self.prefix = ''

        # Subscriber handles (created in on_configure)
        self.odom_sub = None
        self.imu_sub = None
        self.joint_state_sub = None

        # Publisher handles
        self.odom_pub = None
        self.imu_pub = None
        self.joint_state_pub = None
        self.battery_pub = None
        self.battery_timer = None

        self.tf_broadcaster = None

        self.get_logger().info("Lifecycle node created, in 'unconfigured' state.")

    # ------------------------------------------------------------------ #
    #  Lifecycle transitions                                               #
    # ------------------------------------------------------------------ #

    def on_configure(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_configure() is called.')

        self.declare_parameter('prefix', '')
        self.prefix = self.get_parameter('prefix').value
        self.get_logger().info(f"Using prefix: '{self.prefix}'")

        # ---- Subscribers: MentorPi native topics ----
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self._odom_callback, 10)
        self.imu_sub = self.create_subscription(
            Imu, '/imu', self._imu_callback, 10)
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self._joint_state_callback, 10)

        # ---- TF broadcaster ----
        self.tf_broadcaster = TransformBroadcaster(self)

        # ---- Publishers: BotBrain namespaced topics ----
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu/data', 10)
        self.joint_state_pub = self.create_publisher(JointState, 'joint_states', 10)
        self.battery_pub = self.create_publisher(BatteryState, 'battery', 1)

        self.get_logger().info('Node configured successfully.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_activate() is called.')
        super().on_activate(state)
        # Publish battery state periodically (MentorPi has no battery topic)
        self.battery_timer = self.create_timer(2.0, self._battery_timer_callback)
        self.get_logger().info('Node is active.')
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_deactivate() is called.')
        super().on_deactivate(state)
        if self.battery_timer:
            self.destroy_timer(self.battery_timer)
            self.battery_timer = None
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_cleanup() is called.')
        self.destroy_subscription(self.odom_sub)
        self.destroy_subscription(self.imu_sub)
        self.destroy_subscription(self.joint_state_sub)
        self.destroy_publisher(self.odom_pub)
        self.destroy_publisher(self.imu_pub)
        self.destroy_publisher(self.joint_state_pub)
        self.destroy_publisher(self.battery_pub)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_shutdown() is called.')
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------ #
    #  Callbacks                                                           #
    # ------------------------------------------------------------------ #

    def _odom_callback(self, msg: Odometry):
        """Bridge MentorPi /odom → BotBrain namespace odom + re-broadcast TF."""
        # Re-stamp with the robot namespace prefix in frame IDs
        prefix = self.prefix
        out = Odometry()
        out.header.stamp = msg.header.stamp
        out.header.frame_id = f'{prefix}odom'
        out.child_frame_id = f'{prefix}base_link'
        out.pose = msg.pose
        out.twist = msg.twist
        self.odom_pub.publish(out)

        # Re-broadcast TF odom → base_link under prefix
        tf = TransformStamped()
        tf.header.stamp = msg.header.stamp
        tf.header.frame_id = f'{prefix}odom'
        tf.child_frame_id = f'{prefix}base_link'
        tf.transform.translation.x = msg.pose.pose.position.x
        tf.transform.translation.y = msg.pose.pose.position.y
        tf.transform.translation.z = msg.pose.pose.position.z
        tf.transform.rotation = msg.pose.pose.orientation
        self.tf_broadcaster.sendTransform(tf)

    def _imu_callback(self, msg: Imu):
        """Bridge MentorPi /imu → BotBrain namespace imu/data."""
        out = Imu()
        out.header.stamp = msg.header.stamp
        out.header.frame_id = f'{self.prefix}imu_link'
        out.orientation = msg.orientation
        out.orientation_covariance = msg.orientation_covariance
        out.angular_velocity = msg.angular_velocity
        out.angular_velocity_covariance = msg.angular_velocity_covariance
        out.linear_acceleration = msg.linear_acceleration
        out.linear_acceleration_covariance = msg.linear_acceleration_covariance
        self.imu_pub.publish(out)

    def _joint_state_callback(self, msg: JointState):
        """Bridge MentorPi /joint_states → BotBrain namespace joint_states."""
        msg.header.frame_id = ''
        self.joint_state_pub.publish(msg)

    def _battery_timer_callback(self):
        """Publish a placeholder battery state (MentorPi has no battery ROS2 topic)."""
        bat = BatteryState()
        bat.header.stamp = self.get_clock().now().to_msg()
        bat.voltage = float('nan')
        bat.percentage = float('nan')
        bat.present = True
        bat.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
        self.battery_pub.publish(bat)


def main(args=None):
    rclpy.init(args=args)
    node = MentorPiRead()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
