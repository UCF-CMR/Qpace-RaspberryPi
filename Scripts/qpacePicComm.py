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

import threading
import serial
import serial.tools.list_ports
import time

PICCOMM_PACTOSEND = 15 # How many packets to send.
#BUFFER SIZE IS BASED ON DRIVER. 15 PACKETS FIT IN A 4095 BUFFER

def getRFPort(vid,pid):
    """
    Get the port that matches the VID and PID of what is defined (defined above)

    Exceptions
    -----------
    ConnectionError - If it can't find the RF deck
    """
    # produce a list of all serial ports
    ports = serial.tools.list_ports.comports()
    # loop over all ports until the vid and pid match the RFDeck
    for port in ports:
        if vid == port.vid and pid == port.pid:
            return port.device

    raise ConnectionError('RF deck not found. Please check the RF_VID and RF_PID values')

def sendQuipPacketsToUSB(connection,packetPath,cv=None,run_event=None):
    """
    Send the QUIP packets to the usb serial connection. Sends the number of packets defined PICCOMM_PACTOSEND.
    Note:
        - must make sure to put the packets in the path before envoking this method
        - this is meant to be in it's own thread or have a condition variable to envoke wait() and notify()
    Parameters
    ----------
    connection - Serial - the data returned by init() it's the serial connetion to be used to send packets
    packetPath - str - path to the packets that will be sent.
    cv - Condition - condition variable used for wait() and notify() to send all the packets.


    Exceptions
    ----------
    ValueError - If a condition object is not passed through.
    TypeError - If the path is not a string
    """
    if not isinstance(cv,threading.Condition) and not isinstance(run_event,threading.Event):
        raise ValueError("cv must be a threading.Condition() object and run_event must be a threading.Event() object. Make sure this method is envoked with thread.")
    else:
        if isinstance(packetPath,str) and packetPath[-1]=='/':
            regex = re.compile(r'\d+\.qp|init.qp|ctrl.qp')
            directoryPackets = [item for item in os.listdir(packetPath) if regex.match(item)]
            if directoryPackets:
                with cv:
                    while run_event.is_set() and len(directoryPackets) > 0:
                        # Ignore all exceptions when trying to write. We'll just keep trying to write until we can't.
                        try:
                            # wait for a .notify() from the main loop to start sending data.
                            cv.wait()
                            if connection and run_event.is_set():
                                data_to_write = b''
                                for packetToOpen in directoryPackets[-PICCOMM_PACTOSEND:]: #TODO figure out how many packets I can send!!!
                                    try:
                                        with open(packetPath+packetToOpen,'rb') as packet:
                                            data_to_write+=packet.read()
                                    except:
                                        print("Error reading packet:", packetToOpen)
                                        raise
                                try:
                                    connection.write(data_to_write)
                                    connection.flush()
                                except:
                                    print("Error writing to PIC.")
                                    raise
                                else:
                                    directoryPackets = directoryPackets[:-PICCOMM_PACTOSEND] #TODO figure out how many packets I can senddd
                                    cv.notify_all()
                        except:pass
        else:
            raise TypeError("The path for the Packets must be a string.")

def init(vid = None, pid = None):
    """
    Initialize the serial connection. Using the VID and PID we can get the port.

    Parameters
    ----------
    vid - int - VID of the device
    pid - int - PID of the device

    Returns
    -------
    Serial - the serial conncetion

    Exceptions
    -----------
    ValueError - if the pid and vid weren't set.
    """
    if not vid and not pid:
        raise ValueError("Must set the pid and vid")
    # configure the serial connections (the parameters differs on the device you are connecting to)
    try:
        connection = serial.Serial(
                                port= 'COM4',#getRFPort(vid,pid),            #COM4 FOR TESTING
                                baudrate=9600,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE,
                                bytesize=serial.EIGHTBITS
                                )
    except IOError: # if port is already opened, close it and open it again.
        print("Could not get serial Connection...exiting...")
        exit(1)
    return connection