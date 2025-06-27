### Porting to ROS2

1. Just get triggerbox_device.py to work in Python3
2. On Spence mac...
3. pip3 install ... no it says use brew... brew... tricky... so

```
conda create -f triggerbox_ros2
conda activate triggerbox_ros2
conda install pyserial numpy
python3 triggerbox_device.py /dev/tty.usbmodem1101 
```

Made Queue queue for python3...
exceptions parentheses...

4. Copied arduinoudev.py from our forked repo into '/Users/aspence/miniconda3-arm64/envs/triggerbox_ros2/lib/python3.12/site-packages/arduinoudev.py' because lazy. It has a setup.py... you could probably conda install from setup.py the package and it would put there for you...
5. It runs! Fixing all the Queue to queue...
6. 

# Getting running on the lenovo box with trig5 arduino

1. Forgot to commit setup.cfg so it couldnt' find triggerbox_host executable... fixed.
2. Didn't have serial... did

```
spencelab@ros2test:~/ros2_ws$ rosdep install --from-paths src -y --ignore-src
executing command [sudo -H apt-get install -y python3-serial]
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
Suggested packages:
  python3-wxgtk3.0 | python3-wxgtk
The following NEW packages will be installed:
  python3-serial
0 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.
Need to get 78.7 kB of archives.
After this operation, 470 kB of additional disk space will be used.
Get:1 http://us.archive.ubuntu.com/ubuntu jammy/main amd64 python3-serial all 3.5-1 [78.7 kB]
Fetched 78.7 kB in 0s (268 kB/s)          
Selecting previously unselected package python3-serial.
(Reading database ... 294264 files and directories currently installed.)
Preparing to unpack .../python3-serial_3.5-1_all.deb ...
Unpacking python3-serial (3.5-1) ...
Setting up python3-serial (3.5-1) ...
#All required rosdeps installed successfully
```
### Access to serial port
Gah close need to do that dialout group user add jawn probably

```
serial.serialutil.SerialException: [Errno 13] could not open port /dev/ttyACM0: [Errno 13] Permission denied: '/dev/ttyACM0'
Traceback (most recent call last):
```
Fixed!

Find your groups `groups spencelab`

Does not include dialout.

`sudo adduser spencelab dialout`

**REBOOT** the machine! Logging in and out is not enough!

New error...

### It's running!

But I think my topics are missing the node name in front etc. ALSO must always remember to `. install/setup.bash`!

So i get now:
```
spencelab@ros2test:~/ros2_ws$ . install/setup.bash 
spencelab@ros2test:~/ros2_ws$ ros2 topic list
/aout_confirm
/aout_raw
/aout_volts
/expected_framerate
/parameter_events
/pause_and_reset
/raw_measurements
/rosout
/set_triggerrate
/time_model
spencelab@ros2test:~/ros2_ws$ ros2 topic list -t
/aout_confirm [triggerbox_ros2_interfaces/msg/AOutConfirm]
/aout_raw [triggerbox_ros2_interfaces/msg/AOutRaw]
/aout_volts [triggerbox_ros2_interfaces/msg/AOutVolts]
/expected_framerate [std_msgs/msg/Float32]
/parameter_events [rcl_interfaces/msg/ParameterEvent]
/pause_and_reset [std_msgs/msg/Float32]
/raw_measurements [triggerbox_ros2_interfaces/msg/TriggerClockMeasurement]
/rosout [rcl_interfaces/msg/Log]
/set_triggerrate [std_msgs/msg/Float32]
/time_model [triggerbox_ros2_interfaces/msg/TriggerClockModel]
spencelab@ros2test:~/ros2_ws$ ros2 topic echo /raw_measurements 
start_timestamp: 1712791137.2870135
pulsenumber: 10550
fraction_n_of_255: 110
stop_timestamp: 1712791137.2923086
---
start_timestamp: 1712791138.2945035
pulsenumber: 10650
fraction_n_of_255: 18
stop_timestamp: 1712791138.2998571
---
start_timestamp: 1712791139.3024065
pulsenumber: 10751
fraction_n_of_255: 191
stop_timestamp: 1712791139.3076122
---
start_timestamp: 1712791140.3100817
pulsenumber: 10852
fraction_n_of_255: 103
stop_timestamp: 1712791140.3148384
---
start_timestamp: 1712791141.318424
pulsenumber: 10953
fraction_n_of_255: 33
stop_timestamp: 1712791141.3223727
---
^Cspencelab@ros2test:~/ros2_ws$ ros2 topic echo /time_model
gain: 0.010010829431015212
offset: 1712791031.6713433
---
gain: 0.010010877060864001
offset: 1712791031.671114
---
gain: 0.01001086394535979
offset: 1712791031.6712198
---
gain: 0.010010850077359702
offset: 1712791031.6713362
---

```

But this page makes me think I should have node names before topics etc. (https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Understanding-ROS2-Topics/Understanding-ROS2-Topics.html#rqt-graph)

YES! For rqt to see your custom message types and thus display them in the topic monitor you must do `. install/setup.bash` before `rqt` then it works.

It's publishing to /time_model
