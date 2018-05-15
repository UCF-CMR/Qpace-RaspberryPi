#! /usr/bin/env python3
# qpacePicComm.py by Jonathan Kessluk & Minh Pham
# 4-10-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#

import RPi.GPIO as gpio
import time

gpio.setmode(gpio.BCM)
gpio.setup(17, gpio.IN)


#gpio.add_event_detect(17,gpio.RISING)
#gpio.add_event_callback(17,function_name_no_args)

while(gpio.input(17)):
