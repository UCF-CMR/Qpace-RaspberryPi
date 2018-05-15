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
	GPIO.setup(35, GPIO.OUT, initial=1)					#Solenoid 1
	GPIO.setup(31, GPIO.OUT, initial=1)					#Solenoid 2
	GPIO.setup(37, GPIO.OUT, initial=1)					#Solenoid 3


def goPro(recordingTime):
	#Turning on the device
	GPIO.output(19, 1)
	time.sleep(3)
	GPIO.output(13, 0)
	time.sleep(1)
	GPIO.output(13, 1)
	time.sleep(10)

	#Begin Recording
	GPIO.output(15, 0)
	time.sleep(0.5)
	GPIO.output(15, 1)

	#Recording time
	time.sleep(recordingTime)

	#Stop Recording
	GPIO.output(15, 0)
	time.sleep(0.5)
	GPIO.output(15, 1)

	#Call Subprocess "hc-star" to enable USB hub
	#print("Transfering Data...")
	#subprocess.call(["/home/pi/hc-start"])

	#Shutdown Device
	GPIO.output(13, 0)
	time.sleep(5)
	GPIO.output(13, 1)

	GPIO.output(19, 0)


def stepper(delay, qturn):
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

def led(power):
	GPIO.output(23, power)

def solenoid(solPins : list, duration):
"""
solPins is a list of tuples, each containing a frequency (in Hz) and a solenoid
pin number (<freq, pinNum>).

duration is the total time, in seconds, for which the solenoids will be firing.
"""
	solPins.sort()
	counter = 0

	def fire(pin : tuple):
		if (pin[0] > 0):
			dutyCycle = 1 / pin[0]
			GPIO.output(pin[1], False)		#Turns solenoid on
			time.sleep(dutyCycle / 2)		#Waits for half of the duty cycle
			GPIO.output(pin[1], True)		#Turns solenoid off
			time.sleep(dutyCycle / 2)
			counter += dutyCycle			#increments counter

	#counter maintains how long the solenoids have been firing.
	while (counter < duration):
		for i in range(0, len(solPins)):
			fire(solPins[i])

def solenoid(freq, duration):
	counter = 0
