#!/usr/bin/env python3
# qpacePiCommands.py by Jonathan Kessluk, Minh Pham, and Connor Westcott
# qpaceTagChecker by Eric Prather
# 9-3-2018, Rev. 2.5
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This module handles the individual commands for the Pi
#TODO: Re-do comments/documentation

import base64
import os
from subprocess import check_output,Popen
from math import ceil
from time import strftime,gmtime,sleep
import threading
import datetime
import random
import tarfile
import qpaceLogger as qpLog
import traceback
import qpaceExperimentParser as exp
import socket
import sys
import ntpath

try:
	import xtea3
except:
	pass

CMD_DEFAULT_TIMEOUT = 5 #seconds
CMD_POLL_DELAY = .35 #seconds
MISCPATH = '/home/pi/data/misc/'
TEXTPATH = '/home/pi/data/text/'
TEMPPATH = '/home/pi/temp/'
ROOTPATH = '/home/pi/'

def generateChecksum(data):
	"""
	Generates a FNV checksum on the packet data

	Parameters
	----------
	data - bytes - use this to do the checksum on.

	Returns
	-------
	the 4 byte checksum

	Raises
	------
	Any exception gets popped up the stack.
	"""
	checksum = 0x811C9DC5 # 32-Bit FNV Offset Basis
	for byte in data:
		checksum ^= byte
		checksum *= 0x1000193 # 32-Bit FNV Prime
	checksum &= 0xFFFFFFFF
	return checksum.to_bytes(4,byteorder='big')

