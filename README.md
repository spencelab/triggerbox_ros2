# Porting to ROS2

## 20260520 Getting to work on fresh ubuntu 24 camdev in lab
1. clone this repo into ros2_ws/src
2. **NEED** to also clone triggerbox_ros2_interfaces
3. then colcon build will do both and you and try with `source install/setup.bash` then `ros2 run triggerbox_ros2 triggerbox_host`.
4. you will likely have errors due to no python serial library OR your user spencelab not having been added to dialout.
5. if former, try `sudo apt install python3-serial`
6. if latter, try `sudo adduser spencelab dialout` and then reboot.
7. This code expects and will exit with error if arduino does not have version 13 firmware. (assert in triggerbox_device.py).
8. I wrote a script in this repo to check if an arduino is flashed with triggerbox by asking for name and version using it's handshaking protocol. it's an executable. call with `./get_triggerbox_name_version` or `./get_triggerbox_name_version /dev/ttyACM0` etc. Gives:

```
spencelab@ros2test:~/ros2_ws/src/triggerbox_ros2/scripts$ ./get_triggerbox_name_version 
Phase 1: udev/name handshake at 9600
name raw: b'trig1\x00\x00\x00DB'
name: trig1
crc ok: True

Phase 2: triggerbox firmware version at 115200
attempt 1: no V packet yet
attempt 2: no V packet yet
attempt 3: no V packet yet
attempt 4: no V packet yet
attempt 5: no V packet yet
attempt 6: no V packet yet
attempt 7: no V packet yet
attempt 8: no V packet yet
attempt 9: no V packet yet
Got V packet on attempt 10
payload length: 7
payload hex: 0D 0A 00 00 00 38 0B
checksum: 5a
version decimal=13, hex=0xD
value=13, pulsenumber=10, ticks=2872
```
9. The firmware included in this triggerbox_ros2 repo is for version 13.
10. In order to flash an arduino with this firmware version from ubuntu 24, you can do the following.
    1. Download install arduino IDE 2.3.8 or newer from arduino, i used appimage, had to properties make executable and `sudo apt install fuse`.
    2. Download the arduino_udev_ros2 repo from spencelab.
    3. Copy the UDEV library from arduino_udev_ros2 into the arduino IDE area `cp -r ~/arduino_udev_ros2/firmware/UDEV ~/Arduino/libraries/`
    4. Restart the IDE, maybe you can build triggerbox.ino?
    5. Yes! It works. I flashed an ancient Arduino Nano from home. It came up as `/dev/ttyUSB0` and caused an ubuntu system error when the UDEV rule failed, but no biggy. Had to choose Processer -> AtMega328P (Old Bootloader) for it to flash, otherwise Arduino IDE fell back to programmger and said no response. Awesome.
    6. Then it will still crash as it reads out garbage from EEPROM as the name 0xFF, but version was correct with new `get_triggerbox...` script. So you just need to set a name with: `arduino-udev-name /dev/ttyUSB0 --set-name trig9 --verbose`. i got back `
RAW: 0x4E 0x3D 0x74 0x72 0x69 0x67 0x39 0x0 0x0 0x0 0x43 0x37 
SET NAME: trig9 (0x74 0x72 0x69 0x67 0x39)
`
    7. The you can ping it! with any script.

