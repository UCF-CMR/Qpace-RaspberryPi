#!/usr/bin/env python3
# qpaceFileHandler.py by Jonathan Kessluk with controbutions from Taesung Yoon and Eric Prather
# 6-22-2018, Rev. 2
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# Handler for encoding and decoding packets for file transfer.

from  qpacePiCommands import generateChecksum,Command
import qpaceInterpreter as interp
#import tstSC16IS750 as SC16IS750
import SC16IS750
from time import sleep
from datetime import datetime,timedelta
from math import ceil
import re
import os
import traceback
import hashlib

WTC_PACKET_BUFFER_SIZE = 10

MISCPATH = '/home/pi/data/misc/'
GRAVEPATH = '/home/pi/graveyard/'
TEXTPATH = '/home/pi/data/text/'
TEMPPATH = '/home/pi/temp/'
ROOTPATH = '/home/pi/'
# This is 2GB. In testing, a file that is 3GB will only cause less than 300MB of RAM usage in python. Don't ask me how that works.
# Therefore, we will only allow files that are 2GB.
MAX_FILE_SIZE = 2147483648
MAX_RAM_ALLOTMENT = 419430400 # This is how many bytes are in 400MB. Restrict file sizes to this because of RAM.,///





class DataPacket():
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
	data_size = max_size - header_size
	validDesignators = [0]   	# WTC, Pi 1, Pi 2, GS.
	pid = 0

	def __init__(self,data, pid,rid, xtea = False,opcode = None):
		"""
		Constructor for a packet.

		Parameters:
		data - bytes - the data to be put into a packet
		pid - int - PID of the packet, must be +1 the last PID used
		rid - int - RID of the packet, should always be 0x00
		xtea - legacy and not used
		opcode - optional - can change the opcode from the default. default will be set to the first opcode in the valid_opcodes attribute.

		Returns: None

		Raises:
		Type Error - if the data is not a string, bytes, or bytearray.
		ValueError - If there's no data size
		ValueError - The pid is not valid
		ValueError - the pid is out of order
		Value error - packet is too large.
		"""
		# Is the data in a valid data type? If so, convert it to a bytearray.
		self.downloadPacketChecksum = False
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
		#DataPacket.data_size = DataPacket.max_size - DataPacket.header_size

		# Is the data size set yet or is it valid?
		if DataPacket.data_size is None:
			raise ValueError('data_size is not set.')

		data_in_bytes = len(data)
		if data_in_bytes <= self.data_size: # Make sure the data is below the max bytes
			if (DataPacket.last_id + 1) == pid:
				if pid > DataPacket.max_id:
					DataPacket.pid = pid % DataPacket.max_id # If the pid is > max_id, force it to be smaller!
				if pid < 0:
					raise ValueError("Packet pid is invalid.")
				DataPacket.last_id = pid
			else:
				if pid == 0:
					DataPacket.pid = 0
				#else:
					#raise ValueError("Packet pid out of order.")

			self.data = data
			self.bytes = data_in_bytes
			DataPacket.pid = pid
			# self.useFEC = useFEC
			self.rid = rid
			self.xtea = xtea
			self.paddingSize = 0
			self.opcode = opcode if opcode is not None else DataPacket.valid_opcodes[0]
		else:
			raise ValueError("Packet size is too large for the current header information ("+str(len(data))+"). Data input restricted to " + str(self.data_size) + " Bytes.")

	def generateDownloadChecksum(self, data):
		m = hashlib.md5()
		m.update(data)
		checksum = m.digest() # Returns 16 Bytes
		return checksum[-4:] # Can only store 4 Bytes so take the last four
		

	def build(self):
		"""
		Build the packet
		Adds padding to the data, adds the RID, PID, opcode, and checksum.

		Parameters: None

		Returns: Bytestring of the packet.

		Raises: None

		"""
		# Construct the packet's data

		# Do a TMR expansion where the data is replicated 3 times but not next to each other
		# to avoid burst errors.
		# if self.useFEC:
		# 	data = self.data * 3
		# else:
		# 	data = self.data
		data = self.data

		padding = DataPacket.data_size - len(data)
		data += DataPacket.padding_byte * padding
		self.paddingSize = padding
		packet = self.rid.to_bytes(1,byteorder='big') + self.opcode + DataPacket.pid.to_bytes(4,byteorder='big') + data
		# If the packet is for download use safe checksum maker
		if self.downloadPacketChecksum:
			packet += generateDownloadChecksum(data)
		else:
			packet += generateChecksum(packet)
		# After constructing the packet's contents, pad the end of the packet until we reach the max size.
		return packet

	def send(self,chip):
		"""
		Builds the packet and then sends it to the WTC.

		Parameters: chip - SC16IS750 object to send the packet to.

		Returns: None

		Raises: None

		"""
		chip.block_write(SC16IS750.REG_THR, self.build())

