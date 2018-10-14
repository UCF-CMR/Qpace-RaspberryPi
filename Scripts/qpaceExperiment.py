#! /usr/bin/env python3
# qpaceExperiment.py by Minh Pham, Jonathan Kessluk, Chris Britt
# 08-07-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import time
import qpaceLogger as logger

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
	SOL1   = 35
	SOL2   = 31
	SOL3   = 37
	SOLX   = 35
	SOLY   = 31
	SOLZ   = 37

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

def put(pin,state):
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

def low(pin):
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
	put(pin,0)

def high(pin):
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
	put(pin, 1)

def toggle(pin):
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
	put(pin,GPIO.input(pin)^1)

def flip(pin,delay=.1):
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
	put(pin,GPIO.input(pin)^1) # Invert the pin
	time.sleep(delay)
	put(pin,GPIO.input(pin)^1) # Put it back

def read(pin):
	return GPIO.input(pin)

def reset(pingroup=None):
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
			reset(PINGROUP.gopro)
			reset(PINGROUP.stepper)
			reset(PINGROUP.led)
			reset(PINGROUP.solenoid)
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

def gopro_on():
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
	high(PIN.GOPPWR) #Active High
	time.sleep(3)
	flip(PIN.GOPBUT,delay=1)
	time.sleep(5)

def press_capture():
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
	flip(PIN.GOPCAP,delay=.5)

def gopro_start():
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
	init_gopro() # Turn on camera and set mode
	logger.logSystem("ExpCtrl: Beginning to record")
	press_capture() # Begin Recording

def transOn():
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
	high(PIN.GOPDEN)

def transOff():
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
	low(PIN.GOPDEN)

def goProTransfer():
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
		logger.logSystem("ExpCtrl: Enabling the USB and mounting the drive...")
		transOn()
		time.sleep(3)
		import os
		try: # Mount the GoPro
			os.system('sudo mount /dev/sda1 '+MountPoint)
		except Exception as e:  # MOUNTING THE DRIVE FAILED
			logger.logError("ExpCtrl: Could not mount the drive", e)
		else:   # Mounting the drive was successful
			try:
				from shutil import move
				import re
				logger.logSystem("ExpCtrl: Moving video over to the Pi")
				files = os.listdir(GoProDirectory)
				for name in files:
					if re.match('.+\.(MP4|JPG)',name):
						os.system('cp '+GoProDirectory + name + ' ' + SavePoint)
			except Exception as e:  #Moving the file from the GOPRO failed
				logger.logError("ExpCtrl: Could not move the video", e)
			else: #Moving the file is successful
				try: # Delete all other uneccessary files
					logger.logSystem("ExpCtrl: Removing misc files from GoPro")
					for name in files:
						if re.match('.+\..+',name):
							os.system('sudo rm '+GoProDirectory+name)
				except Exception as e: # Could not delete the files
					logger.logError("ExpCtrl: Could not delete misc. files on the GoPro", e)
			logger.logSystem("ExpCtrl: Unmounting the USB")
			try: # Attempt to umount.
				os.system('sudo umount /dev/sda1')
			except Exception as e: # Failed to call the shell
				logger.logError("ExpCtrl: Could not unmount the drive", e)
		time.sleep(.25)
		transOff()

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

	def reverse():
		Stepper.nextState -= 2 # subtract 2 from the NEXT state to figure out the previous state
		put(PIN.STPENA, Stepper.rotationStates[Stepper.nextState%4][0])
		put(PIN.STPENB, Stepper.rotationStates[Stepper.nextState%4][1])
		Stepper.nextState += 1

def stepper_turn(delay, qturn,multiplier = 1):
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

def led(state):
	"""
	This function turns the LED light on or off.

	Parameters
	----------
	Boolean - power - To turn the LED on/off, power is set to True/False, respectively.

	Returns
	--------
	Void
	"""
	put(PIN.LEDPWR,state)

