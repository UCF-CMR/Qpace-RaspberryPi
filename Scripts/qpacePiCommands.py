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
import datetime
import random
import tarfile
import qpaceLogger as qpLog

WTC_PACKET_BUFFER_SIZE = 10 # How many packets can the WTC store?


CMD_DEFAULT_TIMEOUT = 5 #seconds
CMD_POLL_DELAY = .35 #seconds
MISCPATH = 'home/pi/data/misc/'
TEMPPATH = '/home/pi/temp/'
ROOTPATH = '/home/pi/'
MISCPATH = '/mnt/c/users/jonat/desktop/cmr/pi/data/misc/'
ROOTPATH= '/mnt/c/users/jonat/desktop/cmr/pi/'
TEMPPATH = '/mnt/c/users/jonat/desktop/cmr/pi/temp/'

UNAUTHORIZED = b'OKAY'

# def _waitForWTCResponse(chip, trigger = None, timeout = None):
#     """
#     Wait for the WTC to respond with a continue code and then return.
#
#     Parameters
#     ----------
#     chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
#     trigger - bytes - waits until it receives a specific byte sequence from the WTC. If None
#                       is given, then it will read and return from the WTC, otherwise it will return None.
#     timeout - int - number of seconds to wait for a response from the WTC. If None, then the default timeout
#                     will be used.
#
#     Returns
#     -------
#     bytes - The bytes read from the registers on the WTC if the trigger is None.
#     True - If a trigger is given and it matched
#     False - If the trigger never matched the input and the timeout occurred
#
#     Raises
#     ------
#     TypeError - If the trigger is not bytes or string OR the timeout is not an int.
#     """
#     if isinstance(trigger,str):
#         trigger = trigger.encode('utf-8')
#     elif not isinstance(timeout,int) and not isinstance(timeout,float) and not isinstance(trigger,bytes) and not isinstance(trigger,bytearray):
#         raise TypeError("Trigger must be bytes or string.")
#     logText = "Waiting for {} seconds for the WTC to respond".format(timeout or CMD_DEFAULT_TIMEOUT)
#     if trigger:
#         logText += " with '{}'".format(trigger)
#     logger.logSystem([[logText]])
#
#     attempts_remaining = ceil((timeout or CMD_DEFAULT_TIMEOUT)/CMD_POLL_DELAY)
#     if attempts_remaining < 1:
#         attempts_remaining = 1
#
#     buf = b''
#     while attempts_remaining > 0 and buf != trigger:
#         sleep(CMD_POLL_DELAY)
#         attempts_remaining -= 1
#         waiting = chip.byte_read(SC16IS750.REG_RXLVL)
#         if waiting > 0 :
#             for i in range(waiting):
#                 buf += chip.byte_read(SC16IS750.REG_RHR)
#     if buf == trigger:
#         return True
#     elif trigger is None and buf is not b'':
#         return buf
#     else:
#         return False

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
		logger.logSystem('SendBytesToCCDR: Data will not be sent to the WTC: not string or bytes.')
		raise TypeError("Data to the WTC must be in the form of bytes or string")
	try:
		chip.block_write(0, sendData) # 0 is SC16IS750.REG_THR
	except Exception as err:
		#TODO do we actually handle the case where it just doesn't work?
		print(err)
	else:
		return True
	return False

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

class CMDPacket():
	"""
	Reason for Implementation
	-------------------------
	This is a class dedicated to handling packets used in responding to commands from Ground.
	"""

	data_size = 118 #Bytes
	padding_byte = b'\x04'

	def __init__(self,chip,opcode,data):
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
		self.opcode = opcode
		self.packetData = data
		self.chip = chip

	def respond(self):
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
			return sendBytesToCCDR(self.chip,sendData)



	def isValid(self): #TODO Make sure the packet is not corrupted
		"""
		Not implemented yet.

		Parameters
		----------
		None

		Returns
		-------
		True if the packet is valid
		False if the packet is invalid

		Raises
		------
		Any exception gets popped up the stack.
		"""
		pass

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

	def __init__(self,chip,opcode,tag=None, cipherText = None,plainText=None):
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
		if cipherText:
			data = PrivilegedPacket.returnRandom(4) + cipherText + PrivilegedPacket.returnRandom(6) + b'\x00'*12
		elif plainText:
			data = PrivilegedPacket.returnRandom(4) + PrivilegedPacket.encodeXTEA(plainText + tag) + PrivilegedPacket.returnRandom(6) + b'\x00'*12
		else:
			data = PrivilegedPacket.returnRandom(4) + CMDPacket.padding_byte * PrivilegedPacket.encoded_data_length + PrivilegedPacket.returnRandom(6) + b'\x00'*12
		CMDPacket.__init__(self,opcode=opcode,chip=chip,data=data)


	@staticmethod
	def encodeXTEA(plainText):
		"""
		Encode a plaintext into ciphertext.
		"""
		cipherText = plainText
		return cipherText

	@staticmethod
	def decodeXTEA(cipherText):
		"""
		decode a ciphertext into plaintext.
		"""
		plainText = cipherText
		return plainText


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

