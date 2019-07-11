#! /usr/bin/env python3
# qpaceExperiment.py by Minh Pham, Jonathan Kessluk, Chris Britt
# 08-07-2018, Rev. 3
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import time
import datetime
import os
from subprocess import check_output
from qpaceLogger import Logger as qpLog


try:
	import RPi.GPIO as GPIO
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
except:
	#print("Unable to import RPi.GPIO")
	pass

# Go pro items are depreciated
# GoProDirectory = '/home/pi/gopro/DCIM/101GOPRO/'
# MountPoint = '/home/pi/gopro'
PICTUREPATH = '/home/pi/data/pic/'
VIDEOPATH = '/home/pi/data/vid/'
MAX_PENDING_DELTA = 300 # in seconds



class Camera():
	"""
	View documentation https://www.raspberrypi.org/documentation/raspbian/applications/camera.md

	"For frame rates over 120fps, it is necessary to turn off automatic exposure and gain control using -ex off.
	 Doing so should achieve the higher frame rates, but exposure time and gains will need to be set to fixed values supplied by the user."
	"""


	exposureModes = ['off','auto','night','sports','snow','beach','fixedfps','antishake']
	whiteBalanceModes = ['off','auto','sun','cloud','tungsten','fluorescent','incandescent']
	imxfxModes = ['none','negative','solarise','oilpaint','saturation','blackboard','whiteboard']
	modes = [0,1,2,3,4,5,6,7]

	class CameraConfigurationError(Exception):
		def __init__(self,message=None):
			if message:
				super().__init__(message)
			else:
				super().__init__('PiCam Configuration is Invalid.')
	class CameraProcessFailed(Exception):
		def __init__(self,reason=None,exitCode=''):
			if not reason:
				reason ='execute'
			if exitCode:
				exitCode = 'Exit Code {}.'.format(exitCode)
			super().__init__('PiCam failed to {}. {}'.format(reason,exitCode))

	def __init__(self):
		"""
		Constructor for the Camera() class

		Parameters: None

		Returns: None

		Raises: None

		"""
		self.attr = {
			'fps': None,
			'w': None,
			'h': None,
			'q': None, # Only used for images
			'sh': None,
			'ci': None,
			'co': None,
			'br': None,
			'sa': None,
			'vs': False,
			'ex': None,
			'awb': None,
			'ifx': None,
			'cfx': None, #tuple (U,V)
			'rot': None,
			'hf': None,
			'vf': None,
			'roi': (0.15,0.10,0.70,0.90), #tuple (x,y,w,h) DEFAULT VALUES (I spent a time on finding these so please use them)
			'md': 0,  # check documentation.
			'a': None, # Annotations. Verification does not cover this. Only use when using the documentation to support you.
			'ae': None # Annotation Parameters. Verification does not cover this. Only use when using the documentation to support you.
		}

	@classmethod
	def getSettings():
		"""
		Get the settings from the raspiCam

		Parameters: None

		Returns: The output of the raspivid --settings command as a string

		Raises: None

		"""
		return check_output(['raspivid','--settings'])

	def getSettings(self):
		"""
		Get the settings from the raspiCam

		Parameters: None

		Returns: The output of the raspivid --settings command as a string

		Raises: None

		"""
		return Camera.getSettings()

	def set(self,**kwargs):
		"""
		Set settings for the piCam.

		Parameters: kwargs that relate to the dictionary above.
		            All the kwargs should be valid raspivid parameters.
		            Furthermore, all kwargs should follow the shorthand or error checking will not take place.

		Returns:

		Raises:

		"""
		for key,value in kwargs.items():
			if key in self.attr:
				#print("Appending (Key, Value): ({0}, {1})".format(key, value))
				self.attr[key] = value


	def verifySettings(self):
		"""
		Check all the settings if they were set and see if they fall within the valid range of the PiCam.
		This is just to avoid errors when running the raspivid command.

		Parameters: None

		Returns: None

		Raises: CameraConfigurationError() if a setting is invalid.

		"""
		if self.attr['sh'] and (self.attr['sh'] < -100 or self.attr['sh'] > 100):
			raise CameraConfigurationError('Sharpness must be set between -100 and 100.')
		if self.attr['co'] and (self.attr['co'] < -100 or self.attr['co'] > 100):
			raise CameraConfigurationError('Contrast must be set between -100 and 100.')
		if self.attr['br'] and (self.attr['br'] < 0 or self.attr['br'] > 100):
			raise CameraConfigurationError('Brightness must be set between 0 and 100.')
		if self.attr['sa'] and (self.attr['sa'] < -100 or self.attr['sa'] > 100):
			raise CameraConfigurationError('Saturation must be set between -100 and 100.')
		if self.attr['vs'] and (self.attr['vs'] is not True and self.attr['vs'] is not False):
			raise CameraConfigurationError('Video stabilisation must be set to True or False.')
		if self.attr['ex'] and (self.attr['ex'] not in exposureModes):
			raise CameraConfigurationError('Exposure must be set to a value in exposureModes.')
		if self.attr['awb'] and (self.attr['awb'] not in whiteBalanceModes):
			raise CameraConfigurationError('White balance must be set to a value in whiteBalanceModes.')
		if self.attr['ifx'] and (self.attr['ifx'] not in imxfxModes):
			raise CameraConfigurationError('Image effects must be set to a value in imxfxModes.')
		if self.attr['cfx']:
			if type(self.attr['cfx']) is tuple and len(self.attr['cfx']) is 2:
				if self.attr['cfx'][0] < 0 or self.attr['cfx'][0] > 255 or self.attr['cfx'][1] < 0 or self.attr['cfx'][1] > 255 :
					raise CameraConfigurationError('U or Y value must be between 0 and 255.')
			else:
				raise CameraConfigurationError('Color effects must be set as a tuple where the values are (U,Y) for the U or Y channels of the image.')
		if self.attr['rot'] and (self.attr['rot'] < 0 or self.attr['rot'] > 359):
			self.attr['rot'] = self.attr['rot'] % 360
		if self.attr['hf'] and (self.attr['hf'] is not True and self.attr['hf'] is not False):
			raise CameraConfigurationError('Horizontal Flip must be True or False.')
		if self.attr['vs'] and (self.attr['vf'] is not True and self.attr['vf'] is not False):
			raise CameraConfigurationError('Vertical Flip must be True or False.')
		if self.attr['roi']:
			if type(self.attr['roi']) is tuple and len(self.attr['roi']) is 4:
				for item in self.attr['roi']:
					if item < 0 or item > 1:
						raise CameraConfigurationError('Region of Interest values must be between 0 and 1.')
			else:
				raise CameraConfigurationError('Region of interest must be a tuple representing (x,y,w,h) the x,y for the top left and width and height.')
		if self.attr['md'] and self.attr['md'] not in modes:
			raise CameraConfigurationError('Camera mode must be in the mode list (0 - 7)')

		# if not self.attr['w']:
		# 	raise CameraConfigurationError('Define a width.')
		# if not self.attr['h']:
		# 	raise CameraConfigurationError('Define a height.')
		# if not self.attr['fps']:
		# 	raise CameraConfigurationError('Define an FPS between 0.1 and 200.')

		if self.attr['md'] and self.attr['fps']:
			if self.attr['md'] is 1:
				if self.attr['fps'] <.1 or self.attr['fps'] >30:
					raise CameraConfigurationError('Mode 1: FPS Must be 0.1-30.')
			elif self.attr['md'] is 2:
				if self.attr['fps'] <.1 or self.attr['fps'] >15:
					raise CameraConfigurationError('Mode 2: FPS Must be 0.1-15.')
			elif self.attr['md'] is 3:
				if self.attr['fps'] <.1 or self.attr['fps'] >15:
					raise CameraConfigurationError('Mode 3: FPS Must be 0.1-15.')
			elif self.attr['md'] is 4:
				if self.attr['fps'] <.1 or self.attr['fps'] >40:
					raise CameraConfigurationError('Mode 4: FPS Must be 0.1-40.')
			elif self.attr['md'] is 5:
				if self.attr['fps'] <.1 or self.attr['fps'] >40:
					raise CameraConfigurationError('Mode 5: FPS Must be 0.1-40.')
			elif self.attr['md'] is 6:
				if self.attr['fps'] <40 or self.attr['fps'] >90:
					raise CameraConfigurationError('Mode 6: FPS Must be 40-90.')
			elif self.attr['md'] is 7:
				if self.attr['fps'] <40 or self.attr['fps'] >200:
					raise CameraConfigurationError('Mode 7: FPS Must be 40-200.')
		if self.attr['q']:
			if self.attr['q'] < 0 or self.attr['q'] > 100:
				raise CameraConfigurationError('JPEG Quality must be set between 0-100. 100 is uncompressed.')

	def capture(self,filename=None):
		"""
		Run raspistill and take a picture instead of a video

		Parameters:
		filename - optional - filename of the file to save

		Returns: None

		Raises:
		CameraConfigurationError() if a setting is invalid
		CameraProcessFailed() if it could not capture.

		"""
		self.verifySettings()
		if not filename:
			filename = 'picam_{}'.format(str(round(time.time()*100)))
		query = ['raspistill']
		if self.attr['h']:
			query.append('-h')
			query.append(str(self.attr['h']))
		if self.attr['w']:
			query.append('-w')
			query.append(str(self.attr['w']))
		if self.attr['q']:
			query.append('-q')
			query.append(str(self.attr['q']))
		if self.attr['roi']:
			query.append('-roi')
			x, y, w, h = self.attr['roi'] 
			query.append("{},{},{},{}".format((x,y,w,h)))
		else:
			query.append('-q')
			query.append('75')

		query.append('-o')
		query.append('{}{}.jpg'.format(PICTUREPATH,filename))
		#print("QUERY: ", query)
		ret = os.system(' '.join(query)) # Take the picture
		if ret:
			raise Camera.CameraProcessFailed('capture',ret)

	def record(self,time=None,filename=None):
		"""
		Run raspivid and record a video

		Parameters:
		Time - the time in milliseconds for the camera to record
		filename - optional - the filename to save as

		Returns: None

		Raises:
		CameraConfigurationError if no time is given or setting is invalid
		CameraProcessFailed if it could not record

		"""
		self.verifySettings()
		if not filename:
			filename = 'picam_{}'.format(str(round(time.time()*100)))

		if not time or type(time) is not int or time < 0:
			raise CameraConfigurationError('Must set time to record in milliseconds.')

		query = ['raspivid']
		for option,value in self.attr.items():
			if value:
				if option is 'cfx':
					value = '{}:{}'.format(value[0],value[1])
				if option is 'roi':
					value = ','.join(value)

				query.append('-{}'.format(option))
				query.append(value)

		query.append('-t')
		query.append(str(time))
		query.append('-o')
		query.append('{}{}.h264'.format(VIDEOPATH,filename))

		# Build the command to execute the raspivid stuffs
		piCamQuery = ' '.join(query)
		# Build the command to add the MP4 wrapper
		mp4Wrapper = 'MP4Box -add {}{}.h264 {}{}.mp4'.format(VIDEOPATH,filename,VIDEOPATH,filename)
		# Build the command to remove the raw video after the mp4 video is made
		removalQuery = 'rm {}{}.h264'.format(VIDEOPATH,filename)
		# Execute all of them. Use && so each one only executes with the success of them all. use & to plit the thread
		ret = os.system('{} && {} && {} &'.format(piCamQuery,mp4Wrapper,removalQuery))
		if ret:
			CameraProcessFailed('PiCam && Conversion && removal',ret)


