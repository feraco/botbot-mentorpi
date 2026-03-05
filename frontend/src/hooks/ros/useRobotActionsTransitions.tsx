'use client';

import { RobotStatus } from '@/types/RobotStatus';
import { robotTransitions } from '@/utils/ros/modeStates';
import { useMemo } from 'react';
import { useRobotProfile } from '@/contexts/RobotProfileContext';
import { RobotActionTypeName } from '@/types/RobotActionTypes';

export default function useRobotActionsTransitions(currentStatus: RobotStatus) {
  const { currentProfile } = useRobotProfile();

  return useMemo(() => {
    const baseActions = robotTransitions[currentStatus] || [];

    // Add G1-specific actions at the beginning
    if (currentProfile?.id === 'g1-r1') {
      // Add damping and zeroTorque as first actions for all states except emergency
      if (currentStatus !== 'emergency') {
        const g1Actions: RobotActionTypeName[] = ['damping', 'zeroTorque'];
        return [...g1Actions, ...baseActions];
      }
    }

    // MentorPi: wheeled diff-drive rover — replace quadruped actions with drive-relevant ones
    if (currentProfile?.id === 'mentorpi-r1') {
      if (currentStatus !== 'emergency') {
        const mentorPiActions: RobotActionTypeName[] = [
          'antiCollisionOn',
          'lightOn',
        ];
        return mentorPiActions;
      }
    }

    return baseActions;
  }, [currentStatus, currentProfile]);
}
