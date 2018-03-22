#! /usr/bin/env python3
# qpacePicComm.py by Jonathan Kessluk
# 3-22-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Functions necessary to interact with the PIC and send information back and forth

#import signal
import os
import re

import serial
import serial.tools.list_ports
import time

PICCOMM_RF_VID = 0x04D8
PICCOMM_RF_PID = 0x000A
PICCOMM_PAK_SIZE = 512
PICCOMM_SER =  None

def getRFPort():
    # produce a list of all serial ports
    ports = serial.tools.list_ports.comports()
    # loop over all ports until the vid and pid match the RFDeck
    for port in ports:
        print(port.pid) if  PICCOMM_RF_VID == port.vid and PICCOMM_RF_PID == port.pid:
            return port.device

    raise Exception('RF deck not found. Please check the RF_VID and RF_PID values')

def sendAllPacketsToUSB(packetPath,cv=None):
    """
    must make sure to put the packets in the path before envoking this method
    this is meant to be in it's own thread
    """
    if cv is None:
        raise ValueError("a Condition() object must be passed through. Make sure this method is envoked with thread.")
    else:
        #signal.signal(PICCOMM_STOP, stop_handler)
        if isinstance(packetPath,str) and packetPath[-1]=='/':
            regex = re.compile(r'\d+\.qp|init.qp')
            directoryPackets = [item for item in os.listdir(packetPath) if regex.match(item)]
            if directoryPackets:
                with cv:
                    while True:
                        try:
                            # wait for a .notify() from the main loop to start sending data.
                            cv.wait()
                            if PICCOMM_SER.is_open():
                                data_to_write = b''
                                for packetToOpen in directoryPackets[-4:]: #TODO figure out how many packets I can send!!!
                                    try:
                                        with open(packetPath+packetToOpen,'rb') as packet:
                                            data_to_write+=packet.read()
                                    except OSError as err:
                                        print("Error reading packet:", packetToOpen)
                                        raise err
                                    else:
                                        try:
                                            PICCOMM_SER.write(data_to_write)
                                        except (IOError,OSError) as err:
                                            print("Error writing to PIC.")
                                            raise err
                                        else:
                                            directoryPackets = directoryPackets[:-4] #TODO figure out how many packets I can senddd
                            else:
                                try:
                                    PICCOMM_SER.open()
                                except IOError: pass
                        except:pass
        else:
            raise TypeError("packetPath must be a string.")

if __name__ != '__main__':
    # configure the serial connections (the parameters differs on the device you are connecting to)
    PICCOMM_SER = serial.Serial(
                                port= getRFPort(),
                                baudrate=9600,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE,
                                bytesize=serial.EIGHTBITS
                            )
    try:
        PICCOMM_SER.open()
    except IOError: # if port is already opened, close it and open it again.
            PICCOMM_SER.close()
            PICCOMM_SER.open()