class PIN():
	"""
	Pin handler class. Each class variable is an alias for the pin assignment.
	"""
	GOPPWR = 19 # Gopro power. No longer used.
	GOPBUT = 13 # Gopro Mode button.
	GOPCAP = 15 # Gopro Capture button.
	GOPDEN = 40 # Gopro data enable. High implies USB plugged in
	LEDPWR = 23 # LED Power
	STPEN  = 33	# Stepper motor enable. No longer used
	STPENA = 29 # Stepper coil A
	STPENB = 21 # Stepper coil B
	SOLX   = 37 # Solinoid for the X plane. Side opposite to stepper.
	SOLY   = 35 # Solinoid for the Y plane.
	SOLZ   = 31 # Solinoid for the Z plane.

class PINGROUP():
	"""
	Tuples that represent functional groups of the pins.
	"""
	gopro = (PIN.GOPBUT,PIN.GOPCAP,PIN.GOPDEN)#,PIN.GOPPWR)
	solenoid = (PIN.SOLX,PIN.SOLY,PIN.SOLZ)
	stepper = (PIN.STPENA,PIN.STPENB)#,PIN.STPEN)
	led = (PIN.LEDPWR,)

class Stepper():
	"""
	Class that handles maintaining state for the stepper motors. featurs rotating forward and backwards.
	"""
	rotationStates = {
		0: (0,0),
		1: (1,0),
		2: (1,1),
		3: (0,1)
	}
	nextState = 0

	@staticmethod
	def forward(action):
		"""
		Rotates the stepper forward by one step.

		Parameters: an Action object, can be self

		Returns: None

		Raises: None

		"""
		action.put(PIN.STPENA, Stepper.rotationStates[Stepper.nextState%4][0])
		action.put(PIN.STPENB, Stepper.rotationStates[Stepper.nextState%4][1])
		Stepper.nextState += 1

	@staticmethod
	def reverse(action):
		"""
		Rotates the stepper backwards by one step

		Parameters: an Action object, can be self

		Returns: None

		Raises: None

		"""
		Stepper.nextState -= 2 # subtract 2 from the NEXT state to figure out the previous state
		action.put(PIN.STPENA, Stepper.rotationStates[Stepper.nextState%4][0])
		action.put(PIN.STPENB, Stepper.rotationStates[Stepper.nextState%4][1])
		Stepper.nextState += 1

