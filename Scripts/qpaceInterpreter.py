#!/usr/bin/env python3
# qpaceInterpreter.py by Jonathan Kessluk
# 9-30-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Credit to the SurfSat team for CCDR driver and usage.
#
# The interpreter will be invoked when pin 7 goes high. This will grab incoming data from the WTC,
# Figure out if they are packets or commands. If it's a command it will execute the command
# and if they are packets it will direct them to the packet directory and then decode it.

try:
	import pigpio
except:
	pass

try:
	import xtea3
except:
	pass
import time
import datetime
import os
from struct import pack
from  qpacePiCommands import generateChecksum, Command
import tstSC16IS750 as SC16IS750
import SC16IS750
import qpaceControl
import qpaceFileHandler as fh

qpStates = qpaceControl.QPCONTROL

SECRETS = '/qctrl.secret'
SECRETS = 'qctrl.secret' #TODO Remove for flight

WHATISNEXT_WAIT = 2 #in seconds
packetBuffer = [] #TODO Possibly remove for flight. Not really an issue. used for debugging
# Routing ID defined in packet structure document
validRoutes = (0x01,0x02,0x54) # Pi1, Pi2, Gnd, WTC, Dev
# Add commands to the map. Format is "String to recognize for command" : function name
cmd = Command() # Creates an instance for the Command class so we can pass the packetQueue into it.
COMMANDS = {
	b'st': 	cmd.status,
	b'ls': 	cmd.directoryListingSet,
	b'dl': 	cmd.directoryList,
	b'mv': 	cmd.move,
	b'te': 	cmd.tarExtract,
	b'tc':	cmd.tarCreate,
	b'dr': 	cmd.dlReq,
	b'df': 	cmd.dlFile,
	b'sv':	cmd.splitVideo,
	b'cv':	cmd.convertVideo,
	b'up': 	cmd.upReq,
	b'is':	cmd.immediateShutdown,
	b'hb':  cmd.runHandbrake,
	b'se':	cmd.startExperiment
}

class LastCommand():
	"""
	Reason for Implementation
	-------------------------
	Small handler class to help with figuring out which command was the last command received.
	Similar to just using a struct in C.

	"""
	type = "No commands received"
	timestamp = "Never"
	fromWhom = "N/A"
	commandCount = 0

	@staticmethod
	def set(a, b, c):
		LastCommand.type = a
		LastCommand.timestamp = b
		LastCommand.fromWhom = c
		LastCommand.commandCount += 1

def waitForBytesFromCCDR(chip,n,timeout = 2.5,interval = 0.25):
	"""
	Returns true when the number of bytes in the buffer is equal to n
	Returns false when timeout occurs

	Parameters
	----------
	chip - SC16IS750 Object
	n - int - How many bytes to wait for.
	timeout - int - How long in seconds to wait for those bytes. DEFAULT 2.5s
					If timeout is None or 0, check without a timeout.
	interval - int - How often to check if N bytes are in the buffer. DEFAULT .25s

	Returns
	-------
	True if there are N bytes in the read buffer.
	False if timeout.

	Raises
	------
	Any exception gets poppuped up the stack.
	"""
	if interval > timeout:
		interval = .25
	total_attempts = timeout//interval
	attempts = 0
	if timeout:
		while(attempts < total_attempts and chip.byte_read(SC16IS750.REG_RXLVL) is not n):
			time.sleep(interval)
			attempts += 1

		if attempts >= total_attempts:
			return False
	else:
		while(chip.byte_read(SC16IS750.REG_RXLVL) < n):
			time.sleep(interval)
	return True

