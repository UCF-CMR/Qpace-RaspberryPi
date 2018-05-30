#!/usr/bin/env python3
# qpaceQUIP.py by Jonathan Kessluk
# 5-22-2018, Rev. 2
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

import qpaceChecksum as checksum

try:
    raise ImportError
    import qpaceLogger as logger
    quip_LOGGER=True
except ImportError:
    quip_LOGGER=False

def quipPrint(*strings):
    """
    If the logger was imported then log it. If there was a problem
    importing the logger then just print to screen.

    Parameters
    ----------
    strings - take in variable arguments
    """
    string = ' '.join(map(str,strings))
    if quip_LOGGER:
        logger.logSystem([['QUIP:'+ string]])
    else:
        print(string)

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
    data_size = None        # in bytes. Initial state is None. Gets calculated later
    max_id = 0xFFFFFFFF     # 4 bytes. Stored as an int.
    last_id = 0            # -1 if there are no packets yet.

    validDesignators = [0]   # WTC, Pi 1, Pi 2, GS.

    def __init__(self,data, pid,rid,useFEC = False,lastPacket = False):
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

        if useFEC:
            Packet.data_size = (Packet.max_size - Packet.header_size) // 3
        else:
            Packet.data_size = Packet.max_size - Packet.header_size
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
        else:
            raise ValueError("Packet size is too large for the current header information ("+str(len(data))+"). Data input restricted to " + str(Packet.data_size) + " Bytes.")

    def buildHeader(self,useFEC=True):
        """
            Build the header for the packet.

            Returns
            -------
            bytearray - packet header data.
        """
        # The byte order will be bigendian
        pid = self.pid.to_bytes(4,byteorder='big')     # 4 bytes
        rid = self.rid.to_bytes(1,byteorder='big')
        return rid + pid # should be 5 bytes

    def buildData(self):
        """
            Build the data for the packet. All data is repeated 3 times for FEC.

            Returns
            -------
            bytearray - packet data that is triple redundant and interlaced by size of the data
        """
        # Do a TMR expansion where the data is replicated 3 times but not next to each other
        # to avoid burst errors.
        if self.useFEC:
            return self.data * 3
        else:
            return self.data

    def build(self):
        """
            Build the entire packet.

            Returns
            -------
            int - the whole packet. if converted to binary/hex it will be the packet.
        """
        # Construct the packet's data
        packet = self.buildHeader() + self.buildData() + b'\x03'
        if self.lastPacket:
            packet += b'\x04'
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

