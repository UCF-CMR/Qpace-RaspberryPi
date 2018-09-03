#!/usr/bin/env python3
# qpaceInterpreter.py by Jonathan Kessluk
# 4-19-2018, Rev. 1.5
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab incoming data from the WTC,
# Figure out if they are packets or commands. If it's a command it will execute the command
# and if they are packets it will direct them to the packet directory and then decode it.
#TODO: Re-do comments/documentation

import time
import pigpio
import datetime
from qpaceWTCHandler import initWTCConnection
from  qpacePiCommands import *
import SC16IS750
import qpaceLogger as logger
import qpaceStates as states
import qpaceFileHandler as fh

upNext = 'IDLE'
qpStates = states.QPCOMMAND
# Routing ID defined in packet structure document
class ROUTES():
	PI1ROUTE= 0x01
	PI2ROUTE= 0x02
	GNDROUTE= 0x00
	WTCROUTE= 0xFF
	DEVELOPMENT = 0x54 #'T'


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

def flushRxReg(chip):
	while(chip.byte_read(SC16IS750.REG_RXLVL) > 0):
		chip.byte_read(SC16IS750.REG_RHR)

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
			arguments = fieldData['information'] #These are bytes objects
		except UnicodeError:
			#TODO Alert ground of problem decoding command!
			raise BufferError("Could not decode ASCII bytes to string for command query.")
		else:
			logger.logSystem([["Interpreter: Command Received!",command,str(arguments)]])
			LastCommand.type = command
			LastCommand.timestamp = str(datetime.datetime.now())
			LastCommand.fromWhom = fromWhom
			COMMANDS[fieldData['opcode']](chip,command,arguments) # Run the command

def run(chip,experimentEvent, runEvent, shutdownEvent,rebootEvent):
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
	logger.logSystem([["Interpreter: Starting..."]])
	if chip is None:
		chip = initWTCConnection()
		if chip is None:
			raise ConnectionError("A connection could not be made to the CCDR.")

	# Initialize the pins
	gpio = pigpio.pi()
	gpio.set_mode(CCDR_IRQ, pigpio.INPUT)

	configureTimestamp = False


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
		isValid = fieldData['route'] in (ROUTES.PI1ROUTE, ROUTES.PI2ROUTE,ROUTES.DEVELOPMENT) and fieldData['checksum'] == CMDPacket.generateChecksum(packetString)
		if isValid and (fieldData['opcode'] == b'NOOP*' or fieldData['opcode'] == b'NOOP<'):
			returnVal = PrivledgedPacket.decodeXTEA(fieldData['information'])
			fieldData['opcode'] = returnVal[4:6] # 4:6 as defined in the packet structure document for XTEA packets
			fieldData['information'] = returnVal[6:98] # 6:98 as defined in the packet structure document for XTEA packets
			 # 98:100 and 106:118 as defined in the packet structure document for XTEA packets
			isValid = True# (returnVal[106:118] == b'\x00'*12) and checkCyclicTag(retVal[98:100])
		return isValid, fieldData

	def WTCRXBufferHandler(gpio,level,tick):
		packetData = chip.block_read(SC16IS750.REG_RHR,chip.byte_read(SC16IS750.REG_RXLVL))
		print("Data came in: ", packetData)
		chip.packetBuffer.append(packetData)
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
			if len(packetData) == 4:
				logger.logSystem([['PseudoSM: Configuring the timestamp.',str(byte)]])
				os.system("sudo date -s '@" + str(byte) +"'")
				chip.block_write(SC16IS750.REG_THR,packetData)
				configureTimestamp = False
			if byte in qpStates.values():
				# The byte was found in the list of SSCOMMANDs
				if byte == qpStates['SHUTDOWN']:
					logger.logSystem([['PseudoSM: Shutdown was set!']])
					upNext = 'SHUTDOWN' # Just in case the interrupt is fired before shutting down.
					shutdownEvent.set()	# Set for shutdown
					rebootEvent.clear()	# Clear for full shutdown, no reboot.
				elif byte == qpStates['REBOOT']:
					logger.logSystem([['PseudoSM: Reboot was set!']])
					upNext = 'REBOOT'	# Just in case the interrupt is fired before rebooting.
					shutdownEvent.set()	# Set for shutdown
					rebootEvent.set()	# Set for reboot instead of shutdown
				elif byte == qpStates['PIALIVE']:
					logger.logSystem([['PseudoSM: PIALIVE from WTC.']])
					wtc_respond('PIALIVE')
					upNext = 'IDLE' # Forces upNext to be IDLE if this is sent.
				elif byte == qpStates['TIMESTAMP']:
					logger.logSystem([['PseudoSM: TIMESTAMP from WTC.']])
					wtc_respond('TIMESTAMP')
					configureTimestamp = True
				elif byte == qpStates['WHATISNEXT']:
					print('WHATISNEXT? Sending back:',upNext)
					wtc_respond(upNext)	# Respond with what the Pi would like the WTC to know.
				elif byte == qpStates['ERRNONE']:
					print('ERRNONE recv')
					pass
				elif byte == qpStates['ERRMISMATCH']:
					print('ERRMISMATCH recv')
					pass
				else:
					logger.logSystem([['PseudoSM: Could not determine what to do. State existed but a method is not written for it.']])
		else:
			print('Input is not a valid WTC state.')
			return packetData, configureTimestamp
			#TODO the SSCOMMAND was not found to be legitimate. What do I do?

		return b'',configureTimestamp # Return nothing if the packetData was handled as a WTC command


	callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)
	logger.logSystem([['Interpreter: Callback active. Waiting for data from the SC16IS750.']])
	while not shutdownEvent.is_set():
		try:
			chunkPacket = fh.ChunkPacket(chip)
			while(len(chip.packetBuffer)>0):
				packetData = chip.packetBuffer.pop(0)
				packetData, configureTimestamp = surfSatPseudoStateMachine(packetData,configureTimestamp)
				if len(packetData) != 0:
					# Otherwise input is an actual packet
					# We'll just assume that the chunk is 32 bytes always. That's the WTC's job.
					chunkPacket.push(packetData)
					if chunkPacket.complete:
						packetData = chunkPacket.build()
						fieldData = splitPacket(packetData) # Return a nice dictionary for the packets
						# Check if the packet is valid. If it's XTEA, decode it.
						isValid,fieldData = checkValidity(fieldData)
						if isValid:
							print('Input is valid')
							print('OPCODE: ', fieldData['opcode'])
							#TODO Let ground station know that there is a valid thing
							if fieldData["opcode"] in COMMANDS: # Double check to see if it's a command
								processCommand(chip,fieldData,fromWhom = 'CCDR')
							else:
								chip.packetBuffer.append(packetData)
						else:
							#TODO Alert the WTC? Send OKAY back to ground?
							print('Input is NOT valid!')

			runEvent.wait() #Mutex for the run
			time.sleep(.5) # wait for a moment

		except KeyboardInterrupt:
			continue
		except StopIteration:
			break
	logger.logSystem([["Interpreter: Starting cleanup for shutdown."]])
	#decoder = Decoder(file_location,TEMP_PACKET_LOCATION,suppress=True,rush=True)
	#decoder.run(True)

	callback.cancel()
	chip.close()
	gpio.stop()
	logger.logSystem([["Interpreter: Shutting down..."]])