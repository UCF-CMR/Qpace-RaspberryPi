#!/usr/bin/env python3
# qpaceWTCHandler.py by Jonathan Kessluk
# 4-19-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This script is run at boot to initialize the system clock and then wait for interrupts.
#TODO: Re-do comments/documentation

import os
import threading
import time
import datetime

import qpaceLogger
import qpaceExperiment as exp
import qpaceInterpreter as qpi
import qpaceTODOParser as todo
import tstSC16IS750 as SC16IS750
#import SC16IS750
import qpaceStates as states

try:
	import pigpio
	gpio = pigpio.pi()
except:
	gpio = None
REBOOT_ON_EXIT = False
CONN_ATTEMPT_MAX = 5 # 5 attempts to connect to WTC via SC16IS750
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
	# QPACE IS 0X48
	I2C_ADDR_WTC = 0x48#0x4c # I2C addresses for WTC comm chips
	# QPACE IS 115200
	I2C_BAUD_WTC = 115200 # UART baudrates for WTC comm chips
	# QPACE IS 1843200
	XTAL_FREQ = 1843200#11059200 # Crystal frequency for comm chips
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

class Queue():
	"""
	Reason for Implementation
	-------------------------
	This is a generic queue used for the NextQueue, PacketQueue, and ResponseQueue
	"""
	WAIT_TIME = 5 #in seconds
	# MAX = 10

	def __init__(self,logger=None,name="Queue",suppressLog=False):
		self.internalQueue = []
		self.enqueueCount = 0
		self.cv = threading.Condition()
		self.name = name
		self.suppress = suppressLog
		self.response = None
		self.logger=logger
		logger.logSystem('{}: Initializing...'.format(name))

	def isEmpty(self):
		""" Check to see if the queue is empty."""
		return len(self.internalQueue) == 0

	# @staticmethod
	# def NextQueue.isFull():
	# 	return len(internalQueue) >= NextQueue.MAX

	def enqueue(self,item):
		"""
		Enqueue an item to the queue.
		Set up a threading.Condition variable for use by NextQueue. This is only useful for the "wait" feature.
		"""
		if self.isEmpty():
			self.cv.acquire() # If we are putting something in for the first time, set up the Lock

		if not self.suppress:
			if not isinstance(item,int) and len(item) > 32:# If we are logging something quite long, don't include it in the log
				logMessage = 'data (len:{}) [{}]'.format(len(item),item[:10])
			else:
				logMessage = "'{}'".format(item)

			logger.logSystem("{}: Adding {} to the queue.".format(self.name,logMessage))

		if item in states.QPCONTROL:
			item = states.QPCONTROL[item]

		self.internalQueue.append(item)
		self.enqueueCount += 1

	def peek(self):
		"""
		Just look at the top of the queue.
		"""
		if self.isEmpty():
			return []

		else:
			return self.internalQueue[0]

	def dequeue(self):
		"""
		Remove an item from the queue.
		"""
		if self.isEmpty():
			return []
		else:
			item =  self.internalQueue.pop(0)

			if not self.suppress:
				if not isinstance(item,int) and len(item) > 32:# If we are logging something quite long, don't include it in the log
					logMessage = 'data (len:{}) [{}]'.format(len(item),item[:10])
				else:
					logMessage = "'{}'".format(item)
				logger.logSystem("{}: Removed item from queue: {}".format(self.name,logMessage))


			if self.isEmpty():
				try:
					self.cv.release() # If there is nothing in the queue, release the lock.
				except RuntimeError:
					pass # If it's already released for some reason, ignore it.
			return item


	def stackPop(self, n):
		response = self.internalQueue[-popN:]
		NextQueue.internalQueue = NextQueue.internalQueue[:-popN]
		return response

	def getCount(self):
		return self.enqueueCount

	def waitUntilEmpty(self,popN=1,timeout=WAIT_TIME):
		"""
		This method waits until the queue is empty, and returns the result values of the queue.
		Before returning, this method will pop the queue one time unless specified and return
		Those values. Those values will be removed from the responseQueue.

		WARNING: Be careful where this is placed. Depending on the thread it is placed in, an
				 infinite wait is possible. The queue must be able to be dequeued for this wait to
				 exit properly. To counter this, a timeout is set.
		"""
		logger.logSystem("{}: Entered a wait. pop={}, timeout={}".format(self.name,popN,str(timeout)))
		try:
			# Wait until the queue is empty.
			while not self.isEmpty():
				if not self.cv.wait(timeout):
					logger.logSystem('{}: Wait timed out. Exiting wait.'.format(self.name))
					# After the wait time, let's just continue going. Something held up.
					return None
			# pop the number of resposes we want off the back and then return them.
			logger.logSystem('{}: Wait completed.'.format(self.name))
			return None
		except RuntimeError as e:
			logger.logError("{}: Lock was not aquired for wait".format(self.name),e)
			return None # The lock was not aquired for some reason.

	def blockWithResponse(self,response,timeout=WAIT_TIME):
		"""
		This method will block until the response is read by another thread.
		Adds response to self.response; until self.response is null, this will block for a certain time
		until a timeout.
		"""
		logger.logSystem("{}: Adding a response. '{}' must be read before continuing... Will wait {} seconds before removing the response".format(self.name,response,timeout))
		try:
			self.response = response
			pollingDelay = .5
			fragments = timeout/pollingDelay
			counter = 0
			while True:
				if self.response is None:
					logger.logSystem("{}: Response was read... continuing on.".format(self.name))
					break
				if counter >= fragments:
					logger.logSystem("{}: Response was not read: Timeout!".format(self.name))
					break
				time.sleep(pollingDelay)
				counter+=1
		except:
			logger.logError("{}: Was not able to wait for response to be read.".format(self.name))

	def waitForResponse(self,timeout=WAIT_TIME):
		"""
		This method will block until the response is available.
		reads response from self.response; until self.response is not null, this will block for a certain time
		until a timeout.
		"""
		logger.logSystem("{}: Someone is waiting for the response to be read. (Timeout={})".format(self.name,timeout))
		try:
			pollingDelay = .5
			fragments = timeout/pollingDelay
			counter = 0
			while True:
				if self.response is not None:
					logger.logSystem("{}: Response was found... continuing on. Response: {}".format(self.name,self.response))
					break
				if counter >= fragments:
					logger.logSystem("{}: Response was not read: Timeout!".format(self.name))
					break
				time.sleep(pollingDelay)
				counter+=1
			response = self.response
			self.response = None
			return response
		except:
			logger.logError("{}: Was not able to wait for response to be read.".format(self.name))

	def clearResponse(self):
		self.resposne = None

