#!/usr/bin/env python3
import sys
import argparse
import numpy as np
import time

# import roslib; roslib.load_manifest('triggerbox')
# ? ros2

#import rospy
import rclpy
from rclpy.node import Node

from triggerbox_ros2.api import TriggerboxAPI
from triggerbox_ros2_interfaces.msg import TriggerClockModel, AOutVolts, AOutRaw, AOutConfirm, \
     TriggerClockMeasurement
# Hmm wow the response is a function that gets defined by the ROS framework.
# Let's hope it's the same in ROS 2.
from triggerbox_ros2_interfaces.srv import SetFramerate
from triggerbox_ros2.triggerbox_device import TriggerboxDevice

import std_msgs.msg

def _make_ros_topic(base, other):
    if base == '~':
        return base+other

    #ensure no start slash and one trailing slash
    if base[0] == '/':
        base = base[1:]
    if base[-1] == '/':
        base = base[:-1]

    return base + '/' + other

class TriggerboxHost(TriggerboxDevice, TriggerboxAPI, Node):
    '''an in-process version of the triggerbox client with identical API
       porting to ROS2 - added Node as third multiple super, so prior code
       see first two supers first. Hopefully they dont mask any ROS2 node stuff.'''
    def __init__(self, device,ros_topic_base='~'):
        #Node.__init__('triggerbox_host')
        # if above doesn't work could try below; goal is to call parent Node init:
        super(TriggerboxAPI,self).__init__('triggerbox_host')
        
        self._gain = np.nan
        self._offset = np.nan
        self._expected_framerate = None

        self.pub_time = self.create_publisher(
                                TriggerClockModel,
                                _make_ros_topic(ros_topic_base,'time_model'),
                                10)
        # This quality of service roughly emulates latch=True from ROS1 happarently.
        # https://pypi.org/project/rosros/
        qos = rclpy.qos.QoSProfile(depth=2,
                 durability=rclpy.qos.DurabilityPolicy.TRANSIENT_LOCAL)
        self.pub_rate = self.create_publisher(
                                std_msgs.msg.Float32,
                                _make_ros_topic(ros_topic_base,'expected_framerate'),
                                qos)
        self.pub_raw = self.create_publisher(
                                TriggerClockMeasurement,
                                _make_ros_topic(ros_topic_base,'raw_measurements'),
                                10)
        self.pub_aout_confirm = self.create_publisher(
                                AOutConfirm,
                                _make_ros_topic(ros_topic_base,'aout_confirm'),
                                10)
        # hmm will this pass device to Node?
        # Ok TriggerboxDevice takes on input arg to __init__ which is device
        # TriggerboxAPI has no __init__ so this was supposed to his the dev.
        super(TriggerboxHost,self).__init__(device)

        self.set_trig_sub = self.create_subscription(
                std_msgs.msg.Float32,
                _make_ros_topic(ros_topic_base,'set_triggerrate'),
                self._on_set_triggerrate,
                10)
        self.pause_reset_sub = self.create_subscription(
                std_msgs.msg.Float32,
                _make_ros_topic(ros_topic_base,'pause_and_reset'),
                self._on_pause_and_reset,
                10)
        self.aout_volts_sub = self.create_subscription(
                AOutVolts,
                _make_ros_topic(ros_topic_base,'aout_volts'),
                self._on_aout_volts,
                10)
        self.aout_raw_sub = self.create_subscription(
                AOutRaw,
                _make_ros_topic(ros_topic_base,'aout_raw'),
                self._on_aout_raw,
                10)
        self.set_framerate_srv = self.create_service(
                SetFramerate,
                _make_ros_topic(ros_topic_base,'set_framerate'),
                self._on_set_framerate_service)

        # emit expected frame rate every 5 seconds
        self.timer = self.create_timer(5.0, self._on_emit_framerate)
        
        rclpy.logging.set_logger_level('/triggerbox_host',rclpy.logging.LoggingSeverity.DEBUG)

    def _on_set_triggerrate(self,_msg):
        self.get_logger().info('triggerbox_host: _on_set_triggerrate %s'%_msg.data)
        self.set_triggerrate(_msg.data)

    def _on_pause_and_reset(self,_msg):
        self.get_logger().info('triggerbox_host: _on_pause_and_reset %s'%_msg.data)
        self.pause_and_reset(_msg.data)

    def _on_aout_volts(self,_msg):
        self.get_logger().info('triggerbox_host: _on_aout_volts %s'%_msg)
        self.set_aout_ab_volts(_msg.aout0,_msg.aout1)

    def _on_aout_raw(self,_msg):
        self.get_logger().info('triggerbox_host: _on_aout_raw %s'%_msg)
        self.set_aout_ab_raw(_msg.aout0,_msg.aout1)

    def _on_set_framerate_service(self, request, response):
        self.set_frames_per_second_blocking(request.data)
        return response

    def _on_emit_framerate(self, _=None):
        if self._expected_framerate is not None:
            etr = std_msgs.msg.Float32()
            etr.data = self._expected_framerate
            self.pub_rate.publish(etr)

    #Callbacks from the underlying hardware
    def _notify_framerate(self, expected_trigger_rate):
        self._expected_framerate = expected_trigger_rate
        etr = std_msgs.msg.Float32()
        etr.data = expected_trigger_rate
        self.pub_rate.publish(etr)
        self._api_callback(self.framerate_callback, expected_trigger_rate)

    def _notify_clockmodel(self, gain, offset):
        self._gain = gain
        self._offset = offset
        model = TriggerClockModel()
        model.gain = gain
        model.offset = offset
        self.get_logger().info('Got clock model')
        self.pub_time.publish(model)
        self._api_callback(self.clockmodel_callback, gain, offset)

    def _notify_clock_measurement(self, start_timestamp, pulsenumber, fraction_n_of_255, stop_timestamp):
        if fraction_n_of_255 > 255:
            #occasionally, when changing framerates, and due to the async
            #and out-of-order nature of comms with the hardware, we gen a
            #fraction value that exceeds 255 here. Ignore it.
            #If a similar bogus value made it into the model, it will
            #eventually be filtered out anyway
            self.get_logger().error("triggerbox_host: invalid raw clock measurment. fraction %s exceeds 255" % fraction_n_of_255)
            return
        tcm=TriggerClockMeasurement()
        tcm.start_timestamp = start_timestamp
        tcm.pulsenumber = pulsenumber
        tcm.fraction_n_of_255 = fraction_n_of_255
        tcm.stop_timestamp = stop_timestamp
        self.pub_raw.publish(tcm)
        self._api_callback(self.clock_measurement_callback, start_timestamp, pulsenumber, fraction_n_of_255, stop_timestamp)

    def _notify_aout_confirm(self, pulsenumber, fraction_n_of_255, aout0, aout1):
        if fraction_n_of_255 > 255:
            #occasionally, when changing framerates, and due to the async
            #and out-of-order nature of comms with the hardware, we gen a
            #fraction value that exceeds 255 here. Ignore it.
            self.get_logger().errror("triggerbox_host: invalid raw clock measurment. fraction %s exceeds 255" % fraction_n_of_255)
            return

        self.pub_aout_confirm.publish(pulsenumber, fraction_n_of_255, aout0, aout1)

    def _notify_fatal_error(self, msg):
        self.get_logger().fatal(msg)
        # This might not be the right thing in ROS2 - may hang. Was rospy.signal_shutdown()....
        # Some web pages say raise SystemExit() and wrap the spin() in a try catch for it...
        rclpy.shutdown(msg)
        self._api_callback(self.fatal_error_callback, msg)

    def _notify_connected(self, name, device):
        self.get_logger().info("triggerbox_host: connected to %r on device %r" % (name, device))
        self._api_callback(self.connected_callback, name, device)

    #ClientAPI
    def have_estimate(self):
        return (not np.isnan(self._gain)) and (not np.isnan(self._offset))

    def wait_for_estimate(self):
        while not self.have_estimate():
            self.get_logger().info('triggerbox_host: waiting for clockmodel estimate')
            time.sleep(0.5)
        self.get_logger().info('triggerbox_host: got clockmodel estimate')

    def timestamp2framestamp(self, timestamp ):
        return (timestamp-self._offset)/self._gain

    def framestamp2timestamp(self, framestamp ):
        return framestamp*self._gain + self._offset

    def get_frames_per_second(self,wait_for_valid=True):
        while True:
            result = self._expected_framerate
            if result is not None:
                break
            if not wait_for_valid:
                break
            time.sleep(0.01)
        return result

    def set_frames_per_second(self,value):
        self.get_logger().info('triggerbox_host: setting FPS to %s' % value)
        self.set_triggerrate(value)

    def set_frames_per_second_blocking(self, *args, **kwargs):
        while not self.connected:
            self.get_logger().info('triggerbox_host: waiting for connection')
            time.sleep(0.5)
        self.set_frames_per_second(*args, **kwargs)

    def synchronize(self, pause_duration_seconds=2 ):
        self.get_logger().info('triggerbox_host: synchronizing')
        self.pause_and_reset(pause_duration_seconds)

# Need a main() function because we have to specify as the entry point
# in setup.py...
def main():
    # ros 1
    # rospy.init_node('triggerbox_host')
    # ros2
    rclpy.init(args=sys.argv)
    # node = rclpy.create_node('triggerbox_host') <- dont need it's super of tb
    # The bellow will initialize a node from it's superclass;
    tb = TriggerboxHost('/dev/ttyACM0')
    tb.set_frames_per_second_blocking(100.0)
    tb.wait_for_estimate()
    # ros 1
    # rospy.spin()
    # ros 2
    rclpy.spin(tb)
    tb.destroy_node() # apparently optional...
    rclpy.shutdown()
    
if __name__=='__main__':
    main()
    