class Encoder():
    def __init__(self,path_for_encode,path_for_packets, useFEC=True,destination=None,suppress=False):
        """
        Constructor for the Encoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to encode the file.
        path_for_packets - str - where to store the packets.
        suppress - bool - suppress output to the terminal.

        Raises
        ------
        TypeError - raises if the paths aren't valid paths.
        """
        # We want a path for the packets and a file for the decoding that's useable.
        if path_for_packets[-1] != '/' or path_for_encode[-1] == '/':
            if path_for_packets == ".":
                path_for_packets = ''
            else:
                raise TypeError("Please provide a valid directory for the packets to be placed and a valid file to encode.")
        self.file = path_for_encode[:path_for_encode.rfind('/')+1] + path_for_encode[path_for_encode.rfind('/')+1:].replace(' ','_')
        self.packets = path_for_packets
        self.suppress = suppress
        self.packets_built = 0
        self.destination = destination
        self.useFEC = useFEC
        self.crc32checksum = checksum.checksum(open(self.file,'rb'))
        self.filesize = os.path.getsize(self.file)
        if useFEC:
            Packet.data_size = (Packet.max_size - Packet.header_size) // 3
        else:
            Packet.data_size = Packet.max_size - Packet.header_size
        self.expected_packets = self.filesize / Packet.data_size

    def run(self):
        """
        Main method to run for the encoder. This will encode a file into packets.

        Returns
        -------
        True - successful
        False - unsuccessful for any reason
        """
        # If we are successful at encoding the file build the init packet.
        try:
            if self.encode():
                self.buildInitPacket()
            else:
                return False
        except:
            return False
        else:
            return True

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
                if not self.suppress: quipPrint("Beginning to encode file into packets.")
                pid = 0 # zero so we can start at 1
                try:
                    packetToBuild = None
                    while True: # Until we are done...
                        pid += 1 # choose the next PID in order
                        data = fileToEncode.read(Packet.data_size-1)
                        if data:
                            try:
                                packetToBuild = Packet(data,pid, 0, useFEC=self.useFEC)
                                if not quip_LOGGER:
                                    sys.stdout.write("\rEncoding file: %d%%" % (pid*100/ceil(self.expected_packets)))
                                    sys.stdout.flush()
                            except Exception as err:
                                quipPrint(str(err))
                        else:
                            # If there's no more data set the last packet created as op_code 0x7
                            self.saveLastPacket(packetToBuild)
                            if not quip_LOGGER:
                                sys.stdout.write("\rEncoding file: 100%")
                                sys.stdout.flush()
                            break #If there's nothing else to read, back out. We are done.

                        with open(self.packets+str(pid)+".qp", 'wb') as packet:
                            packet.write(packetToBuild.build())
                except OSError as err:
                    #quipPrint("Could not write packet: ", pid)
                    raise err
                else:
                    if not self.suppress: quipPrint("\nSuccessfully built ", pid, " packets.")
                    self.packets_built = pid
        except FileNotFoundError:
            quipPrint("Can not find file: ", self.file)
        except OSError:
            quipPrint("There was a problem encoding: ",self.file)
        else: # success
            if not self.suppress: quipPrint("Finished encoding file into packets.")
            return True
        return False

    def buildFileInfo(self):
        try:
            if self.useFEC:
                fec = 'OkEC'
            else:
                fec = 'NoEC'
            return [self.file.split("/")[-1],str(self.packets_built),str(self.filesize),str(self.destination),str(self.crc32checksum),fec]
        except:
            raise ValueError("Can not build file info.")
    def buildInitPacket(self):
        """
        Create the init packet. This packet is crucial and without sending one, the decoder may
        not have all the information it needs.

        Exceptions
        ----------
        Warning - The init packet could not be created.
        """
        if not self.suppress: quipPrint("Creating initialization packet.")
        try:
            with open(self.packets+"0.qp",'wb') as packet:
                # Write to the actual packet. Make sure the op_code is 0x1 since it's the init packet
                # Separate the data with a ':' since filenames should not have that anyway.
                initdata = " ".join(self.buildFileInfo())
                packet.write(Packet(initdata,0,0,useFEC=True).build())
        except (OSError,ValueError,Exception) as error:
            err = Warning("Could not write initialization packet: 0.qp")
            quipPrint("Exception message: " + str(error) + "\n" + str(err))
            raise err from error
    def saveLastPacket(self,packet):
        """
        Set a packet as the last packet.

        Parameters
        ----------
        packet - Packet - an instance of the Packet that we'd like to build. Change it's op_code
                          and then re-write the packet.

        Returns
        -------
        True - if successful
        False - if failed
        """
        try:
            # If the packet we want to write doesn't have enough space for the EOT character, write an empty packet with only EOT characters
            if len(packet.data) == Packet.data_size:
                with open(self.packets+str(packet.pid+1)+".qp",'wb') as lastPacket:
                    newPacket = Packet(b'',packet.pid+1,packet.rid,packet.useFEC,lastPacket=True) #chr(4) is the EOT character
                    lastPacket.write(newPacket.build())

            else:
                packet.lastPacket = True
            # Save the intended packet.
            with open(self.packets+str(packet.pid)+".qp",'wb') as packetToRewrite:
                packetToRewrite.write(packet.build())
        except:
            return False
        else:
            return True

    def removePacketFragments(self):
        """
        Delete all the packets in the packet directory.
        """
        filelist = glob.glob(os.path.join(self.packets, "*.qp"))
        for f in filelist:
            os.remove(f)