class Command():
	"""
	Reason for Implementation
	-------------------------
	Handler class for all commands. These will be invoked from the Interpreter.
	"""
	def __init__(self,packetQueue=None,nextQueue=None):
		self._packetQueue = packetQueue
		self._nextQueue = nextQueue

	# Getters and Setters for self.packetQueue
	@property
	def packetQueue(self):
		return self._packetQueue

	@packetQueue.setter
	def packetQueue(self,queue):
		self._packetQueue = queue

	# Getters and Setters for self.nextQueue
	@property
	def nextQueue(self):
		return self._nextQueue

	@nextQueue.setter
	def nextQueue(self,queue):
		self._nextQueue = queue

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
		p = CMDPacket(chip=chip,opcode='STATS',data=data).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')
		if thread:
			thread.join() # Make sure we wait for the thread to close if it's still going.

	def directoryListingSet(self,chip,logger,cmd,args):
		"""
		Create a DirectoryListingPacket and respond with the response packet.
		"""
		pathname = args.split(' ')[0]
		tag = b"AA"

		self.pathname = pathname
		lenstr = str(len(os.listdir(pathname))) # Get the number of files/directories in this directory.
		padding = CMDPacket.padding_byte*(PrivilegedPacket.encoded_data_length-len(lenstr)) #98 due to specification of packet structure
		plainText = lenstr.encode('ascii')
		plainText += padding
		p = PrivilegedPacket(chip=chip,opcode="NOOP*",tag=tag,plainText=plainText).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

	def directoryList(self,chip,logger,cmd,args):
		"""

		Create a SendDirectoryList packet and respond with the response packet.
		"""
		pathname = args.split(' ')[0]
		tag = b"AA"
		self.pathname = pathname
		filepath = '../temp/DirList'
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
		p = PrivilegedPacket(chip=chip,opcode="NOOP*", tag=tag,plainText=plainText).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

	def move(self,chip,logger,cmd,args):
		"""
		Move a file from one location to another.
		Create a MoveFilePacket and respond with the response packet.
		"""
		args = args.split(' ')
		originalFile = args[0]
		pathToNewFile = args[1]
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
		p = PrivilegedPacket(chip=chip,opcode="NOOP*",tag=tag,plainText=plainText).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

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
		p = PrivilegedPacket(chip=chip,opcode="NOOP*",tag=b'AA',plainText=plainText).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

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
		p = PrivilegedPacket(chip=chip,opcode='NOOP*',tag=b'AA',plainText=plainText).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

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
		p = CMDPacket(chip=chip,opcode='DOWNR',data=data).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

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
		filename = args[0:92].replace(CMDPacket.padding_byte,b'').replace(b'/',b'@')
		if qfh.UploadRequest.isActive():
			logger.logSystem("UploadRequest: Redundant Request? ({})".format(str(filename)))
		qfh.UploadRequest.set(filename=filename)
		logger.logSystem("UploadRequest: Upload Request has been received. ({})".format(str(filename)))

		response = b'up'
		response += b'Active Requests: ' + bytes([len(qfh.UploadRequest.received)])
		response += b' Using Scaffold: ' + filename
		response += PrivilegedPacket.padding_byte * (PrivilegedPacket.encoded_data_length - len(response))
		p = PrivilegedPacket(chip,'NOOP*',tag=b'AA',plainText=response).build()
		self.packetQueue.enqueue(p)
		self.nextQueue.enqueue('SENDPACKET')

	def manual(self,chip,logger,cmd,args):
		print('NOTHING HAS BEEN WRITTEN FOR THE "MANUAL" METHOD.')

	def dil(self,chip,logger,cmd,args,runningExperiment=None):
		"""
		Special command for DEBUG mainly. Used to manually affect the instruments of the experiment module.
		This can only be done if an experiment is NOT running.
		"""
		import qpaceExperiment as exp
		import SC16IS750
		print("running experiment")
		exp.pinInit()
		exp.led(True)
		exp.goProOn()
		exp.goProCapToggle()
		sleep(10)
		exp.goProCapToggle()
		exp.goProTransfer()
		exp.goProOff()
		exp.led(False)

		print("DONE :D :D :D")

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