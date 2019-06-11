import threading
import qpaceExperimentParser as exp
import qpaceLogger

experimentEvent = threading.Event()
experimentEvent.clear()
runEvent = threading.Event()
disableCallback = threading.Event()
disableCallback.clear()

logger = qpaceLogger.Logger()

filename = "SampleScript.txt"
print("About to run exp")
exp.run(filename, experimentEvent, runEvent, logger, None, disableCallback)

os.system("ls data/pic/")
filename = input("What is the file name?")

with open(filename, 'rb') as pic:
  data = base64.base64encode(pic.read())
  
with open("test.encode", 'wb') as encoded:
  encoded.write(data)