```
spencelab@ros2test:~/ros2_ws/src/triggerbox_ros2/scripts$ ./get_triggerbox_name_version /dev/ttyUSB0
Phase 1: udev/name handshake at 9600
name raw: b'trig9\x00\x00\x00C7'
name: trig9
crc ok: True

Phase 2: triggerbox firmware version at 115200
attempt 1: no V packet yet
attempt 2: no V packet yet
attempt 3: no V packet yet
attempt 4: no V packet yet
attempt 5: no V packet yet
attempt 6: no V packet yet
attempt 7: no V packet yet
attempt 8: no V packet yet
attempt 9: no V packet yet
attempt 10: no V packet yet
attempt 11: no V packet yet
Got V packet on attempt 12
payload length: 7
payload hex: 0D 0C 00 00 00 F5 14
checksum: 22
version decimal=13, hex=0xD
value=13, pulsenumber=12, ticks=5365
```
11. You can use triggerbox_host in ROS2 with this package if you identify the triggerbox /dev/ttyACM0 etc. just fine. If you want the fancy mapping to it's given name, so it reliably appears as `/dev/trig2` and you can disambiguate it from eg the treadmill, which is really useful, you need to use arduino_udev and do a few more setup steps. Those are:
## 20260519 Getting to work with cambuffer_recorder_ng

Using arduino from my dev box with red proto board shield on top with driver chip and switch and one bnc.

It is flaky. With switch in 5V position (towards USB in jack) switch needs jiggling for to work. Too much time in bags.

But it will work and trigger the ximea nicely at 100hz.

To start it and change frame rat:
```
ros2 run triggerbox_ros2 triggerbox_host
ros2 service call /triggerbox_host/set_framerate triggerbox_ros2_interfaces/srv/SetFramerate "{data: 25.0}"
```

Figured out with
```
ros2 service type /triggerbox_host/set_framerate
ros2 interface show triggerbox_ros2_interfaces/srv/SetFramerate
```

## 20260521 Pulse Blanking Version 14 Patch and Test Instructions:

https://chatgpt.com/g/g-p-6a03947397fc8191b3298417bda72197/c/6a0394fa-c8ec-83ea-a1c0-96703d8dfd53

Yep, this is the right repo now. I made a focused patch for output blanking while the triggerbox clock keeps running.

Download the triggerbox output-blanking patch

What this adds

Firmware now has:

E0 = disable/blank physical trigger output while Timer1 keeps running
E1 = enable physical trigger output from Timer1

It bumps firmware version from:

13 → 14

so you can confirm the flashed firmware is the new one.

ROS2 host now adds services:

/triggerbox_host/set_output_enabled   std_srvs/srv/SetBool
/triggerbox_host/enable_output        std_srvs/srv/Trigger
/triggerbox_host/disable_output       std_srvs/srv/Trigger
/triggerbox_host/start_clock          std_srvs/srv/Trigger
/triggerbox_host/stop_clock           std_srvs/srv/Trigger

It also publishes:

/triggerbox_host/output_enabled       std_msgs/msg/Bool

Default behavior is:

Timer1 clock runs at configured FPS.
Physical trigger output starts DISABLED.
Clock model can stabilize.
Cameras do not receive pulses until enable_output.

That is the safe rig behavior. Bench testing can opt into immediate pulses with:

ros2 run triggerbox_ros2 triggerbox_host --ros-args -p output_enabled_on_start:=true
Branch and apply
cd ~/ros2_ws/src/triggerbox_ros2

git status
git switch main
git pull origin main

git switch -c output-blanking-clock-run
unzip -o /path/to/triggerbox_ros2_output_blanking_patch.zip

Build:

cd ~/ros2_ws

colcon build --packages-select triggerbox_ros2 \
  --event-handlers console_direct+

source install/setup.bash
Flash firmware

Copy/install the updated firmware/triggerbox/triggerbox.ino to Arduino IDE or open it directly.

After flashing, your checker should report:

version decimal=14, hex=0xE
Test services

Start host:

ros2 run triggerbox_ros2 triggerbox_host

Confirm services:

ros2 service list | grep triggerbox_host
ros2 topic list | grep output_enabled

Check output state:

ros2 topic echo /triggerbox_host/output_enabled

Enable physical trigger pulses:

ros2 service call /triggerbox_host/enable_output std_srvs/srv/Trigger "{}"

Disable physical trigger pulses:

ros2 service call /triggerbox_host/disable_output std_srvs/srv/Trigger "{}"

Or set directly:

