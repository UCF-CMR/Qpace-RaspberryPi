#!/usr/bin/env python3
# qpaceInterpreter.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab incoming data from the WTC,
# Figure out if they are QUIP packets or commands. If it's a command it will execute the command
# and if they are QUIP packets it will direct them to the packet directory and then decode it.
#TODO: Re-do comments/documentation

import time
import SC16IS750
import pigpio
import datetime
from qpaceWTCHandler import initWTCConnection
from qpaceQUIP import Packet,Decoder
import qpacePiCommands as cmd
import qpaceLogger as logger

INTERP_PACKETS_PATH = "temp/packets/"
INTERP_CMD_SIZE = 2 # How many characters will we expect to be the command length

# Add commands to the map. Format is "String to recognize for command" : function name
COMMANDS = {
    "SD":cmd.immediateShutdown,       # Shutdown the Pi
    "RE":cmd.immediateReboot,         # Reboot the Pi
    "SF":cmd.sendFile,                # Initiate sending files to WTC from the pi filesystem
    "AP":cmd.asynchronousSendPackets, # Send specific packets from the Pi to the WTC
    "HI":cmd.pingPi,                  # Ping the pi!
    "ST":cmd.saveStatus,              # Accumulate status about the operation of the pi, assemble a txt file, and send it. (Invokes sendFile)
    #"CS":cmd.checkSiblingPi,         # Check to see if the sibling Pi is alive. Similar to ping but instead it's through ethernet
    #"PC":cmd.pipeCommandToSiblingPi, # Take the args that are in the form of a command and pass it along to the sibling pi through ethernet
    #"UC":cmd.performUARTCheck        # Tell the pi to perform a "reverse" ping to the WTC. Waits for a response from the WTC.
}

XTEACOMMANDS = {

}

class LastCommand():
    """
    Small handler class to help with figuring out which command was the last command sent.
    Similar to just using a struct in C.
    """
    type = "No commands received"
    timestamp = "Never"
    fromWhom = "N/A"

def sendBytesToCCDR(chip,sendData):
    """
    Send a string or bytes to the WTC. This method, by default, is dumb. It will pass whatever
    is the input and passes it directly on to the WTC.

    Parameters
    ----------
    chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
    sendData - a string or bytes that we want to send to the WTC

    Raises
    ------
    TypeError - thrown if sendData is not a string or bytes
    """
    if isinstance(sendData,str):
        sendData = sendData.encode('ascii')
    elif not isinstance(sendData,bytes) and not isinstance(sendData,bytearray):
        logger.logSystem([['Data will not be sent to the WTC: not string or bytes.']])
        raise TypeError("Data to the WTC must be in the form of bytes or string")
    try:
        logger.logSystem([['Sending to the WTC:', str(sendData)]])
        for byte in sendData:
            chip.block_write(SC16IS750.REG_THR, sendData)
    except Exception as err:
        #TODO do we actually handle the case where it just doesn't work?
        logger.logError('sendBytesToCCDR: An error has occured when attempting to send data to the WTC. Data to send:' + str(sendData),err)
        pass