class DummyPacket(DataPacket):
	""" A dummy packet prefabricated for use to send to ground when no other packet is available or necessary"""
	def __init__(self):
		"""
		Constructor for the Dummy packet. Shouldn't really need anything else.

		Parameters: None

		Returns: None

		Raises: None

		"""
		self.data=DataPacket.padding_byte*118
		self.opcode = b'DUMMY'
		self.rid = b'\xAA'
	def build(self):
		"""
		Override for the dummy packet's build.

		Parameters: None

		Returns: the packet's bytestring

		Raises: None

		"""
		toSend =  self.rid + self.opcode + self.data
		return toSend + generateChecksum(toSend)

class ChunkPacket():
	""" Helper class to take chunks and make them into a packet if 4 are received"""
	TIMEDELAYDELTA = 1.5 # in seconds
	chunks = []
	complete = False
	lastInputTime = None

	def __init__(self, chip,logger):
		"""
		Constructor for ChunkPacket

		Parameters:
		chip - an SC169S750 object to do operations with if necessary.
		logger - a qpaceLogger.Logger() object to log operations

		Returns: None

		Raises: None

		"""
		self.chip = chip
		self.logger = logger

	def push(self,data):
		"""
		Add a chunk to the internal list

		Parameters:
		data - the data to add to the list

		Returns: None

		Raises: None

		"""
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
			self.logger.logSystem("ChunkPacket: Attempted to push when complete...")
			ChunkPacket.complete = True


	def build(self):
		"""
		Build a packet out of the four chunks

		Parameters: None

		Returns: The bytestring of the packet

		Raises: None

		"""
		if ChunkPacket.complete:
			packet = b''
			for chunk in ChunkPacket.chunks:
				packet += chunk
			if len(packet) != DataPacket.max_size:
				self.logger.logSystem("Packet is not {} bytes! It is {} bytes!".format(str(DataPacket.max_size),str(len(packet))) ,str(packet)[50:])
				#print("QUICK FIX IN QPACE FILE HANDLER")
				packet = packet[(len(packet)-DataPacket.max_size):]
				if(packet[-4:] != generateChecksum(packet[:-4])):
					packet = b''
					#print("THE DATA SEND ISN'T VALID:\nCHECKSUMS DON'T MATCH")
					Command.PrivilegedPacket(opcode=b"ERROR", plainText=b"ERROR OCCURING").send()
				#else:
					#print("QUICK FIX IS VALID")
			ChunkPacket.chunks[:] = [] #reset chunks to empty
			ChunkPacket.complete = False #reset copmlete to False
			ChunkPacket.lastInputTime = None # reset the timer.
			return packet
		else:
			#print('Packet is not complete yet.')
			pass