ros2 service call /triggerbox_host/set_output_enabled std_srvs/srv/SetBool "{data: true}"
ros2 service call /triggerbox_host/set_output_enabled std_srvs/srv/SetBool "{data: false}"

Clock controls, mostly for debugging:

ros2 service call /triggerbox_host/start_clock std_srvs/srv/Trigger "{}"
ros2 service call /triggerbox_host/stop_clock std_srvs/srv/Trigger "{}"
Intended rig sequence
1. Start triggerbox_host.
2. It sets FPS and starts Timer1 clock, but output is blanked.
3. Wait for clock model estimate.
4. Configure/start all camera recorders.
5. Call /triggerbox_host/enable_output.
6. Record.
7. Call /triggerbox_host/disable_output.
8. Stop camera recorders.
Notes

This patch does not require changes to triggerbox_ros2_interfaces; it uses standard ROS services from std_srvs.

The default “pulses off” behavior is safer for acquisition. The logs and /output_enabled topic should make it obvious why no pulses are present. Tiny guardrail, fewer accidental rat-cinema jump scares.

### Lots of fun profiling on hardware trigger.

Trying to get the thread rt priority:
```
spencelab@ros2test:~/ros2_ws$ sudo groupadd -f realtime
[sudo] password for spencelab: 
spencelab@ros2test:~/ros2_ws$ sudo usermod -aG realtime $USER
spencelab@ros2test:~/ros2_ws$ sudo tee /etc/security/limits.d/99-realtime.conf >/dev/null <<'EOF'
> @realtime   -   rtprio     80
@realtime   -   memlock    unlimited
@realtime   -   nice       -10
EOF
spencelab@ros2test:~/ros2_ws$ cat /etc/security/limits.d/99-realtime.conf 
@realtime   -   rtprio     80
@realtime   -   memlock    unlimited
@realtime   -   nice       -10
spencelab@ros2test:~/ros2_ws$ 
```

You need to reboot, but **THAT WORKS** and on reboot, running in terminal with no browser open, it dumps to disk with 16 frame ximea buffer and we had ZERO frame drops at the camera for 30 seconds or a minute or so. GREAT! And even cooler you can see the buffer working. camera triggers are on sync but a lag in disk writing follow by catching up!

<img width="3540" height="678" alt="image" src="https://github.com/user-attachments/assets/08c733a6-0f8d-4513-a9e2-6c6894db5a2a" />

See it should be around 10ms, it lags off to 47ms and then a series of 1ms writes catch up!

## Older work
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

## Getting running on the lenovo box with trig5 arduino

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

So i get now: (NOTES ABOUT THIS: I HAD HARDCODED NEW TOPIC NAMES WITH NO BASE. NOW Fixed below.).
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

### 2025-06-30 Re-up working!

Ok I tried to do this again and had some issues with make_ros_topic - it was trying to make a topci `~time_model` in old school ros1 and ros2 requires the slash `~/time_model`. So i deleted the bit in make_ros_topic in triggerbox_host i believe so it just always adds slash, and it works! In ubuntu 22 on the testing lenovo. i flashed a freqsh v=13 firmware triggerbox onto the vilros test plate that had a EMG board on it. works great. i get:

