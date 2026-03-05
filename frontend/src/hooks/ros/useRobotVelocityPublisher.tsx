'use client';

import { useMemo, useRef } from 'react';
import { Twist } from '@/interfaces/ros/Twist';
import * as ROSLIB from 'roslib';
import { Vector3 } from 'roslib';
import { getRosTopic, TopicMsgType } from '@/utils/ros/topics-and-services-v2';
import { getRosMsgType } from '@/utils/ros/messages';
import { useRobotConnection } from '@/contexts/RobotConnectionContext';
import { useRobotProfile } from '@/contexts/RobotProfileContext';
import { useSpeedMode } from '@/contexts/SpeedModeContext';
import { auditLogger } from '@/utils/audit-logger';

export default function useRobotVelocityPublisher(useDummy: boolean = false) {
  const { connection } = useRobotConnection();
  const { currentProfile } = useRobotProfile();
  const { speedMultiplier, speedMode } = useSpeedMode();
  const lastLogTimeRef = useRef<number>(0);
  const isMovingRef = useRef<boolean>(false);
  const controlTypeRef = useRef<'joystick' | 'keyboard' | 'gamepad'>('joystick');

  const velocityTopic = useMemo(() => {
    if (!connection.ros || !connection.online) return null;
    const topicName = getRosTopic('velocityNipple', currentProfile, useDummy);
    const topic = new ROSLIB.Topic({
      ros: connection.ros,
      name: topicName,
      messageType: getRosMsgType(TopicMsgType['velocityNipple']),
      compression: 'cbor',
      throttle_rate: 0,
      queue_size: 1,
    });
    topic.subscribe(() => {});
    return topic;
  }, [connection.ros, connection.online, useDummy, currentProfile]);

  const publishVelocity = (newVelocity: Twist, inputSource?: 'joystick' | 'keyboard' | 'gamepad') => {
    if (!velocityTopic) {
      // console.warn(
      //   'Conexão ROS não estabelecida ou offline. Não foi possível publicar.'
      // );
      return;
    }

    // Scale joystick's normalized [-1, 1] output to actual physical units (m/s, rad/s).
    // The joystick always sends a fraction of the maximum; multiplying by the robot's
    // hardware limits converts that fraction into the real velocity the robot expects.
    // Profiles that don't define these capabilities fall back to 1.0 (no change).
    const maxLinear  = currentProfile?.capabilities?.maxLinearVelocity  ?? 1.0;
    const maxAngular = currentProfile?.capabilities?.maxAngularVelocity ?? 1.0;

    // Apply speed multiplier AND physical scaling to the velocity
    const scaledVelocity: Twist = {
      linear: new Vector3({
        x: newVelocity.linear.x * speedMultiplier * maxLinear,
        y: newVelocity.linear.y * speedMultiplier * maxLinear,
        z: newVelocity.linear.z * speedMultiplier * maxLinear,
      }),
      angular: new Vector3({
        x: newVelocity.angular.x * speedMultiplier * maxAngular,
        y: newVelocity.angular.y * speedMultiplier * maxAngular,
        z: newVelocity.angular.z * speedMultiplier * maxAngular,
      }),
    };

    // Check if robot is moving (non-zero velocity after scaling)
    const isCurrentlyMoving =
      scaledVelocity.linear.x !== 0 ||
      scaledVelocity.linear.y !== 0 ||
      scaledVelocity.linear.z !== 0 ||
      scaledVelocity.angular.x !== 0 ||
      scaledVelocity.angular.y !== 0 ||
      scaledVelocity.angular.z !== 0;

    // Throttle audit logging to once per second when moving
    const now = Date.now();
    const timeSinceLastLog = now - lastLogTimeRef.current;

    // Update control type if provided
    if (inputSource) {
      controlTypeRef.current = inputSource;
    }

    // Log when starting movement, every second during movement, or when stopping
    if (isCurrentlyMoving && (!isMovingRef.current || timeSinceLastLog > 1000)) {
      // Starting movement or periodic log during movement
      const action = controlTypeRef.current === 'keyboard' ? 'keyboard_control' :
                     controlTypeRef.current === 'gamepad' ? 'gamepad_control' :
                     'joystick_control';

      auditLogger.log({
        event_type: 'command',
        event_action: action,
        robot_id: connection.connectedRobot?.id,
        robot_name: connection.connectedRobot?.name,
        event_details: {
          linear_x: scaledVelocity.linear.x.toFixed(2),
          linear_y: scaledVelocity.linear.y.toFixed(2),
          angular_z: scaledVelocity.angular.z.toFixed(2),
          speed_mode: speedMode,
          speed_multiplier: speedMultiplier,
        }
      });

      lastLogTimeRef.current = now;
    } else if (!isCurrentlyMoving && isMovingRef.current) {
      // Stopping movement
      auditLogger.log({
        event_type: 'command',
        event_action: 'command_sent',
        robot_id: connection.connectedRobot?.id,
        robot_name: connection.connectedRobot?.name,
        event_details: {
          command: 'stop',
          source: controlTypeRef.current
        }
      });
    }

    isMovingRef.current = isCurrentlyMoving;
    velocityTopic.publish(scaledVelocity);
  };

  return publishVelocity;
}