class Action():
	"""
	Class that handles all the methods relating to the experiment control aspect of the spacecraft.
	An object of this class must be created to run the ETC.
	"""
	#GoPro is Depreciated
	GoProIsOn = False

	def __init__(self,logger=None,queue=None):
		"""
		Constructor class for Action()

		Parameters:
		logger - optional - only useful for flight operation. For testing this can be omitted.
		queue - optional - the nextQueue. Only useful for flight, not for testing.

		Returns: None

		Raises: None

		"""
		if logger is None:
			class DummyLogger():
				def logSystem(self,*x): print('System: {}'.format(x))
				def logError(self,*x): print('Error:  {}'.format(x))
				def logData(self,*x): print('Data:   {}'.format(x))
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

		Parameters:
		pin - pin to set to the specific state
		state - low or high, 0 or 1, true or false

		Returns: None

		Raises: None

		"""
		GPIO.output(pin,state)

	def low(self,pin):
		"""
		Clear a pin

		Parameters:
		pin - the pin you'd like to clear

		Returns: None

		Raises: None

		"""
		self.put(pin,0)

	def high(self,pin):

		"""
		Set a pin

		Parameters:
		pin - the pin you'd like to set

		Returns: None

		Raises: None

		"""
		self.put(pin, 1)

	def toggle(self,pin):
		"""
		Toggle a pin

		Parameters:
		pin - the pin you'd like to toggle

		Returns: None

		Raises: None

		"""
		self.put(pin,GPIO.input(pin)^1)

	def flip(self,pin,delay=.1):
		"""
		Toggle a pin, wait, and then reset the pin bck to its initial state.
		Similar to pressing a button.

		Parameters:
		pin - the pin you'd like to flip
		delay - optional - the delay in seconds to wait before reverting the pin.


		Returns: None

		Raises: None

		"""
		self.put(pin,GPIO.input(pin)^1) # Invert the pin
		time.sleep(delay)
		self.put(pin,GPIO.input(pin)^1) # Put it back

	def read(self,pin):
		"""
		Read the current value of a pin

		Parameters:
		pin - the pin you'd like to read

		Returns: The value low or high of the pin

		Raises: None

		"""
		return GPIO.input(pin)

	def reset(self,pingroup=None):
		"""
		Initialize the pins to their efault states.
		If a pingroup is supplied, then only reset that pin group

		Parameters:
		pingroup - pingroup tuple - the PINGROUP tuple you'd like to reset. If None is supplied, reset All

		Returns: None

		Raises: None

		"""
		try:
			GPIO
		except NameError:
			#print("GPIO is not defined, the pins were not reset!")
			pass
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
				#GPIO.setup(PIN.STPEN, GPIO.OUT, initial=1)				#Step Enable
				GPIO.setup(PIN.STPENA, GPIO.OUT, initial=0)				#Step A Enable
				GPIO.setup(PIN.STPENB, GPIO.OUT, initial=0)				#Step B Enable


			# elif pingroup == PINGROUP.gopro:
			# 	#GOPRO IS DEPRECIATED
			# 	self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
			# 	#GoPro pin setup
			# 	#GPIO.setup(PIN.GOPPWR, GPIO.OUT, initial=0)				#Power
			# 	GPIO.setup(PIN.GOPBUT, GPIO.OUT, initial=1)				#On Button
			# 	GPIO.setup(PIN.GOPCAP, GPIO.OUT, initial=1)				#Capture Button
			# 	GPIO.setup(PIN.GOPDEN, GPIO.OUT, initial=0)
			# 	#gopro_off(True) # Flip the data enable to ensure that the gopro is off.


	def gopro_on(self):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		if not self.GoProIsOn:
			self.flip(PIN.GOPBUT,delay=2.33)
			time.sleep(1.75)


	def gopro_off(self,forceOff=False):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		if forceOff:
			self.flip(PIN.GOPDEN,delay=2.33)
		elif self.GoProIsOn:
			self.flip(PIN.GOPBUT,delay=2.33)
			time.sleep(1.75)

	def press_capture(self):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		self.flip(PIN.GOPCAP,delay=.5)

	def gopro_start(self):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		self.init_gopro() # Turn on camera and set mode
		self.logger.logSystem("ExpCtrl: Beginning to record")
		self.press_capture() # Begin Recording

	def transOn(self):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		self.high(PIN.GOPDEN)

	def transOff(self):
		""" DEPRECIATED """
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
		self.low(PIN.GOPDEN)

	def goProTransfer(self):
		""" DEPRECIATED"""
		self.logger.logSystem('GO PRO METHODS ARE DEPRECIATED')
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
							os.system('cp '+GoProDirectory + name + ' ' + VIDEOPATH)
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
		Activates the stepper motor in the forward direction

		Parameters:
		delay - how long in seconds between each turn
		qturn - how many qturns to do
		multiplier - optional - the actual number of turns is qturn * multiplier

		Returns: None

		Raises: None

		"""
		if qturn > 0:
			# Multiply * 4 because we are doing qTurns
			for i in range(0, qturn*multiplier):
				Stepper.forward(self)
				time.sleep(delay)
		else:
			for i in range(0, -qturn*multiplier): #qturn is already negative so make it positive
				Stepper.reverse(self)
				time.sleep(delay)
		time.sleep(3)

	def led(self,state):
		"""
		Turns the LED on or Off

		Parameters:
		state - 0 or 1, False or True

		Returns: None

		Raises: None

		"""
		self.put(PIN.LEDPWR,state)

	def solenoid_run(self,solenoidPins,hz=1,duration=0,override = False):
		"""
		Runs the solenoids at a constant rate.

		Parameters:
		solenoidPins - a Tuple of the pins that the solenoids are.
		hz - the rate in hz of how quickly the solenoids should fire
		duration - how long they should fire for
		override - optional - In testing, the fastest that was beneficial is 12hz. Anything over that requires the override flag.

		Returns: None

		Raises: None

		"""
		if hz < 1:
			self.logger.logSystem('Solenoid: Hz was set <1. This makes no sense.')
			return
		elif hz > 12 and not override:
			self.logger.logSystem('Solenoid: Max is 12Hz, please override.')
			hz = 12

		period = 1/hz
		for pinSelect in range(int(duration//period)):
			self.put(solenoidPins[pinSelect%len(solenoidPins)],1) # turn the solenoid on
			time.sleep(period/2)
			self.put(solenoidPins[pinSelect%len(solenoidPins)],0) # turn the solenoid off
			time.sleep(period/2)

		self.reset(PINGROUP.solenoid)

	def solenoid_ramp(self,solenoidPins, start_hz, end_hz, granularity=100,override = False):
		"""
		Ramps the solenoids from one HZ to another HZ

		Parameters:
		solenoidPins - a Tuple of the pins that the solenoids are.
		start_hz - the rate in hz of how quickly the solenoids should fire. This is the starting HZ
		end_hz - the rate in hz of how quickly the solenoids should fire. This is the goal to achieve
		granularity - optional - larger granularity, slower the change
		override - optional - In testing, the fastest that was beneficial is 12hz. Anything over that requires the override flag.

		Returns:None

		Raises:None

		"""
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
			self.put(solenoidPins[pinSelect%len(solenoidPins)],1) # turn the solenoid on
			time.sleep((start_period/2) + (diff_period/granularity)*i)
			self.put(solenoidPins[pinSelect%len(solenoidPins)],0) # turn the solenoid off
			time.sleep((start_period/2) + (diff_period/granularity)*i)
			pinSelect += 1

		self.reset(PINGROUP.solenoid)

	def solenoid_tap(self,solenoidPins, hz=12):
		"""
		Tap the solenoid one time.

		Parameters:
		solenoidPins - a Tuple of the pins that the solenoids are.
		hz - optional - how quickly to pull back the piston

		Returns:


		Raises:

		"""
		period = 1/hz # 12 hz (max speed)
		for pin in solenoidPins:
			self.put(pin,1) # turn the solenoid on
			time.sleep(period/2)
			self.put(pin,0) # turn the solenoid off
			time.sleep(period/2)

		self.reset(PINGROUP.solenoid)

	def wtc_request(self,request,pendingTimeout=MAX_PENDING_DELTA,responseTimeout=5):
		"""
		Adds a request to the NextQueue and waits for a response. There is a timeout though!

		Return TRUE for request ACCEPTED; Return FALSE for request DENIED.
		If PENDING is returned, continue to enqueue until a response is received.

		To avoid an infinite loop, count up how many pendings we've received. Should we get more than
		a lot of pendings, then back out and assume denied.

		Parameters:
		request - str - the request to be made to the wtc
		pendingTimeout - optional - the time to wait on PENDING to change to another state
		responseTimeout - optional - the time to wait until there is a response from the wtc.


		Returns: True if the response is ACCEPTED. False if it's anything else.

		Raises: None

		"""
		try:
			from qpaceControl import QPCONTROL as qp
		except ImportError:
			return False

		pendingMAXCount = pendingTimeout // responseTimeout
		pendingCount = 0
		response = qp['PENDING']
		while response is qp['PENDING']:# or response is None: # None implies timeout
			if pendingCount > pendingMAXCount:
				return False
			self.queue.enqueue(request)
			response = self.queue.waitForResponse(responseTimeout)
			pendingCount += 1

		return response is qp['ACCEPTED']

