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

def off(pin):
	GPIO.output(pin,0)

def on(pin):
	GPIO.output(pin,1)

def reset(pingroup):
	if pingroup == PINGROUP.led:
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
	reset(PINGROUP.gopro)
	reset(PINGROUP.stepper)
	reset(PINGROUP.led)
	reset(PINGROUP.solenoid)

def goProOn():
	logger.logSystem([["ExpCtrl: Initializing the GoPro."]])
	#Turning on the device
	on(PIN.GOPPWR) #Active High
	time.sleep(2.25)
	# Press the button
	off(PIN.GOPBUT) #Active Low
	time.sleep(.75)
	on(PIN.GOPBUT)
	time.sleep(5)

def goProCapToggle():
	logger.logSystem([["ExpCtrl: Pressing capture button."]])
	off(PIN.GOPCAP) #Active Low
	time.sleep(.75)
	on(PIN.GOPCAP)

def goProOff():
	logger.logSystem([["ExpCtrl: Turning the GoPro off."]])
	#Turn off the gopro
	off(PIN.GOPPWR)
	time.sleep(.25)
	#reset pins to initial state
	reset(PINGROUP.gopro)

def goProTransfer():
	time.sleep(1)
	if GPIO.input(PIN.GOPPWR):
		#TURN USB ENABLE
		logger.logSystem([["ExpCtrl: Enabling the USB and mounting the drive..."]])
		on(PIN.GOPDEN)

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

def goProRec(recordingTime):
	"""
	This function activates the GoPro camera.

	Parameters
	----------
	Integer / Float - recordingTime - The desired time that the camera will be
	recording for, in seconds.

	Returns
	-------
	None.
	"""

	def init_gopro():
		#Turning on the device
		on(PIN.GOPPWR) #Active High
		time.sleep(.75)
		off(PIN.GOPBUT) #Active Low
		time.sleep(1)
		on(PIN.GOPBUT)
		time.sleep(10)
	def press_capture():
		off(PIN.GOPCAP) #Active Low
		time.sleep(0.75)
		on(PIN.GOPCAP)
	logger.logSystem([["ExpCtrl: Initializing the GoPro"]])
	init_gopro() #Turn on camera and set mode
	logger.logSystem([["ExpCtrl: Beginning to record for "+ recordingTime +" seconds."]])
	press_capture() #Begin Recording
	time.sleep(recordingTime) #Delay for recording time
	logger.logSystem([["ExpCtrl: Stopping recording..."]])
	press_capture() #Stop Recording

	#TURN USB ENABLE
	logger.logSystem([["ExpCtrl: Enabling the USB and mounting the drive..."]])
	on(PIN.GOPDEN)

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
	off(PIN.GOPPWR)
	time.sleep(.25)
	#reset pins to initial state
	reset(PINGROUP.gopro)

def stepper(delay, qturn):
		"""
		This function activates the stepper motor.

		Parameters
		----------
		Integer / Float - delay - The time between each phase of the stepper motor.
		Integer - qturn - The number of turns.

		Returns
		-------
		None.

		"""
		#Setstep definition

		def setStep(a, b):
			GPIO.output(29, a)
			GPIO.output(21, b)

		#qturn
		'''
		for i in range(0, qturn):
		setStep(1, 0, 1, 0)
		time.sleep(delay)
		setStep(0, 1, 1, 0)
		time.sleep(delay)
		setStep(0, 1, 0, 1)
		time.sleep(delay)
		setStep(1, 0, 0, 1)
		time.sleep(delay)
		setStep(1, 0, 1, 0)
		time.sleep(delay)

		'''


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

		#reverse qturn
		'''
		for i in range(0, qturn):
		setStep(1, 0, 1, 0)
		time.sleep(delay)
		setStep(1, 0, 0, 1)
		time.sleep(delay)
		setStep(0, 1, 0, 1)
		time.sleep(delay)
		setStep(0, 1, 1, 0)
		time.sleep(delay)
		setStep(1, 0, 1, 0)
		time.sleep(delay)
		'''

		for i in range(0, qturn):
				setStep(1, 1)
				time.sleep(delay)
				setStep(1, 0)
				time.sleep(delay)
				setStep(0, 0)
				time.sleep(delay)
				setStep(0, 1)
				time.sleep(delay)

		#complete

def led(power):
	"""
	This function turns the LED light on or off.

	Parameters
	----------
	Boolean - power - To turn the LED on/off, power is set to True/False, respectively.
	"""
	if power:
		on(PIN.LEDPWR)
	else:
		off(PIN.LEDPWR)

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
		GPIO.output(35, True)
		GPIO.output(31, True)
		GPIO.output(37, True)

		def fire(pin : tuple):
				GPIO.output(pin[1], False)		#Turn solenoid on
				time.sleep(pin[0])			#Waits for specific duty cycle
				GPIO.output(pin[1], True)		#Turn solenoid off

		for i in range(0, 10):
				fire(solPins[-1])
		for j in range(0, len(solPins) - 1):
				fire(solPins[j])







