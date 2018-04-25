#! /usr/bin/env python3
# experiment.py by Minh Pham
# 3-06-2018, Rev. 1.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida

import RPi.GPIO as GPIO
import time

GPIO.setwarning(False)
GPIO.setmode(GPIO.BOARD)

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

	#GoPro pin setup
	GPIO.setup(19, GPIO.OUT, initial=0)				#Power
	GPIO.setup(13, GPIO.OUT, initial=1)				#On Button
	GPIO.setup(15, GPIO.OUT, initial=1)				#Capture Button

	#Stepper pin setup
	GPIO.setup(33, GPIO.OUT, initial=0)				#Step Enable
	GPIO.setup(29, GPIO.OUT, initial=0)				#Step A Enable
	GPIO.setup(21, GPIO.OUT, initial=0)				#Step B Enable

	#LED pin setup
	GPIO.setup(23, GPIO.OUT)						#Controls the LEDs
    
    #Solenoid setup
    GPIO.setup(35, GPIO.OUT)						#Solenoid 1
    GPIO.setup(31, GPIO.OUT)						#Solenoid 2
    GPIO.setup(37, GPIO.OUT)						#Solenoid 3


def goPro(recordingTime):
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
    
def led(power):
	"""
	This function turns the LED light on or off.

	Parameters
	----------
	Boolean - power - To turn the LED on/off, power is set to True/False, respectively.
	"""
	GPIO.output(23, power)

def solenoid(solPins : list):
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
       	time.sleep(pin[0])				#Waits for specific duty cycle
        GPIO.output(pin[1], True)		#Turn solenoid off

    for i in range(0, 10):
		fire(solPins[-1])
		for j in range(0, len(solPins) - 1):
	    	fire(solPins[j])







