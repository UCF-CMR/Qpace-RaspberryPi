#!/usr/bin/env python3
# RUT.py by Connor Westcott
# 9-17-2019, Rev. 0.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida


# Raspberry Pi Unit Tester a.k.a R-PUT


import serial
import unittest

class RPUT(unittest.TestCase):
	'''
	A UnitTest class for testing all the functionallity of
	the Raspberry Pi code on the EM or Flight Models to 
	validate the integrety and function of the RPi code.
	
	This will consist on smaller tests that will
	validate all possible operations the RPi can do.
	As well as tests to run through the most common
	commands and sequences that are expected for 
	successful mission on the RPi's part.
	'''

	def setUp(self, COM, baud=115200):
		'''
		Open up the serial port to connect
		to the RPi on the Unit for testing
		to begin. 
		Note: Serial port will be supplied by user
		'''
		self.ser = serial.Serial(COM, baud)
		
	def tearDown(self):
		'''
		Close the serial port to release any
		permissions that may have been caused 
		by opening it. This will ensure that the 
		next test will be able to open the COM 
		port for testing
		'''
		self.ser.close()
		
	def test_WHATISNEXT(self):
		'''
		Check to see if the RPi accepts WHATISNEXT
		and returns IDLE.
		
		IDLE is expected since nothing should be queued
		for the Pi to do. If something is in the queue to
		be done, then the Pi is remembering things it should
		not and there is next queue failure. 
		'''
		self.ser.write(0x4A)
		resp = self.ser.read(128, timeout=1.0)
		self.assertEqual(resp, 0x48)