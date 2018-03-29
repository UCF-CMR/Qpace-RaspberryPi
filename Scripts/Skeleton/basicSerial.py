# import serial
#
#
#
# print serial.tools.list_ports.comports()
# # print [port for port in serial.tools.list_ports.comports() if port[2] != 'n/a']
#
# # with serial.Serial() as ser:
# #     ser.baudrate = 19200
# #     ser.port = 'COM11'
# #     ser.open()
# #     ser.write(b'hello')

import serial
import serial.tools.list_ports
import time

RF_VID = 0x04D8
RF_PID = 0x000A

def getRFPort():
    # produce a list of all serial ports
    ports = serial.tools.list_ports.comports()
    # loop over all ports until the vid and pid match the RFDeck
    for port in ports:
        print(port.pid) if  RF_VID == port.vid and RF_PID == port.pid:
            return port.device

    raise Exception('RF deck not found. Please check the RF_VID and RF_PID values')


PACKET_SIZE = 512

# configure the serial connections (the parameters differs on the device you are connecting to)
ser = serial.Serial(
    port= getRFPort(),
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
)

if(ser.isOpen() == True):
    print('------CONNECTED------')

    with open("5k.bin", "rb") as f:
        byte = f.read(PACKET_SIZE*100)
        while byte:
            # txt = byte #"Helloworld" #+ '\r\n'
            packet = byte
            # packet = bytearray()
            # packet.extend(map(ord, txt))

            ser.write(packet)

            out = ''
            # let's wait one second before reading output (let's give device time to answer)
            time.sleep(1)
            while ser.inWaiting() > 0:
                out += ser.read(1).decode('utf-8')

            if out != b'':
                print(">>" + out)

            byte = f.read(PACKET_SIZE*100)



# print("hello")
# print(getRFPort())
