#!/usr/bin/env python3
# qpaceFileHandler.py by Jonathan Kessluk
# 6-22-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Handler for encoding and decoding packets for file transfer.

from  qpacePiCommands import generateChecksum,Command
import qpaceInterpreter as interp
import tstSC16IS750 as SC16IS750
#import SC16IS750
from time import sleep
from datetime import datetime,timedelta
from math import ceil
import os

MISCPATH = '/mnt/c/users/jonat/desktop/cmr/pi/data/misc/'
ROOTPATH= '/mnt/c/users/jonat/desktop/cmr/pi/'
TEMPPATH = '/mnt/c/users/jonat/desktop/cmr/pi/temp/'

class DataPacket():#Packet):
	"""
	Packet structure for QPACE:
	---------------------------------------------------------------------
	|					  |						   |					|
	| Designator  (1 Byte)| Misc integer (4 Bytes) |  Data (123 Bytes)  |	  (128Bytes)
	|					  |						   |					|
	---------------------------------------------------------------------
	"""
	padding_byte = b'\x04'
	max_size = 128		  		# in bytes
	header_size = 14			# in bytes
	max_id = 0xFFFFFFFF	 		# 4 bytes. Stored as an int.
	last_id = 0					# -1 if there are no packets yet.
	valid_opcodes = (b'NOOP>',b'NOOP!')

	validDesignators = [0]   	# WTC, Pi 1, Pi 2, GS.

	def __init__(self,data, pid,rid, xtea = False,opcode = b'NOOP>'):
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

		# if useFEC:
		# 	self.data_size = ((DataPacket.max_size - DataPacket.header_size) // 3)
		# else:
		# 	self.data_size = DataPacket.max_size - DataPacket.header_size
		self.data_size = DataPacket.max_size - DataPacket.header_size

		# Is the data size set yet or is it valid?
		if self.data_size is None:
			raise ValueError('data_size is not set.')

		data_in_bytes = len(data)
		if data_in_bytes <= self.data_size: # Make sure the data is below the max bytes
			if (DataPacket.last_id + 1) == pid:
				if pid < 0 or pid > DataPacket.max_id:
					raise ValueError("Packet pid is invalid.")
				DataPacket.last_id = pid
				self.pid = pid % DataPacket.max_id # If the pid is > max_id, force it to be smaller!
			else:
				if pid == 0:
					DataPacket.pid = 0
				else:
					raise ValueError("Packet pid out of order.")

			self.data = data
			self.bytes = data_in_bytes
			# self.useFEC = useFEC
			self.rid = rid
			self.xtea = xtea
			self.paddingSize = 0
			self.opcode = opcode if opcode is not None else DataPacket.opcode[0]
		else:
			raise ValueError("Packet size is too large for the current header information ("+str(len(data))+"). Data input restricted to " + str(self.data_size) + " Bytes.")


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
		# if self.useFEC:
		# 	data = self.data * 3
		# else:
		# 	data = self.data
		data = self.data

		padding = self.data_size - len(data)
		data += DataPacket.padding_byte * padding
		self.paddingSize = padding
		packet = self.rid.to_bytes(1,byteorder='big') + self.opcode + self.pid.to_bytes(4,byteorder='big') + data
		packet += generateChecksum(packet)
		print('PACKET TO SEND LEN:', len(packet))
		# After constructing the packet's contents, pad the end of the packet until we reach the max size.
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
		chip.block_write(SC16IS750.REG_THR, self.build())

class DummyPacket(DataPacket):
	def __init__(self):
		self.data=DataPacket.padding_byte*118
		self.opcode = b'DUMMY'
		self.rid = b'\x00'
	def build(self):
		return self.rid + self.opcode + self.data

class XTEAPacket():
	pass

class ChunkPacket():
	TIMEDELAYDELTA = 1.5 # in seconds
	chunks = []
	complete = False
	lastInputTime = None

	def __init__(self, chip,logger):
		self.chip = chip
		self.logger = logger

	def push(self,data):
		if not ChunkPacket.complete:
			if ChunkPacket.lastInputTime is not None and (datetime.now() - ChunkPacket.lastInputTime) > timedelta(seconds = ChunkPacket.TIMEDELAYDELTA):
				ChunkPacket.chunks[:] = [] # reset the chunks..
			ChunkPacket.lastInputTime = datetime.now()
			ChunkPacket.chunks.append(data)
			#Acknowledge WTC with chunk number
			self.chip.byte_write(SC16IS750.REG_THR,0x60 + len(ChunkPacket.chunks)) # Defined by WTC state machine
			if len(ChunkPacket.chunks) == 4: # We are doing 4 chunks!
				ChunkPacket.complete = True

		else:
			self.logger.logSytem("ChunkPacket: Attempted to push when complete...")
			ChunkPacket.complete = True


	def build(self):
		if ChunkPacket.complete:
			print('Building a packet!')
			packet = b''
			for chunk in ChunkPacket.chunks:
				#print('<',len(chunk),'>',chunk)
				packet += chunk
			if len(packet) != DataPacket.max_size:
				self.logger.logSystem("Packet is not {} bytes! It is {} bytes!".format(str(DataPacket.max_size),str(len(packet))) ,str(packet)[50:])
				packet = b''
			ChunkPacket.chunks[:] = [] #reset chunks to empty
			ChunkPacket.complete = False #reset copmlete to False
			ChunkPacket.lastInputTime = None # reset the timer.
			return packet
		else:
			print('Packet is not complete yet.')
			pass

