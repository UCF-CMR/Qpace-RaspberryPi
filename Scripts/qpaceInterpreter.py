#!/usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab incoming data from the WTC,
# Figure out if they are QUIP packets or commands. If it's a command it will execute the command
# and if they are QUIP packets it will direct them to the packet directory and then decode it.

import time
import SC16IS750
import RPi.GPIO as gpio
import datetime
from qpaceWTCHandler import initWTCConnection
from qpaceQUIP import Packet,Decoder
import qpacePiCommands as cmd
import qpaceLogger as logger

PACKET_SIZE = Packet.max_size

INTERP_PACKETS_PATH = "packets/"
INTERP_CMD_SIZE = 2 # How many characters will we expect to be the command length

# Add commands to the map. Format is "String to recognize for command" : function name
COMMAND_LIST = {
    "SD":cmd.immediateShutdown,       # Shutdown the Pi
    "RE":cmd.immediateReboot,         # Reboot the Pi
    "SF":cmd.sendFile,                # Initiate sending files to WTC from the pi filesystem
    "AP":cmd.asynchronousSendPackets, # Send specific packets from the Pi to the WTC
    "HI":cmd.pingPi,                  # Ping the pi!
    "ST":cmd.saveStatus,            # Accumulate status about the operation of the pi, assemble a txt file, and send it. (Invokes sendFile)
    "CS":cmd.checkSiblingPi,          # Check to see if the sibling Pi is alive. Similar to ping but instead it's through ethernet
    "PC":cmd.pipeCommandToSiblingPi,  # Take the args that are in the form of a command and pass it along to the sibling pi through ethernet
    "UC":cmd.performUARTCheck         # Tell the pi to perform a "reverse" ping to the WTC. Waits for a response from the WTC.
}

class LastCommand():
    """
    Small handler class to help with figuring out which command was the last command sent.
    Similar to just using a struct in C.
    """
    type = "No commands received"
    timestamp = "Never"
    fromWhom = "N/A"

def isCommand(query = None):
    """
    Checks to see if the query is a command as defined by the COMMAND_LIST

    Parameters
    ----------
    query - bytes - a query that could be or could not be a command.

    Returns
    -------
    True - If it is a command
    False - If it is not a command
    """
    if query:
        return query[:INTERP_CMD_SIZE].decode('utf-8') in COMMAND_LIST
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
            query = query.decode('utf-8')
        except UnicodeError:
            raise BufferError("Could not decode bytes to string for command query.")
        else:
            query = query.split(' ')
            logger.logSystem([["Command Received:",query[0],' '.join(query[1:])]])
            LastCommand.type = query[0]
            LastCommand.timestamp = str(datetime.datetime.now())
            LastCommand.fromWhom = fromWhom
            COMMAND_LIST[query[0]](chip,query[0],query[1:]) # Run the command

