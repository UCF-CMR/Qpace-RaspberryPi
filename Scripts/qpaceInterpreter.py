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
from qpaceWTCHandler import initWTCConnection,NextQueue
from  qpacePiCommands import *
import tstSC16IS750 as SC16IS750
import SC16IS750
import qpaceLogger as logger
import qpaceStates as states
import qpaceFileHandler as fh

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
	#b'Upload File': Command.upFile, #TODO ????
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
			return False
	else:
		while(chip.byte_read(SC16IS750.REG_RXLVL) < n):
			time.sleep(interval)
	return True


def flushRxReg(chip):
	while(chip.byte_read(SC16IS750.REG_RXLVL) > 0):
		chip.byte_read(SC16IS750.REG_RHR)

def processIncomingPacketData(chip, fieldData):
	print("Interpreter is processing packet as Incoming Data.")
	if fieldData['noop'] == b'NOOP!':
		fh.Scaffold.finish(fieldData['information'])
	else:
		fh.Scaffold.construct(fieldData['pid'],fieldData['information'])
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
		# Magic numbers defined in Packet Specification Document
		if packetData[1:6] == b'NOOP*':
			packet = {
				"TYPE":			"XTEA",
				"route":       	packetData[0],
				"noop":			packetData[1:6],
				"xteaStartRand":packetData[6:10],
				"opcode":      	packetData[10:12],
				"information": 	packetData[12:102],
				"tag":			packetData[102:104],
				"xteaEndRand": 	packetData[104:110],
				"xteaPadding":	packetData[110:124],
				"checksum":    	packetData[124:]
			}
		elif packetData[1:6] == b'NOOP>' or packetData[1:6] == b'NOOP!':
			packet = {
				"TYPE":			"DATA",
				"route":		packetData[0],
				"noop":			packetData[1:6],
				"opcode":		packetData[1:6],
				"pid":			int.from_bytes(packetData[6:10],byteorder='big'),
				"information":	packetData[10:124],
				"checksum":		packetData[124:]
			}
		else:
			packet = {
				"TYPE":		   "NORM",
				"route":       packetData[0],
				"opcode":      packetData[1:6],
				"information": packetData[6:124],
				"checksum":    packetData[124:]
			}

		return packet #based on packet definition document

	def checkCyclicTag(tag):
		return True

	def checkValidity(fieldData):
		if fieldData['TYPE'] == 'XTEA':
			isValid = True
			#returnVal = PrivledgedPacket.decodeXTEA(fieldData['information'])
			#TODO add in XTEA encryption and decryption.
		elif fieldData['TYPE'] == 'DATA':
			isValid = True
		elif fieldData['TYPE'] == 'NORM':
			# return True,fieldData
			packetString = bytes([fieldData['route']]) + fieldData['opcode'] + fieldData['information']
			isValid = fieldData['route'] in (ROUTES.PI1ROUTE, ROUTES.PI2ROUTE,ROUTES.DEVELOPMENT) and fieldData['checksum'] == CMDPacket.generateChecksum(packetString)
		return isValid, fieldData

	def WTCRXBufferHandler(gpio,level,tick):
		packetData = chip.block_read(SC16IS750.REG_RHR,chip.byte_read(SC16IS750.REG_RXLVL))
		print("Data came in: ", packetData)
		chip.packetBuffer.append(packetData)
		# Manual testing. Remove for real test.
		#testData = b'\x01MANUL====\x00' + b'Q'*93 +b'EE======' + b'\x00'*12
		#packetData = testData + CMDPacket.generateChecksum(testData)

	def wtc_respond(response):
		if response in ss.SSCOMMAND:
			chip.byte_write(SC16IS750.REG_THR,bytes([ss.SSCOMMAND[response]]))
		else:
			chip.write(response)

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
				if byte == qpStates['NOOP']:
					logger.logSystem([['PseudoSM: NOOP.']])
					NextQueue.enqueue('NOOP')
				elif byte == qpStates['SHUTDOWN']:
					logger.logSystem([['PseudoSM: Shutdown was set!']])
					#NextQueue.enqueue('SHUTDOWN') # Just in case the interrupt is fired before shutting down.
					shutdownEvent.set()	# Set for shutdown
				elif byte == qpStates['REBOOT']:
					logger.logSystem([['PseudoSM: Reboot was set!']])
					#NextQueue.enqueue('SHUTDOWN')
					shutdownEvent.set()
				elif byte == qpStates['PIALIVE']:
					logger.logSystem([['PseudoSM: PIALIVE from WTC.']])
					wtc_respond('PIALIVE')
				elif byte == qpStates['TIMESTAMP']:
					logger.logSystem([['PseudoSM: TIMESTAMP from WTC.']])
					wtc_respond('TIMESTAMP')
					configureTimestamp = True
				elif byte == qpStates['WHATISNEXT']:
					wtc_respond(NextQueue.peek()) # Respond with what the Pi would like the WTC to know.
					if waitForBytesFromCCDR(chip,1,timeout=15): # Wait for 15s for a response from the WTC
						response = chip.read_byte(SC16IS750.REG_RHR) == qpStates['True']

						NextQueue.addResponse()
					else:
						NextQueue.addResponse(False)
				elif byte == qpStates['ERRNONE']:
					print('ERRNONE recv')
					pass
				elif byte == qpStates['ERRMISMATCH']:
					print('ERRMISMATCH recv')
					pass
				else:
					logger.logSystem([['PseudoSM: State existed for {} but a method is not written for it.'.format(str(byte))]])
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
							print('Packet has passed Validation.')
							print('OPCODE: ', fieldData['opcode'])
							#TODO Let ground station know that there is a valid thing
							if fieldData['opcode'] == fh.DataPacket.opcode or fieldData['opcode'] == b'NOOP!':
								processIncomingPacketData(chip,fieldData)
							elif fieldData['opcode'] in COMMANDS: # Double check to see if it's a command
								processCommand(chip,fieldData,fromWhom = 'CCDR')
							else:
								chip.packetBuffer.append(packetData)
						else:
							#TODO Alert the WTC? Send OKAY back to ground?
							print('Packet did NOT pass validation.')

			runEvent.wait() # Mutex for the run
			time.sleep(.5)  # wait for a moment

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
