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

import time
import qpaceStates as states

try:
	import pigpio
	gpio = pigpio.pi()
except:
	gpio = None
CCDR_IRQ = 16 #BCM 16, board 36
REBOOT_ON_EXIT = False
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

class NextQueue():
	# MAX = 10
	WAIT_TIME = 25 #in seconds
	requestQueue = []
	responseQueue = []
	requestCount = 0
	cv = threading.Condition()

	@staticmethod
	def isEmpty():
		return len(NextQueue.requestQueue) == 0

	# @staticmethod
	# def NextQueue.isFull():
	# 	return len(queue) == NextQueue.MAX

	@staticmethod
	def enqueue(item):
		if NextQueue.isEmpty():
			NextQueue.cv.acquire() # If we are putting something in for the first time, set up the Lock
		logger.logSystem([["NextQueue: Adding '{}' to the queue.".format(item)]])
		try:
			item = states.QPCOMMAND[item]
		except KeyError:
			item = states.QPCOMMAND['NOOP']
		NextQueue.requestQueue.append(item)
		NextQueue.requestCount += 1

	@staticmethod
	def peek():
		if NextQueue.isEmpty():
			return states.QPCOMMAND['IDLE']

		else:
			return NextQueue.requestQueue[0]

	@staticmethod
	def dequeue():
		if NextQueue.isEmpty():
			return states.QPCOMMAND['IDLE']
		else:
			next =  NextQueue.requestQueue.pop(0)
			logger.logSystem([["NextQueue: Removed item from queue: '{}'".format(next)]])
			if NextQueue.isEmpty():
				try:
					NextQueue.cv.release() # If there is nothing in the queue, release the lock.
				except RuntimeError:
					pass # If it's already released for some reason, ignore it.
			return next

	@staticmethod
	def addResponse(response):
		NextQueue.responseQueue.append(response)

	@staticmethod
	def clearResponse(n=None):
		if n:
			for i in range(n):
				NextQueue.responseQueue.pop()
		else:
			NextQueue.responseQueue.clear()

	@staticmethod
	def waitAndReturn(popN=1,timeout=None):
		# This method waits until the queue is empty, and returns the result values of the queue.
		# Before returning, this method will pop the queue one time unless specified and return
		# Those values. Those values will be removed from the responseQueue
		#
		# Do not use this method in interpreter.run() as that will get us stuck in an infinite loop
		try:
			# Wait until the queue is empty.
			while not NextQueue.isEmpty():
				if not cv.wait(timeout or NextQueue.WAIT_TIME):
					# After the wait time, let's just continue going. Something held up.
					return None
			# pop the number of resposes we want off the back and then return them.
			response = NextQueue.responseQueue[-popN:]
			NextQueue.responseQueue = NextQueue.responseQueue[:-popN]
			return response
		except RuntimeError:
			return None # The lock was not aquired for some reason.

def run():
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
			# Ensure these are in the state we want them in.
			runEvent.set()
			experimentRunningEvent.clear()
			shutdownEvent.clear()

			interpreter = threading.Thread(target=qpi.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent))
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
							interpreter = threading.Thread(target=qpi.run,args=(chip,experimentRunningEvent,runEvent,shutdownEvent))
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
		if gpio:
			gpio.stop()
		shutdownEvent.set()
		interpreter.join()
		todoParser.join()


		if False: #TODO: Change to True for release
			if REBOOT_ON_EXIT:
				logger.logSystem([['Main: Rebooting RaspberryPi...']])
				os.system('sudo reboot') # reboot
			else:
				logger.logSystem([['Main: Shutting down RaspberryPi...']])
				os.system('sudo halt') # Shutdown.

if __name__ == '__main__':
	time.sleep(1)
	try:
		import specialTasks
		from time import strftime,gmtime
		os.rename('specialTasks.py','graveyard/specialTasks'+str(strftime("%Y%m%d-%H%M%S",gmtime()))+'.py')
	except ImportError:
		logger.logSystem([["SpecialTasks: No special tasks to run on boot..."]])
	except OSError:
		logger.logSystem([["SpecialTasks: Was not able to run special tasks or could not rename. (OSError)"]])


	# Main script.
	run()
