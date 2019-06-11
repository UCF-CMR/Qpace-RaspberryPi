
try:
	import pigpio
except:
	pass
import time
import datetime
import os
import traceback
from struct import pack
import threading
import SC16IS750

global packetBuffer #TODO Possibly remove for flight. Not really an issue used for debugging
packetBuffer = []

def run(chip,nextQueue,packetQueue, runEvent,disableCallback):
	cmd.setDisableCallback(disableCallback)
	#Main method for this module. Handles all data coming from the WTC and interprets what the Pi should do with it.
	CCDR_IRQ = 16
	print("Interpreter: Starting...")
	if chip is None:
		e = ConnectionError('The SC16IS750 is not connected. The Interpreter can not run.')
		print(str(e),e)
		raise e

	try:
		# Initialize the pins
		gpio = pigpio.pi()
		gpio.set_mode(CCDR_IRQ, pigpio.INPUT)
	except NameError:
		print('PIGPIO is not defined. Unable to set interrupt')
		gpio = None

	global packetBuffer #TODO Possibly remove for flight. Not really an issue used for debugging
	packetBuffer = []
	callback = None

	def WTCRXBufferHandler(gpio,level,tick):
		"""
		Callback method run by pigpio to handle data when the interrupt pin is fired. May be disabled and recreated at any time

		Parameters: gpio, level, tick - required by pigpio

		Returns: None

		Raises: None

		"""
		try:
			packetData = chip.block_read(SC16IS750.REG_RHR,chip.byte_read(SC16IS750.REG_RXLVL))
		except:
			traceback.print_exc()
			print("I2C READ FAILED")
			return

		#This segment of code is used twice, it is read off for states and for packets,
		#its use in both causes a race condition where the added data is read with the packet
		#short solution is to modify when trying to build packet
		#logger.logResults("Data came in: ", packetData)
		print("Data came in: ", ''.join(map(chr, packetData)))
		packetBuffer.append(packetData)

	def callbackHandler(disableCallback):
		print("Entered: callbackHandler")
		"""
		Gets its own thread. Monitors the disableCallback Event and if it is ever .set(), the callback gets disabled
		re-enable to callback by .clear()

		Parameters:
		disableCallback - threading.Event() - If .set() disable callback. If .clear() enable callback
		shutdownEvent - threading.Event() - If .set() exit immediately and prepare pi for shutdown.

		Returns: None

		Raises:None

		"""
		if gpio:
			callBackIsSet=True
			callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)
			print('Interpreter: Callback active. Waiting for data from the SC16IS750.')
			while True:
				time.sleep(.12)
				if callBackIsSet and disableCallback.is_set(): # If the callback is running and we want to disable it, cancel it.
					callback.cancel()
					callBackIsSet = False
					print('Interpreter: Callback Disabled.')
				if not callBackIsSet and not disableCallback.is_set(): # If the callback is not running and we want to not disable it, start it up again.
					callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)
					callBackIsSet = True
					print('Interpreter: Callback Enabled.')
			if callBackIsSet:
				callback.cancel()
		else:
			print("Interpreter: Callback is not active. PIGPIO was not defined.")
		print("Exited: callbackHandler")

	# Start up the thread for the callbackHandler
	cb_hndlr=threading.Thread(name='callbackHandler',target=callbackHandler,args=(disableCallback))
	cb_hndlr.start()

	
while True:
	while(len(packetBuffer)>0):
		packetData = packetBuffer.pop(0) # Get that input
		print('{} {} {}'.format(len(packetData), packetData, hex(packetData)))
