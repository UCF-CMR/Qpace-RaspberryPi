#!/usr/bin/env python


import time
import serial


ser = serial.Serial(

   port='COM4',
   baudrate = 115200,
   parity=serial.PARITY_NONE,
   stopbits=serial.STOPBITS_ONE,
   bytesize=serial.EIGHTBITS
)


print('Waiting for new data...')
while True:
    time.sleep(1)
    if ser.inWaiting() > 0:
        x=ser.readline()
        print(x.decode('utf-8'))
