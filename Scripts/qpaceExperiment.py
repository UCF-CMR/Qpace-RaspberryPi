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

class PINGROUP():
	"""
	Reason for Implementation
	-------------------------
	Tuples that represent functional groups of the pins.
	"""
	gopro = (PIN.GOPPWR,PIN.GOPBUT,PIN.GOPCAP,PIN.GOPDEN)
	solenoid = (PIN.SOL1,PIN.SOL2,PIN.SOL3)
	stepper = (PIN.STPEN,PIN.STPENA,PIN.STPENB)
	led = (PIN.LEDPWR)

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

def on(pin):
	"""
	DEPRECIATED
	-----------
	Use high() instead.
	"""
	print("\nThe on() method is depreciated. Please use high() next time.\n")
	high(pin)

def off(pin):
	"""
	DEPRECIATED
	-----------
	Use off() instead.
	"""
	print("\nThe off() method is depreciated. Please use low() next time.\n")

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
			GPIO.setup(PIN.SOL1, GPIO.OUT, initial=0)				#Solenoid 1
			GPIO.setup(PIN.SOL2, GPIO.OUT, initial=0)				#Solenoid 2
			GPIO.setup(PIN.SOL3, GPIO.OUT, initial=0)				#Solenoid 3
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

def pinInit():
	"""
	DEPRECIATED
	-----------
	Use reset() instead.
	"""
	print('\nNOTE: pinInit() is depreciated. Please use reset() next time.\n')
	reset()

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

def init_gopro():
	"""
	DEPRECIATED
	-----------
	Use gopro_on() instead.
	"""
	print('\nNOTE: init_gopro() is depreciated. Please use gopro_on() next time.\n')
	gopro_on()

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
		time.sleep(5)
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
		transOff()

def gopro_stop_and_USB():
	"""
	DEPRECIATED
	-----------
	Use individual methods to complete this task instead.
	"""
	print('\nNOTE: gopro_stop_and_USB() is depreciated.')
	print('Please use individual methods next time to accomplish this.')
	print('See documentation.\n')

	logger.logSystem("ExpCtrl: Stopping recording...")
	press_capture() #Stop Recording

	#TURN USB ENABLE
	logger.logSystem("ExpCtrl: Enabling the USB and mounting the drive...")
	high(PIN.GOPDEN)

	import os
	try: # Mount the GoPro
		os.system('sudo mount /dev/sda1 /home/pi/gopro')
	except Exception as e:	# MOUNTING THE DRIVE FAILED
		logger.logError("ExpCtrl: Could not mount the drive", e)
	else:	# Mounting the drive was successful
		try:
			from shutil import move
			import re
			logger.logSystem("ExpCtrl: Moving video over to the Pi")
			files = os.listdir('/home/pi/gopro/DCIM/101GOPRO')
			for name in files:
				if re.match('.+\.(MP4|JPG)',name):
					os.system('cp /home/pi/gopro/DCIM/101GOPRO/'+name+ ' /home/pi/data/vid/')
		except Exception as e:	#Moving the file from the GOPRO failed
			logger.logError("ExpCtrl: Could not move the video", e)
		else: #Moving the file is successful
			try: # Delete all other uneccessary files
				logger.logSystem("ExpCtrl: Removing misc files from GoPro")
				for name in files:
					if re.match('.+\..+',name):
						os.system('sudo rm /home/pi/gopro/DCIM/101GOPRO/'+name)
			except Exception as e: # Could not delete the files
				logger.logError("ExpCtrl: Could not delete misc files on the GoPro", e)
		logger.logSystem("ExpCtrl: Turning off the GoPro and unmounting the USB")
		try: # Attempt to umount.
			os.system('sudo umount /dev/sda1')
		except Exception as e: # Failed to call the shell
			logger.logError("ExpCtrl: Could not unmount the drive", e)
	#Turn off the gopro
	low(PIN.GOPPWR)
	time.sleep(.25)
	#reset pins to initial state
	reset(PINGROUP.gopro)

def setStep(a, b):
	"""
	Set the steppers to a and b for Stepper A and stepper B

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
	put(PIN.STPENA, a)
	put(PIN.STPENB, b)

def stepper_forward(delay, qturn):
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

	for i in range(0, qturn):
		setStep(0, 0)
		time.sleep(delay)
		setStep(1, 0)
		time.sleep(delay)
		setStep(1, 1)
		time.sleep(delay)
		setStep(0, 1)
		time.sleep(delay)

	time.sleep(3)

def stepper_reverse(delay, qturn):
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

	for i in range(0, qturn):
		setStep(1, 1)
		time.sleep(delay)
		setStep(1, 0)
		time.sleep(delay)
		setStep(0, 0)
		time.sleep(delay)
		setStep(0, 1)
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
		put(PIN.SOL1, 1)
		put(PIN.SOL2, 1)
		put(PIN.SOL3, 1)

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