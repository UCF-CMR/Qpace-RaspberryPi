#! /usr/bin/env python3
# experiment.py by Minh Pham
# 3-06-2018, Rev. 1.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import RPi.GPIO as GPIO
import time

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)

def pinInit():
	"""
	This function initializes the pins on the Pi.

	Parameters
    ----------
	None.

    Returns
    -------
    None.
    """
	#GoPro pin setup
	GPIO.setup(19, GPIO.OUT, initial=0)			#Power
	GPIO.setup(13, GPIO.OUT, initial=1)			#On Button
	GPIO.setup(15, GPIO.OUT, initial=1)			#Capture Button

	#Stepper pin setup
	GPIO.setup(33, GPIO.OUT, initial=0)			#Step Enable
	GPIO.setup(29, GPIO.OUT, initial=0)			#Step A Enable
	GPIO.setup(21, GPIO.OUT, initial=0)			#Step B Enable

	#LED pin setup
	GPIO.setup(23, GPIO.OUT)					#Controls the LEDs

    #Solenoid setup
	GPIO.setup(35, GPIO.OUT, initial=1)			#Solenoid 1
	GPIO.setup(31, GPIO.OUT, initial=1)			#Solenoid 2
	GPIO.setup(37, GPIO.OUT, initial=1)			#Solenoid 3

def goPro(recordingTime):
	"""
    This function handles GoPro operations.

    Parameters
    ----------
    Integer / Float - recordingTime - The desired time that the camera will be
    	recording for, in seconds.

    Returns
    -------
    None.

    """
	#Turning on the device
	GPIO.output(19, 1)
	sleep(3)
	GPIO.output(13, 0)
	sleep(1)
	GPIO.output(13, 1)
	sleep(10)

	#Begin Recording
	GPIO.output(15, 0)
	sleep(0.5)
	GPIO.output(15, 1)

	#Recording time
	sleep(recordingTime)

	#Stop Recording
	GPIO.output(15, 0)
	sleep(0.5)
	GPIO.output(15, 1)

	#Call Subprocess "hc-star" to enable USB hub
	print("Transfering Data...")
	#subprocess.call(["/home/pi/hc-start"])

	#Shutdown Device
	GPIO.output(13, 0)
	sleep(5)
	GPIO.outpit(13, 1)

	GPIO.output(19, 0)


def stepper(delay, qturn):
	"""
	This function handles stepper motor operations.

	Parameters
    ----------
    Float - delay - the delay between turns, in seconds.
	Int - qturn - the number of turn cycles.

	Returns
    -------
    None.
    """

    #Setstep definition
    def setStep(a, b):
        GPIO.output(29, a)
        GPIO.output(21, b)

	GPIO.output(33, True)

    #qturn
    for i in range(0, qturn):
        setStep(1, 1)
        time.sleep(delay)
        setStep(0, 1)
        time.sleep(delay)
        setStep(0, 0)
        time.sleep(delay)
        setStep(1, 0)
        time.sleep(delay)

    time.sleep(3)

    #reverse qturn
    for i in range(0, qturn):
        setStep(1, 1)
        time.sleep(delay)
        setStep(1, 0)
        time.sleep(delay)
        setStep(0, 0)
        time.sleep(delay)
        setStep(0, 1)
        time.sleep(delay)

	GPIO.output(33, False)
    #complete

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
		setStep(1, 1)
		time.sleep(delay)
		setStep(0, 1)
		time.sleep(delay)
		setStep(0, 0)
		time.sleep(delay)
		setStep(1, 0)
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
	"""
def led(power):
	"""
    This function handles LED operations.

	Parameters
    ----------
	List of Tuples - solPins - List that holds tuples of the form (<duty cycle>, <pin number>).
		Note: The duty cycle is listed first so that solPins.sort() will sort the pairs by their duty cycles.

	Returns
    -------
    None.
    """

	GPIO.output(23, power)

def solenoid(freq, duration, enables : list):
	"""
    This function handles the parsing and execution of the raw text experiment files.

    Parameters
    ----------
    Float - freq - The frequency that the solenoids will fire at, in Hertz.
	Float - duration - The time that the solenoids will be firing, in seconds.
	List of Ints - enables - A list determining which solenoids should be on (0 is off, otherwise on).

	Returns
    -------
    None.
    """

	counter = 0
	dutyCycle = 1 / freq
	# a pin is considered enabled if it is not 0.
	numEnabled = 3 - enables.count(0)

	pins = (35, 31, 37)

	while (numEnabled > 0 and counter < duration):
		for i in range(0, 3):
			if (enables[i] != 0):
				GPIO.output(pins[i], False)
				time.sleep(dutyCycle / (2 * numEnabled))
				GPIO.output(pins[i], True)
				time.sleep(dutyCycle / (2 * numEnabled))
				counter += dutyCycle / numEnabled
