#! /usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This script is run at boot to initialize the system clock and then wait for interrupts.
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
    import SC16IS750

    I2C_BUS = 1 # I2C bus identifier
    PIN_IRQ_WTC = 4 # Interrupt request pin. BCM pin 4, header pin 7
    I2C_ADDR_WTC = 0x4C # I2C addresses for WTC comm chips
    I2C_BAUD_WTC = 115200 # UART baudrates for WTC comm chips
    XTAL_FREQ = 1843200 # Crystal frequency for comm chips

    chip = SC16IS750.SC16IS750(I2C_ADDR_WTC, I2C_BUS, I2C_BAUD_WTC, XTAL_FREQ)

    # Reset chip and handle exception thrown by NACK
    try: chip.byte_write_verify(SC16IS750.REG_IOCONTROL, 0x01 << 3)
    except OSError: print("REG_IOCONTROL: %s 0x00" % (chip.byte_read(SC16IS750.REG_IOCONTROL) == 0x00))

    # Define UART with 8 databits, 1 stopbit, and no parity
    chip.write_LCR(SC16IS750.DATABITS_8, SC16IS750.STOPBITS_1, SC16IS750.PARITY_NONE)

    # Toggle divisor latch bit in LCR register and set appropriate DLH and DLL register values
    chip.define_register_set(special = True)
    chip.set_divisor_latch()
    chip.define_register_set(special = False)
    #print("REG_LCR:       %s 0x%02X" % chip.define_register_set(special = True))
    #print("REG_DLH/DLL:   %s 0x%04X" % chip.set_divisor_latch())
    #print("REG_LCR:       %s 0x%02X" % chip.define_register_set(special = False))

    # Enable RHR register interrupt
    chip.byte_write(SC16IS750.REG_IER, 0x01)

    # Reset TX and RX FIFOs and disable FIFOs
    chip.byte_write(SC16IS750.REG_FCR, 0x06)
    time.sleep(2.0/XTAL_FREQ)

    # Enable FIFOs
    chip.byte_write(SC16IS750.REG_FCR, 0x01)
    time.sleep(2.0/XTAL_FREQ)
    return chip

if __name__ == '__main__':
    #import qpaceInterpreter as qpI
    #import RPi.GPIO as gpio
    print("IMPORT RPi.GPIO and qpaceInterpreter BEFORE RUNNING")
    exit()
    import sys
    import datetime
    import ctypes
    import ctypes.util
    import time

    WTC_IRQ = 4 # BCM 4, board pin 7
    WHO_FILEPATH = "WHO"

    # Initialize the pins
    # gpio.setup(gpio.BCM)
    # gpio.setup(WTC_IRQ, gpio.IN) # WTC Interupt pin.


    try:
        # Read in only the first character from the WHO file to get the current identity.
        f = open(WHO_FILEPATH,'r')
        identity = f.read(1)
        f.close()

        chip = initWTCConnection()
    except OSError:
        #TODO  Alert WTC of problem, wait for new commands.
        pass # There was a problem getting the identity.
    else: # We have the identity. Request do everything else in this module.
        #TODO SEND THE IDENTITY TO WTC
        buf = b''
        while True: #Is expecting 6 bytes. (YEAR, MONTH, DAY, HOUR, MINUTE, SECOND)
            time.sleep(.5)
            waiting = chip.byte_read(SC16IS750.REG_RXLVL)
            if waiting >= 6 :
                for i in range(5):
                    buf += chip.byte_read(SC16IS750.REG_RHR)

        # (Year, Month, Day, Hour, Minute, Second, Millisecond)
        time_tuple = (2000 + ord(buf[0]), ord(buf[1]), ord(buf[2]), ord(buf[3]), ord(buf[4]), ord(buf[5]))
        # Change the system time on the pi.
        try:
            class timespec(ctypes.Structure):
                _fields_ = [("tv_sec", ctypes.c_long),
                            ("tv_nsec", ctypes.c_long)]

            librt = ctypes.CDLL(ctypes.util.find_library("rt"))

            ts = timespec()
            ts.tv_sec = int( time.mktime( datetime.datetime(*time_tuple).timetuple() ) )
            ts.tv_nsec = 0 # We don't care about nanoseconds

            # http://linux.die.net/man/3/clock_settime
            librt.clock_settime(0, ctypes.byref(ts))
        except:
            #TODO Alert WTC of problem, wait for new commands.
            pass # There was a problem setting the time

        qpI.run(chip)





