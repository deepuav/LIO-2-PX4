#! /usr/bin/env python3

"""
Node for relaying LIO pose from LIO-SAM to PX4
"""

import rospy
import copy
from mavros_msgs.msg import State
from nav_msgs.msg import Odometry

current_state = State()

# state_cb: Read fcu connection and store in global variable
def state_cb(msg: State):
    global current_state
    current_state = msg

# odometry_cb: Read LIO and store in global variable
def odometry_cb(msg: Odometry):
     global lio_msg
     lio_msg = msg

    

class OdometryRelay:
    def __init__(self):
        self.odom_pub = rospy.Publisher("mavros/odometry/out", Odometry, queue_size=5)

    def read_and_pub_lio(self, event=None):
            global lio_msg

            # Make an independent copy of the external odometry message
            px4_compliant_msg = copy.deepcopy(lio_msg)

            # The actual child frame of "odometry/imu" is called "odom_imu"
            # which does not appear in the tf_tree, nor follows ROS convention
            # (REP-105: https://www.ros.org/reps/rep-0105.html). After inspection in rviz,
            # it appears that the frame "odom_imu" is the same as "base_link".
            # "odom_imu" also shares parent frame with "base_link", that is, "odom".
            # Therefore, it should be safe to assume "odom_imu" is identical to
            # "base_link", and sending it to MAVROS odometry plugin for PX4 frame
            # transformation (FLU to FRD according to:
            # https://docs.px4.io/main/en/ros/external_position_estimation.html#reference-frames-and-ros).
            # However, there seems to be a 90 degree yaw offset in the PX4 internal 
            # local frame called "map", that requires an appropriate transform 
            # to external odometry messages. A solution that works, but is a bit hacky
            # is to set the PX4 parameter "SENS_BOARD_ROT" to "Yaw 90deg" to correct the 
            # PX4 parent frame, and then create a 90 degree yawed child frame here called
            # "base_link_px4" for sending and receiving odometry. See README for how to
            # set it up.
            px4_compliant_msg.child_frame_id = "base_link_px4"

            self.odom_pub.publish(px4_compliant_msg)
        

if __name__ == "__main__":
    rospy.init_node("lio_2_px4_node")

    # Wait for Flight Controller connection
    state_sub = rospy.Subscriber("mavros/state", State, callback = state_cb)
    rate = rospy.Rate(20)

    while(not rospy.is_shutdown() and not current_state.connected):
        rate.sleep()
    rospy.loginfo("Flight controller connected")
    
    # Unregister state sub when connected
    state_sub.unregister()

    # Subscribe to LIO-SAM odometry messages, and store msg in global variable "lio_msg"
    odom_sub = rospy.Subscriber("odometry/imu", Odometry, callback = odometry_cb)

    # Wait for LIO-SAM to start streaming
    while (not rospy.is_shutdown() and "lio_msg" not in globals()):
         rate.sleep()
    rospy.loginfo("Receiving LIO data")
    
    # Relay odometry messages at a suitable rate for PX4 (30-50Hz)
    odr = OdometryRelay()
    rospy.Timer(rospy.Duration(.02), odr.read_and_pub_lio)

    rospy.spin()

