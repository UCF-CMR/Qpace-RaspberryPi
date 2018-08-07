#! /usr/bin/env python3
# experiment.py by Minh Pham, Jonathan Kessluk, Chris Britt
# 3-06-2018, Rev. 1.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import RPi.GPIO as GPIO
import time
import qpaceLogger as logger

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

class PIN():
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
	gopro = (PIN.GOPPWR,PIN.GOPBUT,PIN.GOPCAP,PIN.GOPDEN)
	solenoid = (PIN.SOL1,PIN.SOL2,PIN.SOL3)
	stepper = (PIN.STPEN,PIN.STPENA,PIN.STPENB)
	led = (PIN.LEDPWR)

def put(pin,state):
	GPIO.output(pin,state)

def low(pin):
	put(pin,0) # Clear the pin

def high(pin):
	put(pin, 1)# Set the pin

def toggle(pin):
	put(pin,GPIO.input(pin)^1) # Invert the pin

def flip(pin,delay=.1):
	put(pin,GPIO.input(pin)^1) # Invert the pin
	time.sleep(delay)
	put(pin,GPIO.input(pin)^1) # Put it back

def reset(pingroup=None):
	if pingroup is None:
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
	This function initializes all of the pins for the experiment.

	Parameters
	----------
	None.

	Returns
	-------
	None.

	"""
	print('\nNOTE: pinInit() is depreciated. Please use reset()\n')
	reset()
"""
The goPro section has been broken into several functions to allow the Pis to perform complex experiments without using multiple threads
"""

def init_gopro():
	#Turning on the device
	high(PIN.GOPPWR) #Active High
	time.sleep(3)
	flip(PIN.GOPBUT,delay=1)
	time.sleep(5)

def press_capture():
	flip(PIN.GOPCAP,delay=.5)
	logger.logSystem([["ExpCtrl: Initializing the GoPro"]])

def gopro_wait(recordingtime): #this just allows for long waits of continuous recording
	logger.logSystem([["ExpCtrl: GoPro is recording for " + recordingtime +" seconds"]])
	time.wait(recordingtime)


def gopro_start():
	init_gopro() # Turn on camera and set mode
	logger.logSystem([["ExpCtrl: Beginning to record"]])
	press_capture() # Begin Recording


def gopro_stop_and_USB():
	logger.logSystem([["ExpCtrl: Stopping recording..."]])
	press_capture() #Stop Recording

	#TURN USB ENABLE
	logger.logSystem([["ExpCtrl: Enabling the USB and mounting the drive..."]])
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
			logger.logSystem([["ExpCtrl: Moving video over to the Pi"]])
			files = os.listdir('/home/pi/gopro/DCIM/101GOPRO')
			for name in files:
				if re.match('.+\.(MP4|JPG)',name):
					os.system('cp /home/pi/gopro/DCIM/101GOPRO/'+name+ ' /home/pi/data/vid/')
		except Exception as e:	#Moving the file from the GOPRO failed
			logger.logError("ExpCtrl: Could not move the video", e)
		else: #Moving the file is successful
			try: # Delete all other uneccessary files
				logger.logSystem([["ExpCtrl: Removing misc files from GoPro"]])
				for name in files:
					if re.match('.+\..+',name):
						os.system('sudo rm /home/pi/gopro/DCIM/101GOPRO/'+name)
			except Exception as e: # Could not delete the files
				logger.logError("ExpCtrl: Could not delete misc files on the GoPro", e)
		logger.logSystem([["ExpCtrl: Turning off the GoPro and unmounting the USB"]])
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
	put(PIN.STEPENA, a)
	put(PIN.STEPENB, b)

#NOTE: Stepper code needs to be tested again

def stepper_forward(delay, qturn):
	"""
	This function activates the stepper motor in the forward direction.

	Parameters
	----------
	Integer / Float - delay - The time between each phase of the stepper motor.
	Integer - qturn - The number of turns.

	Returns
	-------
	None.

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
	None.

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
	"""
	put(PIN.LEDPWR,state)

def solenoid(solPins):
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
				time.sleep(pin[0])			#Waits for specific duty cycle
				put(pin[1], 1)		#Turn solenoid off

		for i in range(0, 10):
				fire(solPins[-1])
		for j in range(0, len(solPins) - 1):
				fire(solPins[j])