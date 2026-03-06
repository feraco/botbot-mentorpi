'use client';

import { useState, useEffect } from 'react';
import * as ROSLIB from 'roslib';
import { ROSTopicFactory } from '@/utils/ros/topics-and-services';
import { useRobotConnection } from '@/contexts/RobotConnectionContext';
import { Odometry } from '@/interfaces/ros/Odometry';
import { Pose, Vector3 } from 'roslib';

export default function useOdometry(useDummy: boolean = false, topicName?: string): Odometry {
  const { connection } = useRobotConnection();

  const [odometry, setOdometry] = useState<Odometry>({
    header: {
      frame_id: '',
      seq: 0,
      stamp: {
        nanosec: 0,
        sec: 0,
      },
    },
    child_frame_id: '',
    pose: {
      pose: new Pose(),
      covariance: [],
    },
    twist: {
      twist: {
        linear: new Vector3(),
        angular: new Vector3(),
      },
      covariance: [],
    },
  });

  useEffect(() => {
    if (!connection.ros || !connection.online) return;

    const handleMsg = (msg: unknown) => {
      const o = msg as Odometry;
      if (o?.pose?.pose) {
        const { position, orientation } = o.pose.pose;
        if (position && orientation &&
            typeof position.x === 'number' && typeof position.y === 'number' &&
            typeof orientation.w === 'number') {
          setOdometry(o);
        }
      }
    };

    // If a specific topic name is provided (e.g. from the robot profile), use it directly.
    if (topicName) {
      const topic = new ROSLIB.Topic({
        ros: connection.ros,
        name: topicName,
        messageType: 'nav_msgs/Odometry',
        compression: 'cbor',
        throttle_rate: 0,
        queue_size: 1,
      });
      topic.subscribe(handleMsg);
      return () => topic.unsubscribe();
    }

    const topicFactory: ROSTopicFactory = new ROSTopicFactory(
      connection.ros,
      useDummy
    );

    try {
      const odometryTopic = topicFactory.createAndSubscribeTopic<Odometry>(
        'odometry',
        handleMsg
      );

      return () => odometryTopic.unsubscribe();
    } catch (error) {
      console.error('Error setting up odometry subscription:', error);
      return () => {};
    }
  }, [connection.ros, connection.online, useDummy, topicName]);

  return odometry;
}
