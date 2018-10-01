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
#from qpaceInterpreter import *
import qpaceLogger as logger
import qpaceStates as qps


CMD_DEFAULT_TIMEOUT = 5 #seconds
CMD_POLL_DELAY = .35 #seconds
STATUSPATH = ''

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
		chip.block_write(SC16IS750.REG_THR, sendData)
	except Exception as err:
		#TODO do we actually handle the case where it just doesn't work?
		print(err)
		logger.logError('sendBytesToCCDR: An error has occured when attempting to send data to the WTC. Data to send:' + str(sendData),err)
		pass
	else:
		return True
	return False

class CMDPacket():
	"""
	Reason for Implementation
	-------------------------
	This is a class dedicated to handling packets used in responding to commands from Ground.
	"""
	def __init__(self,chip,opcode):
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
		self.packetData = None
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
			print(sendData)
			return sendBytesToCCDR(self.chip,sendData)
		else:
			return sendBytesToCCDR(self.chip,UNAUTHORIZED)

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

	@classmethod
	def generateChecksum(self,data):
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
			self.packetData=b' ' * 118
		return bytes([self.routing]) + self.opcode.encode('ascii') + self.packetData + CMDPacket.generateChecksum(self.packetData)

class PrivilegedPacket(CMDPacket):
	"""
	Reason for Implementation
	-------------------------
	Class to handle all the Privileged packets with XTEA
	"""
	def __init__(self,chip,opcode,tag=None, cipherText = None):
		"""
		Constructor for a PrivledgedPacket

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
		self.tag = tag
		CMDPacket.__init__(self,opcode=opcode,chip=chip)

		if cipherText:
			self.packetData = PrivilegedPacket.decodeXTEA(cipherText)
		else:
			self.packetData = None

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

class StatusPacket(CMDPacket):
	"""
	Reason for Implementation
	-------------------------
	Handler class for Status commands.
	When constructed creates all the necessary payload data.
	"""
	def __init__(self,chip):
		CMDPacket.__init__(self,chip=chip,opcode='STATS')
		timestamp = datetime.datetime.now()
		retval =  bytes([timestamp.month, timestamp.day, timestamp.year - 2000, timestamp.weekday(), timestamp.hour,timestamp.minute,timestamp.second])
		status = b"DIL is go."
		status += b':E(' + str(logger.Errors.get()).encode('ascii') + b'):' #Number of errors logged since last boot
		status += b'M('+ b'' +b')' # status message TODO GET FIRST LINE OF 'STATUS'
		retval += status + b' '*(111-len(status)) # 111 due to defined packet Structure
		self.packetData = retval

class DirectoryListingPacket(PrivilegedPacket):
	"""
	Reason for Implementation
	-------------------------
	Handler class for Directory Listing commands.
	When constructed creates all the necessary payload data.
	"""
	def __init__(self,chip,pathname, tag):
		self.pathname = pathname
		PrivilegedPacket.__init__(self,chip=chip,opcode="NOOP*",tag=tag)
		lenstr = str(len(os.listdir(pathname))) # Get the number of files/directories in this directory.
		padding = " "*(94-len(lenstr)) #98 due to specification of packet structure
		endPadding = b"\x00"*12 # 12 due to specification of packet structure
		retVal = PrivilegedPacket.returnRandom(4)
		retVal += (lenstr + padding + tag).encode('ascii')
		retVal += PrivilegedPacket.returnRandom(6)
		retVal += endPadding
		self.packetData = retVal

class SendDirectoryList(PrivilegedPacket):
	"""
	Reason for Implementation
	-------------------------
	Handler class for Send Directory commands.
	When constructed creates all the necessary payload data.
	"""
	def __init__(self, chip, pathname, tag):
		PrivilegedPacket.__init__(self,chip=chip,opcode="NOOP*", tag=tag)
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
		padding = " " * (94 - len(filepath))
		retVal = PrivilegedPacket.returnRandom(4)
		retVal += PrivilegedPacket.encodeXTEA((filepath + padding + tag).encode('ascii'))
		retVal += PrivilegedPacket.returnRandom(18)
		self.packetData = retVal

class MoveFilePacket(PrivilegedPacket):
	"""
	Reason for Implementation
	-------------------------
	Handler class for Move File commands.
	When constructed creates all the necessary payload data.
	"""
	def __init__(self, chip, originalFile, pathToNewFile, tag):
		PrivilegedPacket.__init__(self,chip=chip,opcode="NOOP*",tag=tag)
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
		padding = " " * (94 - len(wasMoved))
		retVal = PrivilegedPacket.returnRandom(4)
		retVal += PrivilegedPacket.encodeXTEA((wasMoved + padding + tag).encode('ascii'))
		retVal += PrivilegedPacket.returnRandom(18)
		self.packetData = retVal

# class DownloadFileInit(CMDPacket):
# 	def __init__(self,pathname, delay, packetsPerAck,start = 0,end = None):
# 		CMDPacket.__init__('DWNLD')
# 		self.pathname = pathname
# 		self.firstPacket = start
# 		self.lastPacket = end
# 		self.delay = delay
# 		self.packetsPerAck = packetsPerAck
# 		# self.useFEC = useFEC

class TarBallFilePacket(PrivilegedPacket):
	"""
	Reason for Implementation
	-------------------------
	Handler class for creating and extracting compressed files.
	When constructed, creates all the necessary payload data.
	"""
	def __init__(self,chip,tag):
		PrivilegedPacket.__init__(self,chip=chip,opcode="NOOP*",tag=tag)
		self.packetData = PrivilegedPacket.returnRandom(118)

class Command():
	"""
	Reason for Implementation
	-------------------------
	Handler class for all commands. These will be invoked from the Interpreter.
	"""
	class UploadRequest():
		"""
		Reason for Implementation
		-------------------------
		Abstract class.
		Class that handles if there is a request to upload a file to the pi.
		Only one UploadRequest can happen at a time.
		"""
		received = False
		# useFEC = None
		totalPackets = None
		filename = None

		@staticmethod
		def reset():
			"""
			Reset the UploadRequest back to it's original state.

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
			logger.logSystem('UploadRequest: Upload Request has been cleared.',str(Command.UploadRequest.totalPackets),str(Command.UploadRequest.filename))
			Command.UploadRequest.received = False
			# Command.UploadRequest.useFEC = None
			Command.UploadRequest.totalPackets =  None
			Command.UploadRequest.filename = None

		@staticmethod
		def set(pak = None, filename = None):
			"""
			Make an UploadRequest. If there is already an active request IGNORE all future requests.
			If there is not a request going on, then set all the required data and touch the scaffold
			to prepare for upload.

			Parameters
			----------
			pak = the expected packets to be receiving.
			filename = the filename expected to be sent.

			Returns
			-------
			Void

			Raises
			------
			Any exception gets popped up the stack.
			If there is a problem with touching the scaffold it is silenced.
			"""
			logger.logSystem("UploadRequest: Upload Request has been received.",str(pak),str(filename))
			if Command.UploadRequest.isActive():
				logger.logSystem("UploadRequest: Redundant Request?")
			else:
				try:
					from pathlib import Path
					Path('{}.scaffold'.format(filename.decode('ascii'))).touch()
				except:
					#open(filename.decode('ascii') + '.scaffold','wb').close() #Fallback method to make sure it works
					pass
				Command.UploadRequest.received = True
				# Command.UploadRequest.useFEC = fec
				Command.UploadRequest.totalPackets = pak
				Command.UploadRequest.filename = filename

		@staticmethod
		def isActive():
			"""
			Check if there has been an UploadRequest received.
			"""
			return Command.UploadRequest.received

	def status(chip,cmd,args):
		"""
		Create a StatusPacket and respond with the response packet.
		"""
		StatusPacket(chip=chip).respond()
	def directoryListingSet(chip,cmd,args):
		"""
		Create a DirectoryListingPacket and respond with the response packet.
		"""
		pathname = args.split(' ')[0]
		tag = "AA"
		DirectoryListingPacket(chip=chip,pathname=pathname,tag=tag).respond()
	def directoryList(chip,cmd,args):
		"""

		Create a SendDirectoryList packet and respond with the response packet.
		"""
		pathname = args.split(' ')[0]
		tag = "AA"
		SendDirectoryList(chip=chip,pathname=pathname,tag=tag).respond()
	def move(chip,cmd,args):
		"""
		Move a file from one location to another.
		Create a MoveFilePacket and respond with the response packet.
		"""
		args = args.split(' ')
		originalFile = args[0]
		pathToNewFile = args[1]
		tag = 'AA'
		MoveFilePacket(chip=chip,originalFile=originalFile,pathToNewFile=pathToNewFile,tag=tag).respond()
	def tarExtract(chip,cmd,args):
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
		TarBallFilePacket(chip=chip,tag=tag).respond()
	def tarCreate(chip,cmd,args):
		"""
		Create a compressed Tar.
		Create a TarBallFilePacket and respond with the response packet.
		"""
		import tarfile
		args = args.split(' ')
		# The name of the new file will be whatever was input, but since the path could be long
		# create the {}.tar.gz at the filename. Since it could be a directory with a /
		# look for the 2nd to last / and then slice it. Then remove and trailing /'s
		newFile = args[0][args[0].rfind('/',o,len(args[0])-1):].replace('/','')
		tarDir = '../data/misc/{}.tar.gz'.format(newFile)
	    with tarfile.open(tarDir, "w:gz") as tar:
	        tar.add(args[0], arcname=os.path.basename(args[0]))
		TarBallFilePacket(chip=chip,tag=tag).respond()
	def dlReq(chip,cmd,args):
		"""
		Create a DownloadRequestPacket and respond with the response packet.
		"""
		pass
	def dlFile(chip,cmd,args):
		"""
		Create a Transmitter instance and transmit a file packet by packet to the WTC for Ground.
		"""
		import qpaceFileHandler as qfh
		qfh.DataPacket.last_id = 0
		# fec = args[:4]
		ppa = int.from_bytes(args[4:8], byteorder='big')
		msdelay = int.from_bytes(args[8:12], byteorder='big')
		start = int.from_bytes(args[12:16], byteorder='big')
		end = int.from_bytes(args[16:20], byteorder='big')
		filename = args[20:].replace(b'\x1f',b'')
		# print('FEC:',fec)
		print('PPA:',ppa)
		print('DEL:',msdelay)
		print('STR:',start)
		print('END:',end)
		print('FNM:',filename)
		transmitter = qfh.Transmitter(	chip,
										filename.decode('ascii'),
										0x01,
										# useFEC = fec == b' FEC',
										packetsPerAck = ppa,
										delayPerTransmit = msdelay,
										firstPacket = start,
										lastPacket = end,
										xtea = False
									)
		transmitter.run()

	def upReq(chip,cmd,args):
		"""
		We have received an Upload Request. Figure out the necessary information and
		make an UploadRequest active by calling UploadRequest.set()
		"""
		# Numbers based on Packet Specification Document.
		import qpaceFileHandler as qfh

		totPak = int.from_bytes(args[0:4], byteorder='big')
		# fec = args[4:8]
		filename = args[8:96].replace(b'\x1f',b'')
		# print('FEC:',fec)
		print('TPK:',totPak)
		print('FNM:',filename)
		Command.UploadRequest.set(pak=totPak,filename=filename)

	def upFile(chip,cmd,args):
		"""
		Possibly depreciated. To be implemented if not.
		"""
		pass

	def manual(chip,cmd,args,runningExperiment=None):
		"""
		Special command for DEBUG mainly. Used to manually affect the instruments of the experiment module.
		This can only be done if an experiment is NOT running.
		"""
		import qpaceExperiment as exp
		import qpaceStates as qps
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
		# StatusPacket(chip).respond()

		chip.byte_write(SC16IS750.REG_THR,qps.QPCOMMAND['SCIENCESTOP'])
		#waitForBytesFromCCDR(chip,1,timeout=None)
		#chip.read_byte(SC16IS750.REG_RHR) # Clear buffer, WTC will send ERRNONE
		print("DONE :D :D :D")

	def immediateShutdown(chip,cmd,args):
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
		sendBytesToCCDR(chip,b'SP') # SP = Shutdown Proceeding
		Popen(["sudo", "halt"],shell=True) #os.system('sudo halt')
		raise SystemExit # Close the interpreter and clean up the buffers before reboot happens.

	def immediateReboot(chip,cmd,args):
		"""
		Initiate the reboot proceedure on the pi and then reboot it. Will send a status to the WTC
		the moment before it actually reboots.

		Parameters
		----------
		chip - SC16IS750 - an SC16IS75 object which handles the WTC Connection
		cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command

		Raises
		------
		SystemExit - If the interpreter can even get to this point... Close the interpreter.
		"""
		logger.logSystem('CMD: Rebooting...')
		sendBytesToCCDR(chip,b'SP') # SP = Shutdown Proceeding
		Popen(["sudo", "reboot"],shell=True) #os.system('sudo reboot')
		raise SystemExit # Close the interpreter and clean up the buffers before reboot happens.

	def getStatus():

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
		requests_queued = "Unknown"
		nextqueue_size = "Unknown"
		last_command = "Unknown"
		last_command_from = "Unknown"
		last_command_when = "Unknown"
		commands_executed = "Unknown"
		boot = "Unknown"


		try:
			from qpaceWTCHandler import NextQueue
			requests_queued = NextQueue.requestCount
			nextqueue_size = len(NextQueue.requestQueue)
		except Exception as err:
			print(str(err))
			logger.logError("Could not import NextQueue",err)
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
						"Requests queued: {}\n"   +\
						"Size of NextQueue: {}\n" +\
						"CPU Usage: {}%\n"      +\
						"CPU Temp: {} deg C\n"  +\
						"Uptime: {}\n"  		+\
						"RAM Total: {} bytes\n" +\
						"RAM Used: {} bytes\n"  +\
						"RAM Free: {} bytes\n"  +\
						"Disk total: {}\n"      +\
						"Disk free: {}\n"
		return text_to_write.format(identity,boot,last_command,last_command_when,last_command_from,commands_executed,requests_queued,nextqueue_size,cpu,cpu_temp,
								uptime,ram_tot,ram_used,ram_free,disk_total,disk_free)

	def saveStatus(chip,cmd,args):
		"""
		Create a text file with status items and then send that file.
		Invokes sendFile

		Accumulates the following data: CPU Usage, CPU Temp, IP Address, Pi Identity,
										Last command received, Uptime, Running processes,
										RAM Usage, Disk Space used, Disk space total,
										Connected COM ports.
		Parameters
		----------
		chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
		cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
		"""

		text_to_write = Command.getStatus()
		logger.logSystem("saveStatus: Attempting to save the status to a file.")
		timestamp = strftime("%Y%m%d-%H%M%S",gmtime())
		try:
			with open(STATUSPATH+'status_'+timestamp+'.txt','w') as statFile:
				statFile.write(text_to_write)
		except Exception as err:
			logger.logError("There was a problem writing the status file.",err)
			try:
				with open(STATUSPATH+'status_'+timestamp+'.txt','w') as statFile:
					statFile.write("Unable to write status file. {}".format(str(err)))
			except:pass
