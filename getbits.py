#!/usr/bin/env python3


import time
import serial

ser = serial.Serial(

        port='/dev/ttyS0',
        baudrate = 115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS
        )

print('Waiting for new data...')

while True:
    time.sleep(1)
    waiting = ser.inWaiting()
    print('\rThere are', waiting, 'bytes waiting to be read.')
    # if ser.inWaiting() > 0:
    #     x=ser.readline()