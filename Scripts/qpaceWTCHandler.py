#!/usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This script is run at boot to initialize the system clock and then wait for interrupts.
from threading import *
import SC16IS750


SOCKET_PORT = 8675 #Jenny, who can I turn to?
ETHERNET_BUFFER = 2048
WHO_FILEPATH = 'WHO'
WTC_IRQ = 7 # BCM 4, board pin 7
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
    PIN_IRQ_WTC = 4 # Interrupt request pin. BCM pin 4, header pin 7
    I2C_ADDR_WTC = 0x48 # I2C addresses for WTC comm chips
    I2C_BAUD_WTC = 9600 # UART baudrates for WTC comm chips
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

#def _openSocketForSibling(chip = None):
    """
    This function acts as a server and arbitrator for the Ethernet connection.
    It will be spawned as it's own process.

    Parameters
    ----------
    chip - SC16IS750 - chip instance to use for communication with the WTC.

    Returns
    -------
    Nothing.

    Raises
    ------
    ConnectionError - if it cannot make a connection for some reason.
    BufferError - if the buffer to the WTC has an error.
    OSError - if there was a problem with file handling.
    """
    logger.logSystem([["Opening socket for ethernet."]])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Read in only the first character from the WHO file to get the current identity.
    try:
        logger.logSystem([["Attempting to determine Identity"]])
        with open(WHO_FILEPATH,'r') as f:
            identity = f.read(1)
        if identity == 1:
            host = "192.168.1.1"
        elif identity == 2:
            host = "192.168.1.2"
        else:
            raise ConnectionError("Could not connect to Sibling. Bad Identity: " + identity)
        logger.logSystem([["Host was set to an IP address.", host],["Binding the address to the socket..."]])
        server.bind((host, SOCKET_PORT))

        class QPClientHandler(Thread):
            def __init__(self, socket, addr):
                Thread.__init__(self)
                logger.logSystem([["Ethernet: Client is connceting..."]])
                self.socket = socket
                self.addr = addr
                self.start()

            def run(self):
                logger.logSystem([["Ethernet: Waiting for data..."]])
                while True:
                    try:
                        recvval = self.socket.recv(ETHERNET_BUFFER)
                        logger.logSystem([["Ethernet: Data received.",str(recvval)]])
                        if recvval:
                            recvval = recvval.split(b' ')

                            if recvval[0] == b'Hello?':
                                self.socket.send(b'Here!')

                            elif recvval[0] == b'PIPE':
                                self.socket.send(b'OK')
                                command = self.socket.recv(ETHERNET_BUFFER)
                                if qpI.isCommand(command) and chip:
                                    self.socket.send(b'working')
                                    qpI.processCommand(chip,command, fromWhom='Pipe (to Pi '+identity+')')
                                else:
                                    self.socket.send(b'not command')
                    except BrokenPipeError:
                        logger.logSystem([["Ethernet: Client Disconnected."]])
                        break
                    except (BufferError,ConnectionError) as err:
                        logger.logSystem([["Ethernet: An Error has occured.",str(err)]])
                        logger.logError("Ethernet: An Error has occured.", err)
                        raise err

        server.listen(2)
        #print ('server started and listening')
        while True:
            client, address = server.accept()
            QPClientHandler(client, address)
    except (OSError,ConnectionError,BufferError) as err:
        logger.logError("Ethernet: There was an error.", err)
        raise ConnectionError(str(err)) from err

if __name__ == '__main__':
    import sys
    import datetime
    import ctypes
    import ctypes.util
    import time
    #import socket
    import RPi.GPIO as gpio

    import qpaceInterpreter as qpI
    import qpaceLogger as logger
    import qpaceTODOParser as todo

    chip = None
    gpio.set_mode(gpio.BOARD)
    gpio.setup(WTC_IRQ, gpio.IN)
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
            # NOTE: Hold on the ethernet. Not needed for now.
            # Start ethernet stuff
            #ethernetHandler = Thread(name='socketHandler',target=_openSocketForSibling,args=(chip,))
            #ethernetHandler.start()

            logger.logSystem([["Beginning the main loop for the WTC Handler..."]])
            # Create a threading.Event to determine if an experiment is running or not.
            experimentRunningEvent = threading.Event()
            # This is the main loop for the Pi.
            while True:
                if gpio.input(WTC_IRQ):
                    logger.logSystem("Pin " + WTC_IRQ + " was found to be HIGH. Running the interpreter and then the TODO Parser.")

                    qpI.run(chip,experimentRunningEvent) # Run the interpreter to read in data from the CCDR.
                    todo.run(chip,experimentRunningEvent) # Run the todo parser
                    logger.logSystem("Listining to Pin " + WTC_IRQ + " and waiting for the interrupt signal.")
                else:
                    todo.run(chip,experimentRunningEvent) # Run the todo parser
                time.sleep(.5) # Sleep for a moment before checking the pin again.

        except BufferError as err:
            #TODO Alert the WTC of the problem and/or log it and move on
            #TODO figure out what we actually want to do.
            logger.logError("Something went wrong when reading the buffer of the WTC.", err)

        except ConnectionError as err:
            #TODO Alert the WTC of the problem and/or log it and move on
            #TODO figure out what we actually want to do.
            logger.logError("There is a problem with the connection to the WTC", err)

        gpio.cleanup()