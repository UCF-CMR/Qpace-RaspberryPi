#!/usr/bin/env python3
# qpaceInterpreter.py by Jonathan Kessluk
# 4-19-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab incoming data from the WTC,
# Figure out if they are QUIP packets or commands. If it's a command it will execute the command
# and if they are QUIP packets it will direct them to the packet directory and then decode it.
#TODO: Re-do comments/documentation

import time
import SC16IS750
import pigpio
import datetime
from qpaceWTCHandler import initWTCConnection
from qpaceQUIP import Packet,Decoder
from  qpacePiCommands import *
import qpaceLogger as logger
import surfsatStates as ss

INTERP_PACKETS_PATH = "temp/packets/"
# Routing ID defined in packet structure document
PI1ROUTE = 0X01
PI2ROUTE = 0X02
GNDROUTE = 0X00
WTCROUTE = 0XFF

ssStates = ss.SSCOMMAND
ssErrors = ss.SSERRORS


# Add commands to the map. Format is "String to recognize for command" : function name
COMMANDS = {
	b'STATS': 		Command.status,
	b'ls': 			Command.directoryListingSet,
	b'dl': 			Command.directoryList,
	b'mv': 			Command.move,
	b'tb': 			Command.tar,
	b'DOWNR': 		Command.dlReq,
	b'DWNLD': 		Command.dlFile,
	b'up': 			Command.upReq,
	b'Upload File': Command.upFile, #TODO ????
	b'MANUL': 		Command.manual
}

class LastCommand():
	"""
	Small handler class to help with figuring out which command was the last command sent.
	Similar to just using a struct in C.
	"""
	type = "No commands received"
	timestamp = "Never"
	fromWhom = "N/A"

def waitForBytesFromCCDR(chip,n,timeout = 2.5,interval = 0.25):
	if timeout:
		total_attempts = timeout//interval
		attempts = 0
		while(attempts < total_attempts and chip.byte_read(SC16IS750.REG_RXLVL) is not n):
			time.sleep(interval)
			attempts += 1

		if attempts >= total_attempts:
			logger.logSystem([["WaitForBytesFromCCDR: Timeout occurred. Moving on."]])
	else:
		while(chip.byte_read(SC16IS750.REG_RXLVL) < n):
			time.sleep(interval)

def sendBytesToCCDR(chip,sendData):
	"""
	Send a string or bytes to the WTC. This method, by default, is dumb. It will pass whatever
	is the input and passes it directly on to the CCDR.

	Parameters
	----------
	chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
	sendData - a string or bytes that we want to send to the WTC (Can be large block)

	Raises
	------
	TypeError - thrown if sendData is not a string or bytes
	"""
	if isinstance(sendData,str):
		sendData = sendData.encode('ascii')
	elif isinstance(sendData,int):
		sendData = bytes([sendData])
	elif not isinstance(sendData,bytes) and not isinstance(sendData,bytearray):
		logger.logSystem([['Data will not be sent to the WTC: not string or bytes.']])
		raise TypeError("Data to the WTC must be in the form of bytes or string")
	try:
		chip.block_write(SC16IS750.REG_THR, sendData)
	except Exception as err:
		#TODO do we actually handle the case where it just doesn't work?
		print(err)
		logger.logError('sendBytesToCCDR: An error has occured when attempting to send data to the WTC. Data to send:' + str(sendData),err)
		pass
	else:
		return True
	return False

def flushRxReg(chip):
	while(chip.byte_read(SC16IS750.REG_RXLVL) > 0):
		chip.byte_read(SC16IS750.REG_RHR)

