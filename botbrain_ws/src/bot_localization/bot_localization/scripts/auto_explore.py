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
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_srvs.srv import SetBool


# ─────────────────────────── Tuning constants ────────────────────────────── #
FORWARD_SPEED       = 0.45   # m/s  — linear speed when moving forward
ROTATE_SPEED        = 1.30   # rad/s — rotation speed when turning to avoid obstacle
BACKUP_SPEED        = 0.15   # m/s  — reverse speed during corner recovery
SAFETY_DISTANCE     = 0.38   # m    — front clearance to trigger avoidance
FRONT_HALF_ANG_DEG  = 30     # °    — half-width of the "front" detection cone
MIN_ROTATE_TIME     = 0.35   # s    — minimum rotation before checking if path is clear
MAX_ROTATE_TIME     = 3.5    # s    — give up on a direction and try backup recovery
BACKUP_TIME         = 1.2    # s    — how long to back up when cornered
MIN_FORWARD_TIME    = 0.4    # s    — minimum forward drive time (avoids micro-moves)
BODY_CLEARANCE      = 0.12   # m    — ignore readings closer than this (robot's own chassis)
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
        if not (max(msg.range_min, BODY_CLEARANCE) < r < msg.range_max):
            continue
        angle = angle_min_deg + i * angle_inc_deg
        # Normalise to [-180, 180]
        while angle >  180.0: angle -= 360.0
        while angle < -180.0: angle += 360.0
        if start_deg <= angle <= end_deg:
            valid.append(r)

    return min(valid) if valid else float('inf')


def _sector_avg(msg: LaserScan, start_deg: float, end_deg: float) -> float:
    """Return the average valid range in a sector. Used to find the most open direction."""
    angle_min_deg = math.degrees(msg.angle_min)
    angle_inc_deg = math.degrees(msg.angle_increment)
    valid = []
    for i, r in enumerate(msg.ranges):
        if math.isnan(r) or math.isinf(r):
            continue
        if not (max(msg.range_min, BODY_CLEARANCE) < r < msg.range_max):
            continue
        angle = angle_min_deg + i * angle_inc_deg
        while angle >  180.0: angle -= 360.0
        while angle < -180.0: angle += 360.0
        if start_deg <= angle <= end_deg:
            valid.append(r)
    return sum(valid) / len(valid) if valid else 0.0


class AutoExplore(Node):
    """Autonomous exploration node — toggle on/off via SetBool service."""

    def __init__(self, robot_name: str):
        super().__init__('auto_explore')

        ns = f'/{robot_name}' if robot_name else ''

        self._active            = False
        self._last_scan: LaserScan | None = None
        self._state             = 'forward'    # 'forward' | 'rotating' | 'backing'
        self._rotate_dir        = 1.0          # +1 = left  (CCW),  -1 = right (CW)
        self._rotate_start      = 0.0          # when current rotation began
        self._rotate_deadline   = 0.0          # max time for current rotation
        self._backup_start      = 0.0          # when backup began
        self._backup_end        = 0.0          # when backup should end
        self._forward_start     = 0.0          # when forward motion began
        self._stuck_count       = 0            # consecutive rotation timeouts

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
            self._stuck_count = 0
        action = 'started' if self._active else 'stopped'
        res.success = True
        res.message = f'Exploration {action}'
        self.get_logger().info(res.message)
        return res

    def _scan_cb(self, msg: LaserScan):
        self._last_scan = msg

    # ──────────────────────── Control loop ─────────────────────────────── #

    def _best_direction(self, msg: LaserScan) -> float:
        """Return +1 (left/CCW) or -1 (right/CW) toward the most open quadrant."""
        # Sample average range in four quadrants: left, right, back-left, back-right
        left       = _sector_avg(msg,  30.0,  90.0)
        right      = _sector_avg(msg, -90.0, -30.0)
        back_left  = _sector_avg(msg,  90.0, 170.0)
        back_right = _sector_avg(msg, -170.0, -90.0)

        # Prefer forward-adjacent sides; use back only as tiebreak
        left_score  = left  + 0.5 * back_left
        right_score = right + 0.5 * back_right

        return 1.0 if left_score >= right_score else -1.0

    def _loop(self):
        if not self._active or self._last_scan is None:
            return

        msg = self._last_scan
        now = self.get_clock().now().nanoseconds * 1e-9

        front = _sector_min(msg, -FRONT_HALF_ANG_DEG, FRONT_HALF_ANG_DEG)

        twist = Twist()

        if self._state == 'forward':
            fwd_elapsed = now - self._forward_start
            if front < SAFETY_DISTANCE and fwd_elapsed >= MIN_FORWARD_TIME:
                # Obstacle ahead — pick the most open direction and start rotating
                self._stuck_count     = 0
                self._rotate_dir      = self._best_direction(msg)
                self._rotate_start    = now
                self._rotate_deadline = now + MAX_ROTATE_TIME
                self._state = 'rotating'
                self.get_logger().info(
                    f'Obstacle at {front:.2f} m — rotating '
                    f'{"left" if self._rotate_dir > 0 else "right"}')
            else:
                twist.linear.x = FORWARD_SPEED

        elif self._state == 'rotating':
            elapsed = now - self._rotate_start

            # Path is clear AND we've rotated at least MIN_ROTATE_TIME → drive
            if elapsed >= MIN_ROTATE_TIME and front >= SAFETY_DISTANCE:
                self._stuck_count  = 0
                self._forward_start = now
                self._state = 'forward'
                self.get_logger().info(f'Path clear ({front:.2f} m) — driving forward')

            # Rotation timed out — back up to escape the corner
            elif now >= self._rotate_deadline:
                self._stuck_count += 1
                self._backup_start = now
                self._state = 'backing'
                extra = min(self._stuck_count - 1, 3) * 0.5  # longer back-up when repeatedly stuck
                self._backup_end = now + BACKUP_TIME + extra
                self.get_logger().info(
                    f'Corner detected ({front:.2f} m, stuck×{self._stuck_count}) — backing up '
                    f'{BACKUP_TIME + extra:.1f}s')
                twist.linear.x = -BACKUP_SPEED

            else:
                twist.angular.z = self._rotate_dir * ROTATE_SPEED

        elif self._state == 'backing':
            if now >= self._backup_end:
                # Backup done — choose best direction and spin out
                self._rotate_dir      = self._best_direction(msg)
                self._rotate_start    = now
                self._rotate_deadline = now + MAX_ROTATE_TIME
                self._state = 'rotating'
                self.get_logger().info(
                    f'Backup done — rotating {"left" if self._rotate_dir > 0 else "right"}')
            else:
                twist.linear.x = -BACKUP_SPEED

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
