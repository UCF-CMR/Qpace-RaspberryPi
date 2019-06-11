import sys
import time
try:
	import pigpio
except:pass
# General Registers (Require LCR[7] = 0)
REG_RHR       = 0x00 # Receive Holding Register (R)
REG_THR       = 0x00 # Transmit Holding Register (W)
REG_IER       = 0x01 # Interrupt Enable Register (R/W)
REG_IIR       = 0x02 # Interrupt Identification Register (R)
REG_FCR       = 0x02 # FIFO Control Register (W)
REG_LCR       = 0x03 # Line Control Register (R/W)
REG_MCR       = 0x04 # Modem Control Register (R/W)
REG_LSR       = 0x05 # Line Status Register (R)
REG_MSR       = 0x06 # Modem Status Register (R)
REG_SPR       = 0x07 # Scratch Pad Register (R/W)
REG_TCR       = 0x06 # Transmission Control Register (R/W)
REG_TLR       = 0x07 # Trigger Level Register (R/W)
REG_TXLVL     = 0x08 # Transmit FIFO Level Register (R)
REG_RXLVL     = 0x09 # Receive FIFO Level Register (R)
REG_IODIR     = 0x0A # GPIO Pins Direction Register (R/W)
REG_IOSTATE   = 0x0B # GPIO Pins State Register (R)
REG_IOINTENA  = 0x0C # GPIO Interrupt Enable Register (R/W)
REG_IOCONTROL = 0x0E # GPIO Control Register (R/W)
REG_EFCR      = 0x0F # Extra Features Control Register (R/W)

# Special Registers (Require LCR[7] = 1 and LCR != 0xBF)
REG_DLL       = 0x00 # Divisor Latch LSB Register (R/W)
REG_DLH       = 0x01 # Divisor Latch MSB Register (R/W)

# Enhanced Registers (Require LCR[7] = 1 and LCR = 0xBF)
REG_EFR       = 0x02 # Enhanced Features Register (R/W)
REG_XON1      = 0x04 # XON1 Word Register (R/W)
REG_XON2      = 0x05 # XON2 Word Register (R/W)
REG_XOFF1     = 0x06 # XOFF1 Word Register (R/W)
REG_XOFF2     = 0x07 # XOFF2 Word Register (R/W)

# Section 8.1: Receive Holding Register (RHR)
# RHR is position zero of the 64 byte RX FIFO

# Section 8.2: Transmit Holding Register (THR)
# THR is position zero of the 64 byte TX FIFO

# Section 8.3: FIFO Control Register (FCR)
# TX trigger level may only be modified if EFR[4] is set
# TX and RX FIFO resets require two XTAL1 clocks
FCR_RX_TRIGGER_08_BYTES = 0x00 << 6
FCR_RX_TRIGGER_16_BYTES = 0x01 << 6
FCR_RX_TRIGGER_56_BYTES = 0x02 << 6
FCR_RX_TRIGGER_60_BYTES = 0x03 << 6
FCR_TX_TRIGGER_08_BYTES = 0x00 << 4
FCR_TX_TRIGGER_16_BYTES = 0x01 << 4
FCR_TX_TRIGGER_32_BYTES = 0x02 << 4
FCR_TX_TRIGGER_56_BYTES = 0x03 << 4
FCR_TX_FIFO_RESET       = 0x01 << 2
FCR_RX_FIFO_RESET       = 0x01 << 1
FCR_FIFO_ENABLE         = 0x01 << 0

# Section 8.4: Line Control Register (LCR)
LCR_DIVISOR_ENABLE = 0x01 << 7
LCR_BREAK_CONTROL  = 0x01 << 6
LCR_PARITY_NONE    = 0x00 << 3
LCR_PARITY_ODD     = 0x01 << 3
LCR_PARITY_EVEN    = 0x03 << 3
LCR_PARITY_HIGH    = 0x05 << 3
LCR_PARITY_LOW     = 0x07 << 3
LCR_STOPBITS_1     = 0x00 << 2
LCR_STOPBITS_2     = 0x01 << 2
LCR_DATABITS_5     = 0x00 << 0
LCR_DATABITS_6     = 0x01 << 0
LCR_DATABITS_7     = 0x02 << 0
LCR_DATABITS_8     = 0x03 << 0

