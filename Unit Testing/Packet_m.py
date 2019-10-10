import sys
import math
import time
import zlib
import warnings
import bitstring
import random

warnings.simplefilter('always', UserWarning)


class BasePacket:

    length = None

    packet   = None
    checksum = None

    def __init__(self, length):

        self.length = length

    def BytesToInt(self, bytestring):
        value = 0
        for i, c in enumerate(bytestring):
            value |= (c << 8*(len(bytestring)-i-1))
        return value

    def BoolToByte(self, boolean):
        if boolean: value = 0xFF
        else:       value = 0x00
        return value

    def ByteToBool(self, byte):
        return bitstring.Bits(uint=byte, length=8).count(1) > 3

    def IntToBinString(self, value, bits):
        return ("0b{0:0%db}" % bits).format(value)

    def PadBitArray(self, bitarray, length):
        if length*8 > len(bitarray):
            bitarray.append(bitstring.Bits(bin=self.IntToBinString(0, length*8-len(bitarray))))
        return bitarray

    def GenerateChecksum(self):
        bitarray = self.PadBitArray(self.packet, self.length-4)
        checksum = 0x811C9DC5 # 32-Bit FNV Offset Basis
        for byte in bitarray.bytes:
            checksum ^= byte
            checksum *= 0x1000193 # 32-Bit FNV Prime
        checksum &= 0xFFFFFFFF
        return bitstring.Bits(hex=('0x%08X' % checksum))

    def VerifyChecksum(self):
        """Returns true if checksum of the packet matches the expected checksums"""

        # Until an alternative checksum algorithm is implemented, this will always return true
        return True
        #return self.GenerateChecksum() == self.checksum

    def CalcPacketLength(self):
        return len(self.packet + self.checksum)/8

    def ErrorCheck(self, name, value, bits):
        if value < 0 or value > 2**bits-1: raise ValueError("Packet %s limited to %d bits!" % (name, bits))

    def DumpPacket(self):
        return self.PadBitArray(self.packet, self.length-4) + self.checksum

    def LoadPacket(self, bitarray):
        if len(bitarray) != self.length*8: raise ValueError("Packet must be exactly %d bytes!" % self.length)
        self.packet   = bitarray[:-32]
        self.checksum = bitarray[-32:]
        if not self.VerifyChecksum(): raise ValueError("Packet has invalid checksum!")

    def PrintBitArray(self, bitarray, name):
        sys.stdout.write(name + " (%d bytes %d bits):" % divmod(len(bitarray), 8))
        for i in range(len(bitarray)%8):
            bitarray.append(bitstring.Bits(bin="0b0"))
        for i, v in enumerate(bitarray.bytes):
            if i % 16 == 0: sys.stdout.write("\n")
            sys.stdout.write("%02X " % v)
        sys.stdout.write("\n")
    #added func by chance
    def ReturnStringToPrint(self, bitarray, name):
        string1 = ""
        string1 += name+ "(%d bytes %d bits):"%divmod(len(bitarray), 8)
        for i in range(len(bitarray)%8):
            bitarray.append(bitstring.Bits(bin="0b0"))
        for i, v in enumerate(bitarray.bytes):
            if i % 16 == 0: string1 += "\n"
            #string1 += ("%02X " % v) what was before
            if(v >= 32 and v < 126):
                string1 += ("%s" % chr(v))
            else:
                string1 += ("%02X" % v)

        string1 += "\n"
        return string1

    #This guy should return a string that is only on one line with the full packet for parsing
    def ReturnSingleLineOfBytes(self, bitarray):
        string1 = ""
        for i in range(len(bitarray) % 8):
            bitarray.append(bitstring.Bits(bin="0b0"))
        for i, v in enumerate(bitarray.bytes):
            string1 += ("%02X" % v)  #This is hex
        string1 += "\n"
        return string1

    def PrintFullPacket(self):
        self.PrintBitArray(self.DumpPacket(), "Full packet")
        print()


class Download_Ack(BasePacket):
    headsize = 124

    headconf = [
            {"bits":  1*8, "name": "routing",     "value": None},
            {"bits":  5*8, "name": "opcode",      "value": None},
            {"bits":  4*8, "name": "response",    "value": None},
            {"bits": 114*8, "name": "rand1",    "value": None},
            ]

    def __init__(self):
        super().__init__(128)
        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetResponse(self, ASCIIResponse):
        self.SetGenericField("response", ASCIIResponse)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def SetRandoms(self):
        self.SetGenericField("rand1", random.getrandbits(114*8))

    def SetFilePath(self, FilePath):
        self.SetGenericField("FilePath", FilePath)
        """
    def SetActivity(self, Activity):
        self.SetGenericField("Activity", Activity)
        """
    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)


