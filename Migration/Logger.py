import logging

def getLogger(name, lognormal='botlog.log', logerror='errors.log'):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)10s - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(logerror)
    fh.setLevel(logging.WARNING)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    nh = logging.FileHandler(lognormal)
    nh.setLevel(logging.DEBUG)
    nh.setFormatter(formatter)
    logger.addHandler(nh)

    return logger

#def setLoggerLevel(lvl):
#    logger.setLevel(lvl)