#!/usr/bin/env python3
# RUT.py by Connor Westcott
# 9-17-2019, Rev. 0.1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida


# Raspberry Pi Unit Tester a.k.a R-PUT


import serial
import struct
import unittest
import time
import Packet_m
import xtea3

keys = [bytearray.fromhex('34136FF01241F34206194301F600987B'),  #Key0
        bytearray.fromhex('241569FDDC0146796DC0036000DC9801'),  #Key1
        bytearray.fromhex('0F11F6420F9DC321FF09FD4F56CA0A22'),  #key2
        bytearray.fromhex('00F0CDA6FF0FC0CD0F049930FFFFFFF0'),  #Key3
        bytearray("1234567887654321", 'utf8')]  #Key for PI

def encrypt(totalBitArray, maxInputSize=96):
	#Begin encryption stuff here
	cipherTotal = bytearray()
	intCipher = 0
	#shiftVal = 8*(maxInputSize-8)  #this is in bits, must convert
	sliceBegin = 0
	#totalBitArray = bytearray(combinedString, 'utf8')  #Note we have to have a bytes like object here
	#print(ascii(totalBitArray))
	iterRange = int(maxInputSize/8)
	for iter in range(iterRange):  #iterates from 0 to 96/8 -1 or
		slice = totalBitArray[sliceBegin: (sliceBegin+8)]  #Note this function splices from [n: m], meaning n inclusive, and m not inclusive
		cipherTotal += xtea3._encrypt(key=keys[4], block=slice, n=64)  # byteorder='big', signed=False)
		#shiftVal += (8*8)  #this works because it increments after everything, will max out at (96/8 - 8)*8
		sliceBegin += (8)
	intCipher = int.from_bytes(cipherTotal, byteorder='big', signed=False)
	return intCipher

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
	@classmethod
	def setUpClass(self, baud=115200):
		'''
		Open up the serial port to connect
		to the RPi on the Unit for testing
		to begin. 
		Note: Serial port will be supplied by user
		'''
		COM = input("WHAT IS SER PORT? ")
		self.ser = serial.Serial(COM, baud, timeout=2.0)
		
	@classmethod
	def tearDownClass(self):
		'''
		Close the serial port to release any
		permissions that may have been caused 
		by opening it. This will ensure that the 
		next test will be able to open the COM 
		port for testing
		'''
		self.ser.close()
		

	def test_1_Timestamp(self):
		'''Test to configure the timestamp
		on the Pi in order to move forward with other tests'''
		
		self.ser.write(b'B')
		resp = self.ser.read(128)
		self.assertEqual(resp, b'B') # Pi should return timestamp back to 'wtc'
		
		curTime = int(time.time())
		curTime = struct.pack("I", curTime)
		
		self.ser.write(curTime)
		resp = self.ser.read(128)
		self.assertEqual(resp, curTime)    


	def test_2_WHATISNEXT(self):
		'''
		Check to see if the RPi accepts WHATISNEXT
		and returns IDLE.
		
		IDLE is expected since nothing should be queued
		for the Pi to do. If something is in the queue to
		be done, then the Pi is remembering things it should
		not and there is next queue failure. 
		'''
		self.ser.write(b'J')
		#time.sleep(2)
		resp = self.ser.read(128)
		self.assertEqual(resp, b'H')


	def test_3_RunExperiment(self):
		'''
		Send the Pi a StartExp packet to turn the LED
		on and take a picture. This will make sure that
		the LED/Camera operations are functional before
		integration.
		
		
		'''
		packet = Packet_m.General_Pi_Packet()
		packet.SetRouting(0x01)
		packet.SetOpcode(packet.BytesToInt(b"NOOP*"))
		packet.SetRandoms()
		
		FilePath = 'se' + 'UT.ep' + (b'\x04'.decode('utf8'))*87 + 'AA'
		packet.SetFilePath(encrypt(bytearray(FilePath, 'utf8')))
		
		packet.BuildPacket()
		#packet.LoadPacekt(packet.DumpPacket())
		print(packet.DumpPacket().bytes)
		self.ser.write(packet.DumpPacket().bytes)
		
		print(self.ser.read(128))
		
		self.assertEqual(1, 3)
        
        
        
        
if __name__ == '__main__':
	unittest.main()