```
spencelab@ros2test:~/ros2_ws/src/triggerbox_ros2$ ros2 run triggerbox_ros2 triggerbox_host 
INFO:trigger.device:Waiting until serial device confirmed...
INFO:root.serial:connected to device named ''
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:checking firmware version
INFO:root.serial:connected to triggerbox firmware version 13
WARNING:root.serial:No clock measurements until framerate set.
[INFO] [1751303284.935785077] [triggerbox_host]: triggerbox_host: connected to 'v:13' on device '/dev/ttyACM0'
[INFO] [1751303284.937879748] [triggerbox_host]: triggerbox_host: setting FPS to 100.0
INFO:trigger.device:received set_triggerrate command with target of 100.0
[INFO] [1751303284.938357361] [triggerbox_host]: Got clock model
INFO:trigger.device:desired rate 100.0 (actual rate 100.0) using ICR1_AND_PRESCALER 0x9C4 64
[INFO] [1751303284.944930972] [triggerbox_host]: Got clock model
[INFO] [1751303284.945395432] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303285.447141439] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303285.949792132] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303286.452211598] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303286.954629185] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303287.456994117] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303287.959343659] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303288.460215038] [triggerbox_host]: triggerbox_host: waiting for clockmodel estimate
[INFO] [1751303288.897180485] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.89752418542193
[INFO] [1751303288.962573438] [triggerbox_host]: triggerbox_host: got clockmodel estimate
[INFO] [1751303289.910580327] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88166720912373
[INFO] [1751303290.922867025] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.89321736840478
[INFO] [1751303291.936306345] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88989040058513
[INFO] [1751303292.849422258] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.89887679263718
[INFO] [1751303293.863421914] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.89064213871087
[INFO] [1751303294.874911549] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88857880865557
[INFO] [1751303295.888662594] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.89177746523458
[INFO] [1751303296.902946154] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88764501523428
[INFO] [1751303297.917656235] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88722978585729
[INFO] [1751303298.931940264] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88824280233169
[INFO] [1751303299.946035008] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88938141739722
[INFO] [1751303300.960263708] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88931348767154
[INFO] [1751303301.972255338] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88918245366627
[INFO] [1751303302.985092249] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88966828749199
[INFO] [1751303303.998031260] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88779585205677
[INFO] [1751303305.010649616] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88689567203292
[INFO] [1751303306.024470742] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88701791387936
[INFO] [1751303307.040632250] [triggerbox_host]: Got clock model
DEBUG:trigger.device:approximate timer frequency: 99.88776427283234
```

Now examining the topics: in second terminal:

```
spencelab@ros2test:~$ ros2 topic list
/parameter_events
/rosout
/triggerbox_host/aout_confirm
/triggerbox_host/aout_raw
/triggerbox_host/aout_volts
/triggerbox_host/expected_framerate
/triggerbox_host/pause_and_reset
/triggerbox_host/raw_measurements
/triggerbox_host/set_triggerrate
/triggerbox_host/time_model
```

works! to see need . install:

```
spencelab@ros2test:~$ ros2 topic echo /triggerbox_host/time_model 
The message type 'triggerbox_ros2_interfaces/msg/TriggerClockModel' is invalid
spencelab@ros2test:~$ pwd
/home/spencelab
spencelab@ros2test:~$ cd ros2_ws/
spencelab@ros2test:~/ros2_ws$ . install/setup.
bash: install/setup.: No such file or directory
spencelab@ros2test:~/ros2_ws$ . install/setup.bash 
spencelab@ros2test:~/ros2_ws$ ros2 topic list
/parameter_events
/rosout
/triggerbox_host/aout_confirm
/triggerbox_host/aout_raw
/triggerbox_host/aout_volts
/triggerbox_host/expected_framerate
/triggerbox_host/pause_and_reset
/triggerbox_host/raw_measurements
/triggerbox_host/set_triggerrate
/triggerbox_host/time_model
spencelab@ros2test:~/ros2_ws$ ros2 topic echo /triggerbox_host/time_model 
gain: 0.010011299331848193
offset: 1751303552.5350645
---
gain: 0.010011296453507578
offset: 1751303552.5350807
---
gain: 0.010011285478196099
offset: 1751303552.5351677
---
gain: 0.01001133854431243
offset: 1751303552.534838
```

### 2025-06-27 Spence using to test and set up big grey triggerbox with 8 bncs and IR

See the Strawlab_triggerbox wiki page on aspence/spencelab wiki for details. Basically flashed the firmware, changed to trig2, which based on the merb launch file might match the box there, helping with direct swap. Also confirmed in the launch file we want to run a triggerbox_host.

