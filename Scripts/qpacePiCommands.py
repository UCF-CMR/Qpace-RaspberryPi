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



class CMDPacket():
	def __init__(self,opcode,chip):
		self.routing = 0x00
		self.opcode = opcode
		self.packetData = None
		self.chip = chip
		# self.pathname = pathname
		# self.nLines = nLines
		# self.delay = delay

	def respond(self):
		if self.packetData:
			sendData = self.build()
			print(sendData)
			return sendBytesToCCDR(self.chip,sendData)
		else:
			return sendBytesToCCDR(self.chip,UNAUTHORIZED)

	def confirmIntegrity(self): #TODO Make sure the packet is not corrupted
		pass

	@classmethod
	def generateChecksum(self,data):
		checksum = 0x811C9DC5 # 32-Bit FNV Offset Basis
		for byte in data:
			checksum ^= byte
			checksum *= 0x1000193 # 32-Bit FNV Prime
		checksum &= 0xFFFFFFFF
		return checksum.to_bytes(4,byteorder='big')

	def build(self):
		return bytes([self.routing]) + self.opcode.encode('ascii') + self.packetData + CMDPacket.generateChecksum(self.packetData)


class PrivilegedPacket(CMDPacket):
	def __init__(self,chip,opcode,tag=None, encodedData = None):
		self.tag = tag
		CMDPacket.__init__(self,opcode=opcode,chip=chip)

		if encodedData:
			self.packetData = PrivilegedPacket.decodeXTEA(encodedData)
		else:
			self.packetData = None

	@staticmethod
	def encodeXTEA(plainText):
		cipherText = plainText
		return cipherText

	@staticmethod
	def decodeXTEA(cipherText):
		plainText = cipherText
		return plainText


	@staticmethod
	def returnRandom(n):
		retval = []
		for i in range(0,n):
			# Get ascii characters from '0' to 'Z'
			num = random.randint(48,122)
			if num == 92: # If we have a backslash, just replace it with something else. It doesn't really matter.
				num = 55
			retval.append(num)
		return bytes(retval)

class StatusPacket(CMDPacket):
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
	def __init__(self,chip,pathname, tag="AA"):
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
	def __init__(self, chip, pathname, tag='AA'):
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
	def __init__(self, chip, originalFile, pathToNewFile, tag='AA'):
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

# class UploadFilePacket(PrivilegedPacket):
# 	def __init__(self,pid, data):
# 		PrivilegedPacket.__init__('','>')

# class UploadFileHandler(): #In place for the request and the procedure
# 	def __init__(self,filename,expectedPackets, tag):
# 		self.filename = filename
# 		self.expectedPackets = expectedPackets
#
# class DownloadFileHandler(): #In place for the request and the procedure
# 	def __init__(self,pathname):
# 		self.pathname = pathname
# 		# self.useFEC = useFEC

class Command():
	fromWTC = False # Change to True for real operation.
	class UploadRequest():
		received = False
		# useFEC = None
		totalPackets = None
		filename = None

		@staticmethod
		def reset():
			logger.logSystem('UploadRequest: Upload Request has been cleared.',str(Command.UploadRequest.totalPackets),str(Command.UploadRequest.filename))
			Command.UploadRequest.received = False
			# Command.UploadRequest.useFEC = None
			Command.UploadRequest.totalPackets =  None
			Command.UploadRequest.filename = None

		@staticmethod
		def set(pak = None, filename = None):
			logger.logSystem("UploadRequest: Upload Request has been received.",str(pak),str(filename))
			if Command.UploadRequest.isActive():
				logger.logSystem("UploadRequest: Redundant Request?")
			else:
				try:
					from pathlib import Path
					Path(filename.decode('ascii')+'.scaffold').touch()
				except:
					#open(filename.decode('ascii') + '.scaffold','wb').close() #Fallback method to make sure it works
					pass
			Command.UploadRequest.received = True
			# Command.UploadRequest.useFEC = fec
			Command.UploadRequest.totalPackets = pak
			Command.UploadRequest.filename = filename

		@staticmethod
		def isActive():
			return Command.UploadRequest.received

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

	def status(chip,cmd,args):
		StatusPacket().respond()
	def directoryListingSet(chip,cmd,args):
		DirectoryListingPacket().respond()
	def directoryList(chip,cmd,args):
		SendDirectoryList().respond()
	def move(chip,cmd,args):
		pass
	def tar(chip,cmd,args):
		pass
	def dlReq(chip,cmd,args):
		pass
	def dlFile(chip,cmd,args):
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
		# Magic numbers based on Packet Specification Document.
		import qpaceFileHandler as qfh

		totPak = int.from_bytes(args[0:4], byteorder='big')
		# fec = args[4:8]
		filename = args[8:96].replace(b'\x1f',b'')
		# print('FEC:',fec)
		print('TPK:',totPak)
		print('FNM:',filename)
		Command.UploadRequest.set(pak=totPak,filename=filename)

		# receiver = qfh.Receiver(	chip,
		# 							filename.decode('ascii'),
		# 							route = 0x01,
		# 							useFEC = fec == b' FEC',
		# 							xtea = False,
		# 							expected_packets = totPak
		# 						)
		# receiver.run(Command.fromWTC)
	def upFile(chip,cmd,args):
		pass
	def manual(chip,cmd,args):
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

	def pingPi(chip,cmd,args):
		"""
		A ping was received from the WTC. Respond back!

		Parameters
		----------
		chip - SC16IS750 - an SC16IS750 object which handles the WTC Connection
		cmd,args - string, array of args (seperated by ' ') - the actual command, the args for the command
		"""
		logger.logSystem("Pong!")
		sendBytesToCCDR(chip,b'OK')

	# TODO Probably uneccessary now. Should make less information. Not sure what is and what isn't necessary here anymore
	# TODO it will need to be looked at and determined what exactly needs to be done here.
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
