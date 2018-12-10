#! /usr/bin/env python3
# qpaceExperiment.py by Minh Pham, Jonathan Kessluk, Chris Britt
# 08-07-2018, Rev. 2.5
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import time
from qpaceLogger import Logger as qpLog


try:
	import RPi.GPIO as GPIO
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
except:
	print("Unable to import RPi.GPIO")
	pass

GoProDirectory = '/home/pi/gopro/DCIM/100GOPRO/'
MountPoint = '/home/pi/gopro'
SavePoint = '/home/pi/data/vid/'
MAX_PENDING_DELTA = 300 # in seconds

class PIN():
	"""
	Reason for Implementation
	-------------------------
	Pin handler class. Each class variable is an alias for the pin assignment.
	"""
	GOPPWR = 19
	GOPBUT = 13
	GOPCAP = 15
	GOPDEN = 40
	LEDPWR = 23
	STPEN  = 33
	STPENA = 29
	STPENB = 21
	SOLX   = 37 # Side opposite to stepper.
	SOLY   = 35
	SOLZ   = 31

class PINGROUP():
	"""
	Reason for Implementation
	-------------------------
	Tuples that represent functional groups of the pins.
	"""
	gopro = (PIN.GOPPWR,PIN.GOPBUT,PIN.GOPCAP,PIN.GOPDEN)
	solenoid = (PIN.SOLX,PIN.SOLY,PIN.SOLZ)
	stepper = (PIN.STPEN,PIN.STPENA,PIN.STPENB)
	led = (PIN.LEDPWR,)

class Stepper():
	rotationStates = {
		0: (0,0),
		1: (1,0),
		2: (1,1),
		3: (0,1)
	}
	nextState = 0

	@staticmethod
	def forward():
		put(PIN.STPENA, Stepper.rotationStates[Stepper.nextState%4][0])
		put(PIN.STPENB, Stepper.rotationStates[Stepper.nextState%4][1])
		Stepper.nextState += 1

	@staticmethod
	def reverse():
		Stepper.nextState -= 2 # subtract 2 from the NEXT state to figure out the previous state
		put(PIN.STPENA, Stepper.rotationStates[Stepper.nextState%4][0])
		put(PIN.STPENB, Stepper.rotationStates[Stepper.nextState%4][1])
		Stepper.nextState += 1

