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

Getting running on the lenovo box with trig5 arduino

1. Forgot to commit setup.cfg so it couldnt' find triggerbox_host executable... fixed.
2. Didn't have serial... did

```spencelab@ros2test:~/ros2_ws$ rosdep install --from-paths src -y --ignore-src
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