def graveyardHandler(runEvent,shutdownEvent,logger):
	GRAVEYARD_SLEEP = 600 # seconds
	GRAVEYARD_DAYS = 30 #days
	GRAVEYARD_PATH = '/home/pi/graveyard/' # Make sure to include the ending slash.

	graveyard = {}

	logger.logSystem('GraveKeeper: graveyardHandler started.')
	try:
		while not shutdownEvent.is_set():
			# wait for GRAVEYARD_SLEEP seconds and then continue. if we need to shutdown, backout and do so.
			shutdownEvent.wait(GRAVEYARD_SLEEP)
			if shutdownEvent.is_set():
				raise StopAsyncIteration()

			runEvent.wait() # Also wait here if we need to wait.
			logger.logSystem('GraveKeeper: Checking for ghosts...')
			# Check for the ghosts (files in the graveyard that need to be removed)
			# Remove the ghosts
			currentGraveyard = os.listdir(GRAVEYARD_PATH)

			# Remove files that shouldn't be in the map anymore.
			for ghost in graveyard:
				if not ghost in currentGraveyard:
					del graveyard[ghost]

			# Add files that are in the graveyard now OR delete them if they are too old.
			for ghost in currentGraveyard:
				if ghost in graveyard:
					# Check the timings and remove it if necessary
					# If the time of that file is older than GRAVEYARD_DAYS days ago... delete it!
					if graveyard[ghost] < (datetime.datetime.now() - datetime.timedelta(days=GRAVEYARD_DAYS)):
						os.remove('{}{}'.format(GRAVEYARD_PATH,ghost))
				else: # If it's not in the graveyard, add it.
					graveyard[ghost] = datetime.datetime.now()


	except StopAysncIteration:
		logger.logSystem('GraveKeeper: Shutting down...')

