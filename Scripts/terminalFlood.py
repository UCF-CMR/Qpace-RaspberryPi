# Dumps 128 Bytes of data to the terminal and nothing else
import pigpio
import time
import serial
import sys

#if len(sys.argv) < 3:
#  exit()

isSerial = False

try:
    serialData = serial.Serial('/dev/ttyAMA0', 115200)
    isSerial = True
except:
    pass
pi = pigpio.pi()


NUM_PACKETS = 1000 #int(sys.argv[1])
DELAY = 0.1 #float(sys.argv[2])

pi.write(20, 1)

while pi.read(20) != 1:
    print(pi.read(20))

def printData (data):

    if isSerial:
        serialData.write(data.encode('ASCII'))
    else:
        print(data)
        
time.sleep(1)
for packet in range(NUM_PACKETS):
    data = str(packet) + "A"*(128-len(str(packet)))
    printData(data)
    #serialData.write(data.encode('ASCII'))
    time.sleep(DELAY)

