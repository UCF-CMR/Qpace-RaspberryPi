#! /usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 3-27-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# The main python script for interfacing with the PIC simply and easily. Utilizes the modules
# created to facilitate creation, transfer, and the lifetime of data to the ground station.
import threading
import signal
import sys
import time
import qpaceQUIP as quip
import qpacePicComm as pic



def encodeFile(pathToFile,packetsPath):
    """
    Encode a file at pathToFile and store the packets in the directory of packetsPath

    Parameters
    ---------
    pathToFile - str - The path to the file. Must be a file, not directory.
    packetsPath - str - The path to the directory to store packets. Must be a directory, not file

    Exceptions
    ----------
    TypeError - When creating the encoder: if there paths are not strings or incorrect.
    """
    try:
        en = quip.Encoder(pathToFile,packetsPath)
        if en.run():
            print("SUCCESS")
        else:
            print("FAILURE")
    except TypeError as err:
        print(err)


def getComHandler(directoryOfPackets, serialInfo, cv, run_event):
    """
    Create and return a thread that will send the data to a serial connection (vid,pid)

    Parameters
    ----------
    directoryOfPackets - str - a string that is the directory for the packets
    serialInfo - tuple (int,int) - a tuple of the form (vid, pid) to get the port
    cv - threading.Condition - Condition variable to handle wait() and notify()
    run_event - threading.Event - Event variable to handle set() and clear() so the thread can be shutdown.

    Returns
    -------
    Thread - thread to send the data to the pic

    Exceptions
    ----------
    TypeError - If the data types of the parameters are not correct. OR somthing goes wrong
                when creating the thread or init of the port
    ValueError - If the inputs for VID or PID are not correct
    """
    try:
        if isinstance(run_event,threading.Event) and isinstance(serialInfo,tuple) and len(serialInfo) == 2 and isinstance(directoryOfPackets,str) and isinstance(cv,threading.Condition):
            connection = pic.init(vid=serialInfo[0],pid=serialInfo[1])
            return threading.Thread(name='PacketHandler', target=pic.sendQuipPacketsToUSB,args=(connection, directoryOfPackets,cv,run_event))
        else:
            raise TypeError("Path must be str, serialInfo must be tuple: (vid,pid), cv must be Condition, and run_event must be Event")
    except (TypeError,ValueError) as err:
        print(err)
        raise err
    except ConnectionError as err:
        print(err)



if __name__ == '__main__':
    if len(sys.argv) > 1:
        print('starting')
        packets = sys.argv[1]
        condition = threading.Condition()
        run_event = threading.Event()
        run_event.set()
        device = (0x04D8,0x000A)
        # Get the thread to run
        sendThread = getComHandler(packets, device, condition, run_event)

        # Set up some handlers
        def nextBlock(signal, frame):
            print("NOTIFY")
            with condition:
                condition.notify_all()
        def stopHandler(signal,frame):
            print('STOP')
            run_event.clear()
            with condition:
                condition.notify_all()

        signal.signal(signal.SIGTERM,nextBlock)
        signal.signal(signal.SIGINT,nextBlock)

        # Start the thread and wait for it to end.
        if sendThread is not None:
            sendThread.start()

            while sendThread.is_alive():
                time.sleep(1)



    else:
        print("Requires 1 argument: path to packets directory")



