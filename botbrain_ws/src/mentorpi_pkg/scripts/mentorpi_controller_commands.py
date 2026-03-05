#!/usr/bin/env python3
"""
mentorpi_controller_commands.py  —  Joystick button handler for MentorPi

Maps controller button presses from the BotBrain joystick to
MentorPi-specific commands.

Button mappings (matches standard BotBrain layout):
  START  — resume movement (clear e-stop)
  SELECT — trigger emergency stop
  L1     — (reserved / no-op)
  R1     — (reserved / no-op)
"""

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.executors import MultiThreadedExecutor

from joystick_bot.msg import ControllerButtonsState
from bot_custom_interfaces.srv import Mode
from std_srvs.srv import SetBool


class MentorPiControllerCommands(LifecycleNode):
    def __init__(self):
        super().__init__('controller_commands_node')

        self.button_subscription = None
        self.mode_srv_cli = None
        self.emergency_stop_cli = None
        self.timer = None

        self.button_states: dict = {}

        self.get_logger().info("Lifecycle node created, in 'unconfigured' state.")

    # ------------------------------------------------------------------ #
    #  Lifecycle transitions                                               #
    # ------------------------------------------------------------------ #

    def on_configure(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_configure() is called.')

        self.button_subscription = self.create_subscription(
            ControllerButtonsState,
            'button_state',
            self._button_callback,
            1
        )

        self.mode_srv_cli = self.create_client(Mode, 'mode')
        self.emergency_stop_cli = self.create_client(SetBool, 'emergency_stop')

        self.timer = self.create_timer(0.1, self._timer_callback)
        self.timer.cancel()

        self.get_logger().info('Node configured.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_activate() is called.')
        super().on_activate(state)
        self.timer.reset()
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_deactivate() is called.')
        super().on_deactivate(state)
        self.timer.cancel()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        self.get_logger().info('on_cleanup() is called.')
        self.destroy_subscription(self.button_subscription)
        self.destroy_client(self.mode_srv_cli)
        self.destroy_client(self.emergency_stop_cli)
        self.destroy_timer(self.timer)
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: rclpy.lifecycle.State) -> TransitionCallbackReturn:
        return TransitionCallbackReturn.SUCCESS

    # ------------------------------------------------------------------ #
    #  Callbacks                                                           #
    # ------------------------------------------------------------------ #

    def _button_callback(self, msg: ControllerButtonsState):
        self.button_states = {
            'start':  msg.start_button,
            'select': msg.select_button,
            'L1':     msg.l1_button,
            'L2':     msg.l2_button,
            'R1':     msg.r1_button,
            'R2':     msg.r2_button,
            'A':      msg.a_button,
            'B':      msg.b_button,
            'X':      msg.x_button,
            'Y':      msg.y_button,
        }

    def _timer_callback(self):
        if not self.button_states:
            return

        # START → clear emergency stop
        if self.button_states.get('start'):
            self._call_emergency_stop(False)

        # SELECT → trigger emergency stop
        if self.button_states.get('select'):
            self._call_emergency_stop(True)

        self.button_states = {}

    def _call_emergency_stop(self, engage: bool):
        if not self.emergency_stop_cli.service_is_ready():
            return
        req = SetBool.Request()
        req.data = engage
        self.emergency_stop_cli.call_async(req)
        self.get_logger().info(f'Emergency stop → {engage}')


def main(args=None):
    rclpy.init(args=args)
    node = MentorPiControllerCommands()
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
