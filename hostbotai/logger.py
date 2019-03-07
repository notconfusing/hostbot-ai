import airbrake
import hostbotai
import os, sys, random, logging, json
from time import sleep
from logging.handlers import RotatingFileHandler

def load_airbrake_config(fname=None):
    if fname == None:
        fname = 'default_config.json'
    module_path = os.path.dirname(hostbotai.__file__)
    # print(module_path)
    config_file = os.path.join(module_path, '..', 'config', fname)
    with open(config_file, 'r') as tf:
        config = json.load(tf)
        try:
            return {'api_key': config['AIRBRAKE_API_KEY'],
                'project_id': config['AIRBRAKE_PROJECT_ID'],
                'host': config['AIRBRAKE_BASE_URL']}
        except KeyError:
            return None

def get_logger():

    # use Airbrake in production
    airbrake_config = load_airbrake_config()

    if airbrake_config:
        log = airbrake.getLogger(**airbrake_config)
        log.setLevel(logging.INFO)
    else:
        log = logging.getLogger(__name__)
        log.setLevel(logging.INFO)
    # print all debug and higher to STDOUT
    # if the environment is development
    #   stdoutHandler = logging.StreamHandler(sys.stdout)
    #   stdoutHandler.setLevel(logging.ERROR)
    #   log.addHandler(stdoutHandler)

    BASE_DIR = os.path.join(os.path.dirname(hostbotai.__file__), '..')
    logfile = os.path.abspath(BASE_DIR + "/logs/hb.log")
    # print("Logging to " + BASE_DIR + "/logs/hb.log")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    rotateHandler = RotatingFileHandler(logfile, mode='a', maxBytes=1024*(10**3), backupCount=5, encoding='utf-8', delay=0)
    # rotateHandler = ConcurrentRotatingFileHandler(logfile, "a", 32 * 1000 * 1024, backupCount=1000)
    rotateHandler.setLevel(logging.INFO)
    rotateHandler.setFormatter(formatter)
    log.addHandler(rotateHandler)
    return log