class General_Pi_Packet(BasePacket):
    headsize = 112

    headconf = [
            {"bits":  1*8, "name": "routing",     "value": None},
            {"bits":  5*8, "name": "opcode",      "value": None},
            {"bits":  4*8, "name": "rand1",       "value": None},
            #{"bits":  2*8, "name": "Activity",    "value": None},
            {"bits": 96*8, "name": "FilePath",    "value": None},
            #{"bits":  2*8, "name": "randABCD",    "value": None},
            {"bits": 6*8,  "name": "rand2",       "value": None}
            ]

    def __init__(self):
        super().__init__(128)
        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()
        """
    def LoadPacket(self, bitarray):
        if len(bitarray) != self.length*8: raise ValueError("Packet must be exactly %d bytes!" % self.length)
        self.packet   = bitarray[:-32]
        self.checksum = bitarray[-32:]
        #if not self.VerifyChecksum(): raise ValueError("Packet has invalid checksum!")
        """
    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def SetRandoms(self):
        #choices = ["AA", "BB", "CC", "DD", "EE"]
        #chosenKey = random.randint(0, 4)
        self.SetGenericField("rand1", random.getrandbits(4*8))
        self.SetGenericField("rand2", random.getrandbits(6*8))
        #self.SetGenericField("randABCD", self.BytesToInt(bytearray(choices[chosenKey], 'utf8')))

    def SetFilePath(self, FilePath):
        self.SetGenericField("FilePath", FilePath)

    def GetFilePath(self):
        return bytearray(self.headconf[3]["FilePath"])
        """
    def SetActivity(self, Activity):
        self.SetGenericField("Activity", Activity)
        """
    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildOnlyPacket(self):
        self.BuildHeader()
        self.packet = self.head+self.body

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 80).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("CMD:   0x%032X" % self.GetBitdict("cmd")[1]["value"].uint)

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class UploadFinalAck(BasePacket):
    headsize = 124

    headconf = [
            {"bits":  1*8, "name": "routing",     "value": None},
            {"bits":  5*8, "name": "opcode",      "value": None},
            {"bits":  4*8, "name": "number",      "value": None},
            {"bits":  4*8, "name": "checkSum",    "value": None},
            {"bits":  1*8, "name": "binary1",     "value": None},
            {"bits":  1*8, "name": "padding",     "value": None},
            {"bits":  1*8, "name": "binary2",     "value": None},
            {"bits": 107*8, "name": "fileName",   "value": None}
            ]

    def __init__(self):
        super().__init__(128)
        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def SetRelevantResponses(self, number, checksum, padding, fileName):
        self.SetGenericField("number", number)
        self.SetGenericField("checkSum", checksum)
        self.SetGenericField("binary1", 0x20)
        self.SetGenericField("binary2", 0x20)
        self.SetGenericField("padding", padding)
        self.SetGenericField("fileName", fileName)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 80).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("CMD:   0x%032X" % self.GetBitdict("cmd")[1]["value"].uint)

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class UploadFilePacket(BasePacket):
    headsize = 124

    headconf = [
            {"bits":  1*8, "name": "routing",     "value": None},
            {"bits":  5*8, "name": "opcode",      "value": None},
            {"bits":  4*8, "name": "number",       "value": None},
            {"bits": 114*8, "name": "data",       "value": None}
            ]

    def __init__(self):
        super().__init__(128)
        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def SetNumPacket(self, number):
        self.SetGenericField("number", number)

    def SetData(self, data):
        self.SetGenericField("data", data)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 80).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("CMD:   0x%032X" % self.GetBitdict("cmd")[1]["value"].uint)

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class CMDPacket(BasePacket):
    headsize = 44

    headconf = [
            {"bits":  1*8, "name": "routing",     "value": None},
            {"bits":  5*8, "name": "opcode",      "value": None},
            {"bits":  4*8, "name": "rand1",       "value": None},
            {"bits": 32*8, "name": "cmd",         "value": None},
            {"bits":  2*8, "name": "rand2",       "value": None}
            ]

    def __init__(self):
        super().__init__(128)
        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def SetRandoms(self):
        self.SetGenericField("rand1", random.getrandbits(4*8))
        self.SetGenericField("rand2", random.getrandbits(2*8))

    def SetCMDRegion(self, CMDPacket):
        self.SetGenericField("cmd", CMDPacket)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 80).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("CMD:   0x%032X" % self.GetBitdict("cmd")[1]["value"].uint)

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class GroundPacket(BasePacket):

    headsize = 49

    headconf = [
        {"bits":  1*8, "name": "routing",     "value": None},
        {"bits":  5*8, "name": "opcode",      "value": None},
        {"bits": 12*8, "name": "exchto",      "value": None},
        {"bits": 21*8, "name": "exchfrom",    "value": None},
        {"bits":  3*8, "name": "exchsig",     "value": None},
        {"bits":  1*8, "name": "timemonth",   "value": None},
        {"bits":  1*8, "name": "timeday",     "value": None},
        {"bits":  1*8, "name": "timeyear",    "value": None},
        {"bits":  1*8, "name": "timeweekday", "value": None},
        {"bits":  1*8, "name": "timehour",    "value": None},
        {"bits":  1*8, "name": "timeminute",  "value": None},
        {"bits":  1*8, "name": "timesecond",  "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetExchangeTo(self, exchto):
        self.SetGenericField("exchto", exchto)

    def SetExchangeFrom(self, exchfrom):
        self.SetGenericField("exchfrom", exchfrom)

    def SetExchangeSignal(self, exchsig):
        self.SetGenericField("exchsig", exchsig)

    def SetTimeMonth(self, timemonth):
        self.SetGenericField("timemonth", timemonth)

    def SetTimeDay(self, timeday):
        self.SetGenericField("timeday", timeday)

    def SetTimeYear(self, timeyear):
        self.SetGenericField("timeyear", timeyear)

    def SetTimeWeekday(self, timeweekday):
        self.SetGenericField("timeweekday", timeweekday)

    def SetTimeHour(self, timehour):
        self.SetGenericField("timehour", timehour)

    def SetTimeMinute(self, timeminute):
        self.SetGenericField("timeminute", timeminute)

    def SetTimeSecond(self, timesecond):
        self.SetGenericField("timesecond", timesecond)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 72).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        timevalues = []
        timenames = ["timeyear", "timemonth", "timeday", "timehour", "timeminute", "timesecond"]
        for timename in timenames:
            timevalues.append(self.GetBitdict(timename)[1]["value"].int)

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing:  %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:   %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("ExchTo:   %s" % self.GetBitdict("exchto")[1]["value"].bytes.decode("ascii"))
        print("ExchFrom: %s" % self.GetBitdict("exchfrom")[1]["value"].bytes.decode("ascii"))
        print("ExchSig:  %s" % self.GetBitdict("exchsig")[1]["value"].bytes.decode("ascii"))
        print("Date:     %02d/%02d/%02d" % tuple(timevalues)[0:3])
        print("Time:     %02d:%02d:%02d" % tuple(timevalues)[3:6])

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class DDumpPacket(BasePacket):

    headsize = 10

    headconf = [
        {"bits":  1*8, "name": "routing", "value": None},
        {"bits":  5*8, "name": "opcode",  "value": None},
        {"bits":  4*8, "name": "ddump",   "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetDDump(self, ddump):
        self.SetGenericField("ddump", ddump)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 109).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("DDump:   0x%04X" % self.GetBitdict("ddump")[1]["value"].uint)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class SuicidePacket(BasePacket):

    headsize = 6

    headconf = [
        {"bits":  1*8, "name": "routing", "value": None},
        {"bits":  5*8, "name": "opcode",  "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 109).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class ESATDoPacket(BasePacket):

    headsize = 7

    headconf = [
        {"bits":  1*8, "name": "routing", "value": None},
        {"bits":  5*8, "name": "opcode",  "value": None},
        {"bits":  1*8, "name": "thing1",  "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetThing1(self, thing1):
        self.SetGenericField("thing1", thing1)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 109).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("Thing1:  0x%02X" % self.GetBitdict("thing1")[1]["value"].uint)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class ESATConfPacket(BasePacket):

    headsize = 9

    headconf = [
        {"bits":  1*8, "name": "routing", "value": None},
        {"bits":  5*8, "name": "opcode",  "value": None},
        {"bits":  1*8, "name": "thing1",  "value": None},
        {"bits":  1*8, "name": "thing2",  "value": None},
        {"bits":  1*8, "name": "thing3",  "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetThing1(self, thing1):
        self.SetGenericField("thing1", thing1)

    def SetThing2(self, thing2):
        self.SetGenericField("thing2", thing2)

    def SetThing3(self, thing3):
        self.SetGenericField("thing3", thing3)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 109).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("Thing1:  0x%02X" % self.GetBitdict("thing1")[1]["value"].uint)
        print("Thing2:  0x%01X" % self.GetBitdict("thing2")[1]["value"].uint)
        print("Thing3:  0x%01X" % self.GetBitdict("thing3")[1]["value"].uint)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class SDDumpPacket(BasePacket):

    headsize = 15

    headconf = [
        {"bits":  1*8, "name": "routing", "value": None},
        {"bits":  5*8, "name": "opcode",  "value": None},
        {"bits":  4*8, "name": "rstart",  "value": None},
        {"bits":  4*8, "name": "rcount",  "value": None},
        {"bits":  4*8, "name": "rdelay",  "value": None},
    ]

    head = None
    body = None

    def __init__(self):
        super().__init__(128)

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetRouting(self, routing):
        self.SetGenericField("routing", routing)

    def SetOpcode(self, opcode):
        self.SetGenericField("opcode", opcode)

    def SetReadStart(self, rstart):
        self.SetGenericField("rstart", rstart)

    def SetReadCount(self, rcount):
        self.SetGenericField("rcount", rcount)

    def SetReadDelay(self, rdelay):
        self.SetGenericField("rdelay", rdelay)

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for v in self.PadBitArray(self.body, 109).bytes:
            sys.stdout.write("%02X" % v)
        sys.stdout.write("\n")
        sys.stdout.flush()

        routing = self.GetBitdict("routing")[1]["value"].uint
        routingLookup = {0xFF: "WTC", 0x02: "PI2", 0x01: "PI1", 0x00: "GND"}

        print()
        print("Routing: %s" % routingLookup.get(routing, "UNK"))
        print("Opcode:  %s" % self.GetBitdict("opcode")[1]["value"].bytes.decode("ascii"))
        print("RStart:  %d" % self.GetBitdict("rstart")[1]["value"].uint)
        print("RCount:  %d" % self.GetBitdict("rcount")[1]["value"].uint)
        print("RDelay:  %d" % self.GetBitdict("rdelay")[1]["value"].uint)

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")


class ConfigurationPacket(BasePacket):

    wtcsize = 52
    pischedconf = [
        {"bits":  8, "name": "Pi Select",       "value": None, "actbits":  1},
        {"bits": 32, "name": "Start Timestamp", "value": None, "actbits": 32},
        {"bits": 32, "name": "Stop Timestamp",  "value": None, "actbits": 32}
    ]
    wtcconf = [
        {"bits":  8, "name": "routing",   "value": None},
        {"bits": 40, "name": "opcode",    "value": None},
        {"bits": 72, "name": "pisched1",  "value": pischedconf},
        {"bits": 72, "name": "pisched2",  "value": pischedconf},
        {"bits": 72, "name": "pisched3",  "value": pischedconf},
        {"bits": 72, "name": "pisched4",  "value": pischedconf},
        {"bits": 16, "name": "period",    "value": None},
        {"bits": 16, "name": "operation", "value": None},
    ]

    pisize = 72
    piconfigconf = [
        {"bits":  8, "name": "Science Mode",                 "value": None, "actbits":  1},
        {"bits":  8, "name": "Electrometer Enable",          "value": None, "actbits":  1},
        {"bits":  8, "name": "Langmuir Enable",              "value": None, "actbits":  1},
        {"bits":  8, "name": "Picoscope Enable",             "value": None, "actbits":  1},
        {"bits":  8, "name": "Electrometer Primary ADC",     "value": None, "actbits":  1},
        {"bits": 16, "name": "Electrometer Interval (ms)",   "value": None, "actbits": 16},
        {"bits": 16, "name": "Langmuir Interval (10 ms)",    "value": None, "actbits": 16},
        {"bits": 16, "name": "Langmuir Operation (s)",       "value": None, "actbits": 16},
        {"bits": 16, "name": "Picoscope Interval (ns)",      "value": None, "actbits": 16},
        {"bits":  8, "name": "Picoscope Blocks",             "value": None, "actbits":  4},
        {"bits":  8, "name": "Picoscope Voltage Range",      "value": None, "actbits":  4},
        {"bits":  8, "name": "Picoscope Horizontal Trigger", "value": None, "actbits":  4},
        {"bits":  8, "name": "Picoscope Vertical Trigger",   "value": None, "actbits":  4}
    ]
    piconf = [
        {"bits": 136, "name": "piconfig1", "value": piconfigconf},
        {"bits": 136, "name": "piconfig2", "value": piconfigconf},
        {"bits": 136, "name": "piconfig3", "value": piconfigconf},
        {"bits": 136, "name": "piconfig4", "value": piconfigconf}
    ]

    routing   = None
    opcode    = None
    pischeds  = None
    piconfigs = None
    period    = None
    operation = None

    wtcinfo = None
    piinfo  = None

    def __init__(self, length = 128):
        self.length = length

        self.pischeds = []
        self.piconfigs = []

        wtcinfo = bitstring.BitArray()
        piinfo  = bitstring.BitArray()

    def AddPiSched(self, piselect, start, stop):
        if len(self.pischeds) > 4: raise ValueError("Too many Pi schedules added to Packet!")
        self.ErrorCheck("start timestamp", start, 32)
        self.ErrorCheck("stop timestamp", stop, 32)
        if stop < start: raise ValueError("Stop timestamp occurs before start timestamp!")
        if piselect: piselect = 0xFF
        else:        piselect = 0x00
        self.pischeds.append((piselect, start, stop))

    def AddPiConfig(self, science, elecen, langen, picoen, elecpri, elecint, langint, langoper, picoint, picoblks, picovrange, picohtrig, picovtrig):
        if len(self.piconfigs) > 4: raise ValueError("Too many Pi configurations added to Packet!")
        l = [science, elecen, langen, picoen, elecpri, elecint, langint, langoper, picoint, picoblks, picovrange, picohtrig, picovtrig]
        for v, d in zip(l, self.piconfigconf):
            self.ErrorCheck(d["name"], v, d["actbits"])
        science = self.BoolToByte(science)
        elecen  = self.BoolToByte(elecen)
        langen  = self.BoolToByte(langen)
        picoen  = self.BoolToByte(picoen)
        elecpri = self.BoolToByte(elecpri)
        l = [science, elecen, langen, picoen, elecpri, elecint, langint, langoper, picoint, picoblks, picovrange, picohtrig, picovtrig]
        nl = []
        for v, d in zip(l, self.piconfigconf):
            nl.append(v)
        self.piconfigs.append(nl)

    def SetRouting(self, routing):
        self.ErrorCheck("routing", routing, 8)
        self.routing = routing

    def SetOpcode(self, opcode):
        self.ErrorCheck("opcode", opcode, 40)
        self.opcode = opcode
        
    def SetDefaultPeriod(self, period):
        self.ErrorCheck("default period", period, 16)
        self.period = period

    def SetDefaultOperation(self, operation):
        self.ErrorCheck("default operation", operation, 16)
        self.operation = operation

    def DecodeGeneric(self, info, conf, subconf, offset):
        fmt = ""
        for d in conf:
            fmt += "bin:%d," % d["bits"]
        fmt += "bin"
        l = info.unpack(fmt)
        values = []
        fmt = ""
        for d in subconf:
            fmt += "bin:%d," % d["bits"]
        fmt += "bin"
        for v in l[0+offset:4+offset]:
            v = bitstring.Bits(bin=v).unpack(fmt)
            values.append([int(x, 2) for x in v if x is not ""])
        return values, l[:offset] + l[4+offset:]

    def DecodeWTCInfo(self):
        self.pischeds, l = self.DecodeGeneric(self.wtcinfo, self.wtcconf, self.pischedconf, 2)
        self.routing   = int(l[0], 2)
        self.opcode    = int(l[1], 2)
        self.period    = int(l[2], 2)
        self.operation = int(l[3], 2)

    def DecodePiInfo(self):
        self.piconfigs, l = self.DecodeGeneric(self.piinfo, self.piconf, self.piconfigconf, 0)

    def PrintInfo(self):
        print("%-9s%-12s" % ("Routing:", ("0x%02X"  % self.routing)))
        print("%-9s%-12s" % ("Opcode: ", ("0x%010X" % self.opcode)))
        print("%-20s%5d" % ("Orbital Period (s):", self.period))
        print("%-20s%5d" % ("Operation Time (s):", self.operation))
        print("\n%-30s%10s  %10s  %10s  %10s" % ("", "Config #1", "Config #2", "Config #3", "Config #4"))
        for d, t in zip(self.pischedconf + self.piconfigconf, zip(*[s+c for s, c in zip(self.pischeds, self.piconfigs)])):
            sys.stdout.write("%-30s" % (d["name"]+":"))
            for v in t:
                fmt = "d"
                if d["actbits"] == 1 and d["bits"] == 8:
                    v = self.ByteToBool(v)
                    fmt = "s"
                self.ErrorCheck(d["name"], v, d["actbits"])
                sys.stdout.write(("%10" + fmt + "  ") % v)
            sys.stdout.write("\n")

    def BuildPacket(self):
        if self.routing is None: raise ValueError("Packet requires routing!")
        if self.opcode is None: raise ValueError("Packet requires opcode!")
        if len(self.pischeds) != 4: raise ValueError("Packet requires exactly 4 Pi schedules!")
        if self.period is None: raise ValueError("Packet requires a default orbital period!")
        if self.operation is None: raise ValueError("Packet requires a default operation time!")
        if len(self.piconfigs) != 4: raise ValueError("Packet requires exactly 4 Pi configurations!")
        self.wtcinfo = bitstring.BitArray()
        self.wtcinfo.append(bitstring.Bits(bin=self.IntToBinString(self.routing, 8)))
        self.wtcinfo.append(bitstring.Bits(bin=self.IntToBinString(self.opcode, 40)))
        for t in self.pischeds:
            print("For loop")
            for i in range(len(t)):
                self.wtcinfo.append(bitstring.Bits(bin=self.IntToBinString(t[i], self.pischedconf[i]["bits"])))
        print("Appending")
        self.wtcinfo.append(bitstring.Bits(bin=self.IntToBinString(self.period, 16)))
        self.wtcinfo.append(bitstring.Bits(bin=self.IntToBinString(self.operation, 16)))
        self.wtcinfo = self.PadBitArray(self.wtcinfo, self.wtcsize)
        self.piinfo = bitstring.BitArray()
        for t in self.piconfigs:
            for i in range(len(t)):
                self.piinfo.append(bitstring.Bits(bin=self.IntToBinString(t[i], self.piconfigconf[i]["bits"])))
        self.piinfo = self.PadBitArray(self.piinfo, self.pisize)

        self.packet = self.wtcinfo + self.piinfo
        self.checksum = self.GenerateChecksum()

    def LoadPacket(self, bitarray):
        super().LoadPacket(bitarray)
        self.wtcinfo = self.packet[:self.wtcsize*8]
        self.piinfo  = self.packet[self.wtcsize*8:]


class BaseSciencePacket(BasePacket):

    headsize    = None
    headconf    = None
    channels    = None
    measurebits = None

    piselect  = None
    sysident  = None
    timestamp = None

    head = None
    body = None

    def __init__(self, length, headsize, channels, measurebits):
        super().__init__(length)

        self.headsize    = headsize
        self.channels    = channels
        self.measurebits = measurebits

        self.head = bitstring.BitArray()
        self.body = bitstring.BitArray()

    def SetPiSelect(self, piselect):
        self.piselect = self.SetGenericField("piselect", piselect)

    def SetIdentifier(self, sysident):
        self.sysident = self.SetGenericField("sysident", sysident)

    def SetTimestamp(self, timestamp):
        self.timestamp = self.SetGenericField("timestamp", timestamp)

    def CalcRemainingSamples(self):
        return (self.length*8 - self.headsize*8 - len(self.body) - 32)/(self.channels*self.measurebits)

    def DecodeGenericHeader(self):
        fmt = ",bin:".join([str(d["bits"]) for d in self.headconf])
        if len(fmt) > 0: fmt = "bin:" + fmt + ",bin"
        result = self.head.unpack(fmt)
        return result

    def DecodeGenericBody(self):
        fmt = ",".join(["bin:%d" % self.measurebits for i in range(self.channels)]) + ",bin"
        values = []
        r = self.body
        while len(r) >= self.channels*self.measurebits:
            l = r.unpack(fmt)
            values.append(l[:-1])
            r = bitstring.Bits(bin=l[-1])
        return values

    def PrintFullPacket(self):
        super().PrintFullPacket()
        sys.stdout.write("Checksum: %08X" % self.checksum.uint)
        sys.stdout.write("\nHeader: ")
        for v, d in zip(self.DecodeGenericHeader()[:-1], self.headconf):
            sys.stdout.write(("%%0%dX " % math.ceil(d["bits"]/4.0)) % int(v, 2))
        sys.stdout.write("\nBody: ")
        for l in self.DecodeGenericBody():
            for v in l:
                sys.stdout.write(("%%0%dX " % math.ceil(self.measurebits/4.0)) % int(v, 2))
            sys.stdout.write("\n      ")

    def PrintSegmentedPacket(self):
        self.PrintHead()
        print()
        self.PrintBody()
        print()
        self.PrintChecksum()

    def PrintHead(self):
        self.PrintBitArray(self.head, "Head")

    def PrintBody(self):
        self.PrintBitArray(self.body, "Body")

    def PrintChecksum(self):
        self.PrintBitArray(self.checksum, "Checksum")

    def SetGenericField(self, name, value):
        i, bitdict = self.GetBitdict(name)
        self.ErrorCheck(bitdict["name"], value, bitdict["bits"])
        self.headconf[i]["value"] = bitstring.Bits(bin=self.IntToBinString(value, bitdict["bits"]))

    def GetBitdict(self, key):
        return next(((i, d) for i, d in enumerate(self.headconf) if d["name"] == key), None)

    def LoadPacket(self, bitarray):
        super().LoadPacket(bitarray)
        self.head = self.packet[:self.headsize*8]
        self.body = self.packet[self.headsize*8:]

    def BuildHeader(self):
        invalid = ", ".join([d["name"] for d in self.headconf if d["value"] is None])
        if len(invalid) > 0: warnings.warn("Packet headconf not fully defined (%s)!" % invalid)
        self.head = bitstring.BitArray()
        for d in self.headconf: self.head.append(d["value"])
        self.head = self.PadBitArray(self.head, self.headsize)

    def AddSample(self, sample):
        if len(sample) != self.channels:
            raise ValueError("Packet accepts exactly %d measurements!" % self.channels)
        if self.CalcRemainingSamples() < 1:
            raise ValueError("Packet length may not exceed %d bytes!" % self.length)
        for v in sample:
            if v < 0 or v > 2**self.measurebits-1:
                raise ValueError("Packet accepts %d bit measurements only!" % self.measurebits)
            self.body.append(bitstring.Bits(bin=self.IntToBinString(v, self.measurebits)))

    def BuildPacket(self):
        self.BuildHeader()
        self.packet = self.head + self.body
        self.checksum = self.GenerateChecksum()


class ElectrometerPacket(BaseSciencePacket):

    headconf = [
        {"bits":  1, "name": "piselect",  "value": None},
        {"bits":  2, "name": "sysident",  "value": None},
        {"bits": 60, "name": "timestamp", "value": None},
        {"bits":  1, "name": "timeunits", "value": None},
        {"bits": 10, "name": "timestep",  "value": None},
        {"bits":  5, "name": "status",    "value": None},
        {"bits":  1, "name": "primary",   "value": None}
    ]

    def __init__(self, length=128):
        super().__init__(length, headsize=12, channels=4, measurebits=16)
        self.SetIdentifier(1)

    def SetTimeUnits(self, ms):
        if ms: timeunits = 1 # set milliseconds
        else:  timeunits = 0 # set seconds
        self.SetGenericField("timeunits", timeunits)

    def SetTimestep(self, timestep):
        self.SetGenericField("timestep", timestep)

    def SetStatus(self, status):
        self.SetGenericField("status", status)

    def SetActiveChannel(self, primary):
        if primary: value = 1
        else:       value = 0
        self.SetGenericField("primary", primary)

class LangmuirPacket(BaseSciencePacket):

    headconf = [
        {"bits":  1, "name": "piselect",  "value": None},
        {"bits":  2, "name": "sysident",  "value": None},
        {"bits": 60, "name": "timestamp", "value": None},
        {"bits":  5, "name": "status",    "value": None},
        {"bits":  5, "name": "command",   "value": None}
    ]

    def __init__(self, length=128):
        super().__init__(length, headsize=12, channels=2, measurebits=14)
        self.SetIdentifier(2)

    def SetStatus(self, status):
        self.SetGenericField("status", status)

    def SetCommand(self, command):
        self.SetGenericField("command", command)


class PicoscopePacket(BaseSciencePacket):

    headconf = [
        {"bits":  1, "name": "piselect",  "value": None},
        {"bits":  2, "name": "sysident",  "value": None},
        {"bits": 60, "name": "timestamp", "value": None},
        {"bits":  1, "name": "timeunits", "value": None},
        {"bits": 10, "name": "timestep",  "value": None},
        {"bits":  6, "name": "status",    "value": None},
        {"bits":  4, "name": "blocks",    "value": None},
        {"bits":  4, "name": "vrange",    "value": None},
        {"bits":  4, "name": "htrigger",  "value": None},
        {"bits":  4, "name": "vtrigger",  "value": None}
    ]

    def __init__(self, length=128):
        super().__init__(length, headsize=12, channels=4, measurebits=8)
        self.SetIdentifier(3)

    def SetTimeUnits(self, ns):
        if ns: timeunits = 1 # set nanoseconds
        else:  timeunits = 0 # set microseconds
        self.SetGenericField("timeunits", timeunits)

    def SetTimestep(self, timestep):
        self.SetGenericField("timestep", timestep)

    def SetStatus(self, status):
        self.SetGenericField("status", status)

    def SetBlocks(self, blocks):
        self.SetGenericField("blocks", blocks)

    def SetVRange(self, vrange):
        self.SetGenericField("vrange", vrange)

    def SetHTrigger(self, htrigger):
        self.SetGenericField("htrigger", htrigger)

    def SetVTrigger(self, vtrigger):
        self.SetGenericField("vtrigger", vtrigger)


if __name__ == "__main__":

    warnings.simplefilter('ignore', UserWarning)

    elec = ElectrometerPacket()
    lang = LangmuirPacket()
    pico = PicoscopePacket()
    grnd = GroundPacket()
    conf = ConfigurationPacket()
    sddp = SDDumpPacket()
    ddmp = DDumpPacket()
    esat = ESATConfPacket()
    cmd1 = CMDPacket()

    while elec.CalcRemainingSamples() > 0:
        elec.AddSample((0x0123, 0x4567, 0x89AB, 0xCDEF))

    while lang.CalcRemainingSamples() > 0:
        lang.AddSample((0x3579, 0x2468))

    while pico.CalcRemainingSamples() > 0:
        pico.AddSample((0x13, 0x57, 0x9B, 0xDF))

    print("============= ELECTROMETER PACKET =============\n")
    elec.BuildPacket()
    elec.PrintFullPacket()
    elec.LoadPacket(elec.DumpPacket())
    print("\nChecksum Match: %s" % elec.VerifyChecksum())

    print("\n=============== LANGMUIR PACKET ===============\n")
    lang.BuildPacket()
    lang.PrintFullPacket()
    lang.LoadPacket(lang.DumpPacket())
    print("\nChecksum Match: %s" % lang.VerifyChecksum())

    print("\n=============== PICOSCOPE PACKET ==============\n")
    pico.BuildPacket()
    pico.PrintFullPacket()
    pico.LoadPacket(pico.DumpPacket())
    print("\nChecksum Match: %s" % pico.VerifyChecksum())

    curtime = int(round(time.time(), 0)) & 0xFFFFFFFF
    tmstruct = time.gmtime(curtime)

    print("\n============= CONFIGURATION PACKET ============\n")
    conf.SetRouting(0xFF)
    conf.SetOpcode(0x434F4E4650)
    conf.AddPiSched(True, curtime+100, curtime+160)
    conf.AddPiSched(True, curtime+200, curtime+260)
    conf.AddPiSched(True, curtime+300, curtime+360)
    conf.AddPiSched(True, curtime+400, curtime+460)
    conf.SetDefaultPeriod(90*60)
    conf.SetDefaultOperation(15*60)
    conf.AddPiConfig(True,  True,  False, True,  True,  100, 0, 0, 4, 8, 7, 2, 2)
    conf.AddPiConfig(True,  False, False, True,  True,  100, 0, 0, 4, 8, 7, 2, 3)
    conf.AddPiConfig(True,  True,  False, False, False, 200, 0, 0, 4, 8, 7, 2, 4)
    conf.AddPiConfig(False, True,  True,  True,  True,  200, 0, 0, 4, 8, 7, 2, 5)
    conf.BuildPacket()
    conf.LoadPacket(conf.DumpPacket())
    conf.DecodeWTCInfo()
    conf.DecodePiInfo()
    conf.PrintFullPacket()
    conf.PrintInfo()
    print("\nChecksum Match: %s" % conf.VerifyChecksum())

    print("\n=================== CMD PACKET ==================\n")
    cmd1.SetRouting(0xFF)
    cmd1.SetOpcode(cmd1.BytesToInt(b"NOOP*"))
    cmd1.SetRandoms()
    cmd1.SetCMDRegion(0x1e469ecf2c4c4bbfdb80dadb080ea8b412fb4bddbe94ef5c9ef1d1bb02bb3710)
    cmd1.BuildPacket()
    cmd1.PrintFullPacket()
    cmd1.LoadPacket(cmd1.DumpPacket())
    print("\nChecksum Match: %s" % cmd1.VerifyChecksum())
    print("%s"%cmd1.ReturnStringToPrint(cmd1.DumpPacket(), "Total Packet"))

    print("\n================ GROUND PACKET ================\n")
    grnd.SetRouting(0xFF)
    grnd.SetOpcode(grnd.BytesToInt(b"HELLO"))
    grnd.SetExchangeFrom(grnd.BytesToInt(b"GROUND"))
    grnd.SetExchangeTo(grnd.BytesToInt(b"SURFSAT"))
    grnd.SetExchangeSignal(grnd.BytesToInt(b"KN"))
    grnd.SetTimeMonth(tmstruct.tm_mon)
    grnd.SetTimeDay(tmstruct.tm_mday)
    grnd.SetTimeYear(tmstruct.tm_year % 2000)
    grnd.SetTimeWeekday(tmstruct.tm_wday)
    grnd.SetTimeHour(tmstruct.tm_hour)
    grnd.SetTimeMinute(tmstruct.tm_min)
    grnd.SetTimeSecond(tmstruct.tm_sec)
    grnd.BuildPacket()
    grnd.PrintFullPacket()
    grnd.LoadPacket(grnd.DumpPacket())
    print("\nChecksum Match: %s" % grnd.VerifyChecksum())

    print("\n================ SD DUMP PACKET ===============\n")
    sddp.SetRouting(0x07)
    sddp.SetOpcode(sddp.BytesToInt(b"SDDMP"))
    sddp.SetReadStart(7)
    sddp.SetReadCount(6)
    sddp.SetReadDelay(15)
    sddp.BuildPacket()
    sddp.PrintFullPacket()
    sddp.LoadPacket(sddp.DumpPacket())
    print("\nChecksum Match: %s" % sddp.VerifyChecksum())

    print("\n=============== DATA DUMP PACKET ==============\n")
    ddmp.SetRouting(0xFF)
    ddmp.SetOpcode(ddmp.BytesToInt(b"DDUMP"))
    ddmp.SetDDump(0x2003)
    ddmp.BuildPacket()
    ddmp.PrintFullPacket()
    ddmp.LoadPacket(ddmp.DumpPacket())
    print("\nChecksum Match: %s" % ddmp.VerifyChecksum())

    print("\n=============== ESAT CONF PACKET ==============\n")
    esat.SetRouting(0xFF)
    esat.SetOpcode(esat.BytesToInt(b"ESATC"))
    esat.SetThing1(0x11)
    esat.SetThing2(0x01)
    esat.SetThing3(0x00)
    esat.body = bitstring.BitArray("0x124356789")
    esat.BuildPacket()
    esat.PrintFullPacket()
    esat.LoadPacket(esat.DumpPacket())
    print("\nChecksum Match: %s" % esat.VerifyChecksum())