Using the ubuntu 22 test lenovo box, was able to set it's name, and python3 triggerbox_device, but when i did

```
cd ros2_ws
. install/setup.bash
ros2 run triggerbox_ros2 triggerbox_host
```

I get an error about an invalid topic name becuase of a ~. But my notes above suggest I had it working. How? Where?

```
In ROS 2, a topic name starting with a tilde (~) signifies a private namespace. This means the topic name will be resolved relative to the node's name, essentially using the node's name as a namespace. For instance, if you have a node named my_node and you publish to a topic named ~topic, the actual topic name will be /my_node/topic. 
However, the ROS 2 documentation mentions a specific rule for topic names starting with a tilde: they must be separated from the rest of the name with a forward slash (/). So, the correct syntax is ~/foo and not ~foo. This rule is in place to prevent inconsistencies with how ~foo is interpreted in filesystem paths. 
Therefore, the error you are encountering with ros2 topic likely stems from using ~nodename instead of ~/nodename when specifying a private topic name. You need to include the forward slash after the tilde to indicate a private namespace.
In summary:
~ indicates a private namespace, according to Duckietown.
~/topic_name is the correct syntax for a private topic, according to ROS2 Design.
Without the forward slash (~), ROS 2 might interpret the tilde differently or throw an error due to the syntax rule. 
To fix the issue, ensure you are using the correct syntax ~/topic_name when referring to private topics within ros2 topic commands.
```

Well I dont want a private name space. And above I said it was publishing to /time_model. I think the problem is that we are trying to create a bunch of `~time_model` type topics and that's not allowed in ROS2. Was it in ROS1?

```
def _make_ros_topic(base, other):
    if base == '~':
        return base+other

    #ensure no start slash and one trailing slash
    if base[0] == '/':
        base = base[1:]
    if base[-1] == '/':
        base = base[:-1]

    return base + '/' + other
```

I think it should just be /triggerbox_host/time_model etc? Above i just had /time_model in the root space. What do I get in the normal working ROS1 space?

See here:
https://github.com/aspence/spencelab/wiki/Ubuntu-22-Jammy-ROS-2-Humble-Testing

Yeah on ROS1 we get /triggerbox_node/time_model etc:

how and why? base name gets set to triggerbox_node. launch file? Yep looks like it:

from a ros 1 launch file:

```
- <node machine="tmill4merb" name="triggerbox_node" pkg="triggerbox"
    type="triggerbox_host" args="--device /dev/trig2" />
```

Now is the ros1 triggerbox_host.py code differetn wrt base name? No... but initializing different.

Maybe ROS1 takes ~time_model and makes it /NODE_NAME/time_model

I FIXED ALL ABOVE SEE ABOVE. Just commented out the base combine thing without ~. It just worked.


## Trigger output blanking

Firmware version 14 adds a physical trigger-output gate. The Timer1 clock can
run and the host clock model can stabilize while the camera trigger pin is
blanked.

ROS 2 services exposed by `triggerbox_host`:

```bash
ros2 service call /triggerbox_host/set_output_enabled std_srvs/srv/SetBool "{data: false}"
ros2 service call /triggerbox_host/enable_output std_srvs/srv/Trigger "{}"
ros2 service call /triggerbox_host/disable_output std_srvs/srv/Trigger "{}"
ros2 service call /triggerbox_host/start_clock std_srvs/srv/Trigger "{}"
ros2 service call /triggerbox_host/stop_clock std_srvs/srv/Trigger "{}"
```

By default `triggerbox_host` starts with `output_enabled_on_start:=false`: the
timer runs at the configured frame rate and clock-model messages are generated,
but no physical trigger pulses are emitted until `enable_output` is called.
For bench testing, start with:

```bash
ros2 run triggerbox_ros2 triggerbox_host --ros-args -p output_enabled_on_start:=true
```