def readDataFromCCDR(chip):
	"""
	Read in data from the CCDR. This method will block and wait until the data has been read in.

	Parameters
	----------
	chip - instance of the chip used on the CCDR

	Returns
	-------
	buf - bytes of the data read in. Should be 128 bytes or 1 byte.

	Raises
	------
	BufferError - If we can't read from the CCDR for some reason.
	"""
	buf = b''
	time_to_wait = 5#s
	time_to_sleep = .4#s
	numOfAttempts = (time_to_wait//time_to_sleep) + 1
	while(True):
		waiting = chip.byte_read(SC16IS750.REG_RXLVL)
		print('Waiting: ', waiting)
		if waiting <= 4 and waiting > 0:
			for i in range(waiting):
				buf += bytes([chip.byte_read(SC16IS750.REG_RHR)])
			byte = int.from_bytes(buf,byteorder='little')
			break
		elif waiting > 4:
			print('Assuming a packet...')
			#We'll assume if it's not 1 byte, that it's going to be a 128 byte packet.
			for i in range(0,4): #We will receive 4, 32 byte chunks to make a 128 packet

				attempt = 0
				while(True):
					waiting = chip.byte_read(SC16IS750.REG_RXLVL)
					print('Packet Waiting: ', waiting)
					try:
						sleep(time_to_sleep)
						attempt += 1
						# See how much we want to read.
						if waiting > 32:   # If we have 32 bytes in the level register
							logger.logSystem([["Reading in "+ str(waiting) +" bytes from the CCDR"]])
							for i in range(waiting):
								# Read from the chip and write to the buffer.
								buf += bytes([chip.byte_read(SC16IS750.REG_RHR)])




						if attempt == numOfAttempts:
							raise BlockingIOError("Timeout has occurred...")

					except BlockingIOError:
						# TODO Write the start over methods.
						# TODO Alert WTC?
						# TODO log it!
						pass
					except BufferError as err:
						logger.logError("A BufferError was thrown.",err)
						raise BufferError("A BufferError was thrown.") from err
				chip.byte_read(SC16IS750.REG_RHR)# Clear the buffer. WTC will send ERRNONE
			break
		time.sleep(.75)




	return buf



def processCommand(chip, fieldData, fromWhom = 'CCDR'):
	"""
	Split the command from the arguments and then run the command as expected.

	Parameters
	----------
	chip - SC16IS750() - an SC16IS750 object to read/write from/to
	query- bytes - the command string.
	fromWhom - string - a string to denote who sent the command. If fromWhom is not provided, assume the WTC.

	Raises
	------
	ConnectionError - If a connection to the WTC was not passed to the command
	BufferError - Could not decode bytes to string for command query.
	"""

	if not chip:
		raise ConnectionError("Connection to the CCDR not established.")
	if fieldData:
		try:
			command = fieldData['opcode'].decode('ascii')
			arguments = fieldData['information'].decode('ascii')
		except UnicodeError:
			#TODO Alert ground of problem decoding command!
			raise BufferError("Could not decode ASCII bytes to string for command query.")
		else:
			arguments = arguments.split(' ')
			logger.logSystem([["Command Received:",command,str(arguments)]])
			LastCommand.type = command
			LastCommand.timestamp = str(datetime.datetime.now())
			LastCommand.fromWhom = fromWhom
			COMMANDS[fieldData['opcode']](chip,command,arguments) # Run the command

#TODO FIX QUIP, possibly remove.
def processQUIP(chip = None,buf = None):
	"""
	Take the data in the buffer and write files to it. We will assume they are QUIP packets.

	Paramters
	---------
	chip - SC16IS750() - an SC16IS750 object to read/write from/to
	buf - bytes - the input buffer from the WTC

	Returns
	-------
	missedPackets - List - a list of missing packets.

	Raises
	------
	BufferError - If the buffer is empty, assume that there was a problem.
	ConnectionError - If the connection to the WTC was not passed to this method.
	"""
	if not chip:
		raise ConnectionError("Connection to the CCDR not established.")
	if not buf:
		raise BufferError("Buffer is empty, no QUIP data received.")

	logger.logSystem([["Processing input as QUIP packets.", "Packets Received: " + str(len(buf))]])
	if len(buf) > 0:
		missedPackets = []
		attempt = 0

		def _writePacketToFile(packetID,dataToWrite):
			with open(INTERP_PACKETS_PATH+str(packetID)+ ".qp",'wb') as f:
				f.write(b'D'+dataToWrite)

		for i in range(0,len(buf)):
			try:
				# Create an int from the 4 bytes
				packetID = struct.unpack('>I',buf[i][:Packet.header_size])[0]
			except:
				missedPackets.append(str(i))
			else:
				try:
					# Write that packet
					_writePacketToFile(packetID,buf[i])
				except:
					# If we failed, try again
					try:
						_writePacketToFile(packetID,buf[i])
					except:
						#If we failed, consider the packet lost and then carry on.
						missedPackets.append(str(packetID))
		logger.logSystem([["Attempted to write all packets to file system."],
						  ["Missing packets: ", str(missedPackets) if missedPackets else "None"]])
		return missedPackets
	else:
		return []

def run(chip,experimentEvent, runEvent, shutdownEvent):
	"""
	This function is the "main" purpose of this module. Placed into a function so that it can be called in another module.

	Parameters
	----------
	Nothing

	Returns
	-------
	Nothing

	Raises
	------
	ConnectionError - if the CCDR cannot be connected to for some reason.
	BufferError - if the FIFO in the WTC cannot be read OR the buffer was empty.
	InterruptedError - if another InterruptedError was thrown.
	All other exceptions raised by this function are passed up the stack or ignored and not raised at all.
	"""
	CCDR_IRQ = 16
	TEMP_PACKET_LOCATION = 'temp/packets/'
	logger.logSystem([["Beginning the WTC Interpreter..."]])
	if chip is None:
		chip = initWTCConnection()
		if chip is None:
			raise ConnectionError("A connection could not be made to the CCDR.")

	# Initialize the pins
	gpio = pigpio.pi()
	gpio.set_mode(CCDR_IRQ, pigpio.INPUT)

	configureTimestamp = False
	packetBuffer = []

	class ChunkPacket():
		chunks = []
		complete = False

		def push(self,data):
			if not self.complete:
				self.chunks.append(data)
				#Acknowledge WTC with chunk number
				sendBytesToCCDR(chip,0x60 + len(self.chunks)) # Defined by WTC state machine
				print('Chunk:' ,len(self.chunks))
				if len(self.chunks) == 4: # We are doing 4 chunks!
					self.complete = True
			else:
				print('Chunk is complete')
				self.complete = True

		def build(self):
			print('Building a packet!')
			packet = b''
			for chunk in self.chunks:
				packet += chunk
			if len(packet) != 128: print("Packet is not 128 bytes!") #TODO what should we actually do here.
			self.chunks[:] = []
			self.complete = False
			return packet

	def splitPacket(packetData):
		packet = {
			"route":       packetData[0],
			"opcode":      packetData[1:6],
			"information": packetData[6:124],
			"checksum":    packetData[124:]
		}
		return packet #based on packet definition document

	def checkCyclicTag(tag):
		return True

	def checkValidity(fieldData):
		# return True,fieldData
		packetString = bytes([fieldData['route']]) + fieldData['opcode'] + fieldData['information']
		isValid = fieldData['route'] in (PI1ROUTE, PI2ROUTE) and fieldData['checksum'] == CMDPacket.generateChecksum(packetString)
		if isValid and (fieldData['opcode'] == b'NOOP*' or fieldData['opcode'] == b'NOOP<'):
			returnVal = PrivledgedPacket.decodeXTEA(fieldData['information'])
			fieldData['opcode'] = returnVal[4:6] # 4:6 as defined in the packet structure document for XTEA packets
			fieldData['information'] = returnVal[6:98] # 6:98 as defined in the packet structure document for XTEA packets
			 # 98:100 and 106:118 as defined in the packet structure document for XTEA packets
			isValid = True# (returnVal[106:118] == b'\x00'*12) and checkCyclicTag(retVal[98:100])
		return isValid, fieldData

	def WTCRXBufferHandler(gpio,level,tick):
		packetData = chip.block_read(SC16IS750.REG_RHR,chip.byte_read(SC16IS750.REG_RXLVL))#readDataFromCCDR(chip)
		packetBuffer.append(packetData)
		print("Data came in: ", packetData)
		# Manual testing. Remove for real test.
		#testData = b'\x01MANUL====\x00' + b'Q'*93 +b'EE======' + b'\x00'*12
		#packetData = testData + CMDPacket.generateChecksum(testData)



	def wtc_respond(response):
		chip.byte_write(SC16IS750.REG_THR,ss.SSCOMMAND[response])

	def surfSatPseudoStateMachine(packetData,configureTimestamp):
		# Start looking at a pseduo state machine so WTC code doesn't need to change
		if len(packetData) == 1 or (len(packetData) == 4 and configureTimestamp):
			byte = int.from_bytes(packetData,byteorder='little')
			print('byte: ', byte)
			#print('States: ',byte in ssStates.values())
			#print('Errors: ',byte in ssErrors.values())
			if len(packetData) == 4:
				print('configuring timestamp')
				#timestamp = int.from_bytes(timestampBytes, byteorder="little")
				os.system("sudo date -s '@" + str(byte) +"'")
				print('Sending back: ', packetData)
				chip.block_write(SC16IS750.REG_THR,packetData)
				print('Configuration is complete! :D')
				configureTimestamp = False
			if byte in ssStates.values() or byte in ssErrors.values():
				# The byte was found in the list of SSCOMMANDs
				if byte == ssStates['SHUTDOWN']:
					print('shutdown state!')
					sendBytesToCCDR(chip,ssStates['SHUTDOWN'])
					shutdownEvent.set()
				elif byte == ssStates['PIALIVE']:
					print('Sending PIALIVE')
					wtc_respond('PIALIVE')

				elif byte == ssStates['TIMESTAMP']:
					print('Sending TIMESTAMP')
					wtc_respond('TIMESTAMP')
					configureTimestamp = True
					#os.system("sudo date -s '@" + str(timestamp) +"'")
					#sendBytesToCCDR(chip,str(timestampBytes))

					# Then we are done?
					# response = readDataFromCCDR(chip)
					# wtc_respond('CONFIGURATION')
				elif byte == ssErrors['ERRNONE']:
					print('ERRNONE recv')
					pass
				elif byte == ssErrors['ERRMISMATCH']:
					print('ERRMISMATCH recv')
					pass

				else:
					print("Could not determine what to do. State existed but a method was not written for it.")
		else:
			print('Input was not a valid WTC state.')
			return packetData, configureTimestamp
			#TODO the SSCOMMAND was not found to be legitimate. What do I do?

		return b'',configureTimestamp # Return nothing if the packetData was handled as a WTC command


	callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)
	while True:
		try:
			packet = ChunkPacket()
			while(len(packetBuffer)>0):
				packetData = packetBuffer.pop(0)
				packetData, configureTimestamp = surfSatPseudoStateMachine(packetData,configureTimestamp)
				if len(packetData) != 0:
					# Otherwise input is an actual packet
					# We'll just assume that the chunk is 32 bytes always. That's the WTC's job.
					packet.push(packetData)
					if packet.complete:
						packetData = packet.build()
						fieldData = splitPacket(packetData) # Return a nice dictionary for the packets
						# Check if the packet is valid. If it's XTEA, decode it.
						isValid,fieldData = checkValidity(fieldData)
						if isValid:
							print('Input is valid')
							print('OPCODE: ', fieldData['opcode'])
							if fieldData["opcode"] in COMMANDS: # Double check to see if it's a command
								processCommand(chip,fieldData,fromWhom = 'CCDR')
							else:
								packetBuffer.append(packetData)
						else:
							#TODO Alert the WTC? Send OKAY back to ground?
							print('Input is NOT valid!')

				if shutdownEvent.is_set():
					logger.logSystem([["Shutdown flag was set."]])
					raise StopIteration("It's time to shutdown!")

			runEvent.wait() #Mutex for the run
			time.sleep(.5) # wait for a moment

		except KeyboardInterrupt:
			shutdownEvent.set()
			break
		except StopIteration:
			break

	#decoder = Decoder(file_location,TEMP_PACKET_LOCATION,suppress=True,rush=True)
	#decoder.run(True)

	callback.cancel()
	chip.close()
	gpio.stop()
	logger.logSystem([["Interpreter: Shutting down..."]])