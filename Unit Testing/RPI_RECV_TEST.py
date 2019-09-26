import serial

ser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1.0)

while(True):
    data = ser.read(1)
    if data != b'':
        print("READ: ", data)      
        ser.write(b'H')