class Defaults():
	""" Helper class that only stores Default values. Nothing else"""
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
	""" Transmitter object to handle splitting up a file into packets and passing them to the packetQueue"""
	def __init__(self, pathname, route,
				# useFEC =			Defaults.useFEC_DEFAULT,
				ppa = 				Defaults.packetsPerAck_DEFAULT,
				firstPacket = 		Defaults.firstPacket_DEFAULT,
				lastPacket = 		Defaults.lastPacket_DEFAULT,
				xtea = 				Defaults.xtea_DEFAULT,
				packetQueue =		None):
		"""
		Constructor for the Transmitter

		Parameters:
		pathname - the path for the file you want to send
		route - should always be 0x00
		ppa - the number of packets per acknowledgement sent
		firstPacket - the first packet PID to start out on for the file
		lastPacket - the last packet PID to end the file download
		xtea - legacy - not implemented anymore
		packetQueue - the packetQueue to store all the packet data in when it's done generating the packets.
		Returns:

		Raises:

		"""
		self.pathname = pathname
		# self.useFEC = useFEC
		self.firstPacket = firstPacket if firstPacket > 0 else 0
		self.lastPacket = lastPacket if lastPacket >= firstPacket else None # we allow equality here
		self.route = route
		self.packetQueue = packetQueue
		# Attempt to get the file size. Pop up the stack if it cannot be found.
		# Since this happens first, if this succeeds, then the rest of the methods will be fine.
		try:
			self.filesize = os.path.getsize("{}{}".format(ROOTPATH,pathname))
		except Exception as e:
			noDownloadMessage = 'There was an issue with the file: {}'.format(e)
			noDownloadPacket = DataPacket(noDownloadMessage.encode('ascii'), 0, self.route).build()
			self.packetQueue.enqueue(noDownloadPacket)
			#traceback.print_exc()
			DataPacket.last_id = 0
			return

		if self.filesize > MAX_FILE_SIZE:
			noDownloadMessage = 'You cannot download this file. It is too big. Break it up first.'
			noDownloadPacket = DataPacket(noDownloadMessage.encode('ascii'), 0, self.route).build()
			self.packetQueue.enqueue(noDownloadPacket)
			DataPacket.last_id = 0
			#print("TOO BIG BAYBEE")
			return

		self.data_size = DataPacket.max_size - DataPacket.header_size
		self.expected_packets = ((self.filesize // self.data_size) + 1) # This keeps it consitant with PiCommands.py #ceil(self.filesize / self.data_size)
		try:
			# Currently, all checksums are just thic, because the currnet checksum algorithm is too slow
			# and doesn't get applied to 99% of files anyway
			# We are working on a fix for this
			self.checksum = b'THIC'
			"""
			if(self.expected_packets < 1000):   #Way too big to create checksum
				print("Checksumming")
				self.checksum = generateChecksum(open("{}{}".format(ROOTPATH,pathname),'rb').read())
				print("Done checksum")
			else:
				self.checksum = b'THIC'
			"""
		except:
			self.checksum = b'NONE' #Should we just not send the file? I think we should send it anyway.
			#_, __, exc_traceback = sys.exc_info()
			#logger.logError(exc_traceback)

		# if useFEC:
		# 	self.data_size = (DataPacket.max_size - DataPacket.header_size) // 3
		# else:
		# 	self.data_size = DataPacket.max_size - DataPacket.header_size
		#self.data_size = DataPacket.max_size - DataPacket.header_size
		#self.expected_packets = ceil(self.filesize / self.data_size)
		self.ppa = ppa
		self.xtea = xtea
		#self._updateFileProgress()

	def run(self):
		"""
		The main loop for the Transmitter()
		Ends up appending a bunch of packets to the packetQueue.

		Parameters: None

		Returns: None

		Raises:None

		"""
		packetData = self.getPacketData()
		packet = None
		# Get the length of all the packets if NONE was supplied as the last packet.
		if self.lastPacket == None:
			self.lastPacket = len(packetData)
		try:
			sessionPackets = []
			for pid in range(self.lastPacket-self.firstPacket): #range(self.firstPacket, self.lastPacket):#
				
				# try:
				try:
					packet = DataPacket(data=packetData[pid], pid=pid+self.firstPacket, rid=self.route, opcode=None)
					self.pkt_padding = self.data_size - len(packetData[pid])
					self.packetQueue.enqueue(packet.build()) #ADD PACKET TO BUFFER
					#print("SUCCESSS WE ADDED HERE: %d" % pid)
				except Exception as e:
					#logger.logError("ERROR, WE HAVE FOUND SOME ERROR HERE: {0}".format(pid))
					#traceback.print_exc()
					pass
				# except IndexError:
				# 	# IndexError when we don't have enough packets for the current set of acknoledgements
				# 	# This is fine though, raise a StopIteration up one level to exit
				# 	if i == self.packetsPerAck:
				# 		raise StopIteration("All done!")
				# sleep(self.delayPerTransmit/1000) # handled by wtc?

				# Update the progress list.
				if pid+self.firstPacket % self.ppa == 0:
					try:
						self._updateFileProgress(pid+self.firstPacket)
					except:
						#print("ERROR IN 396: NO UPDATE PROGRESS")
						pass
		except StopIteration as e:
			#StopIteration to stop iterating :) we are done here.
			#print(e)
			print("")
			

		#print("Last: {0} | Expected: {1}".format(self.lastPacket, self.expected_packets))

		if(self.lastPacket == self.expected_packets):
			#When it's done it needs to send a DONE packet
			self.pkt_padding = self.data_size
			#                     *below* mod by ten so that way we are always within packet specs and we do not really care about the last packet num so long as it is a DLACK
			temp = [self.checksum, bytes(self.expected_packets%10), self.pathname.encode('ascii')[self.pathname.rfind('/')+1:], bytes([self.pkt_padding])]
			data = b' '.join(temp)
			# if useFEC:
			# 	data += (36 - len(data)) * b'\x04' if len(data) < 36 else b''
			# 	data = data[:36] # only get the first 116 chars. Defined by the packet document
			# else:
			# 	data += (116 - len(data)) * b'\x04' if len(data) < 116 else b''
			# 	data = data[:116] # only get the first 116 chars. Defined by the packet document
			# padding = 116 - len(data)
			# data += DataPacket.padding_byte * padding
			allDone = DataPacket(data=data,pid=self.expected_packets,rid=0x00,opcode=b'NOOP!').build()
			self.packetQueue.enqueue(allDone)
		DataPacket.last_id = 0

	def getPacketData(self):
		"""
		Split the contents of a file up into packet sized chunks to be stored in a packet later

		Parameters: None

		Returns: None

		Raises: None

		"""
		startByte = self.firstPacket*self.data_size
		count = 0
		packetData = []
		#print("START Byte: ", startByte)
		with open("{}{}".format(ROOTPATH,self.pathname),'rb') as f:
			f.seek(startByte)
			while(count < self.ppa):
				data = f.read(self.data_size)
				if data:
					packetData.append(data)
				else:
					packetData.append(b'\x04'*self.data_size)
					break
				count += 1
		#print(packetData)
		#print("WHAT IS OUR SIZE?: %d" % len(packetData))
		return packetData

	def _updateFileProgress(self,sent=0):
		"""
		Update the progress file with information pertinant to the download.

		Parameters: sent - int - the packet pid that was just sent

		Returns: None

		Raises: None

		"""
		try:
			progress = {
				'filename':self.pathname,
				'direction':'Transmit',
				'checksum':self.checksum,
				'generated_packets': sent,
				'expected_packets': self.expected_packets,
				'file_size':self.filesize,
				'ppa':self.ppa,
				'first_packet':self.firstPacket,
				'last_packet':self.lastPacket,
				'xtea':self.xtea
			}
			text_to_write = 'PROGRESS REPORT FOR {}\n{}\n'.format(info['filename'],'-'*30)
			text_to_write = 'Progress: {}%\n\n'.format(round(100*(info['generated_packets']/info['expected_packets'])))
			for key in progress:
				text_to_write += "{}: {}\n".format(key,str(dictionary[key]))

			with open('{}{}_tr.log'.format(TEMPPATH,self.pathname),'w') as f:
				f.write(text_to_write)
		except:
			pass

class Scaffold():
	""" Handles building and finishing files when they are upload. The scaffold is used to help build a file until it's done."""
	last_pid = -1

	@staticmethod
	def determineDataSize():
		"""
		Figure out what the datasize is

		Parameters: None

		Returns: the data size to put in a packet

		Raises: None

		"""
		# if useFEC:
		# 	return (DataPacket.max_size - DataPacket.header_size) // 3
		# else:
		# 	return DataPacket.max_size - DataPacket.header_size
		return DataPacket.max_size - DataPacket.header_size


	@staticmethod
	def construct(pid,newData):
		"""
		Take new data and put it into a scaffold file

		Parameters:
		pid - the pid of the new data to be added
		newData - bytestring to be added to the new file.

		Returns: None

		Raises: None

		"""
		pid = int.from_bytes(pid,byteorder='big')
		missed_packets = []
		filename = UploadRequest.filename
		# useFEC = UploadRequest.useFEC
		with open("{}{}.scaffold".format(TEMPPATH,filename),"rb+") as scaffold:
			scaffoldData = scaffold.read()
			size = Scaffold.determineDataSize()
			scaffoldData = [scaffoldData[i:i + size] for i in range(0, len(scaffoldData), size)]
			try: # Try to put the data in the scaffold
				# Try to place the data. if pid < Scaffold.last_pid + 1, then we should be able to just replace it.
				scaffoldData[pid] = newData
			except IndexError: # If we can't, make room for it.
				# If we are way ahead, pad the file.
				# print(pid,Scaffold.last_pid+1)
				if pid < Scaffold.last_pid + 1:
					Scaffold._removeMissedPacket(pid,filename)
				if pid > Scaffold.last_pid + 1:
					appendCount = pid - len(scaffoldData) # Get the distance between the current pid placement and the length of all the packets

					# print(appendCount)
					for i in range(appendCount):
						scaffoldData.append(b' '*size) #Put some kind of padding byte there
						missed_packets.append(pid+i)

					Scaffold._updateMissedPackets(missed_packets,filename)

					# print(pid,Scaffold.last_pid+1,appendCount)

				#DEBUG For some reason during testing, if these two operations change order, sometimes it won't order the data properly.
				#I suggest leaving it in this order unless a better method is utilized.
				Scaffold.last_pid = pid # Only set the last_pid to the highest PID, therefore if we get here, then we need to set it.
				scaffoldData.append(newData) # Append the new data. if pid == the last_pid +1, then we just need to append. No padding

			scaffoldData = b''.join(scaffoldData)
			scaffold.seek(0)
			scaffold.write(scaffoldData)

	def _updateMissedPackets(missed_packets,filename):
		"""
		Update the .nore file with which packets are missing

		Parameters:
		missed_packets - a list of newly missed packets.
		filename - the name of the file we are downloading

		Returns: None

		Raises: None

		"""
		try:
			with open('{}{}.nore'.format(TEMPPATH,filename),'a+') as f:
				to_write = f.read()
				if to_write:
					to_write += ','
				to_write += str(missed_packets)[1:-1].replace(' ','')
				f.write(to_write)
		except:
			pass
	def _removeMissedPacket(received_packet,filename):
		"""
		Removes packets from the .nore file if they arrive

		Parameters:
		received_packet - the pid of the packet that we received
		filename - the name of the file that is being downloaded

		Returns: None

		Raises: None

		"""
		try:
			with open('{}{}.nore'.format(TEMPPATH,filename),'r+') as f:
				to_write = f.read()
				to_write = to_write.split(',')
				try:
					to_write.remove(received_packet)
				except:
					pass
				f.write(str(received_packet)[1:-1].replace(' ',''))
		except:
			pass
	@staticmethod
	def finish(information):
		"""
		Finish the scaffold, remove the extension, and remove the extra padding by the last packet.

		Parameters: information - all the data found in the NOOP! packet.

		Returns: a tuple of values
		tuple[0] = True or False if the checksums match from the calculated one and the file's reported checksum
		tuple[1] = the filename of the downloaded file

		Raises: None

		"""
		if UploadRequest.isActive():
			information = information.split(b' ')
			checksum = information[0]
			paddingUsed = int.from_bytes(information[1],byteorder='big')
			filename = information[2][:information[2].find(DataPacket.padding_byte)].replace(b'/',b'@').decode('ascii')
			with open(TEMPPATH+filename+'.scaffold','rb+') as f:
				info = f.read()
				f.seek(0)
				f.truncate()
				if paddingUsed:
					f.write(info[:-paddingUsed])
				else:
					f.write(info)
			checksumMatch = checksum == generateChecksum(open(TEMPPATH+filename+'.scaffold','rb').read())
			try:
				os.rename('{}{}.scaffold'.format(TEMPPATH,filename),ROOTPATH + filename.replace('@','/'))
				os.rename('{}{}.nore'.format(TEMPPATH,filename),"{}{}.nore".format(GRAVEPATH,filename))
			except:
				pass
			return checksumMatch,UploadRequest.finished(filename)

class UploadRequest():
	"""
	Abstract class.
	Class that handles if there is a request to upload a file to the pi.
	The most recent upload request is the file that will be worked on. Multiple upload requests can happen at once, but only the most recent is the current one.
	"""
	received = []
	# useFEC = None
	filename = None

	@staticmethod
	def set(filename = None):
		"""
		 Make an upload request. Perpare a scaffold for being uploaded to and add the file to the list if it's not in there.

		Parameters: filename - the name of the file to be uploaded

		Returns: None

		Raises: None

"""
		try:
			filename = str(filename)
			from pathlib import Path
			Path('{}{}.scaffold'.format(TEMPPATH,filename)).touch()
		except:
			#open(filename.decode('ascii') + '.scaffold','wb').close() #Fallback method to make sure it works
			pass
		# If it's not already in there, add it
		if not filename in UploadRequest.received:
			UploadRequest.received.append(filename)
		# UploadRequest.useFEC = fec
		UploadRequest.filename = filename

	@staticmethod
	def finished(who):
		"""
		Finish an upload. When this method is called, remove the file fro the list.

		Parameters: who - filename for who is finished.

		Returns: the filename that was passed in.

		Raises: None

		"""
		if UploadRequest.received:
			try:
				UploadRequest.received.remove(who)
			except:
				# If there's an issue removing it, there's no use complaining.
				# If there's an exception, it's usually due to the object not being in the list anyway.
				pass
		return who
	@staticmethod
	def isActive():
		"""
		Check if there are any active upload requests

		Parameters: None

		Returns: True if there are any filenames in the list

		Raises:None
		"""
		return len(UploadRequest.received) > 0
