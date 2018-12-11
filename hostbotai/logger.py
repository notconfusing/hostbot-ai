# import airbrake
import hostbotai
import os, sys, random, logging
from time import sleep
from logging.handlers import RotatingFileHandler

def get_logger():

  # use Airbrake in production
  # if(ENV=="production"):
  #   log = airbrake.getLogger()
  #   log.setLevel(logging.INFO)
  # else:
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

  # print all debug and higher to STDOUT
  # if the environment is development
    stdoutHandler = logging.StreamHandler(sys.stdout)
    stdoutHandler.setLevel(logging.DEBUG)
    log.addHandler(stdoutHandler)
    BASE_DIR = os.path.join(os.path.dirname(hostbotai.__file__), '..')
    logfile = os.path.abspath(BASE_DIR + "/logs/hb.log")
    # print("Logging to " + BASE_DIR + "/logs/hb.log")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    rotateHandler = RotatingFileHandler(logfile, mode='a', maxBytes=1024*(10**3), backupCount=5, encoding='utf-8', delay=0)
    # rotateHandler = ConcurrentRotatingFileHandler(logfile, "a", 32 * 1000 * 1024, backupCount=1000)
    rotateHandler.setLevel(logging.DEBUG)
    rotateHandler.setFormatter(formatter)
    log.addHandler(rotateHandler)
    return log
