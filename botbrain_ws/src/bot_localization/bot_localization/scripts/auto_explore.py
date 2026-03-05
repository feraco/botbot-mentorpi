#!/usr/bin/env python3
"""
auto_explore.py  —  BotBrain Autonomous Room Explorer

Implements a simple LiDAR-based exploration loop:
  • Moves forward until an obstacle is detected in the front sector
  • Chooses the more open direction (left or right) and rotates away
  • Continues exploring repeatedly, building the RTABMap while moving

Enable / disable via SetBool service:
  ros2 service call /<namespace>/exploration_control std_srvs/srv/SetBool "{data: true}"

All topic / service names are derived from robot_config.yaml so this script
works for any BotBrain robot.
"""

import os
import sys
import math
import yaml
import random
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool


# ─────────────────────────── Tuning constants ────────────────────────────── #
FORWARD_SPEED      = 0.20   # m/s  — linear speed when moving forward
ROTATE_SPEED       = 0.90   # rad/s — rotation speed when avoiding obstacle
SAFETY_DISTANCE    = 0.55   # m    — front clearance threshold to trigger avoidance
FRONT_HALF_ANG_DEG = 30     # °    — half-width of the "front" detection sector
SIDE_HALF_ANG_DEG  = 60     # °    — half-width used to compare left vs right openness
ROTATE_DURATION    = 1.8    # s    — base time to rotate (randomised ±30 % to avoid loops)
# ─────────────────────────────────────────────────────────────────────────── #


def _sector_min(msg: LaserScan, start_deg: float, end_deg: float) -> float:
    """Return the minimum valid range within [start_deg, end_deg] (degrees, -180..180).

    0° is the forward direction of the robot.  Positive angles are
    counter-clockwise (standard REP-103 / LD06 convention).
    """
    angle_min_deg  = math.degrees(msg.angle_min)
    angle_inc_deg  = math.degrees(msg.angle_increment)

    valid = []
    for i, r in enumerate(msg.ranges):
        if math.isnan(r) or math.isinf(r):
            continue
        if not (msg.range_min < r < msg.range_max):
            continue
        angle = angle_min_deg + i * angle_inc_deg
        # Normalise to [-180, 180]
        while angle >  180.0: angle -= 360.0
        while angle < -180.0: angle += 360.0
        if start_deg <= angle <= end_deg:
            valid.append(r)

    return min(valid) if valid else float('inf')


class AutoExplore(Node):
    """Autonomous exploration node — toggle on/off via SetBool service."""

    def __init__(self, robot_name: str):
        super().__init__('auto_explore')

        ns = f'/{robot_name}' if robot_name else ''

        self._active            = False
        self._last_scan: LaserScan | None = None
        self._state             = 'forward'    # 'forward' | 'rotating'
        self._rotate_dir        = 1.0          # +1 = left  (CCW),  -1 = right (CW)
        self._rotate_deadline   = 0.0          # absolute timestamp (seconds)

        # ROS interfaces
        self._cmd_pub = self.create_publisher(
            Twist, f'{ns}/cmd_vel_nipple', 10)

        self.create_subscription(
            LaserScan, f'{ns}/scan', self._scan_cb, 10)

        self.create_service(
            SetBool, f'{ns}/exploration_control', self._control_cb)

        # Control loop at 10 Hz
        self.create_timer(0.1, self._loop)

        self.get_logger().info(
            f'AutoExplore ready — service: {ns}/exploration_control')

    # ────────────────────────── Callbacks ──────────────────────────────── #

    def _control_cb(self, req: SetBool.Request, res: SetBool.Response):
        self._active = req.data
        if not self._active:
            self._stop()
            self._state = 'forward'
        action = 'started' if self._active else 'stopped'
        res.success = True
        res.message = f'Exploration {action}'
        self.get_logger().info(res.message)
        return res

    def _scan_cb(self, msg: LaserScan):
        self._last_scan = msg

    # ──────────────────────── Control loop ─────────────────────────────── #

    def _loop(self):
        if not self._active or self._last_scan is None:
            return

        msg  = self._last_scan
        now  = self.get_clock().now().nanoseconds * 1e-9

        front = _sector_min(msg, -FRONT_HALF_ANG_DEG, FRONT_HALF_ANG_DEG)
        left  = _sector_min(msg,  FRONT_HALF_ANG_DEG, FRONT_HALF_ANG_DEG + SIDE_HALF_ANG_DEG)
        right = _sector_min(msg, -FRONT_HALF_ANG_DEG - SIDE_HALF_ANG_DEG, -FRONT_HALF_ANG_DEG)

        twist = Twist()

        if self._state == 'forward':
            if front < SAFETY_DISTANCE:
                # Obstacle: choose roomier side; add small random jitter to avoid deadlocks
                self._rotate_dir = 1.0 if left >= right else -1.0
                jitter = random.uniform(0.7, 1.3)
                self._rotate_deadline = now + ROTATE_DURATION * jitter
                self._state = 'rotating'
                self.get_logger().info(
                    f'Obstacle at {front:.2f} m — rotating '
                    f'{"left" if self._rotate_dir > 0 else "right"} '
                    f'(L={left:.2f} R={right:.2f})')
            else:
                twist.linear.x = FORWARD_SPEED

        elif self._state == 'rotating':
            if now >= self._rotate_deadline:
                # Finished rotating — recheck before advancing
                if front >= SAFETY_DISTANCE:
                    self._state = 'forward'
                    self.get_logger().info('Path clear — resuming forward')
                else:
                    # Still blocked: choose again and keep rotating
                    self._rotate_dir = 1.0 if left >= right else -1.0
                    jitter = random.uniform(0.7, 1.3)
                    self._rotate_deadline = now + ROTATE_DURATION * jitter
                    self.get_logger().info(
                        f'Still blocked ({front:.2f} m) — rotating '
                        f'{"left" if self._rotate_dir > 0 else "right"}')
            else:
                twist.angular.z = self._rotate_dir * ROTATE_SPEED

        self._cmd_pub.publish(twist)

    def _stop(self):
        self._cmd_pub.publish(Twist())


# ──────────────────────────── Entry point ──────────────────────────────── #

def main(args=None):
    # Read robot_config.yaml to get the robot namespace
    workspace_dir = os.environ.get('BOTBRAIN_WS', '/botbrain_ws')
    config_file   = os.path.join(workspace_dir, 'robot_config.yaml')
    robot_name    = ''
    try:
        with open(config_file, 'r') as f:
            cfg = yaml.safe_load(f)['robot_configuration']
            robot_name = cfg.get('robot_name', '')
    except Exception as e:
        print(f'[auto_explore] Warning: could not read {config_file}: {e}',
              file=sys.stderr)

    rclpy.init(args=args)
    node = AutoExplore(robot_name)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
