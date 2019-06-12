# Dumps 128 Bytes of data to the terminal and nothing else

NUM_PACKETS = 128
DELAY = 1 #sec

for packet in range(NUM_PACKETS):
    data = str(packet) + "A"*(128-packet)
    print(data)