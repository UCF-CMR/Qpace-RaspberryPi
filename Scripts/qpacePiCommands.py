#!/usr/bin/env python3
# qpacePiCommands.py by Jonathan Kessluk and Minh Pham
# 9-3-2018, Rev. 2.5
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# This module handles the individual commands for the Pi
#TODO: Re-do comments/documentation

import os
from subprocess import check_output,Popen
from math import ceil
from time import strftime,gmtime,sleep
import threading
import datetime
import random
import tarfile
import qpaceLogger as qpLog

try:
	import xtea3
except:
	pass



WTC_PACKET_BUFFER_SIZE = 10 # How many packets can the WTC store?


CMD_DEFAULT_TIMEOUT = 5 #seconds
CMD_POLL_DELAY = .35 #seconds
MISCPATH = 'home/pi/data/misc/'
TEXTPATH = 'home/pi/data/text/'
TEMPPATH = '/home/pi/temp/'
ROOTPATH = '/home/pi/'
MISCPATH = '/mnt/c/users/jonat/desktop/cmr/pi/data/misc/'
TEXTPATH = '/mnt/c/users/jonat/desktop/cmr/pi/data/text/'
ROOTPATH= '/mnt/c/users/jonat/desktop/cmr/pi/'
TEMPPATH = '/mnt/c/users/jonat/desktop/cmr/pi/temp/'

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
	Reason for Implementation
	-------------------------
	Handler class for all commands. These will be invoked from the Interpreter.
	"""
	_packetQueue = None
	_nextQueue = None

	def __init__(self,packetQueue=None,nextQueue=None,experimentEvent=None):
		Command._packetQueue = packetQueue
		Command._nextQueue = nextQueue
		self.experimentEvent = experimentEvent

	# Getters and Setters for self.packetQueue
	@property
	def packetQueue(self):
		return Command._packetQueue

	@packetQueue.setter
	def packetQueue(self,queue):
		Command._packetQueue = queue

	# Getters and Setters for self.nextQueue
	@property
	def nextQueue(self):
		return Command._nextQueue

	@nextQueue.setter
	def nextQueue(self,queue):
		Command._nextQueue = queue

	class CMDPacket():
		"""
		Reason for Implementation
		-------------------------
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
			chip - an SC16IS750 object.

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
			This method sends the data to the WTC as a block write.

			Parameters
			----------
			None

			Returns
			-------
			True if successful
			False if unsuccessful

			Raises
			------
			Any exception gets popped up the stack.
			"""
			if self.packetData:
				sendData = self.build()
				self.packetQueue.enqueue(sendData)
				self.nextQueue.enqueue('SENDPACKET')

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
				self.packetData=CMDPacket.padding_byte * self.data_size

			if len(self.packetData) != self.data_size:
				raise ValueError('Length of packetData is not equal to data_size len({})!=Packet.data_size({})'.format(len(self.packetData),self.data_size))

			return bytes([self.routing]) + self.opcode.encode('ascii') + self.packetData + generateChecksum(self.packetData)

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

		def __init__(self,opcode,tag=None, cipherText = None,plainText=None):
			"""
			Constructor for a PrivilegedPacket

			Parameters
			----------
			chip - an SC16IS750 object.
			opcode - bytes - the 5 byte opcode
			tag - bytes - the 2 byte tag
			cipherText - if there is cipherText already for the packet it is automatically decoded.

			Returns
			-------
			Void

			Raises
			------
			Any exception gets popped up the stack.
			"""
			if tryEncryption:
				getEncryption()

			if cipherText:
				data = PrivilegedPacket.returnRandom(4) + cipherText + PrivilegedPacket.returnRandom(6) + b'\x00'*12
			elif plainText:
				data = PrivilegedPacket.returnRandom(4) + PrivilegedPacket.encodeXTEA(plainText + tag) + PrivilegedPacket.returnRandom(6) + b'\x00'*12
			else:
				data = PrivilegedPacket.returnRandom(4) + CMDPacket.padding_byte * PrivilegedPacket.encoded_data_length + PrivilegedPacket.returnRandom(6) + b'\x00'*12
			CMDPacket.__init__(self,opcode=opcode,data=data)

		@staticmethod
		def encodeXTEA(plainText):
			"""
			Encode a plaintext into ciphertext.
			"""
			try:
				if not enc_key or not enc_iv:
					raise RuntimeError('No encryption key or IV')
				cipherText = xtea.new(PrivilegedPacket.enc_key,mode=xtea.MODE_OFB,IV=PrivilegedPacket.enc_iv).encrypt(plaintext)
			except:
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
		def getEncryption():
			tryEncryption = False
			try:
				# This file will be found in the root directory.
				with open(SECRETS,'rb') as fi:
					PrivilegedPacket.enc_key = fi.readline()
					PrivilegedPacket.enc_iv = fi.readline()
			except Exception as e:
				# If we can't even attempt to decode XTEA packets, then there's no reason to run QPACE though...
				logger.logError('Interpreter: Unable to import keys. XTEA Encoding is disabled.',e)

	def status(self,chip,logger,cmd,args):
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
		status += b'F('+ status_file.encode('ascii') +b')' # the File where the major status stuff should be being saved in.
		data += status + b' '*(111-len(status)) # 111 due to defined packet Structure
		p = CMDPacket(opcode='STATS',data=data).send()
		if thread:
			thread.join() # Make sure we wait for the thread to close if it's still going.

	def directoryListingSet(self,chip,logger,cmd,args):
		"""
		Create a DirectoryListingPacket and respond with the response packet.
		"""
		pathname = ROOTPATH + args.split(' ')[0]
		tag = b"AA"

		lenstr = str(len(os.listdir(pathname))) # Get the number of files/directories in this directory.
		padding = CMDPacket.padding_byte*(PrivilegedPacket.encoded_data_length-len(lenstr)) #98 due to specification of packet structure
		plainText = lenstr.encode('ascii')
		plainText += padding
		p = PrivilegedPacket(opcode="NOOP*",tag=tag,plainText=plainText).sned()

	def directoryList(self,chip,logger,cmd,args):
		"""

		Create a SendDirectoryList packet and respond with the response packet.
		"""
		pathname = args.split(' ')[0]
		tag = b"AA"
		self.pathname = pathname
		filepath = TEXTPATH
		try:
			pathList = os.listdir(pathname)
		except:
			pathList = ["No such file or directory:'{}'".format(pathname)]
		with open(filepath, "w") as filestore:
			filestore.write("Timestamp: {}\n".format(strftime("%Y%m%d-%H%M%S",gmtime())))
			for line in pathList:
				filestore.write(line + '\n')
		padding = CMDPacket.padding_byte * (PrivilegedPacket.encoded_data_length - len(filepath))
		plainText = filepath.encode('ascii')
		plainText += padding
		p = PrivilegedPacket(opcode="NOOP*", tag=tag,plainText=plainText).send()

	def splitVideo(self,chip,logger,cmd,args):
		args = args.split(' ')
		path = ROOTPATH + args[0]
		nam_i,ext_i = path.rfind('/'),path.rfind('.')
		ext_i = None if ext_i < 0 or ext_i < nam_i else ext_i # If it's -1 or if it's before the first slash, then ignore it.
		filename = path[nam_i+1:ext_i] #get the filename from the path, remove the extension if there is one.
		minute = args[1]
		second = args[2]

		os.system('cd ffmpeg -i {} -c copy -map 0 -segment_time 00:{}:{} -f segment {}_%03d.mp4 &> /dev/null'.format(pathname,hour,second,filename))
		self.directoryList(chip,logger,cmd,path[:nam_i]) # pass in the path stated above without the file to get the directory list.
		#NOTE: self.directoryList() will send a PrivilegedPacket back to the ground. This calls the directoryList command because we want the same behaviour


	def convertVideo(self,chip,logger,cmd,args):
		args = args.split(' ')
		pathToVideo = args[0]
		nam_i,ext_i = pathToVideo.rfind('/'),pathToVideo.rfind('.')
		ext_i = None if ext_i < 0 or ext_i < nam_i else ext_i # If it's -1 or if it's before the first slash, then ignore it.
		filename = pathToVideo[nam_i+1:ext_i] #get the filename from the path, remove the extension if there is one.
		pathToVideo = ROOTPATH + pathToVideo[:nam_i]
		os.system('MP4Box -add {}{}.h264 {}{}.mp4 &> /dev/null'.format(pathToVideo,filename,pathToVideo,filename))
		returnValue = check_output(['ls','-la',"{}{}.mp4".format(pathToVideo,filename)])
		returnValue += returnValue.encode('ascii') + CMDPacket.padding_byte*(CMDPacket.data_size - len(returnValue))
		p = CMDPacket(opcode='TOMP4',data=returnValue).send()

	def move(self,chip,logger,cmd,args):
		"""
		Move a file from one location to another.
		Create a MoveFilePacket and respond with the response packet.
		"""
		args = args.split(' ')
		originalFile = ROOTPATH + args[0]
		pathToNewFile = ROOTPATH + args[1]
		tag = b'AA'
		try:
			import shutil
			shutil.move(originalFile, pathToNewFile)
			exception = None
			wasMoved = 'was'
		except Exception as e:
			exception = str(e)
			wasMoved = 'was not'

		filepath = '../data/MoveFile.log'
		with open(filepath, "a+") as filestore:
			timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
			filestore.write('[{}] {}: {} {} moved to {}\n'.format(timestamp, wasMoved=='was',originalFile, wasMoved, pathToNewFile))
			if exception: filestore.write('[{}] {}\n'.format(timestamp,exception))
		wasMoved = "{} {} moved.".format(originalFile, wasMoved)
		padding = CMDPacket.padding_byte * (PrivilegedPacket.encoded_data_length - len(wasMoved))
		plainText = wasMoved.encode('ascii')
		plainText += padding
		p = PrivilegedPacket(opcode="NOOP*",tag=tag,plainText=plainText).send()

	def tarExtract(self,chip,logger,cmd,args):
		"""
		Extract a Tar file.
		Create a TarBallFilePacket and respond with the response packet.
		"""
		tempdir = "../temp/"
		args = args.split(' ')
		filename = args[0]
		pathname = args[1]
		with tarfile.open(tempdir + filename) as tar:
			tar.extractall(path=pathname)
		try:
			os.remove(tempdir + filename)
		except:pass
		message = b'DONE'
		plainText = message + CMDPacket.padding_byte * (PrivilegedPacket.encoded_data_length-len(message))
		p = PrivilegedPacket(opcode="NOOP*",tag=b'AA',plainText=plainText).send()

	def tarCreate(self,chip,logger,cmd,args):
		"""
		Create a compressed Tar.
		Create a TarBallFilePacket and respond with the response packet.
		"""
		import tarfile
		args = args.split(' ')
		# The name of the new file will be whatever was input, but since the path could be long
		# create the {}.tar.gz at the filename. Since it could be a directory with a /
		# look for the 2nd to last / and then slice it. Then remove and trailing /'s
		newFile = args[0][args[0].rfind('/') + 1:].replace('/','')
		tarDir = '..{}{}.tar.gz'.format(MISCPATH,newFile)
		with tarfile.open(tarDir, "w:gz") as tar:
			tar.add(args[0], arcname=os.path.basename(args[0]))

		plainText = tarDir.encode('ascii') + CMDPacket.padding_byte*(CMDPacket.data_size - len(tarDir))
		p = PrivilegedPacket(opcode='NOOP*',tag=b'AA',plainText=plainText).send()

	def dlReq(self,chip,logger,cmd,args):
		"""
		Create a DownloadRequestPacket and respond with the response packet.
		"""
		import qpaceFileHandler as qfh
		path = args[4:].replace(b'\x04',b'').decode('ascii')
		try:
			size_of_file = os.path.getsize("{}{}".format(ROOTPATH,path))
		except FileNotFoundError as e:
			size_of_file = 0
			# 114 is the maximum alotment of data space in the files. the other 14 bytes are header and checksum data
			# Get the number of packets estimated to be in this thing.
			data = ((size_of_file//114) + 1).to_bytes(4,'big')
			data += b'\n'
		if size_of_file > qfh.MAX_FILE_SIZE:
			data += ('File Too large. Send less than 400MB at a time.\n')
		if size_of_file > 0:
			data += check_output(['ls','-la',"{}{}".format(ROOTPATH,path)])
		else:
			data += ('FileNotFound:{}{}'.format(ROOTPATH,path)).encode('ascii')
		padding = CMDPacket.data_size - len(data)
		data += CMDPacket.padding_byte * padding if padding > 0 else 0
		p = CMDPacket(opcode='DOWNR',data=data).send()

	def dlFile(self,chip,logger,cmd,args):
		"""
		Create a mitter instance and transmit a file packet by packet to the WTC for Ground.
		"""
		import qpaceFileHandler as qfh
		qfh.DataPacket.last_id = 0
		# fec = args[:4]
		start = int.from_bytes(args[4:8], byteorder='big')
		end = int.from_bytes(args[8:12], byteorder='big')
		filename = args[12:].replace(CMDPacket.padding_byte,b'')
		# print('FEC:',fec)
		print('STR:',start)
		print('END:',end)
		print('FNM:',filename)
		try:
			transmitter = qfh.Transmitter(	chip,
											filename.decode('ascii'),
											0x01,
											# useFEC = fec == b' FEC',
											firstPacket = start,
											lastPacket = end,
											xtea = False,
											packetQueue = self._packetQueue
										)
		except FileNotFoundError:
			logger.logSystem('Transmitter: Could not find the file requested for: {}'.format(filename.decode('ascii')))
		else:
			transmitter.run()
		finally:
			# For however many transactions the WTC can handle, enqueue a SENDPACKET so when the WTC asks "WHATISNEXT" the Pi can tell it it wants to send packets.
			for x in range((len(self._packetQueue)//WTC_PACKET_BUFFER_SIZE) + 1):
				self.nextQueue.enqueue('SENDPACKET') # taken from qpaceControl

	def upReq(self,chip,logger,cmd,args):
		"""
		We have received an Upload Request. Figure out the necessary information and
		make an UploadRequest active by calling UploadRequest.set()
		"""
		# Numbers based on Packet Specification Document.
		import qpaceFileHandler as qfh
		filename = args.replace(CMDPacket.padding_byte,b'').replace(b'/',b'@')
		if qfh.UploadRequest.isActive():
			logger.logSystem("UploadRequest: Redundant Request? ({})".format(str(filename)))
		qfh.UploadRequest.set(filename=filename)
		logger.logSystem("UploadRequest: Upload Request has been received. ({})".format(str(filename)))

		response = b'up'
		response += b'Active Requests: ' + bytes([len(qfh.UploadRequest.received)])
		response += b' Using Scaffold: ' + filename
		response += PrivilegedPacket.padding_byte * (PrivilegedPacket.encoded_data_length - len(response))
		p = PrivilegedPacket('NOOP*',tag=b'AA',plainText=response).send()

	def manual(self,chip,logger,cmd,args):
		print('NOTHING HAS BEEN WRITTEN FOR THE "MANUAL" METHOD.')



	def runHandbrake(self,chip,logger,cmd,args):
		pass


	def startExperiment(self,chip,logger,cmd,args):

		filename = args.replace(CMDPacket.padding_byte)

		if self.experimentEvent is None or self.experimentEvent.is_set():
			raise StopIteration('experimentEvent is None or experimentEvent is set.') # If experimentEvent does not exist or is set, return False to know there is a failure.
		runEvent = threading.Event()
		runEvent.set()
		# Run an experiment file from the experiment directory
		logger.logSystem("Command recieved: Running an experiment.", task[2]) # Placeholder
		parserThread = threading.Thread(name='experimentParser',target=exp.run, args=(task[2],self.experimentEvent,runEvent,logger,self.nextQueue))
		parserThread.start()

		data = 'Attempting to start experiment <{}> if it exists.'.format(filename)
		data += CMDPacket.padding_byte * (CMDPacket.data_size - len(data))
		p = CMDPacket(opcode='RSPND',data=data).send()

	def immediateShutdown(self,chip,logger,cmd,args):
		"""
		Initiate the shutdown proceedure on the pi and then shut it down. Will send a status to the WTC
		The moment before it actually shuts down.

		Parameters
		----------
		chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
		cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command

		Raises
		------
		SystemExit - If the interpreter can even get to this point... Close the interpreter.
		"""
		logger.logSystem('CMD: Shutting down...')
		Popen(["sudo", "halt"],shell=True) #os.system('sudo halt')
		raise SystemExit # Close the interpreter and clean up the buffers before reboot happens.

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
			mem=str(os.popen('free -b').readlines())
			mem=[num for num in mem.split('\n')[1].split(' ') if num]
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

		logger.logSystem("saveStatus: Attempting to save the status to a file.")
		try:
			with open(MISCPATH+'status_'+timestamp,'w') as statFile:
				statFile.write(text_to_write)
		except Exception as err:
			logger.logError("There was a problem writing the status file.",err)