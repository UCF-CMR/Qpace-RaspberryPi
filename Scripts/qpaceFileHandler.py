#!/usr/bin/env python3
# qpaceFileHandler.py by Jonathan Kessluk
# 6-22-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Handler for encoding and decoding packets for file transfer.

# Still in work

import qpaceLogger as logger
from qpaceInterpreter import ROUTES
from qpacePiCommands import CMDPacket
from math import ceil

class Corrupted(Exception):
	def __init__(self, message):
		super(Exception, self).__init__(message)

class Packet():
	"""
	Packet structure for QPACE:
	----------------------------------------------------------------------
	|                      |                        |                    |
	| Designator  (1 Byte) | Misc integer (4 Bytes) |  Data (123 Bytes)  |      (128Bytes)
	|                      |                        |                    |
	----------------------------------------------------------------------
	"""
	padding_byte = b' '
	header_size = 5         # in bytes
	max_size = 128          # in bytes
	xtea_header_size = 10	# in bytes
	data_size = None        # in bytes. Initial state is None. Gets calculated later
	max_id = 0xFFFFFFFF     # 4 bytes. Stored as an int.
	last_id = 0            # -1 if there are no packets yet.

	validDesignators = [0]   # WTC, Pi 1, Pi 2, GS.

	def __init__(self,data, pid,rid,useFEC = False, xtea = False):
		"""
		Constructor for a packet.

		Parameters
		---------
		data - str, bytes, bytearray - If a str it must be hex and valid bytes.
		pid - int - Integer to be the PID of the packet. Can not be negative and must be
					+1 the last pid used.

		Exceptions
		----------
		ValueError - if the data passed to the packet is too large to fit in the packet.
					 or the pid is out of order.
					 or the pid is negative.
		TypeError - if the data is not a string,int,bytes,or bytearray.
		"""
		# Is the data in a valid data type? If so, convert it to a bytearray.
		if isinstance(data,bytearray):
			pass
		elif isinstance(data,bytes):
			data = bytearray(data)
		elif isinstance(data,str):
			try:
				data = bytearray.fromhex(data)
			except ValueError:
				data = bytearray(data.encode('utf-8'))
		elif data is None:
			data = bytearray(b'')
		else:
			raise TypeError("Input data is of incorrect type. Must input str, bytes, or bytearray")


		headerSize = Packet.xtea_header_size if xtea else Packet.header_size
		if useFEC:
			Packet.data_size = (Packet.max_size - headerSize) // 3
		else:
			Packet.data_size = Packet.max_size - headerSize
		# Is the data size set yet or is it valid?
		if Packet.data_size is None:
			raise ValueError('data_size is not set.')

		data_in_bytes = len(data)
		if data_in_bytes <= Packet.data_size: # Make sure the data is below the max bytes
			if (Packet.last_id + 1) == pid:
				if pid < 0 or pid > Packet.max_id:
					raise ValueError("Packet pid is invalid.")
				Packet.last_id = pid
				self.pid = pid % Packet.max_id # If the pid is > max_id, force it to be smaller!
			else:
				if pid == 0:
					Packet.pid = 0
				else:
					raise ValueError("Packet pid out of order.")
			self.data = data
			self.bytes = data_in_bytes
			self.useFEC = useFEC
			self.rid = rid
			self.lastPacket = lastPacket
			self.xtea = xtea
		else:
			raise ValueError("Packet size is too large for the current header information ("+str(len(data))+"). Data input restricted to " + str(Packet.data_size) + " Bytes.")


	def build(self):
		"""
			Build the entire packet.

			Returns
			-------
			int - the whole packet. if converted to binary/hex it will be the packet.
		"""
		# Construct the packet's data

        # Do a TMR expansion where the data is replicated 3 times but not next to each other
		# to avoid burst errors.
        if self.useFEC:
			data = self.data * 3
		else:
			data = self.data

		packet = self.rid.to_bytes(1,byteorder='big') + self.pid.to_bytes(4,byteorder='big') + data
		# After constructing the packet's contents, pad the end of the packet until we reach the max size.
		padding = Packet.max_size - len(packet)
		packet += Packet.padding_byte * padding
		return packet

	@staticmethod
	def getParity(info):
		parity = int(bin(info[0])[2])
		for bit in bin(info[0])[3:]:
			parity ^= int(bit)
		for byte in info[1:]:
			for bit in bin(byte)[2:]:
				parity ^= int(bit)
		return parity

	def send(self,chip):
		chip.block_write(chip.REG_THR, self.build())

class XTEAPacket():
	pass

class ChunkPacket():
	chunks = []
	complete = False

	def __init__(self, chip):
		self.chip = chip

	def push(self,data):
		if not self.complete:
			self.chunks.append(data)
			#Acknowledge WTC with chunk number
			sendBytesToCCDR(self.chip,0x60 + len(self.chunks)) # Defined by WTC state machine
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

