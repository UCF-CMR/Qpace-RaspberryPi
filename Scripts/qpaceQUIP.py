#! /usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 2-20-2018, Rev. 1
# Q-Pace project, Center for Microgravity Research
# University of Central Florida
#
# The Qpace Unornamented Information Protocol module. Provides the necessary tools needed to use QUIP

import argparse
import sys
import os, os.path
import struct
import time
import glob
from math import ceil,log
from itertools import zip_longest

class Corrupted(Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)

class Packet():
    sync = b'\xff\xff'      # 2 bytes
    start = b'\xab\xcd'     # 2 bytes
    end = b'\xdc\xba'       # 2 bytes
    id_bits = 32            # 4 bytes
    overflow = 0            # 0 for false. (1 bit)
    placeholder_bits = 4    # in bits

    max_size = 256          # in bytes
    data_size = 77          # in bytes
    max_id = 0xFFFFFFFF     # 4 bytes. Stored as an int.
    packet_data_size = None # packet_data_size in bytes
    last_id = -1            # -1 if there are no packets yet.

    def __init__(self,data, pid,**kwargs):
        """
        Constructor for a packet.

        Parameters
        ---------
        data - int, str, bytes, bytearray - If a str it must be hex and valid bytes.
        pid - int - Integer to be the PID of the packet. Can not be negative and must be
                    +1 the last pid used.

        Exceptions
        ----------
        ValueError - if the data passed to the packet is too large to fit in the packet.
                     or the pid is out of order.
                     or the pid is negative.
        TypeError - if the data is not a string,int,bytes,or bytearray.
        """
        if pid < 0:
            raise ValueError("Packet pid is invalid. Must be a positive number.")
        # Is the data in a valid data type? If so, convert it to a bytearray.
        if isinstance(data,int):
            data = bytearray(data.to_bytes(data.bit_length()//8+1,byteorder='big'))
        elif isinstance(data,bytearray):
            pass
        elif isinstance(data,bytes):
            data = bytearray(data)
        elif isinstance(data,str):
            try:
                data = bytearray.fromhex(data)
            except ValueError:
                data = bytearray(map(ord,data))
        else:
            raise TypeError("Input data is of incorrect type. Must input str, int, bytes, or bytearray")

        # If we need to set an op_code, do it. Otherwise the opcode will just be 0x0
        if 'op_code' in kwargs:
            self.op_code = kwargs['op_code']
        else:
            self.op_code = 0x0

        data_in_bytes = len(data)
        if data_in_bytes <= Packet.data_size: # Make sure the data is below the max bytes
            # Only worry about the PID for packets of code 0x0 and 0x7. anything else does not need a PID
            if self.op_code == 0x0 or self.op_code == 0x7 and (Packet.last_id + 1) == pid:
                Packet.last_id = pid
                self.pid = pid % Packet.max_id # If the pid is > max_id, force it to be smaller!
            elif self.op_code > 0x0 and self.op_code < 0x7:
                self.pid = 0
            else:
                raise ValueError("Packet pid out of order.")
            if pid > Packet.max_id:
                # Set the overflow to 0 for even multiples of pid and 1 for odd.
                Packet.overflow = (Packet.max_id / pid) % 2
            self.data = data
            self.bytes = data_in_bytes

        else:
            raise ValueError("Packet size is too large for the current header information. Data input restricted to " + str(Packet.data_size) + " Bytes.")

    def buildHeader(self):
        """
            Build the header for the packet.

            Returns
            -------
            bytearray - packet header data.
        """
        # The byte order will be bigendian
        pid = bytearray(self.pid.to_bytes(4,byteorder='big'))       # 4 bytes
        header_end = bytearray(((Packet.overflow << 7) | (self.op_code << 4)).to_bytes(1,byteorder='big'))
        return Packet.sync + Packet.start + (pid + header_end)*3

    def buildData(self):
        """
            Build the data for the packet. All data is repeated 3 times for FEC.

            Returns
            -------
            bytearray - packet data that is triple redundant and interlaced by size of the data
        """
        # Do a TMR expansion where the data is replicated 3 times but not next to each other
        # to avoid burst errors.
        return self.data*3

    def buildFooter(self):
        """
            Build the footer for the packet.

            Returns
            -------
            bytearray - packet footer data.
        """
        # The byte order will be big endian
        return Packet.end + Packet.sync

    def build(self):
        """
            Build the entire packet.

            Returns
            -------
            int - the whole packet. if converted to binary/hex it will be the packet.
        """
        header = self.buildHeader()
        data = self.buildData()
        footer = self.buildFooter()
        # Construct the packet's data
        packet = header + data + footer
        # After constructing the packet's contents, pad the end of the packet until we reach the max size.
        # This will force the packets to always be 256 bytes.
        while len(packet) < Packet.max_size:
            packet += b'\xff'
        return packet

class Encoder():
    def __init__(self,path_for_encode,path_for_packets, suppress=False,destructive=False):
        """
        Constructor for the Encoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to encode the file.
        path_for_packets - str - where to store the packets.
        suppress - bool - suppress output to the terminal.
        destructive - bool - delete the file when done with it.

        Raises
        ------
        TypeError - raises if the paths aren't valid paths.
        """
        # We want a path for the packets and a file for the decoding that's useable.
        if path_for_packets[-1] != '/' or path_for_encode[-1] == '/':
            if path_for_packets == ".":
                path_for_packets = ''
            else:
                raise TypeError("Please provide a valid path for the packets to be found and a valid file to save the data.")
        self.file = path_for_encode
        self.packets = path_for_packets
        self.suppress = suppress
        self.destructive = destructive
        self.packets_built = 0

    def run(self):
        """
        Main method to run for the encoder. This will encode a file into packets.

        Returns
        -------
        True - successful
        False - unsuccessful for any reason
        """
        try:
            # If we are successful at encoding the file build the init packet.
            try:
                if self.encode():
                    self.buildInitPacket()
                    if self.destructive: os.remove(fileToEncode.name)
            except:
                return False
            else:
                return True

        except Warning:
            print("All packets could not be created.")
            if self.destructive: self.removePacketFragments()
            return False

    def encode(self):
        """
        The main encoding method for creating the packets. It will take a file and encode it
        into many packets (size defined by Packet.max_size) split up by certain amounts of
        information (defined by Packet.data_size) and will make sure they all are placed in the
        packet directory


        DANGER: This method will destroy any packets in the packet directory before running.
                Make sure you no longer need any '.qp' files in the packet directory

        Returns
        -------
        True - Completed Successfully.
        False - There was some error. See console output.
        """
        # Delete old '.qp' files
        self.removePacketFragments()
        try:
            with open(self.file,'rb') as fileToEncode:
                if not self.suppress: print("Beginning to encode file into packets.")
                pid = -1 #-1 to start at zero
                try:
                    packetToBuild = None
                    while True: #Until we are done...
                        pid += 1 #choose the next PID in order
                        data = fileToEncode.read(Packet.data_size)
                        if data:
                            packetToBuild = Packet(data,pid)
                        else:
                            # If there's no more data set the last packet created as op_code 0x7
                            self.setLastPacket(packetToBuild)
                            break #If there's nothing else to read, back out. We are done.
                        with open(self.packets+str(pid)+".qp", 'wb') as packet:
                            packet.write(packetToBuild.build())
                except OSError as err:
                    print("Could not write to the directory: ", self.packets)
                    print("Could not write packet: ", pid)
                    raise err
                else:
                    if not self.suppress: print("Successfully built ", pid, " packets.")
                    #self.setAsLastPacket(pid-1) # Set the last packet we wrote as the last packet to transmit.
                    self.packets_built = pid
        except FileNotFoundError:
            print("Can not find file: ", self.file)
        except OSError:
            print("There was a problem encoding: ",self.file)
        else: # success
            if not self.suppress: print("Finished encoded file into packets.")
            return True
        return False

    def buildInitPacket(self):
        """
        Create the init packet. This packet is crucial and without sending one, the decoder may
        not have all the information it needs.

        Exceptions
        ----------
        Warning - The init packet could not be created.
        """
        if not self.suppress: print("Creating initialization packet.")
        try:
            info = []
            with open(self.packets+"init.qp",'wb') as packet:
                info.append(self.file.split("/")[-1])
                info.append(str(self.packets_built))
                info.append(str(os.path.getsize(self.file)))
                #info.append(checksum)
                # Write to the actual packet. Make sure the op_code is 0x1 since it's the init packet
                # Separate the data with a ':' since filenames should not have that anyway.
                packet.write(Packet(":".join(info),0,op_code=0x1).build())
        except OSError:
            err = Warning("Could not write to initialization packet: init.qp")
            print(err)
            raise err

    def setLastPacket(self,packet):
        """
        Set a packet as the last packet.

        Parameters
        ----------
        packet - Packet - an instance of the Packet that we'd like to build. Change it's op_code
                          and then re-write the packet.
        """
        # 0x7 is for the last packet to be received.
        packet.op_code = 0x7
        with open(self.packets+str(packet.pid)+".qp",'wb') as packetToRewrite:
            packetToRewrite.write(packet.build())

    def removePacketFragments(self):
        """
        Delete all the packets in the packet directory.
        """
        filelist = glob.glob(os.path.join(self.packets, "*.qp"))
        for f in filelist:
            os.remove(f)

class Decoder():
    waitDelay = 1 # In seconds. This is for the asynchronous decoding.

    def __init__(self, path_for_decode, path_for_packets, suppress=False,destructive=False,rush=False):
        """
        Constructor for the Encoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to decode to.
        path_for_packets - str - where the packets are stored.
        suppress - bool - suppress output to terminal
        destructive - bool - delete the packets when done with them.

        Raises
        ------
        TypeError - raises if the paths aren't valid paths.
        """
        # We want a path for the packets and a file for the decoding that's useable
        if path_for_packets[-1] !='/':
            if path_for_packets == ".":
                path_for_packets = ''
            else:
                raise TypeError("Please provide a valid paths for decoding.")
        if path_for_decode[-1] == '/':
            self.file_path = path_for_decode
            self.file_name = None
        else:
            # Split the path and the name apart.
            self.file_path = path_for_decode[:path_for_decode.rfind('/')+1]
            self.file_name = path_for_decode[path_for_decode.rfind('/')+1:]
        self.packets = path_for_packets
        self.suppress = suppress
        self.destructive = destructive
        self.rush = rush
        self.expected_packets = None
        self.file_size = None

    def run(self):
        """
        Main method to run for the decoder. Takes the packets from a path and decodes them into a file.

        Exception
        ---------
        If there was an exception thrown up the call stack then continue throwing it up.
        """
        try:
            # Controller will deal with the packets and naming them
            self.init()
            #self.prepareFileLocation()
            missedPackets = self.bulkDecode()
            # If missedPackets is none then we know we are good to go. Otherwise, we'll need
            # to asynchronously decode the file
            if missedPackets is None:
                if not self.suppress: print("There are no missing packets.")
                self.buildScaffold()
            else:
                self.fullAsyncDecode(missedPackets)
        except: raise

    def init(self):
        """
        Initialize the decoder. This must be done to make sure the filename is read properly from
        the init packet. If this is not done, then some data may not be initialized.

        This method should always be called before using any data that comes from the init packet.

        Exceptions
        ----------
        OSError - the init file could not be read.
        ValueError - converting the bytes to ints or strings did not work as expected.
        Corrupted - if the init packet is corrupted throw a Corrupted exception
        """
        try:
            initPacket = self.readInit()
            if self.file_name is None:
                self.file_name = initPacket[0].decode('utf-8')
            self.expected_packets = int(initPacket[1])
            self.file_size = int(initPacket[2])
        except (OSError,ValueError,Corrupted): raise



    def readInit(self):
        """
        Read the data from the special initialization packet. This data is important to the
        decoding process.

        Returns
        -------
        list - list of bytearrays of the data in the init packet (after resolving the TMR expansion)

        Exceptions
        ----------
        OSError - cannot read the init file for any reason.
        Corrupted - if the init packet was corrupted throw a Corrupted exception
        """
        information = None
        try:
            with open(self.packets+"init.qp",'rb') as init:
                information = init.read()
                # Resolve the TMR expansion from the packet. Since we have 19 bytes of header,
                # Start from 19 and go until the ending sequence (but search for it from the back)
                Decoder.isWrapperCorrupted(information)
                information = Decoder.resolveExpansion(information[19:information.rfind(Packet.end + Packet.sync)])
                # Split on the ':' since that should not be in any data
                information = information.split(b':')
        except OSError as err:
            print("Could not read init file from ", self.packets)
            raise err
        except Corrupted as err:
            raise err
        return information

    def readPacketInfo(self,pid):
        """
        Open up a packet and get it's data after resolving the TMR expansion.

        Parameters
        ----------
        pid - int - the integer of the pid of the packet we want to read.

        Returns
        -------
        bytearray - the bytearray of the resolved TMR expansion.

        Exceptions
        ----------
        FileNotFoundError - It cannot find the packet.
        OSError - It cannot access the packet for some other reason.
        Corrupted - If the packet is found to be corrupted throw the Corrupted exception up the stack
        """
        try:
            with open(self.packets+str(pid)+".qp",'br') as packet:
                packet_data = packet.read()
                Decoder.isWrapperCorrupted(packet_data)
                # Resolve the TMR expansion. Since we have 19 bytes of header, start at 19.
                return Decoder.resolveExpansion(packet_data[19:packet_data.rfind(Packet.end + Packet.sync)])
        except (FileNotFoundError,OSError,Corrupted): raise


    def bulkDecode(self):
        """
        The main bulk decoding of a directory of packets. Takes the directory where the packets are
        and attempts to decode them all. This is really the method that should be called when first
        attempting to decode a file.

        DANGER: if the file we are trying to create already exists, then it will get removed
                immediately.

        Returns
        -------
        None - if successful
        list - list of pids of packets not able to be decoded for any reason.

        Raises
        ------
        OSError - init file can't be read.
        Corrupted - init file can't be read due to corruption
        """
        missedPackets = []
        # get all the packets in the directory that have an integer name.
        # directoryPackets = [int(item) for item in [item.replace('.qp','') for item in os.listdir('./packets')] if item.isdigit()]
        if not self.suppress: print("Beginning to decode packets into a file.")
        # Make sure the init packet has been read for the data we need.
        try:
            if self.file_name is None or self.expected_packets is None: self.init()
        except (OSError,Corrupted): raise

        newFile = self.file_path+self.file_name
        # Delete the file if it already exists.
        if os.path.exists(newFile):
            if not self.suppress: print("File already exists. Overwriting with new data (", newFile,")")
            os.remove(newFile)

        pid = -1 # -1 to start at zero
        scaffold_data = []
        while True: # Until we are done...
            try:
                pid += 1
                # Remove the sync and start bits, thus [4:19]
                # header = self.decipherHeader(Decoder.resolveExpansion(packet_data[4:19]))
                # If the packet cannot be found, throw a FileNotFoundError to indicate that.
                information = self.readPacketInfo(pid)
                scaffold_data = self.ammendScaffoldData(scaffold_data,information,pid)

            except FileNotFoundError as e:
                if pid == self.expected_packets: #If the PID is the expected packets then we are done.
                    try:
                        with open(newFile+".scaff", 'wb') as scaffoldToBuild:
                            # Write the scaffold data to the file. We first need to flatten the list
                            scaffoldToBuild.write(bytearray([item for sublist in scaffold_data for item in sublist]))
                    except OSError:
                        print("Failed to write scaffold data: ", newFile or self.file_path)
                    else:
                        if not self.suppress: print("Completed read of packets.")
                    finally:
                        break #This is important to get out of the While Loop
                else: # If there are any packets after the packet we are missing.
                    missedPackets.append(pid)
                    # Ammend the scaffold with placeholder bytes if there is no packet for it.
                    scaffold_data = self.ammendScaffoldData(scaffold_data,bytearray(b'_')*Packet.data_size,pid)
                    continue # Not necessary but good for readability. Hop back to the top of the while loop.
            except OSError:
                print("Unable to read the packet: ",self.packets+str(pid)+".qp")
            except Corrupted as err:
                missedPackets.append(pid)
                # Ammend the scaffold with placeholder bytes if there is no packet for it.
                scaffold_data = self.ammendScaffoldData(scaffold_data,bytearray(b'_')*Packet.data_size,pid)
                continue # Not necessary but good for readability. Hop back to the top of the while loop.
        if missedPackets:
            if not self.suppress: print("Packets missing during decoding. Scaffold intact.")
            return missedPackets
        else:
            if not self.suppress: print("Successfully decoded packets into a file.")
            return None

    def ammendScaffoldData(self,scaffold_data,to_write,pid):
        """
        Decide how to ammend to the scaffold data. This method just takes some of the decision
        logic out of the bulk of the code.

        Parameters
        ----------
        scaffold_data - list - list of bytearrays to be written to the scaffold later
        to_write - bytearray - what will be ammended to the scaffold_data
        pid - int - which packet the data in 'to_write' belongs to. This must be an int or the
                    method will ignore the data.

        Returns
        -------
        list of bytearrays - list of the data to be written to the file where each index is a
                             bytearray representation of the information in a packet
        """
        # Every Packet.data_size bytes, split into a list.
        try:
            scaffold_data[int(pid)]=to_write
        except IndexError:
            scaffold_data.append(to_write)
        except ValueError:
            pass
        return scaffold_data

    def buildScaffold(self):
        """
        Turn the file from a scaffold to a useable file.
        """
        newFile = self.file_path+self.file_name
        os.rename(newFile+".scaff",newFile)
        if self.destructive: self.removePacketFragments()

    def asyncBulkDecode(self,pidList):
        """
        Decode the file asynchronously based on a list if pids.

        Parameters
        ----------
        pidList - list of ints - pids of the packet to be integrated into the file asynchronously

        Returns
        --------
        list - list of pids that it did not decode
        None - it has no more pids to decode

        Exceptions
        ----------
        OSError - init file can't be read.
        TypeError - input is not a list
        Corrupted - if the init file is corrupted
        """
        # Make sure we have an integer or list
        if isinstance(pidList,int):
            pidList = [pidList]
        elif not isinstance(pidList,list):
            raise TypeError("Argument must be a list of integers.")

        if pidList:
            # Make sure the init file has already been read and read it if not.
            try:
                if self.file_name is None: self.init()
            except (OSError,Corrupted): raise
            missedPackets = []
            # Begin to asynchronously add the packets
            try:
                scaffold_data = None
                filePath = self.file_path+self.file_name+".scaff"
                # Make sure the file exists before trying to do anything. There must be a '.scaff' file in the file directory.
                if not os.path.exists(filePath):
                    raise FileNotFoundError('Scaffold does not exist.')
                # Open and read the file.
                with open(filePath,'rb') as scaffold:
                    scaffold_data = scaffold.read()
                    split = Packet.data_size
                    # Split the data into a list that is separated by 77 bytes that way the
                    # packet information placeholders can be overwritten.
                    scaffold_data = [scaffold_data[i:i+split] for i in range(0, len(scaffold_data), split)]
                while pidList: # While there are packets to ammend...
                    try:
                        tempPID = pidList.pop()
                        information = self.readPacketInfo(tempPID)
                        scaffold_data = self.ammendScaffoldData(scaffold_data,information,tempPID)
                    except (FileNotFoundError,Corrupted):
                        # If the packet can't be found, add it to the missedPackets list.
                        missedPackets.append(tempPID)
                    except OSError as err:
                        raise OSError(str(err) + "\nThere was a problem accessing the packet directory: " + self.packets)
                with open(self.file_path+self.file_name+".scaff",'wb') as scaffold:
                    # Write the scaffold data to the file by flattening the scaffold_data
                    scaffold.write(bytearray([item for sublist in scaffold_data for item in sublist]))
            except OSError as err:
                raise OSError(str(err) + "\nUnable to access the scaffold: " + self.file_path + self.file_name + ".scaff")
            return missedPackets or None # Return None instead of an empty list. This makes detecting completion easier.
        return None

    def fullAsyncDecode(self, missedPackets):
        """
        Asynchronously decode a file. As long as there are packets left to decode
        (missedPackets evaluates to True) then wait for Decoder.waitDelay seconds and check to
        see if the packets have arrived again.

        If we want to rush the job, do it once and then return.
        If it does not decode all the packets then it will poll for them until they all
        appear OR it receives a SIGINT.

        DANGER: If this is used for a previously built scaffold and the missing packets are not
        included, then the file will appear corrupted until the original missing packets are included.

        Parameters
        ----------
        missedPackets - list - list of ints for the pids of the packets that are missing.
        """
        if not self.suppress: print("Attempting an async for: ", missedPackets)
        # If we want to rush, only do this once and don't wait for any packets it couldn't do.
        if self.rush:
            missedPackets = self.asyncBulkDecode(missedPackets)
            if missedPackets:
                print("There were packets missing: ", missedPackets,"\n Your scaffold will be intact at", self.file_path)
            else:
                if not self.suppress: print("Completed asynchronously building the scaffold.")
        else: # otherwise, attempt to decode and then poll to get the erst of the packets.
            try:
                while missedPackets: # While there are still packets to wait for
                    time.sleep(Decoder.waitDelay)
                    missedPackets = self.asyncBulkDecode(missedPackets)
                    if not self.suppress: print("Waiting for packets:",missedPackets)
                self.buildScaffold()
            except OSError as err:
                print(err)
            except KeyboardInterrupt: # If a SIGINT is sent, then it's time to stop.
                print("\nNo longer waiting for packets...\nYour scaffold will be intact at", self.file_path)

    def removePacketFragments(self):
        """
        Delete all the packets in the packet directory.
        """
        filelist = glob.glob(os.path.join(self.packets, "*.qp"))
        for f in filelist:
            os.remove(f)

    #def prepareFileLocation(self):
    #     """
    #     Create a blank file that is the size of the current file we want, we'll then substitute
    #     the placeholders for real data.
    #     """
    #    # Open a file and write to it placeholder characters for the actual data.
    #    with open(self.file_path+self.file_name+".scaff",'wb') as tempFile:
    #        tempFile.write(b'_'*self.file_size)

    @staticmethod
    def resolveExpansion(information):
        """
        Resolves our TMR expansion by resolving errors up to one bit. Look into Triple Modular
        Redundancy for more information on the theory behind this method.
        The expansion is also offset by it's own size, this is to avoid burst errors.
        This method will vote based on a whole byte. If all three bytes are different, then
        the packet was corrupted.

        Parameters
        ----------
        information - bytearray - the information that has been TMR expanded.

        Returns
        -------
        bytearray - The information that has been decided to be the correct data. (this will
                    be 1/3 the size of the information coming in)

        Exception
        ---------
        Corrupted - If the three bytes do not agree, then there was a problem in transfering the data
                  and we should consider the data corrupt.
        """
        majority_info = bytearray()
        size = len(information)//3
        for i in range(0,size):
            # Create a tuple for the data.
            tmr = (information[i], information[i + size], information[i + size * 2])
            # Choose the data iff it has the maximum count. If all three are different. Then
            # we know the file is corrupt. turn the tuple into a set to collapse the data
            tmr_set = set(tmr)
            if len(tmr_set) < 3:
                majority_info += bytes([(max(tmr_set, key = tmr.count))])
            else:
                raise Corrupted("The file is determined to be corrupted based on resolving the TMR expansion.")
        return majority_info

    @staticmethod
    def decipherHeader(header):
        """
        Reads what would be the header of a packet and returns a dictionary to easily read each
        field of the header.

        Parameters
        ----------
        header - bytearray - bytearray of the header that does not include the sync or start
                             bytes.

        Returns
        -------
        dictonary for the header information with the following keys:
            pid
            overflow
            op_code
        """
        header_dict = {}
        # Header: sync(2) - start(2)- pid(4)- [overflow(1),op(3),reserved(4)](1)
        header_dict['pid'] = struct.unpack('>L',header[0:4])[0] # Convert byte array to int.
        header_dict['overflow'] = (header[4] >> 7) & 1  # Bit mask to get the first bit
        header_dict['op_code'] =  (header[4] >> 4) & 7  # Bit mask to get the 2nd - 4th bits
        return header_dict

    @staticmethod
    def isWrapperCorrupted(data):
        """
        Check if the header, footer, or sync is corrupted. Also check the file size.

        Parameter
        ---------
        data - bytes - the bytes of the data of a packet. This should be the whole packet (i.e. 256 bytes)

        Exception
        ---------
        Corrupted - If the packet is corrupted, raise a Corrupted Exception
        """
        try:
            Decoder.resolveExpansion(data[4:19])
            rindex = data.rfind(Packet.end + Packet.sync)
            # data[0:2] are the sync bytes, data[2:4] are the start bytes
            # rindex will be -1 if it cannot find the end and sync sequence at the end of the packet
            # even if it found it, check to see if all the final padding bits are \xff. If they aren't
            # then the padding was corrupted OR the ending sequence was corrupted
            # add 4 to the rindex to ignore the end/sync and subtract 4 from the max size to ignore them as well.
            if len(data) != 256 or data[0:2] != Packet.sync or data[2:4] != Packet.start or\
               rindex < 0 or data[rindex+4:Packet.max_size] != b'\xff'*(Packet.max_size - rindex - 4):
                raise Corrupted("The wrapper is corrupted.")
        except Corrupted: raise

class Controller():
    def __init__(self, coder,asyncList=[]):
        """
        Constructor for the controller.
        The Controller acts as the default use case of QUIP.

        Parameters
        ----------
        coder - Encoder or Decoder - An instance of an Encoder or Decoder.
        asyncList - If a list of integers that are the pid to the packets that are missing.
                    If it is given then the Controller will assume that you need to asynchronously
                    build up the scaffold because it already exists

        Raises
        ------
        TypeError - If the coder is not an Encoder or Decoder
        """
        if not isinstance(coder,Encoder) and not isinstance(coder,Decoder):
             raise TypeError("Invalid type: " + str(type(coder)) + ". Must initialize an encoder or decoder.")
        self.coder = coder
        self.asyncList = asyncList

    def begin(self):
        """
        The default method for the controller. Handles the coder properly, as well as working with
        an asynchronous decoding.
        """
        if isinstance(coder,Decoder) and self.asyncList:
            self.coder.fullAsyncDecode(self.asyncList)
        elif not self.asyncList:
            try:
                self.coder.run()
            except Corrupted:
                print("Something was corrupted. Most likely the init packet. Requesting that it is sent again.")
                Controller.sendAgain(['init'])
                try:
                    self.coder.run()
                except Corrupted:
                    print("Something was corrupted. Most likely the init packet. Since this is the second attempt, the controller will exit.\nCheck your data and try again.")
    @staticmethod
    def sendAgain(listOfPid):
        """
        Send the following packets again...must be a list of ints or strings of specific identifiers.

        Parameters
        ----------
        listOfPid - list - list of ints for the pids of the packets that should be sent again.
                           If there is a string, it should be a specific identifier:
                           init
        """
        if isinstance(listOfPid,list):
            for packet in listOfPid:
                # Send the packets somehow
                pass
# Code to be run after importing everything.
# -------------------------------------------
if __name__ == '__main__':
    print("TODO: OPCODES")
    # Set up all the argument parsing options.
    parser = argparse.ArgumentParser(description='Interact with QUIP and encode/decode packets.')
    parser.add_argument('--version',action='version', version = 'Version: 1')
    mutex_group = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument('-s','--suppress',
                        help="Hide the terminal outputs.",
                        default=False,
                        action='store_true')
    parser.add_argument('--destructive',
                        help="Delete the file or packets when the script is done with them. Be careful!",
                        default=False,
                        action='store_true')
    parser.add_argument('-r','--rush',
                        help="Decoding: don't wait for packets if they are not available.",
                        default=False,
                        action='store_true')
    mutex_group.add_argument('-e','--encode',
                        help="Set the mode to Encode.",
                        default=False,
                        action='store_true')
    mutex_group.add_argument('-d','--decode',
                        help="Set the mode to Decode.",
                        default=False,
                        action='store_true')
    parser.add_argument('-p','--packets',
                        dest="packet_location",
                        help="Set the path for the packets to be sent/found.",
                        type=str,
                        required=True)
    parser.add_argument('-f','--file',
                        dest='file_location',
                        help="Set the path for the file to be written/read.",
                        type=str,
                        required=True)
    parser.add_argument('-a','--async',
                        help="Comma separated list of packets to decode asynchronously. Danger: Failure to supply correct packets could result in a non-built or corrupted file.",
                        dest='asyncList',
                        default='',
                        type=str)

    args = parser.parse_args()  # Parse the args coming in from the user
    ctrl = None

    try:
        if bool(args.asyncList):
            print("Warning: if all the packets missing are not given the file will appear corrupted.")
            # Turn all the asynchronous pids into ints. This will throw a ValueError if one is not an int.
            args.asyncList = list(map(lambda x: int(x),args.asyncList.split(',')))

        if args.encode: # If set to encode
            coder = Encoder(args.file_location,args.packet_location,suppress=args.suppress,destructive=args.destructive)
        else: # If set to decode or async
            coder = Decoder(args.file_location,args.packet_location,suppress=args.suppress,destructive=args.destructive,rush=args.rush)
        ctrl = Controller(coder,asyncList=args.asyncList)
    except TypeError as err:
        print("Error: ",err)
        exit()
    except ValueError:
        print("Invalid async list values. Must be a comma separated list of integers.")
        exit()

    # Actually start working.
    ctrl.begin()