# Section 8.5: Line Status Register (LSR)
# LSR_FIFO_DATA_ERROR is valid for all data in FIFO
# LSR_BREAK_INTERRUPT, LSR_FRAMING_ERROR, and LSR_PARITY_ERROR are valid only for top byte in FIFO
# To check error for all RX bytes, must read LSR then read RHR and repeat for all data
LSR_RX_DATA_AVAIL   = 0x01 << 0
LSR_OVERFLOW_ERROR  = 0x01 << 1
LSR_PARITY_ERROR    = 0x01 << 2
LSR_FRAMING_ERROR   = 0x01 << 3
LSR_BREAK_INTERRUPT = 0x01 << 4
LSR_THR_EMPTY       = 0x01 << 5
LSR_THR_TSR_EMPTY   = 0x01 << 6
LSR_FIFO_DATA_ERROR = 0x01 << 7

# Section 8.6: Modem Control Register (MCR)
# MCR[7:5] and MCR[2] can only be modified if EFR[4] is set
MCR_PRESCALER_1 = 0x00 << 7
MCR_PRESCALER_4 = 0x01 << 7
MCR_IRDA        = 0x01 << 6
MCR_XON_ANY     = 0x01 << 5
MCR_LOOPBACK    = 0x01 << 4
MCR_TCR_TLR     = 0x01 << 2
MCR_RTS         = 0x01 << 1
MCR_DTR         = 0x01 << 0 # Not available on 740 variant

# Section 8.7: Modem Status Register (MSR)
MSR_CD        = 0x01 << 7 # Not available on 740 variant
MSR_RI        = 0x01 << 6 # Not available on 740 variant
MSR_DSR       = 0x01 << 5 # Not available on 740 variant
MSR_CTS       = 0x01 << 4
MSR_DELTA_CD  = 0x01 << 3 # Not available on 740 variant
MSR_DELTA_RI  = 0x01 << 2 # Not available on 740 variant
MSR_DELTA_DSR = 0x01 << 1 # Not available on 740 variant
MSR_DELTA_CTS = 0x01 << 0

# Section 8.8: Scratch Pad Register (SPR)

# Section 8.9: Interrupt Enable Register (IIR)
# IER[7:4] can only be modified if EFR[4] is set
IER_CTS      = 0x01 << 7
IER_RTS      = 0x01 << 6
IER_XOFF     = 0x01 << 5
IER_SLEEP    = 0x01 << 4
IER_MODEM    = 0x01 << 3 # Not available on 740 variant
IER_RX_ERROR = 0x01 << 2
IER_TX_READY = 0x01 << 1
IER_RX_READY = 0x01 << 0

# Section 8.10: Interrupt Identification Register (IIR)
# Modem interrupt status must be read via MSR register
# GPIO interrupt status must be read via IOState register
IIR_FIFO_ENABLE = 0x80 # Mirrors FCR[0]
IIR_NONE        = 0x01 # Priority X
IIR_RX_ERROR    = 0x06 # Priority 1
IIR_RX_TIMEOUT  = 0x0C # Priority 2
IIR_RX_READY    = 0x04 # Priority 2
IIR_TX_READY    = 0x02 # Priority 3
IIR_MODEM       = 0x00 # Priority 4 # Not available on 740 variant
IIR_GPIO        = 0x30 # Priority 5 # Not available on 740 variant
IIR_XOFF        = 0x10 # Priority 6
IIR_CTS_RTS     = 0x20 # Priority 7

