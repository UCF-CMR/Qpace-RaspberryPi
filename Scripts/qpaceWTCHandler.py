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
import qpaceInterpreter as qpi
import qpaceTODOParser as todo
import os
import threading
import tstSC16IS750 as SC16IS750
#import SC16IS750
import pigpio
import time

gpio = pigpio.pi()
CCDR_IRQ = 16 #BCM 16, board 36
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
	CCDR_IRQ = 16 #BCM 16, board 36
	I2C_ADDR_WTC = 0x4c#0x48 # I2C addresses for WTC comm chips
	I2C_BAUD_WTC = 115200 # UART baudrates for WTC comm chips
	XTAL_FREQ = 11059200#1843200 # Crystal frequency for comm chips
	DATA_BITS = SC16IS750.LCR_DATABITS_8
	STOP_BITS = SC16IS750.LCR_STOPBITS_1
	PARITY_BITS = SC16IS750.LCR_PARITY_NONE

	# init the chip
	chip = SC16IS750.SC16IS750(gpio,I2C_BUS,I2C_ADDR_WTC, XTAL_FREQ, I2C_BAUD_WTC, DATA_BITS, STOP_BITS, PARITY_BITS)
	chip.packetBuffer = []

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

def run():
	try:
		import specialTasks
		from time import strftime,gmtime
		os.rename('specialTasks.py','graveyard/specialTasks'+str(strftime("%Y%m%d-%H%M%S",gmtime()))+'.py')
	except ImportError:
		logger.logSystem([["SpecialTasks: No special tasks to run on boot..."]])
	except OSError:
		logger.logSystem([["SpecialTasks: Was not able to run special tasks or could not rename. (OSError)"]])
	import sys
	import datetime
	import time
	logger.logSystem([["Main: Initializing GPIO pins to default states"]])
	exp.reset()

	chip = initWTCConnection()
	if chip:
		#chip.byte_write(SC16IS750.REG_THR, ord(identity)) # Send the identity to the WTC
		#TODO Implement identity on the WTC
		try:
			# Begin running the rest of the code for the Pi.
			logger.logSystem([["Main: Starting..."]])
			# Create a threading.Event to determine if an experiment is running or not.
			# Or if we are doing something and should wait until it's done.
			experimentRunningEvent = threading.Event()
			runEvent = threading.Event()
			shutdownEvent = threading.Event()
			rebootEvent = threading.Event()
			# Ensure these are in the state we want them in.
			runEvent.set()
			experimentRunningEvent.clear()
			shutdownEvent.clear()
			rebootEvent.clear()

			interpreter = threading.Thread(target=qpi.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent,rebootEvent))
			todoParser = threading.Thread(target=todo.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent))

			logger.logSystem([["Main: Starting up the Interpreter and TodoParser."]])
			interpreter.start() # Run the Interpreter
			todoParser.start() # Run the TodoParser

			while True:
				try:
					time.sleep(.4)

					# If the scripts aren't running then we have two options
					if not (interpreter.isAlive() or todoParser.isAlive()):
						# If we want to shutdown, then break out of the loop and shutdown.
						if shutdownEvent.is_set():
							break
						else: # Otherwise, something must have happened....restart the Interpreter and TodoParser
							logger.logSystem([['Main: TodoParser and Interpreter are shutdown when they should not be. Restarting...']])
							interpreter = threading.Thread(target=qpi.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent,rebootEvent))
							todoParser = threading.Thread(target=todo.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent))
							interpreter.start()
							todoParser.start()
				except KeyboardInterrupt:
					shutdownEvent.set()

			logger.logSystem([["Main: The Interpreter and TodoParser have exited."]])
		except BufferError as err:
			#TODO Alert the WTC of the problem and/or log it and move on
			#TODO figure out what we actually want to do.
			logger.logError("Main: Something went wrong when reading the buffer of the WTC.", err)

		except ConnectionError as err:
			#TODO Alert the WTC of the problem and/or log it and move on
			#TODO figure out what we actually want to do.
			logger.logError("Main: There is a problem with the connection to the WTC", err)

		# If we've reached this point, just shutdown.
		logger.logSystem([["Main: Cleaning up and closing out..."]])
		gpio.stop()
		shutdownEvent.set()
		interpreter.join()
		todoParser.join()

		#TODO: Remove for final version.
		shutdownPrompt = input("Do you want to shutdown? Y/n:")
		#if True:
		if (shutdownPrompt == 'Y'):
			if rebootEvent.is_set():
				logger.logSystem([['Main: Rebooting RaspberryPi...']])
				os.system('sudo reboot') # reboot
			else:
				logger.logSystem([['Main: Shutting down RaspberryPi...']])
				os.system('sudo halt') # Shutdown.

if __name__ == '__main__':
	time.sleep(.5)
	run()
