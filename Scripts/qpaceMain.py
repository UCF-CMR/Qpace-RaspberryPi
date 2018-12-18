#!/usr/bin/env python3
# qpaceMain.py by Jonathan Kessluk
# 4-19-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This script is run at boot to initialize the system clock and then wait for interrupts.

import os
import threading
import time
import datetime
import pathlib
import json # Used for the graveyard
try:
	import qpaceLogger
except:
	class Logger():
		def __init__(self):
			pass
		def logSystem(self,*stuff):
			pass
	qpaceLogger = Logger()

try:
	import qpaceExperiment as exp
	import qpaceInterpreter as qpi
	import qpaceTODOParser as todo
	import tstSC16IS750 as SC16IS750
	#import SC16IS750
	import qpaceStates as states
except:
	pass

try:
	import pigpio
	gpio = pigpio.pi()
except:
	gpio = None

ALLOW_SHUTDOWN = False
REBOOT_ON_EXIT = False
CONN_ATTEMPT_MAX = 3 # 5 attempts to connect to WTC via SC16IS750
THREAD_ATTEMPT_MAX = 3 # 5 attempts to restart threads, otherwise don't restart. When all have reached max, shutdown.
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
		self.logger.logSystem('{}: Initializing...'.format(name))

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

			self.logger.logSystem("{}: Adding {} to the queue.".format(self.name,logMessage))

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
		Remove an item from the queue. If empty, return None
		"""
		if self.isEmpty():
			return None
		else:
			item =  self.internalQueue.pop(0)

			if not self.suppress:
				if not isinstance(item,int) and len(item) > 32:# If we are logging something quite long, don't include it in the log
					logMessage = 'data (len:{}) [{}]'.format(len(item),item[:10])
				else:
					logMessage = "'{}'".format(item)
				self.logger.logSystem("{}: Removed item from queue: {}".format(self.name,logMessage))


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
		self.logger.logSystem("{}: Entered a wait. pop={}, timeout={}".format(self.name,popN,str(timeout)))
		try:
			# Wait until the queue is empty.
			while not self.isEmpty():
				if not self.cv.wait(timeout):
					self.logger.logSystem('{}: Wait timed out. Exiting wait.'.format(self.name))
					# After the wait time, let's just continue going. Something held up.
					return None
			# pop the number of responses we want off the back and then return them.
			self.logger.logSystem('{}: Wait completed.'.format(self.name))
			return None
		except RuntimeError as e:
			self.logger.logError("{}: Lock was not aquired for wait".format(self.name),e)
			return None # The lock was not aquired for some reason.

	def blockWithResponse(self,response,timeout=WAIT_TIME):
		"""
		This method will block until the response is read by another thread.
		Adds response to self.response; until self.response is null, this will block for a certain time
		until a timeout.
		"""
		self.logger.logSystem("{}: Adding a response. '{}' must be read before continuing... Will wait {} seconds before removing the response".format(self.name,response,timeout))
		try:
			self.response = response
			pollingDelay = .5
			fragments = timeout/pollingDelay
			counter = 0
			while True:
				if self.response is None:
					self.logger.logSystem("{}: Response was read... continuing on.".format(self.name))
					break
				if counter >= fragments:
					self.logger.logSystem("{}: Response was not read: Timeout!".format(self.name))
					break
				time.sleep(pollingDelay)
				counter+=1
		except:
			self.logger.logError("{}: Was not able to wait for response to be read.".format(self.name))

	def waitForResponse(self,timeout=WAIT_TIME):
		"""
		This method will block until the response is available.
		reads response from self.response; until self.response is not null, this will block for a certain time
		until a timeout.
		"""
		self.logger.logSystem("{}: Someone is waiting for the response to be read. (Timeout={})".format(self.name,timeout))
		try:
			pollingDelay = .5
			fragments = timeout/pollingDelay
			counter = 0
			while True:
				if self.response is not None:
					self.logger.logSystem("{}: Response was found... continuing on. Response: {}".format(self.name,self.response))
					break
				if counter >= fragments:
					self.logger.logSystem("{}: Response was not read: Timeout!".format(self.name))
					break
				time.sleep(pollingDelay)
				counter+=1
			response = self.response
			self.response = None
			return response
		except:
			self.logger.logError("{}: Was not able to wait for response to be read.".format(self.name))

	def clearResponse(self):
		self.response = None

def graveyardHandler(runEvent,shutdownEvent,logger):
	GRAVEYARD_SLEEP = 1800 # Seconds    Every 30 minutes
	GRAVEYARD_DAYS = 0#30 # Days
	GRAVEYARD_MINUTES = .2 # Minutes
	GRAVEYARD_PATH = '../graveyard/' # Make sure to include the ending slash.
	GRAVEYARD_LEDGER = '../data/misc/grave.ledger'

	previous_graveyard_size = 0

	logger.logSystem('GraveKeeper: Starting...')
	try:
		while not shutdownEvent.is_set():
			# wait for GRAVEYARD_SLEEP seconds and then continue. if we need to shutdown, backout and do so.
			shutdownEvent.wait(GRAVEYARD_SLEEP)
			if shutdownEvent.is_set():
				raise StopIteration()

			runEvent.wait() # Also wait here if we need to wait.
			logger.logSystem('GraveKeeper: Hunting for ghosts.')

			#logger.logSystem('GraveKeeper: Checking for ghosts... (Graveyard size: {})'.format(len(graveyard)))
			# Check for the ghosts (files in the graveyard that need to be removed)
			# Remove the ghosts
			currentGraveyard = None
			def updateGraveyard():
				try:
					return os.listdir(GRAVEYARD_PATH)
				except Exception as e:
					logger.logError("GraveKeeper: There's no graveyard to manage.",e)
					return None

			def createLedger():
				try:
					with open(GRAVEYARD_LEDGER,'w') as f:
						f.write('{}')
				except Exception as e:
					logger.logError('GraveKeeper: Encountered an error when creating the ledger and cannot recover. Exiting...',e)
					raise StopIteration()
			currentGraveyard = updateGraveyard()
			if currentGraveyard is not None:
				try:
					with open(GRAVEYARD_LEDGER, 'r+') as f:
						graveyard = json.loads(f.read())
						# Add files that are in the graveyard now OR delete them if they are too old.
						for ghost in currentGraveyard:
							if ghost in graveyard:
								time_of_death = datetime.datetime.strptime(graveyard[ghost],'%Y%m%d%H%M%S') # Get the time that the file was added to the graveyard
								# Check the timings and remove it if necessary
								# If the time of that file is older than GRAVEYARD_DAYS days ago... delete it!
								if time_of_death < (datetime.datetime.now() - datetime.timedelta(days=GRAVEYARD_DAYS,minutes=GRAVEYARD_MINUTES)):
									try:
										logger.logSystem('GraveKeeper: Deleted {}'.format(ghost))
										os.remove('{}{}'.format(GRAVEYARD_PATH,ghost))
									except: pass
							else: # If it's not in the graveyard, add it.
								logger.logSystem('GraveKeeper: Added {}'.format(ghost))
								graveyard[ghost] = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
						f.seek(0)
						f.truncate()
						f.write(json.dumps(graveyard))
				except FileNotFoundError as e:
					logger.logError('GraveKeeper: Could not open the ledger. Attempting to create a new one at {}.'.format(GRAVEYARD_LEDGER),e)
					createLedger()
				except json.decoder.JSONDecodeError as e:
					logger.logError('GraveKeeper: JSON error. Attempting to create a new ledger.',e)
					createLedger()
				except Exception as e:
					logger.logError('GraveKeeper: Could not add a ghost to the graveyard.',e)

			currentGraveyard = updateGraveyard()
			if currentGraveyard is not None:
				try:
					with open(GRAVEYARD_LEDGER, 'r+') as f:
						graveyard = json.loads(f.read())
						# Remove files that shouldn't be in the map anymore.
						graveyardCopy = dict(graveyard) # Python doesn't like modifying iterables
						for ghost in graveyardCopy:
							if not ghost in currentGraveyard:
								logger.logSystem('GraveKeeper: Forgot about <{}>'.format(ghost))
								del graveyard[ghost]
						f.seek(0)
						f.truncate()
						f.write(json.dumps(graveyard))
				except FileNotFoundError as e:
					logger.logError('GraveKeeper: Could not open the ledger. <{}>'.format(GRAVEYARD_LEDGER),e)
				except json.decoder.JSONDecodeError as e:
					logger.logError('GraveKeeper: JSON error. Can not remove items from the list in ledger.',e)
				except Exception as e:
					logger.logError('GraveKeeper: Could not remove ghosts from the graveyard.',e)

	except StopIteration:
		logger.logSystem('GraveKeeper: Shutting down...')

def healthCheck(logger):
	#logger.logSystem('HealthCheck: Beginning health check to ensure all directories and files exist.')
	# Important scripts. If one of them are missing, then abort.
	criticalFiles = ('qpaceExperiment.py','qpaceExperimentParser.py','qpaceFileHandler.py','qpaceInterpreter.py','qpaceLogger.py','qpaceMain.py',
					'qpacePiCommands.py','qpaceStates.py', 'qpaceTODOParser.py', 'SC16IS750.py')
	# Paths/files that must exist for proper operation. Create them if necessary. Non-critical
	importantPaths = ('../graveyard/grave.ledger')
	# Directories that must exist for proper operation. Create them if necessary. Critical to have, but can be created at runtime.
	importantDir = ('../data','../data/exp','../data/misc','../data/pic','../data/text','../data/vid',
					'../graveyard', '../logs', '../Scripts', '../temp')
	paths = []
	directories = []
	files = []
	for path,dirlist,filelist in os.walk('..'):
		paths += [path]
		directories += dirlist
		files += filelist

	criticalNotFound = []
	for crit in criticalFiles:
		if crit not in files:
			criticalNotFound.append(crit)

	for dir in importantDir:
		if dir not in paths:
			logger.logSystem('HealthCheck: Can not find {}. Creating it...'.format(dir))
			try:
				os.makedirs(dir,exist_ok=True)
			except:
				logger.logSystem('HealthCheck: Failed to create {}'.format(dir))
				return False

	if criticalNotFound:
		logger.logSystem('HealthCheck: Fatal. Can not find {}.'.format(criticalNotFound))
		return False
	return True


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
			logger.logSystem('Interpreter: Could not connect to SC17IS750. Max attemptes reached: {}'.format(connectionAttempts))




	if chip is not None:
		try:
			# Begin running the rest of the code for the Pi.
			logger.logSystem("Main: Starting QPACE...")
			# Create a threading.Event to determine if an experiment is running or not.
			# Or if we are doing something and should wait until it's done.
			experimentRunningEvent = threading.Event()
			runEvent = threading.Event()
			shutdownEvent = threading.Event()
			parserEmpty = threading.Event()
			# Ensure these are in the state we want them in.
			runEvent.set()
			experimentRunningEvent.clear()
			shutdownEvent.clear()
			parserEmpty.clear()

			# Initialize the nextQueue for WHATISNEXT operations
			nextQueue = Queue(logger=logger,name='NextQueue')
			packetQueue = Queue(logger=logger,name='PacketQueue')

			# Initialize threads
			interpreter = threading.Thread(target=qpi.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
			todoParser = threading.Thread(target=todo.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,parserEmpty,logger))
			graveyardThread = threading.Thread(target=graveyardHandler,args=(runEvent,shutdownEvent,logger))

			logger.logSystem("Main: Starting up threads.")
			interpreter.start() # Run the Interpreter
			todoParser.start() # Run the TodoParser
			graveyardThread.start() # Run the graveyard


			interpreterAttempts = 0
			todoParserAttempts = 0
			graveyardAttempts = 0
			# The big boy main loop. Good luck QPACE.
			while True:
				try:
					time.sleep(.35)
					if shutdownEvent.is_set():
						break

					# Check the interpreter, restart if necessary. The Interpreter should always be running and never shutdown early.
					if not interpreter.isAlive() and interpreterAttempts < THREAD_ATTEMPT_MAX:
						logger.logSystem("Main: Interpreter is shutdown when it should not be. Attempt {} at restart.".format(interpreterAttempts + 1))
						interpreter = threading.Thread(target=qpi.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,logger))
						interpreter.start()
						interpreterAttempts += 1

					# Check the TodoParser, restart it if necessary. The TodoParser is allowed to be shutdown early.
					if not todoParser.isAlive() and not parserEmpty.is_set() and todoParserAttempts < THREAD_ATTEMPT_MAX:
						logger.logSystem('Main: TodoParser is shutdown when it should not be.  Attempt {} at restart.'.format(todoParserAttempts + 1))
						todoParser = threading.Thread(target=todo.run,args=(chip,nextQueue,packetQueue,experimentRunningEvent,runEvent,shutdownEvent,parserEmpty,logger))
						todoParser.start()
						todoParserAttempts += 1

					# Check the graveyard, restart it if necessary. The graveyard shouldn't be shutdown but it doesn't really matter
					if not graveyardThread.isAlive() and graveyardAttempts < THREAD_ATTEMPT_MAX:
						logger.logSystem('Main: Graveyard is shutdown when it should not be.  Attempt {} at restart.'.format(graveyardAttempts + 1))
						graveyardThread = threading.Thread(target=graveyardHandler,args=(runEvent,shutdownEvent,logger))
						graveyardThread.start()
						graveyardAttempts += 1

					if interpreterAttempts + todoParserAttempts + graveyardAttempts == THREAD_ATTEMPT_MAX * 3:
						welp_oh_no = "Main: All threads are closed and could not be started. Exiting."
						logger.logSystem(welp_oh_no)
						logger.logError(welp_oh_no)
						raise RuntimeError(welp_oh_no)


				except KeyboardInterrupt:
					shutdownEvent.set()

			logger.logSystem("Main: Main loop has been closed.")
		except RuntimeError as err:
			try:
				#TODO Alert the WTC of the problem and/or log it and move on
				#TODO figure out what we actually want to do.
				logger.logError("Main: There is a problem with running threads.", err)

			except BufferError as err:
				logger.logError("Main: Something went wrong when reading the buffer of the WTC.", err)
		except Exception as err:
			logger.logError('Main: Something went wrong in the main loop!',err)
		finally:
			# Close the chip if issues arise OR we need to exit the main loop.
			chip.close()


	# If we've reached this point, just shutdown.
	logger.logSystem("Main: Cleaning up and closing out...")

	# Reset all the pins one last time
	exp.Action(logger).reset()
	# if we need to close out pigpio, do it
	if gpio:
		gpio.stop()
	# Ensure that all threads see it's time to shutdown.
	shutdownEvent.set()
	# If the thread has ever been started before, make sure we join it and wait until it ends
	if interpreter.ident is not None: interpreter.join()
	if todoParser.ident is not None: todoParser.join()
	if graveyardThread.ident is not None: graveyardThread.join()

	# If we want the pi to shutdown automattically, then do so.
	if ALLOW_SHUTDOWN:
		if REBOOT_ON_EXIT:
			logger.logSystem('Main: Rebooting RaspberryPi...')
			os.system('sudo reboot') # reboot
		else:
			logger.logSystem('Main: Shutting down RaspberryPi...')
			os.system('sudo halt') # Shutdown.

if __name__ == '__main__':
	time.sleep(1)
	logger = qpaceLogger.Logger()

	if healthCheck(logger):
		logger.logSystem('HealthCheck: Complete. QPACE is GO.')
		logger.logSystem("Main: Initializing GPIO pins to default states.")
		exp.Action(logger).reset()
		time.sleep(.5)


		# Attempt to run specialTasks.
		try:
			import specialTasks
			from time import strftime,gmtime
			# If there is a method there that starts with 'task_' then that method is a special task.
			methods_to_call = [ task for task in dir(specialTasks) if task.startswith('task_') and not task.startswith('__') ]
			if not methods_to_call:
				logger.logSystem('SpecialTasks: SpecialTasks existed, but there are no tasks to run.')
			else:
				for method in methods_to_call:
					try:
						logger.logSystem('Attempting to call <specialTasks.{}>'.format(method))
						getattr(specialTasks,method)() #run the method if it exists
					except:
						logger.logSystem('Failed to call <specialTasks.{}>'.format(method))

			os.rename('specialTasks.py','../graveyard/specialTasks'+str(strftime("%Y%m%d-%H%M%S",gmtime()))+'.py')
		except ImportError:
			logger.logSystem("SpecialTasks: There were no specialTasks to run on boot.")
		except OSError:
			logger.logSystem("SpecialTasks: Was not able to run special tasks or could not rename. (OSError)")
		except Exception as e:
			logger.logSystem("SpecialTasks: Got an exception. {}".format(str(e)))
		# Main script.
		run(logger)
	else:
		logger.logSystem('HealthCheck: Failed. Aborting QPACE.')
