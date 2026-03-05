#!/usr/bin/env python3
"""
mentorpi_write.py  —  BotBrain command bridge for HiWonder MentorPi

Responsibilities:
  • Subscribes to BotBrain cmd_vel_out (Twist) and drives motors DIRECTLY
    via the HiWonder Board SDK (USB serial → STM32 MCU on the robot)
  • Emergency-stop: clears velocity when triggered
  • Implements BotBrain's Mode and EmergencyStop services
  • Publishes robot_status for the web UI

Motor layout (MentorPi Pro diff-drive, 4-wheel):
  Motors 1, 2  →  LEFT  side  (positive speed = forward)
  Motors 3, 4  →  RIGHT side  (wired in reverse → must negate)

Diff-drive mixer:
  left_speed  = linear_x / MAX_LIN  -  angular_z * HALF_WB / MAX_LIN
  right_speed = linear_x / MAX_LIN  +  angular_z * HALF_WB / MAX_LIN
  (both clamped to [-1, 1]; right side negated before sending to board)

MentorPi hardware limits (approximate MentorPi Pro):
  Linear:    max ~0.5 m/s
  Angular:   max ~2.0 rad/s
  Wheelbase: 0.16 m  →  half = 0.08 m
"""

import os
import sys

# Make the bundled HiWonder SDK importable when installed as a ROS2 package
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool
from bot_custom_interfaces.srv import Mode
from bot_custom_interfaces.msg import RobotStatus

try:
    import ros_robot_controller_sdk as rrc
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


# ------------------------------------------------------------------ #
#  Constants                                                           #
# ------------------------------------------------------------------ #
MAX_LINEAR_X   =  0.5   # m/s
MAX_ANGULAR_Z  =  2.0   # rad/s
HALF_WHEELBASE =  0.08  # metres  (wheelbase = 0.16 m / 2)

DEFAULT_BOARD_DEVICE = '/dev/ttyACM0'   # USB STM32 board


class MentorPiWrite(LifecycleNode):
    def __init__(self):
        super().__init__('robot_write_node')

        self.prefix = ''
        self.emergency_flag = True   # start in e-stop until activated
        self.op_mode = None

        # HiWonder Board SDK handle
        self.board = None
        self.board_device = DEFAULT_BOARD_DEVICE

        # ROS handles (created in on_configure)
        self.callback_group = None
        self.cmd_vel_sub = None
        self.robot_status_pub = None
        self.robot_status_timer = None
        self.mode_srv = None
        self.emergency_stop_srv = None

        self.get_logger().info("Lifecycle node created, in 'unconfigured' state.")

    # ------------------------------------------------------------------ #
    #  Lifecycle transitions                                               #
    # ------------------------------------------------------------------ #

    def on_configure(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_configure() is called.')

        self.declare_parameter('prefix', '')
        self.declare_parameter('board_device', DEFAULT_BOARD_DEVICE)
        self.prefix = self.get_parameter('prefix').value
        self.board_device = self.get_parameter('board_device').value

        self.callback_group = ReentrantCallbackGroup()

        # --- Initialise HiWonder Board SDK (USB serial to STM32) ---
        if not _SDK_AVAILABLE:
            self.get_logger().error(
                'ros_robot_controller_sdk not found — motor control disabled!'
            )
        else:
            try:
                self.board = rrc.Board(device=self.board_device)
                self.get_logger().info(
                    f'Board SDK initialised on {self.board_device}'
                )
            except Exception as exc:
                self.board = None
                self.get_logger().error(
                    f'Failed to open board device {self.board_device}: {exc}'
                )

        # Publisher → BotBrain robot status (for web UI)
        self.robot_status_pub = self.create_publisher(RobotStatus, 'robot_status', 1)
        self.robot_status_timer = self.create_timer(
            0.5, self._robot_status_callback,
            callback_group=self.callback_group
        )
        self.robot_status_timer.cancel()

        # Subscriber ← BotBrain velocity output (from twist_mux)
        self.cmd_vel_sub = self.create_subscription(
            Twist, 'cmd_vel_out', self._cmd_vel_callback, 1,
            callback_group=self.callback_group
        )

        # Services
        self.mode_srv = self.create_service(
            Mode, 'mode', self._mode_callback,
            callback_group=self.callback_group
        )
        self.emergency_stop_srv = self.create_service(
            SetBool, 'emergency_stop', self._emergency_stop_callback,
            callback_group=self.callback_group
        )

        self.get_logger().info('Node configured successfully.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_activate() is called.')
        super().on_activate(state)
        self.emergency_flag = False   # release e-stop on activation
        self.robot_status_timer.reset()
        self.get_logger().info('Node activated — ready to drive motors.')
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_deactivate() is called.')
        super().on_deactivate(state)
        self._stop_motors()
        self.emergency_flag = True
        self.robot_status_timer.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_cleanup() is called.')
        self._stop_motors()
        self.destroy_subscription(self.cmd_vel_sub)
        self.destroy_publisher(self.robot_status_pub)
        self.destroy_service(self.mode_srv)
        self.destroy_service(self.emergency_stop_srv)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self._stop_motors()
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------ #
    #  Motor helpers                                                       #
    # ------------------------------------------------------------------ #

    def _stop_motors(self):
        """Send zero speed to all four wheels."""
        if self.board is not None:
            try:
                self.board.set_motor_speed([[1, 0.0], [2, 0.0], [3, 0.0], [4, 0.0]])
            except Exception as exc:
                self.get_logger().warn(f'Board stop failed: {exc}')

    def _drive(self, left: float, right: float):
        """
        Send normalised wheel speeds to the board.

        Motor layout:
          1, 2  = left  side  (positive value → forward)
          3, 4  = right side  (wired in reverse → negate)
        """
        if self.board is not None:
            try:
                self.board.set_motor_speed([
                    [1,  left],
                    [2,  left],
                    [3, -right],
                    [4, -right],
                ])
            except Exception as exc:
                self.get_logger().warn(f'Board write failed: {exc}')

    @staticmethod
    def _clamp(value: float, limit: float) -> float:
        return max(-limit, min(limit, value))

    # ------------------------------------------------------------------ #
    #  Callbacks                                                           #
    # ------------------------------------------------------------------ #

    def _cmd_vel_callback(self, msg: Twist):
        if self.emergency_flag:
            self._stop_motors()
            return

        linear_x  = self._clamp(msg.linear.x,  MAX_LINEAR_X)
        angular_z = self._clamp(msg.angular.z, MAX_ANGULAR_Z)

        # Differential-drive mixer  (output in [-1, 1])
        left  = linear_x / MAX_LINEAR_X - angular_z * HALF_WHEELBASE / MAX_LINEAR_X
        right = linear_x / MAX_LINEAR_X + angular_z * HALF_WHEELBASE / MAX_LINEAR_X

        left  = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))

        self._drive(left, right)

    def _robot_status_callback(self):
        status = RobotStatus()
        status.emergency_stop = self.emergency_flag
        status.light_state = False
        self.robot_status_pub.publish(status)

    def _mode_callback(self, request: Mode.Request, response: Mode.Response):
        self.get_logger().info(f'Mode request: {request.mode}')
        self.op_mode = request.mode
        response.success = True
        return response

    def _emergency_stop_callback(
        self,
        request: SetBool.Request,
        response: SetBool.Response
    ):
        self.emergency_flag = request.data
        self.get_logger().info(f'Emergency stop: {self.emergency_flag}')
        if self.emergency_flag:
            self._stop_motors()
        response.success = True
        response.message = 'OK'
        return response


def main(args=None):
    rclpy.init(args=args)
    node = MentorPiWrite()
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