def readDataFromCCDR(chip):
    buf = b''
    time_to_wait = 5#s
    time_to_sleep = .4#s
    numOfAttempts = (time_to_wait//time_to_sleep) + 1
    waiting = chip.byte_read(SC16IS750.REG_RXLVL)
    if waiting == 1:
        pass #TODO: Implement handshake stuff
    else: #We'll assume if it's not 1 byte, that it's going to be a 128 byte packet.
        for i in range(0,4): #We will receive 4, 32 byte chunks to make a 128 packet
            attempt = 0
            while True:
                try:
                    sleep(time_to_sleep)
                    attempt += 1
                    # See how much we want to read.

                    if waiting == 32:   # If we have 32 bytes in the level register
                        logger.logSystem([["Reading in "+ str(waiting) +" bytes from the CCDR"]])
                        for i in range(waiting):
                            # Read from the chip and write to the buffer.
                            buf += bytes([chip.byte_read(SC16IS750.REG_RHR)])

                        #TODO Acknowledge to WTC?

                    if attempt == numOfAttempts:
                        raise BlockingIOError("Timeout has occurred...")


                except BlockingIOError:
                    # TODO Write the start over methods.
                    # TODO Alert WTC?
                    # TODO log it!
                except BufferError as err:
                    logger.logError("A BufferError was thrown.",err)
                    raise BufferError("A BufferError was thrown.") from err

    return buf

def readBlockFromCCDR(chip):
    pass

def isCommand(query = None):
    """
    Checks to see if the query is a command as defined by the COMMANDS

    Parameters
    ----------
    query - bytes - a query that could be or could not be a command.

    Returns
    -------
    True - If it is a command
    False - If it is not a command
    """
    #TODO:
    #   Check if the command exists.
    #   If it doesnt, decode it from XTEA and THEN check if it exists
    #   If it does, do it.
    #   If it doesn't exist then return false
    # I.e. First check COMMANDS, then check XTEACOMMANDS, then return false otherwise true
    if query:
        return query[:INTERP_CMD_SIZE].decode('ascii') in COMMANDS
    else:
        return False

def processCommand(chip = None, query = None, fromWhom = 'WTC'):
    """
    Split the command from the arguments and then run the command as expected.

    Parameters
    ----------
    chip - SC16IS750() - an SC16IS750 object to read/write from/to
    query- bytes - the command string.
    fromWhom - string - a string to denote who sent the command. If fromWhom is not provided, assume the WTC.

    Raises
    ------
    ConnectionError - If a connection to the WTC was not passed to the command
    BufferError - Could not decode bytes to string for command query.
    """

    if not chip:
        raise ConnectionError("Connection to the WTC not established.")
    if query:
        try:
            query = query.decode('ascii')
        except UnicodeError:
            raise BufferError("Could not decode bytes to string for command query.")
        else:
            query = query.split(' ')
            logger.logSystem([["Command Received:",query[0],' '.join(query[1:])]])
            LastCommand.type = query[0]
            LastCommand.timestamp = str(datetime.datetime.now())
            LastCommand.fromWhom = fromWhom
            COMMANDS[query[0]](chip,query[0],query[1:]) # Run the command

#TODO FIX QUIP, possibly remove.
def processQUIP(chip = None,buf = None):
    """
    Take the data in the buffer and write files to it. We will assume they are QUIP packets.

    Paramters
    ---------
    chip - SC16IS750() - an SC16IS750 object to read/write from/to
    buf - bytes - the input buffer from the WTC

    Returns
    -------
    missedPackets - List - a list of missing packets.

    Raises
    ------
    BufferError - If the buffer is empty, assume that there was a problem.
    ConnectionError - If the connection to the WTC was not passed to this method.
    """
    if not chip:
        raise ConnectionError("Connection to the CCDR not established.")
    if not buf:
        raise BufferError("Buffer is empty, no QUIP data received.")

    logger.logSystem([["Processing input as QUIP packets.", "Packets Received: " + str(len(buf))]])
    if len(buf) > 0:
        missedPackets = []
        attempt = 0

        def _writePacketToFile(packetID,dataToWrite):
            with open(INTERP_PACKETS_PATH+str(packetID)+ ".qp",'wb') as f:
                f.write(b'D'+dataToWrite)

        for i in range(0,len(buf))
            try:
                # Create an int from the 4 bytes
                packetID = struct.unpack('>I',buf[i][:Packet.header_size])[0]
            except:
                misedPackets.append(str(i))
            else:
                try:
                    # Write that packet
                    _writePacketToFile(packetID,buf[i])
                except:
                    # If we failed, try again
                    try:
                        _writePacketToFile(packetID,buf[i])
                    except:
                        #If we failed, consider the packet lost and then carry on.
                        missedPackets.append(str(packetID))
        logger.logSystem([["Attempted to write all packets to file system."],
                          ["Missing packets: ", str(missedPackets) if missedPackets else "None"]])
        return missedPackets
    else:
        return []

def run(chip = None,runningEvent = None):
    """
    This function is the "main" purpose of this module. Placed into a function so that it can be called in another module.

    Parameters
    ----------
    Nothing

    Returns
    -------
    Nothing

    Raises
    ------
    ConnectionError - if the CCDR cannot be connected to for some reason.
    BufferError - if the FIFO in the WTC cannot be read OR the buffer was empty.
    InterruptedError - if another InterruptedError was thrown.
    All other exceptions raised by this function are passed up the stack or ignored and not raised at all.
    """
    CCDR_IRQ = 12
    TEMP_PACKET_LOCATION = 'temp/packets/'
    logger.logSystem([["Beginning the WTC Interpreter..."]])
    if chip is None:
        chip = initWTCConnection()
        if chip is None:
            raise ConnectionError("A connection could not be made to the CCDR.")

    # Initialize the pins
    gpio = pigpio.pi()
    gpio.set_mode(CCDR_IRQ, pigpio.INPUT)
    # The callback method for handling commands that come in.
    packetBuffer = []

    def WTCRXBufferHandler(gpio,level,tick):
        packetData = readPacketFromCCDR()
        if isCommand(packetData): # Is the input to the buffer a command?
            # Process the command
            # NOTE: This will execute and process the command regardless of experiments running.
            processCommand(chip,packetData,fromWhom='CCDR')
        else:
            packetBuffer.append(packetData)

    callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)

    try:
        while True:
            time.sleep(.1) # wait for a moment

            while len(packetBuffer) > 0:
                packetData = packetBuffer.pop(0)
                missingPackets = processQUIP(chip,buf)
                #TODO how to handle any packets that weren't interpreted correctly?
                decoder = Decoder(file_location,TEMP_PACKET_LOCATION,suppress=True,rush=True)
                decoder.run(True)

    except KeyboardInterrupt: break

    callback.cancel()
    chip.close()
    gpio.stop()