class Command():
	"""
	Handler class for all commands. These will be invoked from the Interpreter.

	ALL Commands must have the following parameters OR have optional parameters after these:
	(logger, args, silent = False)

	logger - the qpaceLogger.Logger() object for logging data
	args - a bytestring of arguments from the command packet
	silent - optional - If True, then no response packets are sent. These commands are executed silently.

	"""
	_packetQueue = None
	_nextQueue = None
	_tagChecker = None
	_cantsend = False

	def __init__(self,packetQueue=None,nextQueue=None,experimentEvent=None,shutdownEvent = None,disableCallback=None,tagChecker=None):
		Command._packetQueue = packetQueue
		Command._nextQueue = nextQueue
		Command._tagChecker = tagChecker
		self.experimentEvent = experimentEvent
		self.shutdownEvent = shutdownEvent
		self.shutdownAllowed = None
		self.disableCallback = disableCallback
	# Getters and Setters for self.packetQueue
	@property
	def packetQueue(self):
		return Command._packetQueue

	@packetQueue.setter
	def packetQueue(self,queue):
		Command._packetQueue = queue

	@property
	def tagChecker(self):
		return Command._tagChecker

	@tagChecker.setter
	def tagChecker(self,tagChecker):
		Command._tagChecker = tagChecker

	# Getters and Setters for self.nextQueue
	@property
	def nextQueue(self):
		return Command._nextQueue

	@nextQueue.setter
	def nextQueue(self,queue):
		Command._nextQueue = queue

	def setExperimentEvent(self, experimentEvent):
		self.experimentEvent = experimentEvent

	def setDisableCallback(self, disableCallback):
		self.disableCallback = disableCallback

	class CMDPacket():
		"""
		This is a class dedicated to handling packets used in responding to commands from Ground.
		"""

		data_size = 118 #Bytes
		padding_byte = b'\x04'

		def __init__(self,opcode,data):
			"""
			Constructor for CMDPacket.

			Parameters
			----------
			opcode - bytes - set the opcode for the packet
			data - data to store inside the packet

			Returns
			-------
			Void

			Raises
			------
			Any exception gets popped up the stack.
			"""
			self.routing = 0x00
			if type(opcode) is bytes:
				self.opcode = opcode
			else:
				self.opcode = opcode.encode('ascii')
			if type(data) is bytes:
				self.packetData = data
			else:
				self.packetData = data.encode('ascii')

		def send(self):
			"""
			This method sends the data to the WTC  by enquing the data into the packetQueue and
			then queining a SENDPACKET

			Parameters
			----------
			None

			Returns
			-------
			None

			Raises
			------
			Any exception gets popped up the stack.
			"""
			if self.packetData:
				sendData = self.build()
				Command._packetQueue.enqueue(sendData)
				#Command._nextQueue.enqueue('SENDPACKET')

		def build(self):
			"""
			Creates the packet from all the indiviual pieces of data.

			Parameters
			----------
			None

			Returns
			-------
			Void

			Raises
			------
			Any exception gets popped up the stack.
			"""
			if self.packetData == None:
				self.packetData= Command.CMDPacket.padding_byte * self.data_size

			if len(self.packetData) != self.data_size:
				raise ValueError('Length of packetData is not equal to data_size len({})!=Packet.data_size({})'.format(len(self.packetData),self.data_size))

			return bytes([self.routing]) + self.opcode + self.packetData + generateChecksum(self.packetData)

	class PrivilegedPacket(CMDPacket):
		"""
		Reason for Implementation
		-------------------------
		Class to handle all the Privileged packets with XTEA
		"""

		encoded_data_length = 94
		enc_key = None
		enc_iv = None
		tryEncryption = True

		def __init__(self,opcode="NOOP*", cipherText = None,plainText=None):
			"""
			Constructor for a PrivilegedPacket

			Parameters
			----------
			opcode -optional- bytes - the 5 byte opcode
			cipherText - if there is cipherText already then we don't touch it.
			plainText - encode the plaintext if it is here for sending automaticall.

			Returns
			-------
			Void

			Raises
			------
			Any exception gets popped up the stack.
			"""
			tag = Command._tagChecker.getTag()
			if self.tryEncryption:
				self.getEncryptionKeys()

			if cipherText:
				data = self.returnRandom(4) + cipherText + self.returnRandom(6) + b'\x00'*12
			elif plainText:
				data = self.returnRandom(4) + self.encodeXTEA(plainText + tag) + self.returnRandom(6) + b'\x00'*12
			else:
				data = self.returnRandom(4) + Command.CMDPacket.padding_byte * self.encoded_data_length + self.returnRandom(6) + b'\x00'*12
			Command.CMDPacket.__init__(self,opcode=opcode,data=data)

		@staticmethod
		def encodeXTEA(plainText):
			"""
			Encode a plaintext into ciphertext.

			Parameters: plainText - the plaintext to be encoded

			Returns: the cipherText

			Raises: None

			"""
			#print("INSIDE XTEA")
			try:
				if not PrivilegedPacket.enc_key or not PrivilegedPacket.enc_iv:
					raise RuntimeError('No encryption key or IV')
				cipherText = xtea3.new(PrivilegedPacket.enc_key,mode=xtea3.MODE_OFB,IV=PrivilegedPacket.enc_iv).encrypt(plaintext)
			except:
				#print("We didn't Encrypt Properly")
				cipherText = plainText

			return cipherText

		@staticmethod
		def returnRandom(n):
			"""
			Return N random bytes.

			Parameters
			----------
			n - Number of random bytes to return.

			Returns
			-------
			bytes - randomized bytes.

			Raises
			------
			Any exception gets popped up the stack.
			"""
			retval = []
			for i in range(0,n):
				# Get ascii characters from '0' to 'Z'
				num = random.randint(48,122)
				if num == 92: # If we have a backslash, just replace it with something else. It doesn't really matter.
					num = 55
				retval.append(num)
			return bytes(retval)

		@staticmethod
		def getEncryptionKeys():
			tryEncryption = False
			try:
				# This file will be found in the root directory.
				with open(SECRETS,'rb') as fi:
					Command.PrivilegedPacket.enc_key = fi.readline().rstrip()
					Command.PrivilegedPacket.enc_iv = fi.readline().rstrip()
			except Exception as e:
				# If we can't even attempt to decode XTEA packets, then there's no reason to run QPACE though...
				pass

	def status(self,logger,args, silent=False):
		"""
		Create a StatusPacket and respond with the response packet.
		"""
		timestamp = datetime.datetime.now()
		try:
			import threading
			thread = threading.Thread(target=self.saveStatus, args=(logger,timestamp))
			thread.start()
		except:
			thread = None
		data =  bytes([timestamp.month, timestamp.day, timestamp.year - 2000, timestamp.weekday(), timestamp.hour,timestamp.minute,timestamp.second])
		status = b''
		status += b'E(' + str(logger.Errors.get()).encode('ascii') + b'):' #Number of errors logged since last boot
		status_file = str(timestamp) if thread else 'Save Failed' # Save the timestamp inwhich this status file will be saved as.
		status += b'F('+ status_file.encode('ascii') +b'):' # the File where the major status stuff should be being saved in.
		try:
			from qpaceInterpreter import LastCommand
			status += b'LC('+LastCommand.type.encode('ascii')+b')'
		except Exception as err:
			logger.logError("Could not import LastCommand",err)
		data += status + b' '*(111-len(status)) # 111 defined in packet structure document r4a
		if not silent:
			Command.CMDPacket(opcode='STATS',data=data).send()
		if thread:
			thread.join() # Make sure we wait for the thread to close if it's still going.

	def directoryListingSet(self,logger,args, silent=False):
		"""
		Create a DirectoryListingPacket and respond with the response packet.
		"""
		fileDir = args.replace(b'\x04', b'')
		pathname = ROOTPATH + fileDir.decode('ascii').split(' ')[0]


		try:
			lenstr = str(len(os.listdir(pathname))) # Get the number of files/directories in this directory.
		except FileNotFoundError:
			lenstr = "Error in Directory List Set: No such file or directory {}.".format(fileDir)

		if not silent:
			padding = Command.CMDPacket.padding_byte*(Command.PrivilegedPacket.encoded_data_length-len(lenstr)) #98 due to specification of packet structure
			plainText = lenstr.encode('ascii')
			plainText += padding
			Command.PrivilegedPacket(plainText=plainText).send()

	def directoryList(self,logger,args, silent=False):
		"""

		Create a SendDirectoryList packet and respond with the response packet.
		"""
		fileDir = args.replace(b'\x04', b'')
		pathname = ROOTPATH + fileDir.decode('ascii').split(' ')[0]
		
		filepath = TEXTPATH+ntpath.basename(pathname[:-1]) + "dir.txt"
		try:
			pathList = check_output(['ls','-alh',pathname]).decode("utf-8")
		except:
			pathList = "No such file or directory:'{}'".format(pathname)
		with open(filepath, "w") as filestore:
			filestore.write("Timestamp: {}\n".format(strftime("%Y%m%d-%H%M%S",gmtime())))
			filestore.write(pathList)
		if not silent:
			padding = Command.CMDPacket.padding_byte * (Command.PrivilegedPacket.encoded_data_length - len(filepath))
			plainText = filepath.encode('ascii')
			plainText += padding
			Command.PrivilegedPacket(plainText=plainText).send()

	def splitVideo(self,logger,args, silent=False):
		args = args.decode('ascii').split(' ')
		path = ROOTPATH + args[0]
		nam_i,ext_i = path.rfind('/'),path.rfind('.')
		ext_i = None if ext_i < 0 or ext_i < nam_i else ext_i # If it's -1 or if it's before the first slash, then ignore it.
		filename = path[nam_i+1:ext_i] #get the filename from the path, remove the extension if there is one.
		minute = args[1]
		second = args[2]

		os.system('cd ffmpeg -i {} -c copy -map 0 -segment_time 00:{}:{} -f segment {}_%03d.mp4 &> /dev/null'.format(path,minute,second,filename))
		if not silent:
			self.directoryList(logger,bytes(args[0], 'ascii')) # pass in the path stated above without the file to get the directory list.
		#NOTE: self.directoryList() will send a PrivilegedPacket back to the ground. This calls the directoryList command because we want the same behaviour

	def convertVideo(self,logger,args, silent=False):
		args = args.decode('ascii').split(' ')
		pathToVideo = args[0]
		nam_i,ext_i = pathToVideo.rfind('/'),pathToVideo.rfind('.')
		ext_i = None if ext_i < 0 or ext_i < nam_i else ext_i # If it's -1 or if it's before the first slash, then ignore it.
		filename = pathToVideo[nam_i+1:ext_i] #get the filename from the path, remove the extension if there is one.
		pathToVideo = ROOTPATH + pathToVideo[:nam_i]
		os.system('MP4Box -add {}{}.h264 {}{}.mp4 &> /dev/null'.format(pathToVideo,filename,pathToVideo,filename))
		returnValue = check_output(['ls','-la',"{}{}.mp4".format(pathToVideo,filename)])
		returnValue += returnValue.encode('ascii') + Command.CMDPacket.padding_byte*(Command.CMDPacket.data_size - len(returnValue))
		if not silent:
			Command.CMDPacket(opcode='TOMP4',data=returnValue).send()

	def move(self,logger,args, silent=False):
		"""
		Move a file from one location to another.
		Create a MoveFilePacket and respond with the response packet.
		"""
		args = args.replace(b'\x04', b'').decode('ascii').split(' ')
		# Remove the 'doubledot' this way you can't modify or move or change anything outside of the working directory.
		originalFile = (ROOTPATH + args[0]).replace('..','')
		pathToNewFile = (ROOTPATH + args[1]).replace('..','')

		try:
			import shutil
			shutil.move(originalFile, pathToNewFile)
			exception = None
			wasMoved = 'was'
		except Exception as e:
			exception = str(e)
			wasMoved = 'was not'

		filepath = MISCPATH+'MoveFile.log'
		with open(filepath, "a+") as filestore:
			timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
			m='{} {} moved to {}'.format(originalFile, wasMoved, pathToNewFile)
			filestore.write('[{}] {}\n'.format(timestamp,m))
			logger.logSystem(m)
			if exception: filestore.write('[{}] {}\n'.format(timestamp,exception))

		if not silent:
			wasMoved = "{} {} moved.".format(originalFile, wasMoved)
			if exception:
				wasMoved += " {}".format(exception)
			wasMoved = wasMoved[:Command.PrivilegedPacket.encoded_data_length]
			padding = Command.CMDPacket.padding_byte * (Command.PrivilegedPacket.encoded_data_length - len(wasMoved))
			plainText = wasMoved.encode('ascii')
			plainText += padding
			Command.PrivilegedPacket(plainText=plainText).send()

	def tarExtract(self,logger,args, silent=False):
		"""
		Extract a Tar file.
		Create a TarBallFilePacket and respond with the response packet.
		"""
		args = args.decode('ascii').split(' ')
		inputFilename = ROOTPATH + args[0].replace('\x04', '')
		
		# Raise an error if the filename does not end in .tar
		if (inputFilename[-4:] != '.tar'):
			logger.logError("Error: Received request to extract a non-tar file")
			return
		outputFilename = inputFilename[:-4]
		try:
			with tarfile.open(inputFilename) as tar:
				tar.extractall()
			os.remove(inputFilename)
			logger.logSuccess("Successfully extracted " + inputFilename)
			message = b'Done'
		except:
			logger.logError("Failed to extract " + inputFilename)
			message = b'Failed'
		if not silent:
			plainText = message + Command.CMDPacket.padding_byte * (Command.PrivilegedPacket.encoded_data_length-len(message))
			Command.PrivilegedPacket(plainText=plainText).send()

	def tarCreate(self,logger,args, silent=False):
		"""
		Create a compressed Tar.
		Create a TarBallFilePacket and respond with the response packet.
		"""
		import tarfile
		args = args.replace(b'\x04', b'').decode('ascii').split(' ')
		# The name of the new file will be whatever was input, but since the path could be long
		# create the {}.tar.gz at the filename. Since it could be a directory with a /
		# look for the 2nd to last / and then slice it. Then remove and trailing /'s
		if args[0].endswith('/'):
			args[0] = args[0][:-1]
		newFile = ROOTPATH + args[0][args[0].rfind('/')+1:]+'.tar'
		tarDir = '{}.tar.gz'.format(newFile)
		try:
			with tarfile.open(newFile, "w:gz") as tar:
				tar.add(ROOTPATH+args[0])
			message = tarDir.encode('ascii')
			logger.logSuccess('Successfully created ' + newFile)
		except Exception as e:
			logger.logError("Failed to make tar.\nException: {}".format(e))
			message = b'Failed to tar.'

		if not silent:
			plainText = message + Command.CMDPacket.padding_byte * (Command.PrivilegedPacket.encoded_data_length - len(message))
			Command.PrivilegedPacket(plainText=plainText).send()

	
	def encodeFile(self, path=None, silent=False):
		import qpaceFileHandler as qfh
		
		with open("{}{}".format(ROOTPATH, path), "rb") as dataFile:
			data = base64.b64encode(dataFile.read())#, altchars='+/')

		encoded_filename = "{0}.encode".format(path)

		if os.path.isfile(encoded_filename):
			os.remove(encoded_filename)

		with open(encoded_filename, "wb") as encodedFile:
			encodedFile.write(data)

		path = encoded_filename

		try:
			size_of_file = os.path.getsize("{}{}".format(ROOTPATH,path))
		except FileNotFoundError as e:
			size_of_file = 0
		# 114 is the maximum alotment of data space in the files. the other 14 bytes are header and checksum data
		# Get the number of packets estimated to be in this thing.
		data = ((size_of_file//qfh.DataPacket.data_size) + 1).to_bytes(4,'big')
		self.NumPackets = ((size_of_file//qfh.DataPacket.data_size) + 1)
		data += b'\n'
		if size_of_file > qfh.MAX_FILE_SIZE:
			data += ('File Too large. Send less than 400MB at a time.\n')
		if size_of_file > 0:
			data += check_output(['ls','-la',"{}{}".format(ROOTPATH,path)])
		else:
			data += ('FileNotFound:{}{}'.format(ROOTPATH,path)).encode('ascii')
		if not silent:
			padding = Command.CMDPacket.data_size - len(data)
			data += Command.CMDPacket.padding_byte * padding if padding > 0 else 0
			Command.CMDPacket(opcode='DOWNR',data=data).send()

	def dlReq(self,logger,args, silent=False):
		"""
		Create a DownloadRequestPacket and respond with the response packet.
		"""
		import qpaceFileHandler as qfh
		path = args[:].replace(b'\x04',b'').decode('ascii') # Now just reads the entire list

		encodeThread = threading.Thread(name='file encoder',target=self.encodeFile, args=(path, silent))
		encodeThread.start()
		"""
		Create Encoded file for possible transmission.
		If the file is able to be sent, then we will send
		down the encoded data for re-coding on ground

		WARNING: Assumes path is in the local directory not in another
		outside directory.
		"""
		'''
		with open("{}{}".format(ROOTPATH, path), "rb") as dataFile:
			data = base64.b64encode(dataFile.read())#, altchars='+/')

		encoded_filename = "{0}.encode".format(path)

		if os.path.isfile(encoded_filename):
			os.remove(encoded_filename)

		with open(encoded_filename, "wb") as encodedFile:
			encodedFile.write(data)

		path = encoded_filename

		try:
			size_of_file = os.path.getsize("{}{}".format(ROOTPATH,path))
		except FileNotFoundError as e:
			size_of_file = 0
		# 114 is the maximum alotment of data space in the files. the other 14 bytes are header and checksum data
		# Get the number of packets estimated to be in this thing.
		data = ((size_of_file//qfh.DataPacket.data_size) + 1).to_bytes(4,'big')
		self.NumPackets = ((size_of_file//qfh.DataPacket.data_size) + 1)
		data += b'\n'
		if size_of_file > qfh.MAX_FILE_SIZE:
			data += ('File Too large. Send less than 400MB at a time.\n')
		if size_of_file > 0:
			data += check_output(['ls','-la',"{}{}".format(ROOTPATH,path)])
		else:
			data += ('FileNotFound:{}{}'.format(ROOTPATH,path)).encode('ascii')
		if not silent:
			padding = Command.CMDPacket.data_size - len(data)
			data += Command.CMDPacket.padding_byte * padding if padding > 0 else 0
			Command.CMDPacket(opcode='DOWNR',data=data).send()
		'''

	def dlFile(self,logger,args, silent=False):
		"""
		Create a mitter instance and transmit a file packet by packet to the WTC for Ground.
		"""
		import qpaceFileHandler as qfh
		qfh.DataPacket.last_id = 0
		# fec = args[0]
		ppa = int.from_bytes(args[1:5],byteorder='big')  #HOW MANY YOU WANT BOI
		if ppa < 1:
			# Takes care of the case were we want just one packet
			ppa = 1
		start = int.from_bytes(args[5:9], byteorder='big')
		end = int.from_bytes(args[9:13], byteorder='big')
		filename = args[13:].replace(Command.CMDPacket.padding_byte,b'')

		# 114 is the maximum alotment of data space in the files. the other 14 bytes are header and checksum data
		# Get the number of packets estimated to be in this thing.
		# print('FEC:',fec)
		#print('STR:',start)
		#print('END:',end)
		#print('FNM:',filename)


		"""TODO
		Encode file into Encoded_<Filename>.txt
		Encoding method should use base64 lib
		"""
		filename = filename.decode('ascii')
		encoded_filename = "{0}.encode".format(filename)

		print(Command._cantsend)
		if not silent:
			try:
				#print("Creating transmitter")
				transmitter = qfh.Transmitter(
												encoded_filename,
												0x00,
												# useFEC = fec == b' FEC',
												ppa=ppa,
												firstPacket = start,
												lastPacket = end,
												xtea = False,
												packetQueue = self._packetQueue
											)
				#print("Trying to run transmitter")
				try:
					transmitterThread = threading.Thread(name='qpf Transmitter',target=transmitter.run, args=())
					transmitterThread.start()
					#transmitter.run()
					logger.logSuccess("Transmitter Ran!")
				except Exception as e:
					logger.logError("Transmitter Failed to RUN")
					#logger.logError("%s"%str(e))
					_, __, exc_traceback = sys.exc_info()
					logger.logError(exc_traceback)
					pass
			except FileNotFoundError:
				logger.logSystem('Transmitter: Could not find the file requested for: {}'.format(filename.decode('ascii')))

		'''
		#else:
				# For however many transactions the WTC can handle, enqueue a SENDPACKET so when the WTC asks "WHATISNEXT" the Pi can tell it it wants to send packets.
		for x in range((len(self._packetQueue)//qfh.WTC_PACKET_BUFFER_SIZE)):
			self.nextQueue.enqueue('SENDPACKET') # taken from qpaceControl

		if(self.NumPackets == end):
			self.nextQueue.enqueue('SENDPACKET') # taken from qpaceControl
		'''

	def upReq(self,logger,args, silent=False):
		"""
		We have received an Upload Request. Figure out the necessary information and
		make an UploadRequest active by calling UploadRequest.set()
		"""
		# Numbers based on Packet Specification Document.
		import qpaceFileHandler as qfh
		filename = args.replace(Command.CMDPacket.padding_byte,b'').replace(b' ',b'').replace(b'/',b'@').replace(b'..', b'')
		if qfh.UploadRequest.isActive():
			logger.logSystem("UploadRequest: Redundant Request? ({})".format(str(filename)))
		qfh.UploadRequest.set(filename=filename.decode('ascii'))
		logger.logSystem("UploadRequest: Upload Request has been received. ({})".format(str(filename)))
		if not silent:
			response = b'up'
			response += b'Active Requests: ' + bytes([len(qfh.UploadRequest.received)])
			response += b' Using Scaffold: ' + qfh.UploadRequest.filename.encode('ascii')
			response += Command.PrivilegedPacket.padding_byte * (Command.PrivilegedPacket.encoded_data_length - len(response))
			Command.PrivilegedPacket(plainText=response).send()

	def runHandbrake(self,logger,args, silent=False):
		args = args.replace(b'\x04', b'').decode('ascii').split(' ')
		inputFile = args[0]
		outputFile = args[1]
		# > /dev/null 2>&1 to hide the command from terminal because it outputs gibberish
		# the '&' is so the command runs in the background.
		handbrakeCommand = 'HandBrakeCLI -a none -q 10 -vfr -g -i {} -o {} -e x264 > /dev/null 2>&1 &'.format(inputFile,outputFile)
		os.system(handbrakeCommand)
		if not silent:
			msg = 'HandBrake: In({}) Out({})'.format(inputFile,outputFile).encode('ascii')
			data = msg + Command.PrivilegedPacket.padding_byte * (Command.CMDPacket.data_size - len(msg))
			print(data)
			Command.CMDPacket(opcode='HANDB',data=data).send()

	def startExperiment(self,logger,args, silent=False):

		filename = args.replace(Command.CMDPacket.padding_byte, b'').decode('ascii')


		if self.experimentEvent is None or self.experimentEvent.is_set():
			raise StopIteration('experimentEvent is None or experimentEvent is set.') # If experimentEvent does not exist or is set, return False to know there is a failure.
		runEvent = threading.Event()
		runEvent.set()
		# Run an experiment file from the experiment directory
		logger.logSystem("Command recieved: Running an experiment.", filename) # Placeholder
		parserThread = threading.Thread(name='experimentParser',target=exp.run, args=(filename,self.experimentEvent,runEvent,logger,self.nextQueue,self.disableCallback))
		parserThread.start()
		if not silent:
			data = bytes('Attempting to start experiment <{}> if it exists.'.format(filename), 'ascii')
			data += Command.CMDPacket.padding_byte * (Command.CMDPacket.data_size - len(data))
			Command.CMDPacket(opcode='EXPMT',data=data).send()

	def immediateShutdown(self,logger,args, silent=False):
		"""
		Initiate the shutdown proceedure on the pi and then shut it down. Will send a status to the WTC
		The moment before it actually shuts down.

		Parameters
		----------
		chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
		args - string, array of args (seperated by ' ') - the actual command, the args for the command

		Raises
		------
		SystemExit - If the interpreter can even get to this point... Close the interpreter.
		"""
		# We'll need to call this method twice within 2 minutes to have this work. Otherwise, it won't do anything.
		logger.logSystem('immediateShutdown: A shutdown packet was received. shutdownAllowed is {}set.'.format('' if self.shutdownAllowed else 'not '))
		if self.shutdownAllowed:
			if (datetime.datetime.now() - self.shutdownAllowed) > datetime.timedelta(seconds = 120): # If we tried after two minutes:
				self.shutdownAllowed = datetime.datetime.now() # Reset it to now and don't do anything.
			else: # If we tried and it's withing 2 minutes
				logger.logSystem('immediateShutdown: Shutting down...')
				os.system('sleep 5 && sudo halt &') # fork a process that sleeps for 5 seconds, then does a sudo halt.
				self.shutdownEvent.set() # Close the interpreter and clean up the buffers before reboot happens.
		else:
			self.shutdownAllowed = datetime.datetime.now() # Set the time to now so we can check it on the next packet.

	# Not a command to be envoked by the Interpreter
	def saveStatus(self,logger,timestamp = strftime("%Y%m%d-%H%M%S",gmtime())):

		logger.logSystem("Attempting to get the status of the Pi")
		identity = 0
		cpu = 'Unknown'
		cpu_temp = 'Unknown'
		uptime = 'Unknown'
		ram_tot = 'Unknown'
		ram_used = 'Unknown'
		ram_free = 'Unknown'
		disk_free = 'Unknown'
		disk_total = 'Unknown'
		last_command = "Unknown"
		last_command_from = "Unknown"
		last_command_when = "Unknown"
		commands_executed = "Unknown"
		boot = "Unknown"
		try:
			from qpaceInterpreter import LastCommand
			last_command = LastCommand.type
			last_command_when = LastCommand.timestamp
			last_command_from = LastCommand.fromWhom
			commands_executed = LastCommand.commandCount
			#print("LAST: %s, WHEN %s, FROM %s, Commands %d" %(LastCommand.type, LastCommand.timestamp, LastCommand.fromWhom, LastCommand.commandCount))
		except Exception as err:
			logger.logError("Could not import LastCommand",err)
		try:
			cpu = str(round(100 - float(check_output("top -b -n 2 |grep Cpu|tail -1|awk -v N=8 '{print $N}'", shell=True)),3))
			cpu_temp = str(int(os.popen('cat /sys/class/thermal/thermal_zone0/temp').read()[:-1])/1000)
		except Exception as err:
			logger.logError("There was a problem accessing the CPU stats", err)
		try:
			ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
		except Exception as err:
			logger.logError("There was a problem accessing the IP address", err)
		try:
			uptime =  os.popen("uptime").read().split(' ')
			uptime = "{} {} {} {} {} {}".format(uptime[3],uptime[4],uptime[10],uptime[11],uptime[12],uptime[13])[:-1]
		except Exception as err:
			logger.logError("There was a problem accessing the uptime", err)
		try:
			mem = os.popen('free -b').readlines()
			mem = mem[1].split(' ')
			mem = [num for num in mem if num.isdigit()]
			ram_tot = mem[1]
			ram_used = mem[2]
			ram_free = mem[3]
		except Exception as err:
			logger.logError("There was a problem accessing the RAM stats", err)
		try:
			statvfs = os.statvfs('/')
			disk_used = statvfs.f_frsize * statvfs.f_blocks     # Size of filesystem in bytes
			disk_free = statvfs.f_frsize * statvfs.f_bfree      # Actual number of free bytes
		except Exception as err:
			logger.logError("There was a problem accessing the Disk stats", err)

		try:
			ps_data = check_output(['ps','al']).decode('utf-8')
		except:
			ps_data = 'Unable to get data.\n'

		text_to_write = "Identity: Pi {}\n"     +\
						"Boot: {}\n"			+\
						"Last Command Executed was \"{}\" at {} invoked by \"{}\"\n" +\
						"Commands Executed: {}\n" +\
						"CPU Usage: {}%\n"      +\
						"CPU Temp: {} deg C\n"  +\
						"Uptime: {}\n"  		+\
						"RAM Total: {} bytes\n" +\
						"RAM Used: {} bytes\n"  +\
						"RAM Free: {} bytes\n"  +\
						"Disk total: {}\n"      +\
						"Disk free: {}\n"
		text_to_write = text_to_write.format(identity,boot,last_command,last_command_when,last_command_from,commands_executed,cpu,cpu_temp,
								uptime,ram_tot,ram_used,ram_free,disk_total,disk_free)
		text_to_write += ps_data

		timestamp = str(timestamp).replace(' ', '_')
		#print("WHAT IS THE TIME: %s" % timestamp)
		logger.logSystem("saveStatus: Attempting to save the status to a file.")
		try:
			with open(MISCPATH+'status_'+timestamp,'w') as statFile:
				statFile.write(text_to_write)
		except Exception as err:
			logger.logError("There was a problem writing the status file.",err)
