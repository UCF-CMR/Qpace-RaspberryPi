#! /usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab QUIP packets and direct them to the packet directory, then decode them.

import time
import SC16IS750
import RPi.GPIO as gpio
from qpaceWTCHandler import initWTCConnection

INTERP_PACKETS_PATH = "packets/" #TODO determine actual path
INTERP_CMD_SIZE = 1 # How many characters will we expect to be the command length

# Add commands to the map. Format is "String to recognize for command" : function name
COMMAND_LIST = {

}

def _isCommand(query):
    return query[:INTERP_CMD_SIZE] in COMMAND_LIST

def _processCommand(query):
    cmd = query[:INTERP_CMD_SIZE] # Seperate the specific command
    args = query[INTERP_CMD_SIZE:] # Seperate the args
    COMMAND_LIST[cmd](args) # Run the command

def _processQUIP(buf):
    #TODO do we need to determine the opcode or can we force the packets to be sent in order?
    #TODO we will need to determine the opcode iff we use control packets.

    def isolateOpCode():
        pass

    if len(buf) > 0:
        # write the initial init packet
        with open(INTERP_PACKETS_PATH+"init.qp",'wb') as f:
            f.write(buf[:256])
        buf = buf[256:]

        counter = 0
        while len(buf) > 0:
            with open(INTERP_PACKETS_PATH+str(counter) + ".qp",'wb') as f: # we can just name them with the counter iff we don't determine the opcodes
                f.write(buf[:256])
            buf = buf[256:]
            counter += 1

def run(chip = None):
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
    All exceptions raised by this function are passed up the stack or ignored and not raised at all.
    """
    if chip is None:
        chip = initWTCConnection()

    # Initialize the pins
    gpio.set_mode(gpio.BCM)
    gpio.setup(PIN_IRQ_WTC, gpio.IN)

    print("Waiting for data. Hit Ctrl+C to abort.")
    buf = b''
    while True:
        try:
            if not gpio.input(PIN_IRQ_WTC):
                break

            time.sleep(1)
            waiting = chip.byte_read(SC16IS750.REG_RXLVL)
            if waiting > 0:
                for i in range(waiting):
                    buf += chip.byte_read(SC16IS750.REG_RHR)
                    #print(" 0x%02X" % char)
        except KeyboardInterrupt: # If we get a SIGINT, we can also break off.
            break
    if isCommand(buf):
        processCommand(buf)
    else
        processQUIP(buf)
    gpio.cleanup() #TODO do we actually want to cleanup?