class TransmitCompletePacket(Packet):
    def __init__(self, pathname, checksum, pid,rid,useFEC = False):
            data = b'\x04\x04' + checksum + b'\x00' + pathname
            data += (116 - len(data)) * b'\x04' if len(data) < 116 else b''
            data = data[:116] # only get the first 116 chars. Defined by the packet document
            data += CMDPacket.generateChecksum(data)
        super(Packet,self).__init__(data,pid,rid,useFEC)

class DownloadRequest():
	pass

class Transmitter():
    def __init__(self, chip, pathname, route, useFEC=False, packetsPerAck = 1, delayPerTransmit = 135, firstPacket = 1, lastPacket = None, xtea = False):
        self.chip = chip
        self.pathname = pathname
        self.useFEC = useFEC
        self.packetsPerAck = packetsPerAck
        self.delayPerTransmit = delayperTransmit
        self.firstPacket = firstPacket if firstPacket > 1 else 1
        self.lastPacket = lastPacket if lastPacket > lastPacket else None
        self.route = route
        self.checksum = b' ' #TODO figure out the checksum stuff

		headerSize = Packet.xtea_header_size if xtea else Packet.header_size
        if useFEC:
			self.data_size = (Packet.max_size - headerSize) // 3
		else:
			self.data_size = Packet.max_size - headerSize
		self.expected_packets = ceil(self.filesize / Packet.data_size)

    def run(self):
        packetList = getPackets()
		# Get the length of all the packets if NONE was supplied as the last packet.
		if self.lastPacket == None:
            self.lastPacket = len(packetList)
        totalAcks = ceil((self.lastPacket - self.firstPacket + 1)/self.packetsPerAck)
        for ackCount in range(totalAcks):
            sessionPackets = []
            for i in range(packetsPerAck):
                pid = (ackCount * self.packetsPerAck + i) + self.firstPacket
                packet = Packet(packetList[pid], pid, self.route ,useFEC = self.useFEC)
                packet.send()
            #TODO work out handshake with packets
			#TODO this is where the handshake will go.
			#TODO we will WAIT here for the acknowledgement. Once we get it, continue on.

        #When it's done it needs to send a DONE packet
        allDone = TransmitCompletePacket(self.pathname,self.checksum,self.expected_packets,self.route,useFEC=self.useFEC)
		allDone.send(self.chip)

    def getPackets():
        packetList = []
        with open(pathname,'rb') as f:
            while(True):
                data = f.read(Packet.max_size - self.data_size)
                if data:
                    packetList.append(data)
                else:
                    break
        return packetList

class Receiver():
	class ReceivedPacket():
		def __init__(self, rid, pid, data):
			self.rid = rid
			self.pid = pid
			self.data = data
    def __init__(self, chip, pathname, prepend='',route=None, useFEC=False, packetsPerAck = 1, delayPerTransmit = 135, firstPacket = 1, lastPacket = None, xtea = False):
        self.chip = chip
		self.prepend = prepend
        self.pathname = pathname
        self.useFEC = useFEC
        self.packetsPerAck = packetsPerAck
        self.delayPerTransmit = delayperTransmit
        self.firstPacket = firstPacket if firstPacket > 1 else 1
        self.lastPacket = lastPacket if lastPacket > firstPacket else None
        self.route = route
        self.checksum = b' ' #TODO figure out the checksum stuff

        headerSize = Packet.xtea_header_size if xtea else Packet.header_size
        if useFEC:
			self.data_size = (Packet.max_size - headerSize) // 3
		else:
			self.data_size = Packet.max_size - headerSize
		self.expected_packets = ceil(self.filesize / Packet.data_size)

	def run():
		with open(self.prepend+self.pathname,'rb+') as scaffold:
			while(acceptingPackets):
				packet = getPacket()
				if packet.rid == ROUTES['PI1ROUTE'] or packet.rid == ROUTES['PI2ROUTE']:
					data = scaffold.read()
					scaffold.seek(0)
					offset = packet.pid*self.data_size
					data = data[:offset] + packet.data + data[offset:]
					scaffold.write(data)





	def getPacket():
		buf = b''
		time_to_wait = 5#s
		time_to_sleep = .4#s
		numOfAttempts = (time_to_wait//time_to_sleep) + 1

		for i in range(0,4): #We will receive 4, 32 byte chunks to make a 128 packet
			attempt = 0
			while(True):
				waiting = chip.byte_read(SC16IS750.REG_RXLVL)
				if waiting >= 32: # wait until we have a full chunk
					try:
						logger.logSystem([["Reading in "+ str(waiting) +" bytes from the CCDR"]])
						for i in range(32):
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
				sleep(time_to_sleep)
				attempt += 1
			chip.byte_read(SC16IS750.REG_RHR)# Clear the buffer. WTC will send ERRNONE

		return ReceivedPacket(buf[0],buf[1:4],buf[5:])




	def writeFile():
		pass
