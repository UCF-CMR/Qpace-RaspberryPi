```
#!/usr/bin/python
import sys
import usb.core
import usb.util
import time
import binascii
from threading import Thread

# Max packet size defined by the PIC USB implementation
MAX_PACKET_SIZE = 64


# Don't hate me, but this just makes more sense to me.
def printf(format, *values):
    print(format % values )

# Converts a string to a hex buffer packet for USB
def stb(string):
	if(len(string) > MAX_PACKET_SIZE):
		raise OverflowError('The max packet size is %d!' % MAX_PACKET_SIZE, "You need to split the packets.")

	# Allocate byte array with MAX_PACKET_SIZE by 0x00
	buf = bytearray(MAX_PACKET_SIZE)

	for index, char in enumerate(string):
		# Set buf position to Unicode code point/ASCII value of the char
		buf[index] = ord(char)
	# Return a buffer ready to be sent over USB
	return buf




# class pollRead(threading.Thread):
# 	"""Threaded Url Grab"""
# 	def __init__(self, arg):
# 		threading.Thread.__init__(self, args=(arg,))
# 		# self.python_queue = python_queue

# 	def run(self, dev):
# 		while True:
# 			time.sleep(0.5)
# 			try:
# 				# time.sleep(0.4)
# 				ret = dev.read(0x81, 64, 500)
# 				# info = epo.read(epi.bEndpointAddress,epi.wMaxPacketSize)

# 				# Convert array into string
# 				sret = ''.join([chr(x) for x in ret])
# 				# Split string at null terminators/LF and save the first part
# 				sret = sret.split("\x0a")[0]
# 				# Remove trailing spaces and newlines, optional
# 				sret = sret.strip()
# 				# assert sret == msg
# 				printf("\"%s\"", sret)
# 				print()
# 			except usb.core.USBError as e:
# 				data = None
# 				if e.args == ('Operation timed out',):
# 					continue


# def myfunc(dev):
# 	while True:
# 		print("Alive")
# 		time.sleep(0.5)
# 		try:
# 			# time.sleep(0.4)
# 			ret = dev.read(0x81, 64, 500)
# 			# info = epo.read(epi.bEndpointAddress,epi.wMaxPacketSize)

# 			# Convert array into string
# 			sret = ''.join([chr(x) for x in ret])
# 			# Split string at null terminators/LF and save the first part
# 			sret = sret.split("\x0a")[0]
# 			# Remove trailing spaces and newlines, optional
# 			sret = sret.strip()
# 			# assert sret == msg
# 			printf("\"%s\"", sret)
# 			print()
# 		except usb.core.USBError as e:
# 			data = None
# 			if e.args == ('Operation timed out',):
# 				continue

dev = usb.core.find(idVendor=0x04D8, idProduct=0x003F)
if dev is None:
	raise ValueError('Our device is not connected')
else:
	print(hex(dev.idProduct))
# print(dev)
dev.set_configuration()



collected = 0
attempts = 20
while (collected < attempts):
	try:
		dev.write(0x1, stb("V"), 64) 
		print("fart1")
		# data = dev.read(endpoint.bEndpointAddress,endpoint.wMaxPacketSize)
		collected += 1

		dev.write(0x1, stb("V"), 64) 
		# time.sleep(.5)
		print(collected)
		print("fart2")
		# time.sleep(0.05)
	except usb.core.USBError as e:
		data = None
		if e.args == ('Operation timed out',):
			print("Timeout")
			continue


# python_queue = Queue.Queue()
# sqsThread = pollRead(args=(dev,))
# t = Thread(target=myfunc, args=(dev,))
# t.start()
# sqsThread.start()

# # time.sleep(0.4)
# ret = dev.read(0x81, 64, 500)
# # info = epo.read(epi.bEndpointAddress,epi.wMaxPacketSize)

# # Convert array into string
# sret = ''.join([chr(x) for x in ret])
# # Split string at null terminators/LF and save the first part
# sret = sret.split("\x0a")[0]
# # Remove trailing spaces and newlines, optional
# sret = sret.strip()
# # assert sret == msg
# printf("\"%s\"", sret)
# print()

# collected = 0
# attempts = 50
# while collected < attempts :
# 	try:
# 		# data = dev.read(endpoint.bEndpointAddress,endpoint.wMaxPacketSize)
# 		collected += 1
# 		# print data
# 		# assert len(dev.write(1, msg, 65)) == len(msg)
# 		ret = dev.read(0x81, 64, 200)
# 		# info = epo.read(epi.bEndpointAddress,epi.wMaxPacketSize)
# 		sret = ''.join([chr(x) for x in ret])
# 		# assert sret == msg
# 		print(ret)
# 		print(sret)
# 		print()
# 	except usb.core.USBError as e:
# 		data = None
# 		if e.args == ('Operation timed out',):
# 			continue




# dev.reset()
# usb.util.dispose_resources(dev)


# 0000   1b 00 60 1a bd aa 0a 90 ff ff 00 00 00 00 09 00
# 0010   00 01 00 0b 00 01 01 40 00 00 00 00 42 01 56 65
# 0020   78 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0030   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0040   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0050   00 00 00 00 00 00 00 00 00 00 00

# 0000   1b 00 10 10 37 aa 0a 90 ff ff 00 00 00 00 09 00
# 0010   00 01 00 0b 00 01 01 40 00 00 00 42 01 56 65 78
# 0020   74 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0030   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0040   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0050   00 00 00 00 00 00 00 00 00 00 00

# 0000   1b 00 60 3a 6e 99 0a 90 ff ff 00 00 00 00 09 00
# 0010   00 01 00 0f 00 01 01 40 00 00 00 42 01 56 65 78
# 0020   74 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0030   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0040   00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
# 0050   00 00 00 00 00 00 00 00 00 00 00


# 0000   1b 00 40 92 89 a7 0a 90 ff ff 00 00 00 00 09 00
# 0010   01 01 00 19 00 81 01 40 00 00 00 56 65 72 73 69
# 0020   6f 6e 20 53 33 0a 00 00 00 00 00 00 00 ff ff ff
# 0030   ff ff ff f7 ff ff ff ff ff ff ff ff ff ff ff ff
# 0040   ff ff 22 00 00 0a 21 ec 01 00 01 00 ff ff ff 01
# 0050   ff ff ff ff ff ff ff ff ff ff ff
```