class Decoder():
    # TODO Make decoder work with streams.
    waitDelay = 1 # In seconds. This is for the asynchronous decoding.

    def __init__(self, path_for_decode, path_for_packets, useFEC=True, suppress=False,rush=False):
        """
        Constructor for the Decoder.

        Parameters
        ----------
        path_for_encode - str - The path with a filename on it to decode to.
        path_for_packets - str - where the packets are stored.
        suppress - bool - suppress output to terminal

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
        elif path_for_decode == '.':
            self.file_path = ''
            self.file_name = None
        else:
            # Split the path and the name apart.
            self.file_path = path_for_decode[:path_for_decode.rfind('/')+1]
            self.file_name = path_for_decode[path_for_decode.rfind('/')+1:].replace(' ','_')
        self.packets = path_for_packets
        self.suppress = suppress
        self.rush = rush
        self.expected_packets = None
        self.file_size = None
        self.useFEC = useFEC

        if useFEC:
            Packet.data_size = (Packet.max_size - Packet.header_size) // 3
        else:
            Packet.data_size = Packet.max_size - Packet.header_size

    def run(self, skipAsync = False):
        """
        Main method to run for the decoder. Takes the packets from a path and decodes them into a file.

        Returns
        -------
        missedPackets - list - list of packets that were not able to be decoded. Only returned if we skip the asyncDecode
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
                if not self.suppress: quipPrint("There are no missing packets.")
                self.buildScaffold()
            else:
                if skipAsync:
                    return missedPackets
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
            self.destination = initPacket[3].decode('utf-8')
            self.crc32checksum = initPacket[4].decode('utf-8')
            fec=initPacket[5].decode('utf-8')
            if fec == 'OkEC':
                self.useFEC = True
                Packet.data_size = (Packet.max_size - Packet.header_size) // 3
            elif fec == 'NoEC':
                self.useFEC = False
                Packet.data_size = Packet.max_size - Packet.header_size
            else:
                raise Corrupted("Could not determine if FEC was used.")
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
            with open(self.packets+"0.qp",'rb') as init:
                information = init.read()
                # Resolve the TMR expansion from the packet.
                self.corruptedTest(information,True)
                information = Decoder.resolveExpansion(information[Packet.header_size:])
                #if self.useFEC:
                #    information = Decoder.resolveExpansion(information[Packet.header_size:])
                #else:
                #    information = information[Packet.header_size:information.rfind(b'\x03')]
                # Split on the ' ' since that should not be in any data
                information = information.split(b' ')

        except OSError as err:
            quipPrint("Could not read init file from ", self.packets)
            raise err
        except Corrupted as err:
            quipPrint(err)
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
        bytearray - the bytearray of the info/data of the packet: a resolved TMR expansion .

        Exceptions
        ----------
        FileNotFoundError - It cannot find the packet.
        OSError - It cannot access the packet for some other reason.
        Corrupted - If the packet is found to be corrupted throw the Corrupted exception up the stack
        """
        try:
            with open(self.packets+str(pid)+".qp",'br') as packet:
                packet_data = packet.read()
                self.corruptedTest(packet_data)
                information = packet_data[Packet.header_size:]
                # Resolve the TMR expansion.
                if self.useFEC:
                    return Decoder.resolveExpansion(information)
                else:
                    return information[:information.rfind(b'\x03')]
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
        if not self.suppress: quipPrint("Beginning to decode packets into a file.")
        # Make sure the init packet has been read for the data we need.
        try:
            if self.file_name is None or self.expected_packets is None: self.init()
        except (OSError,Corrupted): raise

        newFile = self.file_path+self.file_name
        # Delete the file if it already exists.
        if os.path.exists(newFile):
            if not self.suppress: quipPrint("File already exists. Overwriting with new data (", newFile,")")
            os.remove(newFile)

        pid = 0 # zero to start at 1
        scaffold_data = []
        while True: # Until we are done...
            try:
                pid += 1
                # If the packet cannot be found, throw a FileNotFoundError to indicate that.
                information = self.readPacketInfo(pid)
                scaffold_data = self.insertScaffoldData(scaffold_data,information,pid)
                if not quip_LOGGER:
                    sys.stdout.write("\rDecoding file: %d%%" % (pid*100/ceil(self.expected_packets)))
                    sys.stdout.flush()

            except FileNotFoundError as e:
                if pid == self.expected_packets: #If the PID is the expected packets then we are done.
                    if not quip_LOGGER:
                        sys.stdout.write("\rDecoding file: 100%\n")
                        sys.stdout.flush()
                    try:
                        with open(newFile+".scaff", 'wb') as scaffoldToBuild:
                            # Write the scaffold data to the file. We first need to flatten the list
                            scaffoldToBuild.write(bytearray([item for sublist in scaffold_data for item in sublist]))
                    except OSError:
                        quipPrint("Failed to write scaffold data: "+ newFile or self.file_path)
                    else:
                        if not self.suppress: quipPrint("Completed read of packets.")
                    finally:
                        break #This is important to get out of the While Loop
                else: # If there are any packets after the packet we are missing.
                    missedPackets.append(pid)
                    # Ammend the scaffold with placeholder bytes if there is no packet for it.
                    scaffold_data = self.insertScaffoldData(scaffold_data,bytearray(b'_')*(Packet.data_size-1),pid) #-1 to account for ETX
                    continue # Not necessary but good for readability. Hop back to the top of the while loop.
            except OSError:
                quipPrint("Unable to read the packet: ",self.packets+str(pid)+".qp")
            except Corrupted as err:
                missedPackets.append(pid)
                # Ammend the scaffold with placeholder bytes if there is no packet for it.
                scaffold_data = self.insertScaffoldData(scaffold_data,bytearray(b'_')*(Packet.data_size-1),pid) #-1 to account for ETX
                continue # Not necessary but good for readability. Hop back to the top of the while loop.
        if missedPackets:
            if not self.suppress: quipPrint("Packets missing during decoding. Scaffold intact.")
            return missedPackets
        else:
            if not self.suppress: quipPrint("Successfully decoded packets into a file.")
            return None

    def insertScaffoldData(self,scaffold_data,to_write,pid):
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
            scaffold_data[int(pid)-1]=to_write #-1 because the pids are shifted.
        except IndexError:
            scaffold_data.append(to_write)
        except ValueError:
            pass
        return scaffold_data

    def buildScaffold(self):
        """
        Turn the file from a scaffold to a useable file.

        Raises
        ------
        Corrupted - The file checksums don't match.
        """
        newFile = self.file_path+self.file_name
        newChecksum = checksum.checksum(open(newFile+'.scaff','rb'))
        if  newChecksum == self.crc32checksum:
            quipPrint("The checksums match! ("  + str(self.crc32checksum) +" == "+ newChecksum +")")
            os.rename(newFile+".scaff",newFile)
        else:
            quipPrint('The file does not have the same checksum. (' + str(self.crc32checksum) +" != "+ newChecksum +")")
            raise Corrupted("The file does not have the same checksum with the init packet.")

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

        if pidList:
            # Make sure we have an integer or list
            if isinstance(pidList,int):
                pidList = [pidList]
            elif not isinstance(pidList,list):
                raise TypeError("Argument must be a list of integers.")
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
                    split = Packet.data_size-1 #-1 to account for the ETX
                    # Split the data into a list that is separated by 77 bytes that way the
                    # packet information placeholders can be overwritten.
                    scaffold_data = [scaffold_data[i:i+split] for i in range(0, len(scaffold_data), split)]
                while pidList: # While there are packets to ammend...
                    try:
                        tempPID = pidList.pop()
                        information = self.readPacketInfo(tempPID)
                        scaffold_data = self.insertScaffoldData(scaffold_data,information,tempPID)
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
        if not self.suppress: quipPrint("Attempting an async for: ", len(missedPackets or []), "packets")
        # If we want to rush, only do this once and don't wait for any packets it couldn't do.
        if self.rush:
            missedPackets = self.asyncBulkDecode(missedPackets)
            if missedPackets:
                quipPrint("There were packets missing: ", len(missedPackets or []),"packets\n Your scaffold will be intact at", self.file_path)
            else:
                if not self.suppress: quipPrint("Completed asynchronously building the scaffold.")
        else: # otherwise, attempt to decode and then poll to get the erst of the packets.
            try:
                while missedPackets: # While there are still packets to wait for
                    time.sleep(Decoder.waitDelay)
                    missedPackets = self.asyncBulkDecode(missedPackets)
                    if not self.suppress: quipPrint("Waiting for packets:", len(missedPackets or []), "packets")
                self.buildScaffold()
            except Corrupted as err:
                quipPrint(err)
                raise err
            except OSError as err:
                quipPrint(err)
            except KeyboardInterrupt: # If a SIGINT is sent, then it's time to stop.
                quipPrint("\nNo longer waiting for packets...\nYour scaffold will be intact at", self.file_path)

    def removePacketFragments(self):
        """
        Delete all the packets in the packet directory.

        Ignore all exception
        """
        try:
            filelist = glob.glob(os.path.join(self.packets, "*.qp"))
            for f in filelist:
                os.remove(f)
        except: pass

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
        information = information[:information.rfind(b'\x03')]
        majority_info = bytes()
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
                raise Corrupted("The file is determined to be corrupted based on trying to resolve the TMR expansion.")
        return majority_info

    @staticmethod
    def getPID(packet):
        header_dict = {}
        return struct.unpack('>L',header[0:4])[0] # Convert byte array to int.

    def corruptedTest(self,packetData,ignoreLength=False):
        """
        Check if the header, footer, or sync is corrupted. Also check the file size.

        Parameter
        ---------
        data - bytes - the bytes of the data of a packet. This should be the whole packet (i.e. 256 bytes)

        Exception
        ---------
        Corrupted - If the packet is corrupted, raise a Corrupted Exception
        """
        if len(packetData) != Packet.max_size or\
           packetData[0] not in Packet.validDesignators or\
           ((Packet.max_size - Packet.header_size != Packet.data_size * (3 if self.useFEC else 1)) and not ignoreLength):
           raise Corrupted("Packet determined to be corrupted.")

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
            try:
                self.coder.fullAsyncDecode(self.asyncList)
            except Corrupted as err:
                quipPrint(err)
                #TODO what to do if the file is corrupted?
        elif not self.asyncList:
            try:
                self.coder.run()
            except Corrupted as err:
                quipPrint("Something was corrupted. Most likely the init packet. Requesting that the init packet is sent again.")
                #Controller.sendAgain(['init'])
                #TODO this protocol.
                try:
                    self.coder.run()
                except Corrupted as err:
                    quipPrint("Something was corrupted. Most likely the init packet. Since this is the second attempt, the controller will exit.\nCheck your data and try again.")

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

    # Set up all the argument parsing options.
    parser = argparse.ArgumentParser(description='Interact with QUIP and encode/decode packets.')
    parser.add_argument('--version',action='version', version = 'Version: 1')
    mutex_group = parser.add_mutually_exclusive_group(required=True)

    parser.add_argument('-s','--suppress',
                        help="Hide the terminal outputs.",
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
    parser.add_argument('-dest','--destination',
                        help="Destination file path for the file.",
                        default='/',
                        type=str)
    parser.add_argument('-NoFEC','--NoFEC',
                        help='Disable FEC in packets. FEC uses Triple Modular Redundancy as well as simple interlacing.',
                        default = False,
                        action = 'store_true') #By default "NoFEC" is false, but will be inverted to use the encoder/decoder

    args = parser.parse_args() # Parse the args coming in from the user
    ctrl = None

    try:
        if bool(args.asyncList):
            quipPrint("Warning: if all the packets missing are not given the file will appear corrupted.")
            # Turn all the asynchronous pids into ints. This will throw a ValueError if one is not an int.
            args.asyncList = list(map(lambda x: int(x),args.asyncList.split(',')))


        if args.encode: # If set to encode
            coder = Encoder(args.file_location,args.packet_location,useFEC = not args.NoFEC,destination=args.destination,suppress=args.suppress)
        else: # If set to decode or async
            coder = Decoder(args.file_location,args.packet_location,useFEC = not args.NoFEC, suppress=args.suppress,rush=args.rush)
        ctrl = Controller(coder,asyncList=args.asyncList)
    except TypeError as err:
        quipPrint("Error: ",err)
        exit()
    except ValueError:
        quipPrint("Invalid async list values. Must be a comma separated list of integers.")
        exit()

    # Actually start working.
    ctrl.begin()