def solenoid_run(solenoidPin,hz,duration,override = False):
	if hz < 1:
		logger.logSystem('Solenoid: Hz was set <1. This makes no sense.')
		return
	elif hz > 12 and not override:
		logger.logSystem('Solenoid: Max is 12Hz, please override.')
		hz = 12

	period = 1/hz
	for i in range(duration/period):
		put(solenoidPin[i%len(solenoidPin)],0) # turn the solenoid on
		time.sleep(period/2)
		put(solenoidPin[i%len(solenoidPin)],1) # turn the solenoid off
		time.sleep(period/2)

def solenoid_ramp(solenoidPin, start_hz, end_hz, granularity=100,override = False):
	if start_hz < 1 or end_hz < 1:
		logger.logSystem('Solenoid: Hz was set <1. This makes no sense.')
		return
	elif (start_hz > 12 or end_hz > 12) and not override:
		logger.logSystem('Solenoid: Max is 12Hz, please override.')
		if start_hz > 12: start_hz = 12
		if end_hz > 12: end_hz = 12
	start_period = 1/start_hz
	end_period = 1/end_hz
	diff_period = (end_period/2) - (start_period/2)
	for i in range(granularity):
		print(1/(2*((start_period/2) + (diff_period/granularity)*i)))
		put(solenoidPin,0) # turn the solenoid on
		time.sleep((start_period/2) + (diff_period/granularity)*i)
		put(solenoidPin,1) # turn the solenoid off
		time.sleep((start_period/2) + (diff_period/granularity)*i)

def solenoid_tap(solenoidPin, hz=12):
	period = 1/hz # 12 hz (max speed)
	put(solenoidPin,0) # turn the solenoid on
	time.sleep(period/2)
	put(solenoidPin,1) # turn the solenoid off
	time.sleep(period/2)

def solenoid(solPins,iterations):
		"""
		This function handles the operation of the solenoids.

		Parameters
		----------
		List of Tuples - solPins - List that holds tuples of the form (<duty cycle>, <pin number>).
		Note: The duty cycle is listed first so that solPins.sort() will sort the pairs by their duty cycles.

		Returns
		-------
		None.

		"""
		solPins.sort()
		# Set all solenoids off by default
		put(PIN.SOLX, 1)
		put(PIN.SOLY, 1)
		put(PIN.SOLZ, 1)

		def fire(pin : tuple):
			put(pin[1], 0)		#Turn solenoid on
			time.sleep(.05)		# Punch the solenoid
			put(pin[1], 1)		#Turn solenoid off
			time.sleep(pin[0])	# Wait for duty cycle

		for i in range(0, iterations):
			fire(solPins[-1])
			for j in range(0, len(solPins) - 1):
				fire(solPins[j])

# The following methods may be uneccessary due to WTC mods.

# def wtc_enableStepper():
# 	# Add the stepper enable request to the queue and then wait for a response
# 	# Will return true if the stepper was enabled, will return false if the stepper was not enbaled
# 	try:
# 		from qpaceWTCHandler import NextQueue
# 	except ImportError:
# 		return False
#
# 	NextQueue.enqueue('STEPON')
# 	response = NextQueue.waitUntilEmpty(1)
# 	if response:
# 		# Get the item in the list. This will be the return of our request.
# 		return response[0]
# 	else:
# 		return False
#
# def wtc_enableSolenoid():
# 	# Add the stepper enable request to the queue and then wait for a response
# 	# Will return true if the stepper was enabled, will return false if the stepper was not enbaled
# 	try:
# 		from qpaceWTCHandler import NextQueue
# 	except ImportError:
# 		return False
#
# 	NextQueue.enqueue('SOLON')
# 	response = NextQueue.waitUntilEmpty(1)
# 	if response:
# 		# Get the item in the list. This will be the return of our request.
# 		return response[0]
# 	else:
# 		return False
#
# def disableAll():
# 	# Add the stepper enable request to the queue and then wait for a response
# 	# Will return true if the stepper was enabled, will return false if the stepper was not enbaled
# 	try:
# 		from qpaceWTCHandler import NextQueue
# 	except ImportError:
# 		return False
#
# 	NextQueue.enqueue('ALLOFF')
# 	response = NextQueue.waitUntilEmpty(1)
# 	if response:
# 		# Get the item in the list. This will be the return of our request.
# 		return response[0]
# 	else:
# 		return False