def run(logger):
	"""
	Main loop for QPACE. All the magic happens here.

	Parameters
	----------
	None

	Returns
	-------
	Void

	Raises
	------
	Ideally Nothing. If anything is raised out of this method, execution stops.
	"""
	import sys
	import datetime
	import time

	chip = initWTCConnection()

	connectionAttempts = 0
	# Attempt to connect to the SC16IS750 until we get a connection.
	while chip is None:
		chip = initWTCConnection()
		if chip is None:
			time.sleep(1)
			logger.logSystem('Interpeter: Connection could not be made to the SC16IS750. Attempt {}'.format(connectionAttempts))
		if connectionAttempts > CONN_ATTEMPT_MAX:
			welp_oh_no = 'Interpreter: Could not connect to SC17IS750. Max attemptes reached: {}'.format(connectionAttempts)
			logger.logSystem(welp_oh_no)
			raise ConnectionError(welp_oh_no)



	#chip.byte_write(SC16IS750.REG_THR, ord(identity)) # Send the identity to the WTC
	#TODO Implement identity on the WTC
	try:
		# Begin running the rest of the code for the Pi.
		logger.logSystem("Main: Starting QPACE...")
		# Create a threading.Event to determine if an experiment is running or not.
		# Or if we are doing something and should wait until it's done.
		experimentRunningEvent = threading.Event()
		runEvent = threading.Event()
		shutdownEvent = threading.Event()
		# Ensure these are in the state we want them in.
		runEvent.set()
		experimentRunningEvent.clear()
		shutdownEvent.clear()

		# Initialize the nextQueue for WHATISNEXT operations
		nextQueue = Queue(logger=logger,name='NextQueue')
		packetQueue = Queue(logger=logger,name='PacketQueue')

		interpreter = threading.Thread(target=qpi.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
		todoParser = threading.Thread(target=todo.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
		graveyardThread = threading.Thread(target=graveyardHandler,args(runEvent,shutdownEvent,logger))

		logger.logSystem("Main: Starting up threads.")
		interpreter.start() # Run the Interpreter
		todoParser.start() # Run the TodoParser
		graveyardThread.start()

		# The big boy main loop. Good luck QPACE.
		while True:
			try:
				time.sleep(.4)

				# If the scripts aren't running then we have two options
				if not (interpreter.isAlive() or todoParser.isAlive()):
					# If we want to shutdown, then break out of the loop and shutdown.
					if shutdownEvent.is_set():
						break
					else: # Otherwise, something must have happened....restart the Interpreter and TodoParser
						logger.logSystem('Main: TodoParser and Interpreter are shutdown when they should not be. Restarting...')
						interpreter = threading.Thread(target=qpi.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
						todoParser = threading.Thread(target=todo.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
						interpreter.start()
						todoParser.start()
			except KeyboardInterrupt:
				shutdownEvent.set()

		logger.logSystem("Main: The Interpreter and TodoParser have exited.")
	except BufferError as err:
		#TODO Alert the WTC of the problem and/or log it and move on
		#TODO figure out what we actually want to do.
		logger.logError("Main: Something went wrong when reading the buffer of the WTC.", err)

	except ConnectionError as err:
		#TODO Alert the WTC of the problem and/or log it and move on
		#TODO figure out what we actually want to do.
		logger.logError("Main: There is a problem with the connection to the WTC", err)

	# If we've reached this point, just shutdown.
	logger.logSystem("Main: Cleaning up and closing out...")
	if gpio:
		gpio.stop()
	shutdownEvent.set()
	interpreter.join()
	todoParser.join()
	graveyardThread.join()


	if False: #TODO: Change to True for release
		if REBOOT_ON_EXIT:
			logger.logSystem('Main: Rebooting RaspberryPi...')
			os.system('sudo reboot') # reboot
		else:
			logger.logSystem('Main: Shutting down RaspberryPi...')
			os.system('sudo halt') # Shutdown.

if __name__ == '__main__':
	time.sleep(1)
	logger = qpaceLogger.Logger()
	logger.logSystem("Main: Initializing GPIO pins to default states.")
	exp.Action(logger).reset()
	time.sleep(.5)

	# Attempt to run specialTasks.
	try:
		import specialTasks
		from time import strftime,gmtime
		if 'fire' in dir(specialTasks):
			specialTasks.fire()
		os.rename('specialTasks.py','../graveyard/specialTasks'+str(strftime("%Y%m%d-%H%M%S",gmtime()))+'.py')
	except ImportError:
		logger.logSystem("SpecialTasks: No special tasks to run on boot...")
	except OSError:
		logger.logSystem("SpecialTasks: Was not able to run special tasks or could not rename. (OSError)")
	except Exception as e:
		logger.logSystem("SpecialTasks: Got an exception. {}".format(str(e)))
	# Main script.
	run(logger)
