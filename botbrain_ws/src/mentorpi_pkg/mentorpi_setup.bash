#!/bin/bash
# mentorpi_setup.bash
# Sourced by robot_select.sh when robot_model == 'mentorpi'
# Sets up the ROS2 environment for the HiWonder MentorPi rover.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- Basic ROS2 / DDS setup ----
unset ROS_DOMAIN_ID
unset RMW_IMPLEMENTATION
unset CYCLONEDDS_URI

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://${SCRIPT_DIR}/../../cyclonedds_config.xml"

echo "✅  MentorPi environment loaded (RMW: $RMW_IMPLEMENTATION)"
