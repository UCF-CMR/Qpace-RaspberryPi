#!/usr/bin/env python3
# qpaceWTCHandler.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This script is run at boot to initialize the system clock and then wait for interrupts.
#TODO: Re-do comments/documentation

import qpaceLogger as logger
import qpaceExperiment as exp

exp.pinInit()

try:
    import specialTasks
    import os
    from time import strftime,gmtime
    os.rename('specialTasks.py','graveyard/specialTasks'+str(strftime("%Y%m%d-%H%M%S",gmtime()))+'.py')
except ImportError:
    pass
except OSError:
    logger.logSystem([["SpecialTasks: Was not able to run any special tasks."]])
    pass

import threading
import SC16IS750
import pigpio

gpio = pigpio.pi()
WHO_FILEPATH = '/home/pi/WHO'
WTC_IRQ = 12
def initWTCConnection():
    """
    This function Initializes and returns the SC16IS750 object to interact with the registers.

    Parameters
    ----------
    Nothing

    Returns
    -------
    "chip" - SC16IS750 - the chip data to be used for reading and writing to registers.

    Raises
    ------
    Any exceptions are passed up the call stack.
    """

    I2C_BUS = 1 # I2C bus identifier
    PIN_IRQ_WTC = None #TODO need to determine this pin # Interrupt request pin. BCM pin 4, header pin 7
    I2C_ADDR_WTC = 0x48 # I2C addresses for WTC comm chips
    I2C_BAUD_WTC = 115200 # UART baudrates for WTC comm chips
    XTAL_FREQ = 1843200 # Crystal frequency for comm chips
    DATA_BITS = SC16IS750.LCR_DATABITS_8
    STOP_BITS = SC16IS750.LCR_STOPBITS_1
    PARITY_BITS = SC16IS750.LCR_PARITY_NONE

    chip = SC16IS750.SC16IS750(gpio,I2C_BUS,I2C_ADDR_WTC, XTAL_FREQ, I2C_BAUD_WTC, DATA_BITS, STOP_BITS, PARITY_BITS)

    # Reset chip and handle exception thrown by NACK
    try: chip.byte_write_verify(SC16IS750.REG_IOCONTROL, 0x01 << 3)
    except OSError: print("REG_IOCONTROL: %s 0x00" % (chip.byte_read(SC16IS750.REG_IOCONTROL) == 0x00))

    # Reset TX and RX FIFOs
    fcr = SC16IS750.FCR_TX_FIFO_RESET | SC16IS750.FCR_RX_FIFO_RESET
    chip.byte_write(SC16IS750.REG_FCR, fcr)
    time.sleep(2.0/XTAL_FREQ)

    # Enable FIFOs and set RX FIFO trigger level
    fcr = SC16IS750.FCR_FIFO_ENABLE | SC16IS750.FCR_RX_TRIGGER_56_BYTES
    chip.byte_write(SC16IS750.REG_FCR, fcr)

    # Enable RX error and RX ready interrupts
    ier = SC16IS750.IER_RX_ERROR | SC16IS750.IER_RX_READY
    chip.byte_write_verify(SC16IS750.REG_IER, ier)

    return chip

if __name__ == '__main__':
    import sys
    import datetime
    import ctypes
    import ctypes.util
    import time

    import qpaceInterpreter as qpI
    import qpaceTODOParser as todo

    chip = None
    gpio.set_mode(WTC_IRQ, pigpio.INPUT)
    try:
        # Read in only the first character from the WHO file to get the current identity.
        with open(WHO_FILEPATH,'r') as f:
            identity = f.read(1)
    except OSError:
        identity = '0'
    chip = initWTCConnection()
    logger.logSystem([["Identity determined as Pi: " + str(identity)]])
    if chip:
        chip.byte_write(SC16IS750.REG_THR, ord(identity)) # Send the identity to the WTC
        # Change the clock to be the proper date time based on 1 int coming in that is time since epoch.

        #TODO old code to change the time. No longer needed as the method for changing time has changed.
        # buf = b''
        # while True: # Is expecting 6 bytes. (YEAR, MONTH, DAY, HOUR, MINUTE, SECOND)
        #     time.sleep(.5)
        #     waiting = chip.byte_read(SC16IS750.REG_RXLVL)
        #     if waiting >= 6 :
        #         for i in range(6):
        #             buf += bytes([chip.byte_read(SC16IS750.REG_RHR)])
        #         break
        #
        # logger.logSystem([["Time received from the WTC.",str(2000 + buf[0]), str(buf[1]), str(buf[2]), str(buf[3]), str(buf[4]), str(buf[5])]])
        # # (Year, Month, Day, Hour, Minute, Second)
        # time_tuple = (2000 + buf[0], buf[1], buf[2], buf[3], buf[4], buf[5])
        # # Change the system time on the pi.
        # try:
        #     class timespec(ctypes.Structure):
        #         _fields_ = [("tv_sec", ctypes.c_long),
        #                     ("tv_nsec", ctypes.c_long)]
        #
        #     librt = ctypes.CDLL(ctypes.util.find_library("rt"))
        #
        #     ts = timespec()
        #     ts.tv_sec = int(time.mktime(datetime.datetime(*time_tuple).timetuple()))
        #     ts.tv_nsec = 0 # We don't care about nanoseconds
        #
        #     # http://linux.die.net/man/3/clock_settime
        #     librt.clock_settime(0, ctypes.byref(ts))
        # except Exception as err:
        #     #TODO Alert WTC of problem, wait for new commands.
        #     logger.logError("Could not set the Pi's system time for some reason.",err)

        try:
            # Begin running the rest of the code for the Pi.
            logger.logSystem([["Beginning the main loop for the WTC Handler..."]])
            # Create a threading.Event to determine if an experiment is running or not.
            experimentRunningEvent = threading.Event()
            # This is the main loop for the Pi.
            while True:
                if gpio.read(WTC_IRQ):
                    logger.logSystem("Pin " + str(WTC_IRQ) + " was found to be HIGH. Running the interpreter and then the TODO Parser.")

                    qpI.run(chip,experimentRunningEvent) # Run the interpreter to read in data from the CCDR.
                    todo.run(chip,experimentRunningEvent) # Run the todo parser

                    logger.logSystem("Listining to Pin " + str(WTC_IRQ) + " and waiting for the interrupt signal.")
                else:
                    todo.run(chip,experimentRunningEvent) # Run the todo parser
                time.sleep(.4) # Sleep for a moment before checking the pin again.

        except BufferError as err:
            #TODO Alert the WTC of the problem and/or log it and move on
            #TODO figure out what we actually want to do.
            logger.logError("Something went wrong when reading the buffer of the WTC.", err)

        except ConnectionError as err:
            #TODO Alert the WTC of the problem and/or log it and move on
            #TODO figure out what we actually want to do.
            logger.logError("There is a problem with the connection to the WTC", err)

        gpio.cleanup()
