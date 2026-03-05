import { RobotProfile } from '../types';

export const MentorPiR1Profile: RobotProfile = {
  id: 'mentorpi-r1',
  name: 'MentorPi-R1',
  manufacturer: 'HiWonder',
  model: 'MentorPi',
  description: 'HiWonder MentorPi wheeled rover with differential drive, LD06 LiDAR and RGB USB camera',
  imageUrl: '/images/robots/mentorpi-r1.png',
  urdfPath: '/models/mentorpi/robot.urdf',

  capabilities: {
    hasCamera: true,
    hasThermalCamera: false,
    hasLidar: true,
    hasArm: false,
    hasGripper: false,
    hasSpeaker: false,
    hasMicrophone: false,
    hasIMU: true,
    hasGPS: false,
    hasOdometry: true,
    maxLinearVelocity: 0.5, // m/s
    maxAngularVelocity: 2.0, // rad/s
    batteryCapacity: 0, // unknown / external
    supportedModes: ['drive'],
  },

  dimensions: {
    length: 0.22, // meters
    width: 0.19, // meters
    height: 0.08, // meters
    weight: 2.0, // kg (approx)
    wheelbase: 0.16, // meters
  },

  topics: {
    // All BotBrain-routed topics live under the 'robotdog' ROS namespace
    velocity: 'robotdog/cmd_vel_joy',
    velocityNipple: 'robotdog/cmd_vel_nipple',
    temperature: 'robotdog/imu_temp',
    battery: 'robotdog/battery',
    laserScan: 'robotdog/scan',
    odometry: 'robotdog/odom',
    listener: 'robotdog/listener',
    map: 'robotdog/map',
    jointStates: 'robotdog/joint_states',
    camera: 'compressed_camera',           // camera node publishes globally
    sportModeState: 'lf/sportmodestate',
    robotStatus: 'robotdog/robot_status',
    thermal: '',
    rgb: '',
    goalPose: 'robotdog/goal_pose',
    cancelGoal: 'robotdog/cancel_goal',
    diagnostics: 'robotdog/diagnostic_stats',
  },

  services: {
    // Services are all under the 'robotdog' ROS namespace
    prompt: 'robotdog/rosa_prompt',
    antiCollision: 'robotdog/obstacle_avoidance',
    light: 'robotdog/light_control',
    stop: 'robotdog/emergency_stop',
    pose: 'robotdog/pose',
    mode: 'robotdog/mode',
    talk: 'robotdog/talk',
    delivery: 'robotdog/delivery_control',
  },

  rosNamespace: 'robotdog',

  defaultSettings: {
    linearSpeed: 0.3,
    angularSpeed: 0.5,
    cameraQuality: 'medium',
    diagnosticsEnabled: false,
  },

  customActions: [
    {
      id: 'stop',
      name: 'Emergency Stop',
      icon: 'OctagonX',
      service: 'stop',
      request: { stop: true },
    },
  ],

  // Hide all quadruped-specific actions — keep only emergency, light, antiCollision
  hiddenActions: [
    'getUp',
    'getDown',
    'balanceStand',
    'jointLock',
    'poseOn',
    'poseOff',
    'sit',
    'riseSit',
    'hello',
    'stopMove',
    'stretch',
    'dance',
    'damping',
    'zeroTorque',
    'prompt',
  ],
};