def run(chip,nextQueue,packetQueue,experimentEvent, runEvent, shutdownEvent, logger):
	"""
	This function is the "main" purpose of this module. Placed into a function so that it can be called in another module.

	Parameters
	----------
	chip - an SC16IS750 object
	experimentEvent - threading.Event - if set an Experiment is running.
	runEvent - threading.Event - if set, do not wait. Otherwise, this acts like a wait-until-set flag
								 used to pause execution.
	shutdownEvent - threading.Event -  if set, begin shutdown procedures.

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
	logger.logSystem("Interpreter: Starting...")
	if chip is None:
		e = ConnectionError('The SC16IS750 is not connected. The Interpreter can not run.')
		logger.logError(str(e),e)
		raise e

	enc_key = None
	enc_iv = None
	try:
		# This file will be found in the root directory.
		with open(SECRETS,'rb') as fi:
			enc_key = fi.readline()
			enc_iv = fi.readline()
	except Exception as e:
		# If we can't even attempt to decode XTEA packets, then there's no reason to run QPACE though...
		logger.logError('Interpreter: Unable to import keys. XTEA Decoding is disabled.',e)

	try:
		# Initialize the pins
		gpio = pigpio.pi()
		gpio.set_mode(CCDR_IRQ, pigpio.INPUT)
	except NameError:
		print('PIGPIO is not defined. Unable to set interrupt')
		gpio = None

	configureTimestamp = False

	global packetBuffer #TODO Possibly remove for flight. Not really an issue used for debugging
	packetBuffer = []
	callback = None

	cmd.packetQueue = packetQueue # set the packet queue so we can append packets.
	cmd.nextQueue = nextQueue
	lastPacketsSent = []

	def decodeXTEA(packetData):
		header = packetData[:10]
		footer = packetData[104:]
		# Note if there's not key or IV that the packet gets passed through. If this happens and it's not decoded, it won't really do anything. It'll fail validation.
		try:
			if not enc_key or not enc_iv:
				raise RuntimeError('No encryption key or IV')
			information = xtea3.new(enc_key,mode=xtea.MODE_OFB,IV=enc_iv).decrypt(packetData[10:104])
		except:
			information = packetData[10:104]

		return header + information + footer



	def decodePacket(packetData):
		"""
		Takes a string of packet data and splits it up into a dictionary of fields.

		Parameters
		----------
		packetData - byte string - full 128 byte packet.

		Returns
		-------
		dictionary

		Raises
		------
		Any exception gets popped up the stack.
		"""
		# Magic numbers defined in Packet Specification Document
		if packetData[1:6] == b'NOOP*':
			packetData = decodeXTEA(packetData)
			packet = {
				"TYPE":			"NORM",
				"route":       	packetData[0],
				"noop":			packetData[1:6],
				"xteaStartRand":packetData[6:10],
				"command":      packetData[10:12],
				"information": 	packetData[12:102],
				"tag":			packetData[102:104],
				"xteaEndRand": 	packetData[104:110],
				"xteaPadding":	packetData[110:124],
				"checksum":    	packetData[124:],
				"contents":		packetData[6:124]
			}
		elif packetData[1:6] in fh.DataPacket.valid_opcodes:
			packet = {
				"TYPE":			"DATA",
				"route":		packetData[0],
				"noop":			packetData[1:6],
				"opcode":		packetData[1:6],
				"pid":			packetData[6:10],
				"information":	packetData[10:124],
				"checksum":		packetData[124:],
				"contents":		packetData[6:124]
			}
		elif packetData[1:6] == b'DLACK':
			packet = {
				'TYPE':		 "DLACK",
				'route': 	 packetData[0],
				'opcode': 	 packetData[1:6],
				'response':  packetData[6:10],
				'gibberish': packetData[10:124],
				'checksum':  packetData[124:],
				'contents':  packetData[6:124]
			}
		else:
			packet = {
				"TYPE":		   "UNKNOWN",
				"route":       packetData[0],
				"opcode":      packetData[1:6],
				"information": packetData[6:124],
				"checksum":    packetData[124:],
				"contents":		packetData[6:124]
			}

		return packet #based on packet definition document

	def processIncomingPacketData(chip, fieldData):
		"""
		Route data that comes in that is determined to be a packet of data.
		Valid data packets are packets with a 'NOOP>' or 'NOOP!' opcode.

		Parameters
		----------
		chip - an SC16IS750 Object
		fieldData - dictionary - dictionary created by calling decodePacket()

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.

		"""
		if fh.UploadRequest.isActive():
			if fieldData['noop'] == b'NOOP!':
				match,who = fh.Scaffold.finish(fieldData['information'])
				logger.logSystem('UploadRequest: Upload Request has been cleared for {}'.format(who))
				if match:
					logger.logSystem('Scaffold: The Upload was successful')
				else:
					logger.logSystem('Scaffold: The Uploaded file does not match the checksum with ground')

			elif fieldData['noop'] == b'NOOP>':
				fh.Scaffold.construct(fieldData['pid'],fieldData['information'])
			else:
				logger.logSystem("Interpreter: A packet is interpreted as data, but its opcode isn't correct.")

		#TODO Remove for flight!!!
		if not fh.UploadRequest.isActive():
			print('UPLOAD REQUEST NOT ACTIVE')

	def processCommand(chip, fieldData, fromWhom = 'WTC'):
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
				command = fieldData['command'].decode('ascii')
				arguments = fieldData['information'] #These are bytes objects
			except UnicodeError:
				#TODO Alert ground of problem decoding command!
				raise BufferError("Could not decode ASCII bytes to string for command query.")
			else:
				logger.logSystem("Interpreter: Command Received! <{}>".format(command))
				LastCommand.set(command, str(datetime.datetime.now()), fromWhom)
				COMMANDS[fieldData['command']](chip,logger,command,arguments) # Run the command

	def isValidTag(tag):
		"""
		To be implemented.
		Will check the tag to see if it is a valid tag coming in and if it hasn't been used in the recent past.

		Parameters
		----------
		tag - bytes - a 2 byte tag.

		Returns
		-------
		True if the tag is valid
		False if the tag is invalid

		Raises
		------
		Any exception gets popped up the stack.
		"""
		return True

	def checkValidity(fieldData):
		"""
		Check to see if a packet coming in is valid.

		Parameters
		----------
		fieldData - dictionary - must be data that has come from decodePacket()

		Returns
		-------
		isValid - Boolean - True: The packet is valid
							False: The packet is not valid
		fieldData - dictionary - Allows the dictionary to be passed through and edited.

		Raises
		------
		Any exception gets popped up the stack.
		"""
		# Figure out the data without the checksum
		if fieldData['TYPE'] == 'UNKNOWN':
			isValid = False
			fieldData = None
		else:
			packetString = bytes([fieldData['route']]) + fieldData['opcode'] + fieldData['contents']
			isValid = fieldData['route'] in validRoutes and fieldData['checksum'] == generateChecksum(packetString)

		if fieldData['TYPE'] == 'DATA':
			if fieldData['opcode'] == b'NOOP>':
				if isValid:
					response = b'GOOD'
				else:
					response = b'REPT'
				packetQueue.enqueue(cmd.PrivilegedPacket(opcode='NOOP>',tag='AA',plainText=fieldData['pid'] + response + cmd.PrivilegedPacket.returnRandom(86)))
				nextQueue.enqueue('SENDPACKET')
		elif fieldData['TYPE'] == 'NORM':
			#TODO tag implementation
			pass
		elif fieldData['TYPE'] == 'DLACK':
			# Honestly, I don't think there's anything to do here...
			pass

		return isValid, fieldData

	def WTCRXBufferHandler(gpio,level,tick):
		"""
		Callback method to handle data coming from the SC16IS750. When the interrupt is fired
		this method gets called and will push data onto the buffer.

		Parameters
		----------
		gpio, level, tick - required to be passed by the pigpio.callback

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		packetData = chip.block_read(SC16IS750.REG_RHR,chip.byte_read(SC16IS750.REG_RXLVL))
		print("Data came in: ", packetData)
		packetBuffer.append(packetData)

	def wtc_respond(response):
		"""
		Respond to the WTC with a control character.

		Parameters
		----------
		response - string - respond with a specific control character if it exists, otherwise
							just block_write the data to the WTC

		Returns
		-------
		Void

		Raises
		------
		Any exception gets popped up the stack.
		"""
		if response in qpStates:
			chip.byte_write(SC16IS750.REG_THR,qpStates[response])
		elif response is not None:
			if isinstance(response,int):
				response = bytes([response])
			chip.write(response)

	def pseudoStateMachine(packetData,configureTimestamp,nextQueue):
		"""
		This is a "state machine" that is run every iteration over the data received by the WTC.
		In reality, it's a glorified switch statement.

		Parameters
		----------
		packetData - the raw input by the WTC.
		configureTimestamp - Boolean - True: we need to set the timestamp. Should only be true on boot.
									   False: The timestamp has been set already.
		nextQueue - qph.Queue - the WHATISNEXT queue. Imperitive for operation.
		Returns
		-------
		packetData - if the incoming data is not a control character, return it.
					 if the incoming data is a control character, return nothing (b'')
		configureTimestamp - returns it so it can access it later.

		Raises
		------
		Any exception gets popped up the stack.
		"""
		# Start looking at a pseduo state machine so WTC code doesn't need to change
		if len(packetData) == 1 or (len(packetData) == 4 and configureTimestamp):
			byte = int.from_bytes(packetData,byteorder='little')
			print('Read from WTC: ', hex(byte))
			if len(packetData) == 4:
				logger.logSystem('PseudoSM: Configuring the timestamp.')
				os.system("sudo date -s '@" + str(byte) +"'")
				chip.block_write(SC16IS750.REG_THR,packetData)
				configureTimestamp = False
				logger.setBoot(newTimestamp=byte)
				logger.logSystem('Timestamp: {}'.format(str(byte)))
			elif byte in qpStates.values():
				logger.logSystem('PseudoSM: State receieved: {}'.format(hex(byte)))
				# The byte was found in the list of QPCONTROLs
				if byte == qpStates['NOOP']:
					logger.logSystem('PseudoSM: NOOP.')
					wtc_respond('DONE')
				elif byte == qpStates['SHUTDOWN']:
					logger.logSystem('PseudoSM: Shutdown was set!')
					#nextQueue.enqueue('SHUTDOWN') # Just in case the interrupt is fired before shutting down.
					wtc_respond('DONE')
					shutdownEvent.set()	# Set for shutdown
				elif byte == qpStates['REBOOT']:
					logger.logSystem('PseudoSM: Reboot was set!')
					#nextQueue.enqueue('SHUTDOWN')
					wtc_respond('DONE')
					shutdownEvent.set()
				elif byte == qpStates['TIMESTAMP']:
					logger.logSystem('PseudoSM: TIMESTAMP from WTC.')
					wtc_respond('TIMESTAMP')
					# Yo, configure the timestamp after this
					configureTimestamp = True
					logger.clearBoot()
				elif byte == qpStates['WHATISNEXT']:
					next = nextQueue.peek()
					if not next:
						next = 'IDLE'
					wtc_respond(next) # Respond with what the Pi would like the WTC to know.
					# Wait for a response from the WTC.
					logger.logSystem('PseudoSM: Waiting {}s for a response from WTC'.format(WHATISNEXT_WAIT))
					# Possibly might need to cancel the callback and restart it here.
					# callback.cancel()
					if waitForBytesFromCCDR(chip,1,timeout=WHATISNEXT_WAIT): # Wait for 15s for a response from the WTC
						response = chip.byte_read(SC16IS750.REG_RHR)
						# If SENDPACKET was queued, but a BUFFERFUL came in as a response, then re-queue the SENDPACKET
						if (next == 'SENDPACKET' or next == qpStates['SENDPACKET']) and response == qpStates['BUFFERFULL']:
							nextQueue.enqueue('SENDPACKET',prepend=True)

						wtc_respond('DONE') # Always respond with done for an "ACCEPTED or PENDING"
						# THIS IS A BLOCKING CALL
						nextQueue.blockWithResponse(response,timeout=5) # Blocking until the response is read or timeout.

					if not nextQueue.isEmpty():
						nextQueue.dequeue() # After "waiting" for the bytes, dequeue the items.
					# If we cancel the callback earlier, re-initialize it here.
					# callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)

				elif byte == qpStates['NEXTPACKET']:
					nextPacket = packetQueue.dequeue()
					if nextPacket:
						wtc_respond(nextPacket)
						lastPacketsSent.append(nextPacket)
					else:
						dummy = fh.DummyPacket().build()
						wtc_respond(dummy)
						lastPacketsSent.append(dummy)

				elif byte == qpStates['BUFFERFULL']:

					wtc_respond('DONE')
				elif byte == qpStates['ACCEPTED']:
					wtc_respond('DONE')
				elif byte == qpStates['DENIED']:
					wtc_respond('DONE')
				elif byte == qpStates['PENDING']:
					wtc_respond('DONE')
				else:
					logger.logSystem('PseudoSM: State existed for {} but a method is not written for it.'.format(hex(byte)))
		else:
			return packetData, configureTimestamp # Return the data if it's not actually a control character.

		return None,configureTimestamp # Return nothing if the packetData was handled as a WTC control

	# Set up the callback.
	if gpio:
		callback = gpio.callback(CCDR_IRQ, pigpio.FALLING_EDGE, WTCRXBufferHandler)
		logger.logSystem('Interpreter: Callback active. Waiting for data from the SC16IS750.')
	else:
		logger.logSystem("Interpreter: Callback is not active. PIGPIO was not defined.")

	# Begin main loop.
	while not shutdownEvent.is_set(): # While we are NOT in shutdown mode
		try:
			# create an instance of a ChunkPacket
			chunkPacket = fh.ChunkPacket(chip,logger)
			runEvent.wait() # Mutex for the run
			time.sleep(.25)  # wait for a moment
			while(len(packetBuffer)>0): # If there is data in the buffer
				runEvent.wait() # Mutex for running.
				if shutdownEvent.is_set():
					raise StopIteration('Shutdown was set. The buffer will be dropped.')
				packetData = packetBuffer.pop(0) # Get that input

				# Determine if the data is a control character or not.
				packetData, configureTimestamp = pseudoStateMachine(packetData,configureTimestamp,nextQueue)
				# If the data was not a control character, then process it.
				if packetData:
					# We'll just assume that the input is a chunk.
					chunkPacket.push(packetData)
					# If, after pushing, the chunk is complete continue on. Otherwise skip.
					if chunkPacket.complete:
						packetData = chunkPacket.build()
						fieldData = decodePacket(packetData) # Return a nice dictionary for the packets
						# Check if the packet is valid.
						# If it's XTEA, decode it at this step and modify the field data appropriately.
						isValid,fieldData = checkValidity(fieldData)
						if isValid:
							#TODO These prints are for DEBUG only.
							print('Packet has passed Validation.')
							# If the opcode is that of a DataPacket procecss as incoming data.
							# If the opcode is a command, process it as a command.
							# If we don't know what it is at this point, then let's log it and
							# trash the data.
							if fieldData['TYPE'] == 'DATA':
								processIncomingPacketData(chip,fieldData)
							elif fieldData['opcode'] in COMMANDS: # Double check to see if it's a command
								try:
									processCommand(chip,fieldData,fromWhom = 'CCDR')
								except StopIteration:
									continue # Used for flow control inside of some commands.
							elif fieldData['TYPE'] == 'DLACK':
									# If the DLACK is good, then clear the queue of lastPackets.
									if fieldData['response'] == b'GOOD':
										lastPacketsSent.clear()
									else:
										# If it's not good, then we need to send those packets again...
										# To do that, we will prepend the packetQueue with the packets from lastPacketsSent
										# And then we will prepend the nextQueue with a 'SENDPACKET' for every BUFFERSIZE of packets.
										# If the last packets sent's count is less than the buffer size
										# Then we'll append dummy packets here to fill that buffer.

										# Offload the last sent packets but don't clear them until we get a good.
										lastPacketsSent_copy = lastPacketsSent[:] #Shallow copy to not affect the original list
										if len(lastPacketsSent_copy) < fh.WTC_PACKET_BUFFER_SIZE: # If there's more buffer space than packets sent...
										for i in range(fh.WTC_PACKET_BUFFER_SIZE - len(lastPacketsSent_copy)): # Append a dummy packet for every packet to send.
										lastPacketsSent_copy.append(fh.DummyPacket().build())
										lastPacketsSent_copy.reverse() # Reverse the list so the last packets get prepended first.
										for pkt in lastPacketsSent_copy: # For every packet to send...
											packetQueue.enqueue(pkt, prepend=True) # Prepend those packets


										# For however many transactions the WTC can handle, enqueue a SENDPACKET so when the WTC asks "WHATISNEXT" the Pi can tell it it wants to send packets.
										for x in range((len(self._packetQueue)//fh.WTC_PACKET_BUFFER_SIZE) + 1):
											nextQueue.enqueue('SENDPACKET',prepend=True) # taken from qpaceControl



							else:
								logger.logSystem("Interpreter: Unknown valid packet.",str(fieldData))
						else:
							pass
							#TODO Alert the WTC? Send OKAY back to ground?
							print('Packet did not pass validation.')

		except KeyboardInterrupt: # Really only needed for DEBUG. Forces a re-check for shutdownEvent.
			continue
		except StopIteration:	  # Used for control flow.
			break
	logger.logSystem("Interpreter: Starting cleanup for shutdown.")

	if gpio:
		callback.cancel()
		gpio.stop()
	logger.logSystem("Interpreter: Shutting down...")