# Section 8.11: Enhanced Features Register (EFR)
# Register only accessible if LCR = 0xBF
EFR_FLOW_CONTROL_CTS_ENABLE    = 0x01 << 7
EFR_FLOW_CONTROL_RTS_ENABLE    = 0x01 << 6
EFR_SPECIAL_CHAR_DETECT_ENABLE = 0x01 << 5
EFR_ENHANCED_FUNCTIONS_ENABLE  = 0x01 << 4
EFR_FLOW_CONTROL_TX_NONE       = 0x00
EFR_FLOW_CONTROL_TX_XON_XOFF_1 = 0x01 << 3
EFR_FLOW_CONTROL_TX_XON_XOFF_2 = 0x01 << 2
EFR_FLOW_CONTROL_RX_NONE       = 0x00
EFR_FLOW_CONTROL_RX_XON_XOFF_1 = 0x01 << 1
EFR_FLOW_CONTROL_RX_XON_XOFF_2 = 0x01 << 0

# Section 8.12: Division Registers (DLL, DLH)
# Registers only accessible if LCR[7] = 1 and LCR != 0xBF
# DLL and DLH can only be set before sleep is enabled (IER[4] = 0)

# Section 8.13: Transmission Control Register (TCR)
# TCR can only be set when EFR[4] = 1 and MCR[2] = 1
# TCR[3:0] must be larger than TCR[7:4] (no hardware check to verify)
# TCR[3:0] and TCR[7:4] define RX FIFO levels to halt and resume TX
# Each nybble represents a value from 0 to 60 bytes with granularity of 4 bytes

# Section 8.14: Trigger Level Register (TLR)
# TLR can only be set when EFR[4] = 1 and MCR[2] = 1
# If TLR[7:4] or TLR[3:0] is zero, FCR sets associated trigger level
# Each nybble represents a value from 4 to 60 bytes with granularity of 4 bytes
# When TLR is used for RX trigger control, FCR[7:6] should be left unset

# Section 8.15: Transmit FIFO Level Register (TXLVL)
# Reports number of spaces available in TX FIFO from 0x00 (0) to 0x40 (64)

# Section 8.16: Receive FIFO Level Register (RXLVL)
# Reports number of bytes stored in RX FIFO from 0x00 (0) to 0x40 (64)

# Section 8.17: GPIO Pins Direction Register (IODir)
# IODir is not available on 740 variant

# Section 8.18: GPIO Pins State Register (IOState)
# IOState is not available on 740 variant

# Section 8.19: GPIO Interrupt Enable Register (IOIntEna)
# IOIntEna is not available on 740 variant

# Section 8.20: GPIO Control Register (IOControl)
IOCONTROL_SOFTWARE_RESET = 0x01 << 3
IOCONTROL_GPIO_SELECT    = 0x01 << 1 # Not available on 740 variant
IOCONTROL_LATCH_ENABLE   = 0x01 << 0 # Not available on 740 variant

# Section 8.21: Extra Features Control Register (EFCR)
EFCR_IRDA_MODE_SLOW = 0x00 << 7
EFCR_IRDA_MODE_FAST = 0x01 << 7 # Not available on 740 or 750 variant
EFCR_RTS_INVERT     = 0x01 << 5
EFCR_RTS_TX_CONTROL = 0x01 << 4
EFCR_TX_DISABLE     = 0x01 << 2
EFCR_RX_DISABLE     = 0x01 << 1
EFCR_RS485_ENABLE   = 0x01 << 0

# Define pigpio i2c_zip constants
I2C_END     = 0x00 # No more commands
I2C_ESCAPE  = 0x01 # Next P is two bytes
I2C_START   = 0x02 # Switch combined flag on
I2C_STOP    = 0x03 # Switch combined flag off
I2C_ADDRESS = 0x04 # Set I2C address to P
I2C_FLAGS   = 0x05 # Set I2C flags to LSB + (MSB << 8)
I2C_READ    = 0x06 # Read P bytes of data
I2C_WRITE   = 0x07 # Write P bytes of data

#PIGPIO CONSTANTS
GPIO_PIN = 20

