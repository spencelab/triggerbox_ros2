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