def processQUIP(chip = None,buf = None):
    #TODO do we need to determine the opcode or can we force the packets to be sent in order?
    #TODO we will need to determine the opcode iff we use control packets.
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



    logger.logSystem([["Processing input as QUIP packets.", "Packets Received: " + str(len(buf)/PACKET_SIZE)]])
    if len(buf) > 0:
        missedPackets = []
        # write the initial init packet
        try:
            with open(INTERP_PACKETS_PATH+"init.qp",'wb') as f:
                f.write(buf[:PACKET_SIZE])
        except:
            missedPackets.append('init')

        buf = buf[PACKET_SIZE:]
        attempt = 0

        def _getPacketID(packet):
            header = Decoder.decipherHeader(packet) #19 should be the size of the header of the packet.
            return header['pid']

        while len(buf) > 0:
            try:
                psuedo_packet = buf[:PACKET_SIZE]
                packetID = _getPacketID(psuedo_packet)
                with open(INTERP_PACKETS_PATH+packetID+ ".qp",'wb') as f:
                    f.write()
            except:
                attempt += 1
                if attempt > 1:
                    missedPackets.append(packetID)
                    buf = buf[PACKET_SIZE:]
            else:
                buf = buf[PACKET_SIZE:]
        logger.logSystem([["Attempted to write all packets to file system."],
                          ["Missing packets: ", str(missedPackets) if missedPackets else "None"]])
        return missedPackets

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
    ConnectionError - if the WTC cannot be connected to for some reason.
    BufferError - if the FIFO in the WTC cannot be read OR the buffer was empty.
    InterruptedError - if another InterruptedError was thrown.
    All other exceptions raised by this function are passed up the stack or ignored and not raised at all.
    """
    WTC_IRQ = 7
    TEMP_PACKET_LOCATION = 'temp/packets/'
    logger.logSystem([["Beginning the WTC Interpreter..."]])
    if chip is None:
        chip = initWTCConnection()
        if chip is None:
            raise ConnectionError("A connection could not be made to the CCDR.")
    # Initialize the pins
    gpio.set_mode(gpio.BOARD)
    gpio.setup(WTC_IRQ, gpio.IN)
    buf = b''
    while True:
        try:
            time.sleep(1)
            attempt = 0
            status = chip.byte_read(SC16IS750.REG_LSR) # Checks the status bit to see if there is something in the RHR
            if status & 0x01 == 1: # If LSB of LSR is high, then data available in RHR:
                # See how much we want to read.
                waiting = chip.byte_read(SC16IS750.REG_RXLVL)
                if waiting > 0:
                    logger.logSystem([["Reading in "+ str(waiting) +" bytes from the CCDR"]])
                    for i in range(waiting):
                        # Read from the chip and write to the buffer.
                        buf += bytes([chip.byte_read(SC16IS750.REG_RHR)])
            # If MSB of LSR is high, then FIFO data error detected:
            elif status & 0x80 == 1:
                if attempt > 1:
                    logger.logError("Something is wrong with the CCDR FIFO and it cannot be read.")
                    try:
                        logger.logSystem([["Attempted to read from the CCDR FIFO but somethign went wrong.","Current contents of the buffer:",buf.decode('utf-8')]])
                    except UnicodeError:
                        BufferError("The FIFO could not be read on the CCDR.")
                else:
                    logger.logError("Something is wrong with the CCDR FIFO. Will try to read again: Attempt " + str(attempt + 1))
                    attempt += 1
            else:
                # If the Interrupt Request pin is Logical Low then break. We don't want to read anymore.
                if not gpio.input(WTC_IRQ):
                    raise InterruptedError("The WTC has ended transmission.")

        except KeyboardInterrupt as interrupt: # If we get a SIGINT, we can also break off.
            logger.logSystem([["SIGINT was thrown to the Interpreter, stopping read from WTC."]])
            logger.logError("Caution: KeyboardInterrupt was thrown to the Interpreter.",interrupt)
            break
        except InterruptedError as interrupt: # IF we are interrupted, break.
            logger.logSystem([["The read has been interrupted."],[str(interrupt)]])
            raise interrupt
        except BufferError as err:
            logger.logError("A buffer error was thrown.",err)
            raise err
    try:
        if isCommand(buf): # Is the input to the buffer a command?
            if not runningEvent.is_set():
                processCommand(chip,buf,fromWhom='WTC')
            else:
                pass #TODO what should we actually do if we have an experiment running but we also get a command?
        else:
            missingPackets = processQUIP(chip,buf) # IF it's not a command, assume it's QUIP data.
            #TODO how to handle any packets that weren't interpreted correctly?
            decoder = Decoder(file_location,TEMP_PACKET_LOCATION,suppress=True,rush=True)
            decoder.run(True)
    except (BufferError,ConnectionError) as err:
        logger.logError("An error was thrown while trying to interpret the incoming data.", err)
        raise err
    except InterruptedError as interrupt:
        logger.logSystem([["The Interpreter was interrupted...", str(interrupt)]])
        raise interrupt