class SC16IS750:

	pi = None
	i2c = None
	xtalfreq = None
	baudrate = None
	databits = None
	stopbits = None
	parity = None

	def __init__(self, pi, i2cbus = 1, i2caddr = 0x48, xtalfreq = 11059200, baudrate = 115200, databits = LCR_DATABITS_8, stopbits = LCR_STOPBITS_1, parity = LCR_PARITY_NONE):

		self.pi = pi
		self.i2c = pi.i2c_open(i2cbus, i2caddr)
		self.xtalfreq = xtalfreq
		self.baudrate = baudrate
		self.databits = databits
		self.stopbits = stopbits
		self.parity = parity

		self.reset()
		self.init_uart()

	def inWaiting(self):
		return self.byte_read(REG_RXLVL)

	def read(self, num):
		sys.stdout.write("Waiting for %d bytes ... " % num)
		sys.stdout.flush()
		while self.inWaiting() < num: pass
		print("done!")
		return self.block_read(REG_RHR, num)

	def readline(self):
		out = bytearray()
		char = None
		sys.stdout.write("Waiting for newline ... ")
		sys.stdout.flush()
		while char != 0x0A and char != 0x0D:
			if self.inWaiting() > 0:
				char = self.byte_read(REG_RHR)
				out.append(char)
		print("done!")
		return out

	def write(self, bytestring):
		self.block_write(REG_THR, bytestring)
		self.gpio_write(bytestring)

	def close(self):
		self.pi.i2c_close(self.i2c)

	def print_register(self, reg, prefix):
		print("%s 0x%02X" % (prefix, self.byte_read(reg)))

	def print_registers(self):
		self.print_register(REG_RHR,       "0x00 REG_RHR:      ")
		self.print_register(REG_IER,       "0x01 REG_IER:      ")
		self.print_register(REG_IIR,       "0x02 REG_IIR:      ")
		self.print_register(REG_LCR,       "0x03 REG_LCR:      ")
		self.print_register(REG_MCR,       "0x04 REG_MCR:      ")
		self.print_register(REG_LSR,       "0x05 REG_LSR:      ")
		self.print_register(REG_MSR,       "0x06 REG_MSR:      ")
		self.print_register(REG_SPR,       "0x07 REG_SPR:      ")
		self.print_register(REG_TXLVL,     "0x08 REG_TXLVL:    ")
		self.print_register(REG_RXLVL,     "0x09 REG_RXLVL:    ")
		self.print_register(REG_IODIR,     "0x0A REG_IODIR:    ")
		self.print_register(REG_IOSTATE,   "0x0B REG_IOSTATE:  ")
		self.print_register(REG_IOINTENA,  "0x0C REG_IOINTENA: ")
		self.print_register(REG_IOCONTROL, "0x0E REG_IOCONTROL:")
		self.print_register(REG_EFCR,      "0x0F REG_EFCR:     ")

	# Initialize UART settings
	def init_uart(self):
		s1, v1 = self.byte_write_verify(REG_LCR, LCR_DIVISOR_ENABLE)
		s2, v2 = self.set_divisor_latch(MCR_PRESCALER_1)
		lcr = self.databits | self.stopbits | self.parity
		s3, v3 = self.byte_write_verify(REG_LCR, lcr)
		if not (s1 and s2 and s3):
			print("Error setting up UART port!")
			sys.exit(1)

	# Reset chip and handle exception thrown by NACK
	def reset(self):
		try: self.byte_write(REG_IOCONTROL, IOCONTROL_SOFTWARE_RESET)
		except pigpio.error: pass

	# Write some test patterns to the scratchpad and verify receipt
	def scratchpad_test(self):
		t1b, t1v = self.byte_write_verify(REG_SPR, 0xFF)
		t2b, t2v = self.byte_write_verify(REG_SPR, 0xAA)
		t3b, t3v = self.byte_write_verify(REG_SPR, 0x00)
		return t1b and t2b and t3b

	# Compute required divider values for DLH and DLL registers
	# Return tuple indicating (boolean success, new values in registers)
	def set_divisor_latch(self, prescaler = MCR_PRESCALER_1):
		prescaler = 4 if prescaler == MCR_PRESCALER_4 else 1
		div = round(self.xtalfreq/(prescaler*self.baudrate*16))
		dlh, dll = divmod(div, 0x100)
		dlhb, dlhv = self.byte_write_verify(REG_DLH, dlh)
		dllb, dllv = self.byte_write_verify(REG_DLL, dll)
		return (dlhb and dllb, (dlhv<<8)|dllv)

	# Retreive interrupt status (IIR[5:0])
	def get_interrupt_status(self):
		# Read IIR, LSR, and RXLVL registers
		n, d = self.pi.i2c_zip(self.i2c, [I2C_WRITE, 1, self.reg_conv(REG_IIR), I2C_READ, 1, I2C_START, I2C_WRITE, 1, self.reg_conv(REG_LSR), I2C_READ, 1, I2C_START, I2C_WRITE, 1, self.reg_conv(REG_RXLVL), I2C_READ, 1, I2C_END])
		if n < 0: raise pigpio.error(pigpio.error_text(n))
		elif n != 3: raise ValueError("unexpected number of bytes received")
		# Mask out two MSBs in IIR value and return tuple
		return (int(d[0]) & 0x3F, int(d[1]), int(d[2]))

	# Change single bit inside register
	def enable_register_bit(self, reg, bit, enable):
		if bit < 0 or bit > 7: return False
		if enable not in [True, False]: return False

		oldvalue = self.byte_read(reg)
		if enable: newvalue = oldvalue |  (0x01 << bit)
		else:      newvalue = oldvalue & ~(0x01 << bit)
		return self.byte_write_verify(REG_LCR, newvalue)

	# MCR[4]: True for local loopback enable, False for disable
	def enable_local_loopback(self, enable):
		return self.enable_register_bit(REG_MCR, 4, enable)

	# LCR[7]: True for special register set, False for general register set
	def define_register_set(self, special):
		return self.enable_register_bit(REG_LCR, 7, special)

	# Write I2C byte to specified register and read it back
	# Return tuple indicating (boolean success, new value in register)
	def byte_write_verify(self, reg, byte):
		n, d = self.pi.i2c_zip(self.i2c, [I2C_WRITE, 2, self.reg_conv(reg), byte, I2C_READ, 1, I2C_END])
		if n < 0: raise pigpio.error(pigpio.error_text(n))
		elif n != 1: raise ValueError("unexpected number of bytes received")
		d = int(d[0])
		return (d == byte, d)

	# Write I2C byte to specified register
	def byte_write(self, reg, byte):
		n, d = self.pi.i2c_zip(self.i2c, [I2C_WRITE, 2, self.reg_conv(reg), byte, I2C_END])

	# Read I2C byte from specified register
	# Return byte received from driver
	def byte_read(self, reg):
		return self.pi.i2c_read_byte_data(self.i2c, self.reg_conv(reg))

	# Write I2C block to specified register
	def block_write(self, reg, bytestring):
		n, d = self.pi.i2c_zip(self.i2c, [I2C_WRITE, len(bytestring)+1, self.reg_conv(reg)] + list(bytestring) + [I2C_END])
		if n < 0: raise pigpio.error(pigpio.error_text(n))
	
	# Writes bytestring to the GPIO output pin
	def gpio_write(self, bytestring):
		self.pi.wave_clear()
		self.pi.wave_add_serial(GPIO_PIN, self.baudrate, bytestring)
		new_send_id = pi.wave_create()
		cbs = pi.wave_send_once(new_send_id)


	# Read I2C block from specified register
	# Return block received from driver
	def block_read(self, reg, num):
		n, d = self.pi.i2c_zip(self.i2c, [I2C_WRITE, 1, self.reg_conv(reg), I2C_READ, num, I2C_END])
		if n < 0: raise pigpio.error(pigpio.error_text(n))
		elif n != num: raise ValueError("all available bytes were not successfully read")
		return d

	# Convert register address given in datasheet to actual address on chip
	def reg_conv(self, reg):
		return reg << 3