class Action():

	def __init__(self,logger=None,queue=None):
		if logger is None:
			class DummyLogger():
				def logSystem(*x): print('System: {}'.format(x))
				def logError(*x): print('Error:  {}'.format(x))
				def logData(*x): print('Data:   {}'.format(x))
			logger = DummyLogger()
		if queue is None:
			class DummyQueue():
				def waitForResponse(*args): logger.logError('Queue is None. Action() cannot run this method.')
			queue = DummyQueue()
		self.logger=logger
		self.queue=queue

	def put(self,pin,state):
		"""
		Set a pin to a specific state


		Parameters
		----------
		pin - int - pin to set to a specific state
		state - int - 0 for low, 1 for high

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		GPIO.output(pin,state)

	def low(self,pin):
		"""
		Clear a pin.

		Parameters
		----------
		pin - int - pin that you'd like to clear.

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		self.put(pin,0)

	def high(self,pin):
		"""
		Set a pin.

		Parameters
		----------
		pin - int - pin that you'd like to set.

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		self.put(pin, 1)

	def toggle(self,pin):
		"""
		Toggle a pin.

		Parameters
		----------
		pin - int - pin that you'd like to toggle.

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		self.put(pin,GPIO.input(pin)^1)

	def flip(self,pin,delay=.1):
		"""
		Toggle a pin, wait, and then reset the pin back to it's initial state.
		Similar to pressing a button.

		Parameters
		----------
		pin - int - pin that you'd like to flip.
		delay - int - Delay in seconds to wait before reverting the pin. DEFAULT: .1s

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		self.put(pin,GPIO.input(pin)^1) # Invert the pin
		time.sleep(delay)
		self.put(pin,GPIO.input(pin)^1) # Put it back

	def read(self,pin):
		return GPIO.input(pin)

	def reset(self,pingroup=None):
		"""
		Initialize the pins to their default states.
		If a pingroup is supplied, then only reset that pin group.

		Parameters
		----------
		pingroup - tupple - PINGROUP tupple you'd like to reset. DEFAULT: None
							If None is supplied, reset ALL pins.

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		try:
			GPIO
		except NameError:
			print("GPIO is not defined, the pins were not reset!")
		else:

			if pingroup is None: # If None, reset all pins
				self.reset(PINGROUP.gopro)
				self.reset(PINGROUP.stepper)
				self.reset(PINGROUP.led)
				self.reset(PINGROUP.solenoid)
			elif pingroup == PINGROUP.led:
				#LED pin setup
				GPIO.setup(PIN.LEDPWR, GPIO.OUT, initial=0)				#Controls the LEDs
			elif pingroup == PINGROUP.solenoid:
				#Solenoid setup
				GPIO.setup(PIN.SOLX, GPIO.OUT, initial=0)				#Solenoid 1
				GPIO.setup(PIN.SOLY, GPIO.OUT, initial=0)				#Solenoid 2
				GPIO.setup(PIN.SOLZ, GPIO.OUT, initial=0)				#Solenoid 3
			elif pingroup == PINGROUP.stepper:
				#Stepper pin setup
				GPIO.setup(PIN.STPEN, GPIO.OUT, initial=1)				#Step Enable
				GPIO.setup(PIN.STPENA, GPIO.OUT, initial=0)				#Step A Enable
				GPIO.setup(PIN.STPENB, GPIO.OUT, initial=0)				#Step B Enable
			elif pingroup == PINGROUP.gopro:
				#GoPro pin setup
				GPIO.setup(PIN.GOPPWR, GPIO.OUT, initial=0)				#Power
				GPIO.setup(PIN.GOPBUT, GPIO.OUT, initial=1)				#On Button
				GPIO.setup(PIN.GOPCAP, GPIO.OUT, initial=1)				#Capture Button
				GPIO.setup(PIN.GOPDEN, GPIO.OUT, initial=0)

	def gopro_on(self):
		"""
		Turn on the GoPro

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		self.high(PIN.GOPPWR) #Active High
		time.sleep(3)
		self.flip(PIN.GOPBUT,delay=1)
		time.sleep(5)

	def press_capture(self):
		"""
		Press the capture button.

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		self.flip(PIN.GOPCAP,delay=.5)

	def gopro_start(self):
		"""
		Turn on the gopro and start recording.

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		self.init_gopro() # Turn on camera and set mode
		self.logger.logSystem("ExpCtrl: Beginning to record")
		self.press_capture() # Begin Recording

	def transOn(self):
		"""
		Enable the Data Enable circuit for the gopro USB transfer.

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		self.high(PIN.GOPDEN)

	def transOff(self):
		"""
		Disable the Data Enable circuit for the gopro USB transfer.

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		self.low(PIN.GOPDEN)

	def goProTransfer(self):
		"""
		Transfer data from the gopro to the pi.

		Parameters
		----------
		None

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		time.sleep(1)
		if True:
			#TURN USB ENABLE
			self.logger.logSystem("ExpCtrl: Enabling the USB and mounting the drive...")
			self.transOn()
			time.sleep(3)
			import os
			try: # Mount the GoPro
				os.system('sudo mount /dev/sda1 '+MountPoint)
			except Exception as e:  # MOUNTING THE DRIVE FAILED
				self.logger.logError("ExpCtrl: Could not mount the drive", e)
			else:   # Mounting the drive was successful
				try:
					from shutil import move
					import re
					self.logger.logSystem("ExpCtrl: Moving video over to the Pi")
					files = os.listdir(GoProDirectory)
					for name in files:
						if re.match('.+\.(MP4|JPG)',name):
							os.system('cp '+GoProDirectory + name + ' ' + SavePoint)
				except Exception as e:  #Moving the file from the GOPRO failed
					self.logger.logError("ExpCtrl: Could not move the video", e)
				else: #Moving the file is successful
					try: # Delete all other uneccessary files
						self.logger.logSystem("ExpCtrl: Removing misc files from GoPro")
						for name in files:
							if re.match('.+\..+',name):
								os.system('sudo rm '+GoProDirectory+name)
					except Exception as e: # Could not delete the files
						self.logger.logError("ExpCtrl: Could not delete misc. files on the GoPro", e)
				self.logger.logSystem("ExpCtrl: Unmounting the USB")
				try: # Attempt to umount.
					os.system('sudo umount /dev/sda1')
				except Exception as e: # Failed to call the shell
					self.logger.logError("ExpCtrl: Could not unmount the drive", e)
			time.sleep(.25)
			self.transOff()

	def stepper_turn(self,delay, qturn,multiplier = 1):
		"""
		This function activates the stepper motor in the forward direction.

		Parameters
		----------
		Integer / Float - delay - The time between each phase of the stepper motor.
		Integer - qturn - The number of turns.

		Returns
		-------
		Void.

		"""
		if qturn > 0:
			# Multiply * 4 because we are doing qTurns
			for i in range(0, qturn*multiplier):
				Stepper.forward()
				time.sleep(delay)
		else:
			for i in range(0, -qturn*multiplier): #qturn is already negative so make it positive
				Stepper.reverse()
				time.sleep(delay)
		time.sleep(3)

	def led(self,state):
		"""
		This function turns the LED light on or off.

		Parameters
		----------
		Boolean - power - To turn the LED on/off, power is set to True/False, respectively.

		Returns
		--------
		Void
		"""
		self.put(PIN.LEDPWR,state)

	def solenoid_run(self,solenoidPins,hz,duration,override = False):
		if hz < 1:
			self.logger.logSystem('Solenoid: Hz was set <1. This makes no sense.')
			return
		elif hz > 12 and not override:
			self.logger.logSystem('Solenoid: Max is 12Hz, please override.')
			hz = 12

		period = 1/hz
		for pinSelect in range(duration/period):
			self.put(solenoidPins[pinSelect%len(solenoidPins)],0) # turn the solenoid on
			time.sleep(period/2)
			self.put(solenoidPins[pinSelect%len(solenoidPins)],1) # turn the solenoid off
			time.sleep(period/2)

		self.reset(PINGROUP.solenoid)

	def solenoid_ramp(self,solenoidPins, start_hz, end_hz, granularity=100,override = False):
		if start_hz < 1 or end_hz < 1:
			self.logger.logSystem('Solenoid: Hz was set <1. This makes no sense.')
			return
		elif (start_hz > 12 or end_hz > 12) and not override:
			self.logger.logSystem('Solenoid: Max is 12Hz, please override.')
			if start_hz > 12: start_hz = 12
			if end_hz > 12: end_hz = 12
		start_period = 1/start_hz
		end_period = 1/end_hz
		diff_period = (end_period/2) - (start_period/2)
		pinSelect = 0
		for i in range(granularity):
			#print("HZ:",1/(2*((start_period/2) + (diff_period/granularity)*i)))
			self.put(solenoidPins[pinSelect%len(solenoidPins)],0) # turn the solenoid on
			time.sleep((start_period/2) + (diff_period/granularity)*i)
			self.put(solenoidPins[pinSelect%len(solenoidPins)],1) # turn the solenoid off
			time.sleep((start_period/2) + (diff_period/granularity)*i)
			pinSelect += 1

		self.reset(PINGROUP.solenoid)

	def solenoid_tap(self,solenoidPins, hz=12):
		period = 1/hz # 12 hz (max speed)
		for pin in solenoidPins:
			self.put(pin,0) # turn the solenoid on
			time.sleep(period/2)
			self.put(pin,1) # turn the solenoid off
			time.sleep(period/2)

		self.reset(PINGROUP.solenoid)

	def wtc_request(self,request,nextQueue,pendingTimeout=MAX_PENDING_DELTA,timeout=5):
		"""
		Adds a request to the NextQueue and waits for a response. There is a timeout though!

		Return TRUE for request ACCEPTED; Return FALSE for request DENIED.
		If PENDING is returned, continue to enqueue until a response is received.

		To avoid an infinite loop, count up how many pendings we've received. Should we get more than
		a lot of pendings, then back out and assume denied.
		"""
		try:
			from qpaceStates import QPCONTROL as qp
		except ImportError:
			return False

		pendingMAXCount = pendingTimeout // timeout
		pendingCount = 0
		response = None
		while response is qp['PENDING'] or response is None: # None implies timeout
			if pendingCount > pendingMAXCount:
				return False
			nextQueue.enqueue(request)
			response = self.queue.waitForResponse(timeout)
			pendingCount += 1

		return response is qp['ACCEPTED']