class Defaults():
	packetsPerAck_DEFAULT = 1
	delayPerTransmit_DEFAULT = 135 #in milliseconds
	firstPacket_DEFAULT = -1
	lastPacket_DEFAULT = -1
	xtea_DEFAULT = False
	# useFEC_DEFAULT = False
	prepend_DEFAULT = ''
	route_DEFAULT = None
	totalPackets_DEFAULT = None

class Transmitter():

	def __init__(self, chip, pathname, route,
				# useFEC =			Defaults.useFEC_DEFAULT,
				firstPacket = 		Defaults.firstPacket_DEFAULT,
				lastPacket = 		Defaults.lastPacket_DEFAULT,
				xtea = 				Defaults.xtea_DEFAULT,
				packetQueue =		None):
		self.chip = chip
		self.pathname = pathname
		# self.useFEC = useFEC
		self.firstPacket = firstPacket if firstPacket > 0 else 0
		self.lastPacket = lastPacket if lastPacket > firstPacket else None
		self.route = route
		self.packetQueue = packetQueue
		# Attempt to get the file size. Pop up the stack if it cannot be found.
		# Since this happens first, if this succeeds, then the rest of the methods will be fine.
		try:
			self.filesize = os.path.getsize("{}{}".format(ROOTPATH,pathname))
		except FileNotFoundError as e:
			raise e


		try:
			self.checksum = generateChecksum(open("{}{}".format(ROOTPATH,pathname),'rb').read())
		except:
			self.checksum = b'NONE' #TODO should we just not send the file? I don't think so.

		# if useFEC:
		# 	self.data_size = (DataPacket.max_size - DataPacket.header_size) // 3
		# else:
		# 	self.data_size = DataPacket.max_size - DataPacket.header_size
		self.data_size = DataPacket.max_size - DataPacket.header_size
		self.expected_packets = ceil(self.filesize / self.data_size)

	def run(self):
		packetData = self.getPacketData()
		packet = None
		# Get the length of all the packets if NONE was supplied as the last packet.
		if self.lastPacket == None:
			self.lastPacket = len(packetData)
		try:
			for pid in range(self.firstPacket,self.lastPacket):
				sessionPackets = []

				# try:
				packet = DataPacket(packetData[pid], pid, self.route)
				self.packetQueue.enqueue(packet.build()) #TODO ADD PACKET TO BUFFER
				# except IndexError:
				# 	# IndexError when we don't have enough packets for the current set of acknoledgements
				# 	# This is fine though, raise a StopIteration up one level to exit
				# 	if i == self.packetsPerAck:
				# 		raise StopIteration("All done!")
				# sleep(self.delayPerTransmit/1000) # handled by wtc?
		except StopIteration as e:
			#StopIteration to stop iterating :) we are done here.
			print(e)
		#When it's done it needs to send a DONE packet
		temp = [self.checksum,bytes([self.expected_packets]),self.pathname.encode('ascii')[self.pathname.rfind('/')+1:]]
		data = b' '.join(temp)
		# if useFEC:
		# 	data += (36 - len(data)) * b'\x04' if len(data) < 36 else b''
		# 	data = data[:36] # only get the first 116 chars. Defined by the packet document
		# else:
		# 	data += (116 - len(data)) * b'\x04' if len(data) < 116 else b''
		# 	data = data[:116] # only get the first 116 chars. Defined by the packet document
		padding = len(data)
		data += DataPacket.padding_byte * padding
		allDone = DataPacket(data,packet.pid+1,0x00,opcode=b'NOOP!').build()
		self.packetQueue.enqueue(allDone)
		DataPacket.last_id = 0


	def getPacketData(self):
		packetData = []
		with open("{}{}".format(ROOTPATH,self.pathname),'rb') as f:
			while(True):
				data = f.read(self.data_size)
				if data:
					packetData.append(data)
				else:
					break
		return packetData

class Scaffold():

	@staticmethod
	def determineDataSize():
		# if useFEC:
		# 	return (DataPacket.max_size - DataPacket.header_size) // 3
		# else:
		# 	return DataPacket.max_size - DataPacket.header_size
		return DataPacket.max_size - DataPacket.header_size

	@staticmethod
	def construct(pid,newData):

		filename = Command.UploadRequest.filename
		# useFEC = Command.UploadRequest.useFEC
		with open(TEMPPATH + filename+".scaffold","rb+") as scaffold:
			scaffoldData = scaffold.read()
			scaffold.seek(0)
			offset = pid * Scaffold.determineDataSize()
			scaffoldData = scaffoldData[:offset] + newData + scaffoldData[offset:]
			scaffold.write(scaffoldData)

	@staticmethod
	def finish(information):
		if Command.UploadRequest.isActive():
			information = information.split(b' ')
			checksum = information[0]
			paddingUsed = int.from_bytes(information[1],byteorder='big')
			filename = information[2][:information[2].find(DataPacket.padding_byte)].replace(b'/',b'@').decode('ascii')
			print('Checksum:', checksum)
			print('paddingUsed:',paddingUsed)
			print('filename:', filename)

			with open(TEMPPATH+filename+'.scaffold','rb+') as f:
				info = f.read()
				f.seek(0)
				f.truncate()
				f.write(info[:-paddingUsed])

			os.rename(TEMPPATH+filename+'.scaffold',ROOTPATH + filename.replace('@','/'))
			return Command.UploadRequest.finished(filename)
